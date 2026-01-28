from .celery_app import celery_app
from minio import Minio
from app.config import settings

import fitz
import tempfile
import os
import re
import logging
import string
from typing import List, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Optional spaCy for OIE
try:
    import spacy
    _SPACY_AVAILABLE = True
except Exception:
    _SPACY_AVAILABLE = False

# Optional OCR
try:
    import pytesseract
    from pdf2image import convert_from_path
    _OCR_AVAILABLE = True
except Exception:
    _OCR_AVAILABLE = False

# Advanced chunking
from .chunking import chunk_document_page

# ------------------------------------------------------
# LOGGING
# ------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tasks")

# ------------------------------------------------------
# DATABASE (SYNC — REQUIRED FOR CELERY ON WINDOWS)
# ------------------------------------------------------
SYNC_DB_URL = settings.database_url.replace("+asyncpg", "")
engine = create_engine(SYNC_DB_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

# ------------------------------------------------------
# MINIO
# ------------------------------------------------------
minio_client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=False,
)

# ------------------------------------------------------
# MINIO HELPERS
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
# NORMALIZATION (CRITICAL FOR HIGHLIGHTING)
# ------------------------------------------------------
_NORMALIZE_PUNCT = str.maketrans("", "", string.punctuation)
_WHITESPACE_RE = re.compile(r"\s+")

def normalize_text(text: str) -> str:
    text = text.lower()
    text = text.translate(_NORMALIZE_PUNCT)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()

# ------------------------------------------------------
# OCR
# ------------------------------------------------------
def ocr_page_image(image) -> str:
    if not _OCR_AVAILABLE:
        return ""
    try:
        return pytesseract.image_to_string(image, lang="eng")
    except Exception as e:
        logger.warning("OCR failed: %s", e)
        return ""

def extract_text_with_ocr(pdf_path: str, page_num: int) -> str:
    if not _OCR_AVAILABLE:
        return ""
    try:
        images = convert_from_path(
            pdf_path, first_page=page_num, last_page=page_num, dpi=300
        )
        if images:
            return ocr_page_image(images[0])
    except Exception as e:
        logger.warning("OCR extraction failed for page %s: %s", page_num, e)
    return ""

# ------------------------------------------------------
# PDF EXTRACTION
# ------------------------------------------------------
def extract_text_pages(pdf_path: str) -> List[Tuple[int, str]]:
    doc = fitz.open(pdf_path)
    pages = []

    for i, page in enumerate(doc):
        page_num = i + 1
        try:
            text = page.get_text() or ""
        except Exception:
            text = ""

        if len(text.strip()) < 50 and _OCR_AVAILABLE:
            ocr_text = extract_text_with_ocr(pdf_path, page_num)
            if len(ocr_text.strip()) > len(text.strip()):
                text = ocr_text

        pages.append((page_num, text))

    doc.close()
    return pages

# ------------------------------------------------------
# CLEANING
# ------------------------------------------------------
_HEADER_FOOTER_PATTERN = re.compile(
    r"(^\s*page\s*\d+\s*$)|(^\s*\d+\s*/\s*\d+\s*$)|(^\s*confidential\s*$)",
    flags=re.IGNORECASE | re.MULTILINE,
)
_WHITESPACE_PATTERN = re.compile(r"\s+")
_NON_PRINTABLE_PATTERN = re.compile(r"[^\x09\x0A\x0D\x20-\x7E\u00A0-\uFFFF]+")
_HYPHEN_BREAK_PATTERN = re.compile(r"(\w)-\s+(\w)")

def clean_text(text: str) -> str:
    text = _HEADER_FOOTER_PATTERN.sub(" ", text)
    text = _NON_PRINTABLE_PATTERN.sub(" ", text)
    text = _HYPHEN_BREAK_PATTERN.sub(r"\1\2", text)
    text = _WHITESPACE_PATTERN.sub(" ", text)
    return text.strip()

# ------------------------------------------------------
# OIE (spaCy with fallback)
# ------------------------------------------------------
_spacy_nlp = None

def _get_spacy():
    global _spacy_nlp
    if _spacy_nlp is None and _SPACY_AVAILABLE:
        try:
            _spacy_nlp = spacy.load("en_core_web_sm")
        except Exception:
            _spacy_nlp = None
    return _spacy_nlp

def extract_naive_triples(text: str, limit: int = 3):
    triples = []
    for sent in re.split(r"[.!?]\s+", text):
        toks = sent.split()
        if len(toks) >= 3:
            triples.append((toks[0], toks[1], " ".join(toks[2:])))
        if len(triples) >= limit:
            break
    return triples

