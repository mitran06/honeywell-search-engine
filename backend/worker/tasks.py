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

# Optional spaCy
try:
    import spacy
    _SPACY_AVAILABLE = True
except Exception:
    _SPACY_AVAILABLE = False

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
# PDF Functions
# ------------------------------------------------------
def extract_text_pages(pdf_path: str) -> List[Tuple[int, str]]:
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        try:
            text = page.get_text()
        except Exception:
            text = ""
        pages.append((i + 1, text))
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

                # Naive OIE triples for this child chunk
                for (subj, pred, obj) in extract_naive_triples(child.text):
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
