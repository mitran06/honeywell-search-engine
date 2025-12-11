from worker.celery_app import celery_app
from minio import Minio
from app.config import settings

import fitz
import asyncio
import tempfile
import os
import json
import re
import logging
from typing import List, Tuple

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

# Optional spaCy for advanced cleaning/lemmatization
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
# DATABASE
# ------------------------------------------------------
DB_URL = settings.database_url
engine = create_async_engine(DB_URL, echo=False, future=True)
Session = async_sessionmaker(engine, expire_on_commit=False)

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
# MinIO Helpers (only download used)
# ------------------------------------------------------
def download_from_minio(object_key: str, file_path: str):
    try:
        resp = minio_client.get_object(settings.minio_bucket, object_key)

        with open(file_path, "wb") as f:
            for chunk in resp.stream(32 * 1024):
                f.write(chunk)

        resp.close()
        resp.release_conn()
    except Exception as e:
        raise RuntimeError(f"MinIO download failed: {e}")

# ------------------------------------------------------
# PDF Functions
# ------------------------------------------------------
def extract_text_pages(pdf_path: str) -> List[Tuple[int, str]]:
    """Return list of (page_number, text). Page numbers start at 1."""
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        try:
            text = page.get_text()
        except Exception as e:
            logger.warning("Failed to extract text from page %s: %s", i + 1, e)
            text = ""
        pages.append((i + 1, text))
    return pages

# Basic regex cleaning (headers/footers, repeated whitespace, non-printables)
_HEADER_FOOTER_PATTERN = re.compile(
    r"(^\s*page\s*\d+\s*$)|(^\s*\d+\s*/\s*\d+\s*$)|(^\s*confidential\s*$)",
    flags=re.IGNORECASE | re.MULTILINE
)

_WHITESPACE_PATTERN = re.compile(r"\s+")
_NON_PRINTABLE_PATTERN = re.compile(r"[^\x09\x0A\x0D\x20-\x7E\u00A0-\uFFFF]+")

def regex_clean(text: str) -> str:
    if not text:
        return ""
    # Remove common header/footer patterns
    text = _HEADER_FOOTER_PATTERN.sub(" ", text)
    # Remove non-printable characters
    text = _NON_PRINTABLE_PATTERN.sub(" ", text)
    # Normalize whitespace
    text = _WHITESPACE_PATTERN.sub(" ", text)
    return text.strip()

# spaCy cleaning optional: sentence segmentation + lemmatization + stopword removal
_spacy_nlp = None
def init_spacy(model_name: str = "en_core_web_sm"):
    global _spacy_nlp
    if not _SPACY_AVAILABLE:
        return
    if _spacy_nlp is None:
        try:
            _spacy_nlp = spacy.load(model_name, disable=["ner", "parser"])
        except Exception:
            # fallback: try to load small pipeline without model name
            try:
                _spacy_nlp = spacy.load("en_core_web_sm", disable=["ner", "parser"])
            except Exception:
                _spacy_nlp = None

def spacy_clean(text: str) -> str:
    if not _SPACY_AVAILABLE:
        return text
    if _spacy_nlp is None:
        init_spacy()
    if _spacy_nlp is None:
        return text
    doc = _spacy_nlp(text)
    # Reconstruct text using lemmatized tokens, skipping punctuation and excessive stopwords
    tokens = []
    for tok in doc:
        if tok.is_punct or tok.is_space:
            continue
        # keep numbers and proper nouns; remove excessive stopwords but preserve some
        if tok.is_stop:
            continue
        tokens.append(tok.lemma_)
    return " ".join(tokens)

def clean_text(text: str, use_spacy: bool = True) -> str:
    """
    Combined cleaning pipeline:
    1. regex cleaning to remove headers/footers and normalize whitespace
    2. optional spaCy lemmatization and light stopword removal
    """
    r = regex_clean(text)
    if use_spacy and _SPACY_AVAILABLE:
        try:
            r2 = spacy_clean(r)
            if r2:
                return r2
        except Exception as e:
            logger.warning("spaCy cleaning failed, falling back to regex only: %s", e)
    return r

