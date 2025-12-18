from .celery_app import celery_app
from minio import Minio
from app.config import settings

import fitz
import tempfile
import os
import re
import logging
from typing import List, Tuple, Iterable

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Optional spaCy for better NLP
try:
    import spacy
    _SPACY_AVAILABLE = True
except Exception:
    _SPACY_AVAILABLE = False

# Optional OCR support
try:
    import pytesseract
    from pdf2image import convert_from_path
    _OCR_AVAILABLE = True
except Exception:
    _OCR_AVAILABLE = False

# ------------------------------------------------------
# LOGGING
# ------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tasks")

# ------------------------------------------------------
# DATABASE (SYNC — REQUIRED FOR WINDOWS + CELERY)
# ------------------------------------------------------
SYNC_DB_URL = settings.database_url.replace("+asyncpg", "")
engine = create_engine(SYNC_DB_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

# ------------------------------------------------------
# MINIO CLIENT
# ------------------------------------------------------
minio_client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=False
)

# ------------------------------------------------------
# MinIO Helpers
# ------------------------------------------------------
def download_from_minio(object_key: str, file_path: str):
    resp = minio_client.get_object(settings.minio_bucket, object_key)
    try:
        with open(file_path, "wb") as f:
            for chunk in resp.stream(32 * 1024):
                f.write(chunk)
    finally:
        resp.close()
        resp.release_conn()


# ------------------------------------------------------
# OCR Functions
# ------------------------------------------------------
def ocr_page_image(image) -> str:
    """Run OCR on a PIL image."""
    if not _OCR_AVAILABLE:
        return ""
    try:
        return pytesseract.image_to_string(image, lang='eng')
    except Exception as e:
        logger.warning(f"OCR failed: {e}")
        return ""


def extract_text_with_ocr(pdf_path: str, page_num: int) -> str:
    """Extract text from a PDF page using OCR (for scanned documents)."""
    if not _OCR_AVAILABLE:
        return ""
    try:
        # Convert specific page to image
        images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num, dpi=300)
        if images:
            return ocr_page_image(images[0])
    except Exception as e:
        logger.warning(f"OCR extraction failed for page {page_num}: {e}")
    return ""


# ------------------------------------------------------
# PDF Functions with OCR fallback
# ------------------------------------------------------
def extract_text_pages(pdf_path: str, use_ocr_fallback: bool = True) -> List[Tuple[int, str]]:
    """
    Extract text from PDF pages.
    Falls back to OCR for pages with little/no text (scanned documents).
    """
    doc = fitz.open(pdf_path)
    pages = []
    
    for i, page in enumerate(doc):
        page_num = i + 1
        try:
            text = page.get_text()
        except Exception:
            text = ""
        
        # OCR fallback for pages with very little text (likely scanned)
        if use_ocr_fallback and len(text.strip()) < 50 and _OCR_AVAILABLE:
            logger.info(f"Page {page_num} has little text, trying OCR...")
            ocr_text = extract_text_with_ocr(pdf_path, page_num)
            if len(ocr_text.strip()) > len(text.strip()):
                text = ocr_text
                logger.info(f"OCR extracted {len(text)} chars from page {page_num}")
        
        pages.append((page_num, text))
    
    doc.close()
    return pages

_HEADER_FOOTER_PATTERN = re.compile(
    r"(^\s*page\s*\d+\s*$)|(^\s*\d+\s*/\s*\d+\s*$)|(^\s*confidential\s*$)",
    flags=re.IGNORECASE | re.MULTILINE
)
_WHITESPACE_PATTERN = re.compile(r"\s+")
_NON_PRINTABLE_PATTERN = re.compile(r"[^\x09\x0A\x0D\x20-\x7E\u00A0-\uFFFF]+")
_HYPHEN_BREAK_PATTERN = re.compile(r"(\w)-\s+(\w)")

def regex_clean(text: str) -> str:
    text = _HEADER_FOOTER_PATTERN.sub(" ", text)
    text = _NON_PRINTABLE_PATTERN.sub(" ", text)
    # Fix PDF line-break hyphenation (e.g., "maxi- mize" → "maximize")
    text = _HYPHEN_BREAK_PATTERN.sub(r"\1\2", text)
    text = _WHITESPACE_PATTERN.sub(" ", text)
    return text.strip()


# ------------------------------------------------------
# Triple Extraction (OpenIE-style)
# ------------------------------------------------------
_spacy_nlp_full = None

