from .celery_app import celery_app
from minio import Minio
from app.config import settings

import fitz
import tempfile
import os
import re
import logging
from typing import List, Tuple

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

def regex_clean(text: str) -> str:
    text = _HEADER_FOOTER_PATTERN.sub(" ", text)
    text = _NON_PRINTABLE_PATTERN.sub(" ", text)
    text = _WHITESPACE_PATTERN.sub(" ", text)
    return text.strip()

_spacy_nlp = None
def init_spacy():
    global _spacy_nlp
    if _SPACY_AVAILABLE and _spacy_nlp is None:
        try:
            _spacy_nlp = spacy.load("en_core_web_sm", disable=["ner", "parser"])
        except Exception:
            _spacy_nlp = None

def clean_text(text: str, use_spacy: bool = True) -> str:
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
# Chunking (UNCHANGED LOGIC)
# ------------------------------------------------------
def chunk_text(text: str, max_tokens: int = 120, overlap_ratio: float = 0.2):
    words = text.split()
    if not words:
        return []

    overlap = int(max_tokens * overlap_ratio)
    step = max(1, max_tokens - overlap)

    chunks = []
    idx = 0
    start = 0

    while start < len(words):
        end = start + max_tokens
        chunks.append((idx, " ".join(words[start:end])))
        idx += 1
        start += step

    return chunks

# ------------------------------------------------------
# CELERY TASK (SYNC, SAFE)
# ------------------------------------------------------
@celery_app.task(name="process_pdf")
def process_pdf(pdf_id: str, object_key: str, use_spacy: bool = True):
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
            cleaned = clean_text(page_text, use_spacy)
            chunks = chunk_text(cleaned)

            for idx, chunk in chunks:
                if not chunk:
                    continue

                db.execute(
                    text("""
                        INSERT INTO pdf_chunks
                        (pdf_metadata_id, page_num, chunk_index, chunk_text, length_chars)
                        VALUES (:pid, :pg, :idx, :txt, :len)
                    """),
                    {
                        "pid": pdf_id,
                        "pg": page_num,
                        "idx": idx,
                        "txt": chunk,
                        "len": len(chunk),
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