# ------------------------------------------------------
# Chunking with 20% overlap
# ------------------------------------------------------
def chunk_text(text: str, max_tokens: int = 120, overlap_ratio: float = 0.2) -> List[Tuple[int, str]]:
    """
    Word-based chunking with overlap.
    - max_tokens: approximate number of words per chunk (default 120). Adjust as needed.
    - overlap_ratio: fraction of overlap between consecutive chunks (0.2 = 20%).
    Returns list of tuples (chunk_index, chunk_text).
    """
    if not text:
        return []

    words = text.split()
    if not words:
        return []

    chunk_size = max(1, int(max_tokens))
    overlap = int(chunk_size * overlap_ratio)
    step = max(1, chunk_size - overlap)

    chunks = []
    idx = 0
    start = 0
    total = len(words)

    while start < total:
        end = start + chunk_size
        chunk_words = words[start:end]
        chunk_text = " ".join(chunk_words).strip()
        chunks.append((idx, chunk_text))
        idx += 1
        start += step

    return chunks

# ------------------------------------------------------
# Async Processing Function
# ------------------------------------------------------
async def _process_pdf_async(pdf_id: str, object_key: str, use_spacy: bool = True):
    tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp_path = tmpfile.name
    tmpfile.close()

    # Initialize spaCy model lazily
    if use_spacy and _SPACY_AVAILABLE:
        try:
            init_spacy()
        except Exception:
            logger.warning("Failed to initialize spaCy; continuing with regex-only cleaning")

    try:
        # download PDF
        download_from_minio(object_key, tmp_path)

        pages = extract_text_pages(tmp_path)
        # We will collect a small summary in case of need; but we will NOT upload chunks to MinIO.
        all_chunks_for_debug = []

        # Single-session DB usage to avoid concurrent asyncpg operations
        async with Session() as session:
            # Set status to PROCESSING
            await session.execute(
                text("UPDATE pdf_metadata SET status='PROCESSING', error_message=NULL WHERE id=:id"),
                {"id": pdf_id}
            )
            await session.commit()

            # Insert chunks page by page. Commit in batches to avoid huge transactions.
            BATCH_COMMIT_EVERY = 100  # commit every 100 chunk inserts
            inserts_since_commit = 0

            for page_num, page_text in pages:
                cleaned = clean_text(page_text, use_spacy=use_spacy)
                chunks = chunk_text(cleaned, max_tokens=120, overlap_ratio=0.2)

                all_chunks_for_debug.append((page_num, len(chunks)))

                for idx, text_chunk in chunks:
                    # ensure we never insert empty chunks
                    if not text_chunk:
                        continue

                    await session.execute(
                        text("""
                            INSERT INTO pdf_chunks
                            (pdf_metadata_id, page_num, chunk_index, chunk_text, length_chars)
                            VALUES (:pid, :pg, :idx, :txt, :len)
                        """),
                        {
                            "pid": pdf_id,
                            "pg": page_num,
                            "idx": idx,
                            "txt": text_chunk,
                            "len": len(text_chunk)
                        }
                    )
                    inserts_since_commit += 1

                    if inserts_since_commit >= BATCH_COMMIT_EVERY:
                        await session.commit()
                        inserts_since_commit = 0

            # final commit
            if inserts_since_commit > 0:
                await session.commit()

        # Completed
        async with Session() as session:
            await session.execute(
                text("UPDATE pdf_metadata SET status='COMPLETED' WHERE id=:id"),
                {"id": pdf_id}
            )
            await session.commit()

        logger.info("PDF processing completed for id=%s object=%s pages=%d",
                    pdf_id, object_key, len(pages))

    except Exception as e:
        # Set FAILED with error message
        try:
            async with Session() as session:
                await session.execute(
                    text("UPDATE pdf_metadata SET status='FAILED', error_message=:msg WHERE id=:id"),
                    {"id": pdf_id, "msg": str(e)}
                )
                await session.commit()
        except Exception as ex_upd:
            logger.error("Failed to set FAILED status for pdf_id=%s: %s", pdf_id, ex_upd)

        logger.exception("Processing failed for pdf_id=%s object=%s: %s", pdf_id, object_key, e)
        raise e

    finally:
        # cleanup temp file
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception as cleanup_err:
            logger.warning("Failed to remove temp file %s: %s", tmp_path, cleanup_err)

# ------------------------------------------------------
# Celery Entry Point
# ------------------------------------------------------
@celery_app.task(name="process_pdf")
def process_pdf(pdf_id: str, object_key: str, use_spacy: bool = True):
    """
    Celery task entrypoint. Keeps synchronous signature for Celery.
    use_spacy: optional boolean; worker can call without spaCy if model not installed.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_process_pdf_async(pdf_id, object_key, use_spacy=use_spacy))
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