def _get_spacy_full():
    """Load spaCy with full pipeline for dependency parsing."""
    global _spacy_nlp_full
    if _spacy_nlp_full is None and _SPACY_AVAILABLE:
        try:
            _spacy_nlp_full = spacy.load("en_core_web_sm")
            logger.info("Loaded spaCy en_core_web_sm for triple extraction")
        except Exception as e:
            logger.warning(f"Could not load spaCy: {e}")
            _spacy_nlp_full = "unavailable"
    return _spacy_nlp_full if _spacy_nlp_full != "unavailable" else None


def extract_triples_spacy(text: str, limit: int = 5) -> List[Tuple[str, str, str]]:
    """
    Extract subject-predicate-object triples using spaCy dependency parsing.
    
    This is a rule-based OpenIE approach that identifies:
    - Subject: nsubj/nsubjpass of main verb
    - Predicate: main verb (ROOT or with aux)
    - Object: dobj/pobj/attr of verb
    """
    nlp = _get_spacy_full()
    if not nlp:
        return extract_naive_triples(text, limit)
    
    triples = []
    
    try:
        doc = nlp(text[:5000])  # Limit to avoid memory issues
        
        for sent in doc.sents:
            # Find main verb
            root = None
            for token in sent:
                if token.dep_ == "ROOT" and token.pos_ == "VERB":
                    root = token
                    break
            
            if not root:
                continue
            
            # Find subject
            subject = None
            for child in root.children:
                if child.dep_ in ("nsubj", "nsubjpass"):
                    # Get the full noun phrase
                    subject = " ".join([t.text for t in child.subtree])
                    break
            
            if not subject:
                continue
            
            # Build predicate (verb + auxiliaries + particles)
            predicate_parts = []
            for child in root.children:
                if child.dep_ in ("aux", "auxpass", "neg"):
                    predicate_parts.append(child.text)
            predicate_parts.append(root.text)
            for child in root.children:
                if child.dep_ == "prt":  # particle (e.g., "give up")
                    predicate_parts.append(child.text)
            predicate = " ".join(predicate_parts)
            
            # Find object
            obj = None
            for child in root.children:
                if child.dep_ in ("dobj", "pobj", "attr", "acomp"):
                    obj = " ".join([t.text for t in child.subtree])
                    break
            
            # If no direct object, try prepositional objects
            if not obj:
                for child in root.children:
                    if child.dep_ == "prep":
                        for pobj in child.children:
                            if pobj.dep_ == "pobj":
                                obj = child.text + " " + " ".join([t.text for t in pobj.subtree])
                                break
                        if obj:
                            break
            
            if obj and len(subject) > 1 and len(obj) > 1:
                triples.append((subject.strip(), predicate.strip(), obj.strip()))
                if len(triples) >= limit:
                    break
    
    except Exception as e:
        logger.warning(f"spaCy triple extraction failed: {e}")
        return extract_naive_triples(text, limit)
    
    # Fallback to naive if no triples found
    if not triples:
        return extract_naive_triples(text, limit)
    
    return triples


def extract_naive_triples(text: str, limit: int = 3) -> List[Tuple[str, str, str]]:
    """Very lightweight triple extraction fallback.

    This avoids heavyweight OpenIE deps; it simply takes the first token as
    subject, second as predicate, and the remainder as object for the first
    few sentences. It is intentionally naive but gives us relation hooks for
    filtering/ranking while keeping the worker fast.
    """
    triples: List[Tuple[str, str, str]] = []
    sentences = re.split(r"[.!?]\s+", text)
    for sent in sentences:
        tokens = sent.strip().split()
        if len(tokens) < 3:
            continue
        subj = tokens[0]
        pred = tokens[1]
        obj = " ".join(tokens[2:])
        triples.append((subj, pred, obj))
        if len(triples) >= limit:
            break
    return triples


def extract_triples(text: str, limit: int = 5) -> List[Tuple[str, str, str]]:
    """Main entry point for triple extraction. Uses spaCy if available."""
    if _SPACY_AVAILABLE:
        return extract_triples_spacy(text, limit)
    return extract_naive_triples(text, limit)


_spacy_nlp = None
def init_spacy():
    global _spacy_nlp
    if _SPACY_AVAILABLE and _spacy_nlp is None:
        try:
            _spacy_nlp = spacy.load("en_core_web_sm", disable=["ner", "parser"])
        except Exception:
            _spacy_nlp = None

def clean_text(text: str, use_spacy: bool = False) -> str:
    text = regex_clean(text)
    if use_spacy and _SPACY_AVAILABLE:
        try:
            init_spacy()
            if _spacy_nlp:
                doc = _spacy_nlp(text)
                return " ".join(
                    tok.lemma_ for tok in doc
                    if not tok.is_stop and not tok.is_punct and not tok.is_space
                )
        except Exception:
            pass
    return text