def extract_triples(text: str, limit: int = 5):
    nlp = _get_spacy()
    if not nlp:
        return extract_naive_triples(text, limit)

    triples = []
    try:
        doc = nlp(text[:5000])
        for sent in doc.sents:
            root = next(
                (t for t in sent if t.dep_ == "ROOT" and t.pos_ == "VERB"), None
            )
            if not root:
                continue

            subj = None
            for c in root.children:
                if c.dep_ in ("nsubj", "nsubjpass"):
                    subj = " ".join(t.text for t in c.subtree)
                    break
            if not subj:
                continue

            pred = root.text
            obj = None
            for c in root.children:
                if c.dep_ in ("dobj", "pobj", "attr", "acomp"):
                    obj = " ".join(t.text for t in c.subtree)
                    break

            if subj and obj:
                triples.append((subj.strip(), pred.strip(), obj.strip()))
                if len(triples) >= limit:
                    break
    except Exception:
        return extract_naive_triples(text, limit)

    return triples or extract_naive_triples(text, limit)

# ------------------------------------------------------
# CELERY TASK
# ------------------------------------------------------
@celery_app.task(name="process_pdf")
def process_pdf(pdf_id: str, object_key: str):
    db = SessionLocal()
    tmp_path = None

    try:
        db.execute(
            text("UPDATE pdf_metadata SET status='PROCESSING' WHERE id=:id"),
            {"id": pdf_id},
        )
        db.commit()

        tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp_path = tmpfile.name
        tmpfile.close()

        download_from_minio(object_key, tmp_path)
        pages = extract_text_pages(tmp_path)

        for page_num, page_text in pages:
            cleaned = clean_text(page_text)
            if not cleaned:
                continue

            parents, children = chunk_document_page(cleaned, page_num)
            parent_db_ids = {}

            # -------------------------------
            # INSERT PARENT CHUNKS
            # -------------------------------
            for p in parents:
                res = db.execute(
                    text("""
                        INSERT INTO pdf_chunks
                        (pdf_metadata_id, page_num, chunk_index, chunk_text,
                         normalized_text, length_chars, token_count,
                         chunk_type, parent_chunk_id)
                        VALUES (:pid, :pg, :idx, :txt, :norm, :len, :tokens, 'PARENT', NULL)
                        RETURNING id
                    """),
                    {
                        "pid": pdf_id,
                        "pg": page_num,
                        "idx": p.index,
                        "txt": p.text,
                        "norm": normalize_text(p.text),
                        "len": p.char_count,
                        "tokens": p.token_count,
                    },
                )
                parent_db_ids[p.index] = res.fetchone()[0]

            # -------------------------------
            # INSERT CHILD CHUNKS
            # -------------------------------
            for c in children:
                parent_id = parent_db_ids.get(c.parent_index)
                res = db.execute(
                    text("""
                        INSERT INTO pdf_chunks
                        (pdf_metadata_id, page_num, chunk_index, chunk_text,
                         normalized_text, length_chars, token_count,
                         chunk_type, parent_chunk_id)
                        VALUES (:pid, :pg, :idx, :txt, :norm, :len, :tokens, 'CHILD', :parent)
                        RETURNING id
                    """),
                    {
                        "pid": pdf_id,
                        "pg": page_num,
                        "idx": c.index,
                        "txt": c.text,
                        "norm": normalize_text(c.text),
                        "len": c.char_count,
                        "tokens": c.token_count,
                        "parent": parent_id,
                    },
                )
                child_chunk_id = res.fetchone()[0]

                for subj, pred, obj in extract_triples(c.text):
                    db.execute(
                        text("""
                            INSERT INTO pdf_triples
                            (pdf_metadata_id, chunk_id, page_num, chunk_index,
                             subject, predicate, object)
                            VALUES (:pid, :cid, :pg, :idx, :s, :p, :o)
                        """),
                        {
                            "pid": pdf_id,
                            "cid": child_chunk_id,
                            "pg": page_num,
                            "idx": c.index,
                            "s": subj,
                            "p": pred,
                            "o": obj,
                        },
                    )

        db.execute(
            text("UPDATE pdf_metadata SET status='COMPLETED' WHERE id=:id"),
            {"id": pdf_id},
        )
        db.commit()

        celery_app.send_task("embed_pdf", args=[pdf_id])
        logger.info("PDF processed successfully: %s", pdf_id)

    except Exception as e:
        db.rollback()
        db.execute(
            text(
                "UPDATE pdf_metadata SET status='FAILED', error_message=:msg WHERE id=:id"
            ),
            {"id": pdf_id, "msg": str(e)},
        )
        db.commit()
        logger.exception("Processing failed for %s", pdf_id)
        raise

    finally:
        db.close()
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