# ------------------------------------------------------
# Advanced Chunking (5 Improvements)
# - Sentence-aware boundaries
# - Larger chunk size (250 tokens)
# - Recursive/hierarchical splitting
# - Parent-child chunks for precision + context
# - Token-based sizing using model tokenizer
# ------------------------------------------------------
from .chunking import chunk_document_page, token_count

# ------------------------------------------------------
# CELERY TASK (SYNC, SAFE)
# ------------------------------------------------------
@celery_app.task(name="process_pdf")
def process_pdf(pdf_id: str, object_key: str, use_spacy: bool = False):
    db = SessionLocal()
    tmp_path = None

    try:
        db.execute(
            text("UPDATE pdf_metadata SET status='PROCESSING', error_message=NULL WHERE id=:id"),
            {"id": pdf_id}
        )
        db.commit()

        tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp_path = tmpfile.name
        tmpfile.close()

        download_from_minio(object_key, tmp_path)
        pages = extract_text_pages(tmp_path)

        inserts = 0
        for page_num, page_text in pages:
            # Embed raw-ish text (only regex cleaned) to preserve phrases; avoid lemmatization/stopword drop
            cleaned = clean_text(page_text, use_spacy=False)
            
            # 🔥 Advanced chunking: creates parent + child chunks
            parents, children = chunk_document_page(cleaned, page_num)
            
            # Track parent DB IDs for linking children
            parent_db_ids = {}
            
            # Insert parent chunks first
            for parent in parents:
                if not parent.text:
                    continue
                
                result = db.execute(
                    text("""
                        INSERT INTO pdf_chunks
                        (pdf_metadata_id, page_num, chunk_index, chunk_text, 
                         length_chars, token_count, chunk_type, parent_chunk_id)
                        VALUES (:pid, :pg, :idx, :txt, :len, :tokens, 'PARENT', NULL)
                        RETURNING id
                    """),
                    {
                        "pid": pdf_id,
                        "pg": page_num,
                        "idx": parent.index,
                        "txt": parent.text,
                        "len": parent.char_count,
                        "tokens": parent.token_count,
                    }
                )
                parent_db_id = result.fetchone()[0]
                parent_db_ids[parent.index] = parent_db_id
                inserts += 1
            
            # Insert child chunks linked to parents
            for child in children:
                if not child.text:
                    continue
                
                parent_db_id = parent_db_ids.get(child.parent_index)
                
                child_result = db.execute(
                    text("""
                        INSERT INTO pdf_chunks
                        (pdf_metadata_id, page_num, chunk_index, chunk_text,
                         length_chars, token_count, chunk_type, parent_chunk_id)
                        VALUES (:pid, :pg, :idx, :txt, :len, :tokens, 'CHILD', :parent_id)
                        RETURNING id
                    """),
                    {
                        "pid": pdf_id,
                        "pg": page_num,
                        "idx": child.index,
                        "txt": child.text,
                        "len": child.char_count,
                        "tokens": child.token_count,
                        "parent_id": parent_db_id,
                    }
                )
                child_chunk_id = child_result.fetchone()[0]

                # Extract triples using spaCy (with naive fallback)
                for (subj, pred, obj) in extract_triples(child.text, limit=5):
                    db.execute(
                        text("""
                            INSERT INTO pdf_triples
                            (pdf_metadata_id, chunk_id, page_num, chunk_index, subject, predicate, object)
                            VALUES (:pid, :cid, :pg, :idx, :subj, :pred, :obj)
                        """),
                        {
                            "pid": pdf_id,
                            "cid": child_chunk_id,
                            "pg": page_num,
                            "idx": child.index,
                            "subj": subj,
                            "pred": pred,
                            "obj": obj,
                        }
                    )
                inserts += 1
                
            if inserts % 100 == 0:
                db.commit()

        db.commit()

        db.execute(
            text("UPDATE pdf_metadata SET status='COMPLETED' WHERE id=:id"),
            {"id": pdf_id}
        )
        db.commit()

        logger.info("PDF processing completed: %s", pdf_id)

        # 🔥 Trigger embedding AFTER chunks exist
        celery_app.send_task("embed_pdf", args=[pdf_id])

    except Exception as e:
        db.rollback()
        db.execute(
            text("UPDATE pdf_metadata SET status='FAILED', error_message=:msg WHERE id=:id"),
            {"id": pdf_id, "msg": str(e)}
        )
        db.commit()
        logger.exception("Processing failed for %s", pdf_id)
        raise

    finally:
        db.close()
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
