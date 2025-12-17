from worker.celery_app import celery_app
from minio import Minio
from app.config import settings

import fitz
import asyncio
import tempfile
import os
import re
import logging
from typing import List, Tuple

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

# ------------------------------------------------------
# OPTIONAL SPACY
# ------------------------------------------------------
try:
    import spacy
    _SPACY_AVAILABLE = True
except Exception:
    _SPACY_AVAILABLE = False

_spacy_nlp = None

def get_spacy():
    global _spacy_nlp
    if not _SPACY_AVAILABLE:
        return None
    if _spacy_nlp is None:
        _spacy_nlp = spacy.load("en_core_web_sm", disable=["ner", "parser"])
    return _spacy_nlp

# ------------------------------------------------------
# LOGGING
# ------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tasks")

# ------------------------------------------------------
# DATABASE
# ------------------------------------------------------
engine = create_async_engine(settings.database_url, echo=False, future=True)
Session = async_sessionmaker(engine, expire_on_commit=False)

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
# STATUS UPDATE (ISOLATED SESSIONS)
# ------------------------------------------------------
async def update_status(pdf_id: str, status: str, error: str | None = None):
    async with Session() as session:
        await session.execute(
            text("""
                UPDATE pdf_metadata
                SET status = :status,
                    error_message = :error
                WHERE id = :id
            """),
            {
                "id": pdf_id,
                "status": status,
                "error": error,
            }
        )
        await session.commit()

# ------------------------------------------------------
# MINIO DOWNLOAD
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
# PDF EXTRACTION
# ------------------------------------------------------
def extract_text_pages(pdf_path: str) -> List[Tuple[int, str]]:
    doc = fitz.open(pdf_path)
    return [(i + 1, page.get_text() or "") for i, page in enumerate(doc)]

# ------------------------------------------------------
# TEXT CLEANING
# ------------------------------------------------------
_HEADER_FOOTER_PATTERN = re.compile(
    r"(^\s*page\s*\d+\s*$)|(^\s*\d+\s*/\s*\d+\s*$)",
    flags=re.IGNORECASE | re.MULTILINE,
)
_WHITESPACE_PATTERN = re.compile(r"\s+")

def clean_text(text: str, use_spacy: bool = True) -> str:
    text = _HEADER_FOOTER_PATTERN.sub(" ", text)
    text = _WHITESPACE_PATTERN.sub(" ", text).strip()

    if use_spacy and _SPACY_AVAILABLE:
        nlp = get_spacy()
        if nlp:
            doc = nlp(text)
            text = " ".join(
                tok.lemma_
                for tok in doc
                if not tok.is_stop and not tok.is_punct
            )

    return text

# ------------------------------------------------------
# CHUNKING
# ------------------------------------------------------
def chunk_text(text: str, max_tokens: int = 120, overlap_ratio: float = 0.2):
    words = text.split()
    if not words:
        return []

    overlap = int(max_tokens * overlap_ratio)
    step = max(1, max_tokens - overlap)

    chunks = []
    idx = 0
    for start in range(0, len(words), step):
        chunk = " ".join(words[start:start + max_tokens])
        if chunk:
            chunks.append((idx, chunk))
            idx += 1
    return chunks

# ------------------------------------------------------
# CORE ASYNC PROCESSOR (FIXED)
# ------------------------------------------------------
async def _process_pdf_async(pdf_id: str, object_key: str, use_spacy: bool = True):
    tmp_path = None

    try:
        # 1. Mark processing
        await update_status(pdf_id, "PROCESSING")

        # 2. Download PDF
        tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp_path = tmpfile.name
        tmpfile.close()
        download_from_minio(object_key, tmp_path)

        # 3. Extract + preprocess (NO DB here)
        pages = extract_text_pages(tmp_path)

        processed_pages = []
        for page_num, page_text in pages:
            cleaned = clean_text(page_text, use_spacy=use_spacy)
            chunks = chunk_text(cleaned)
            processed_pages.append((page_num, chunks))

        # 4. Insert chunks (DB-only section)
        async with Session() as session:
            insert_count = 0

            for page_num, chunks in processed_pages:
                for idx, chunk in chunks:
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
                            "txt": chunk,
                            "len": len(chunk),
                        }
                    )

                    insert_count += 1
                    if insert_count % 100 == 0:
                        await session.commit()

            await session.commit()

        # 5. Mark completed
        await update_status(pdf_id, "COMPLETED")
        logger.info("PDF processed successfully: %s", pdf_id)

    except Exception as e:
        await update_status(pdf_id, "FAILED", str(e))
        logger.exception("PDF processing failed: %s", pdf_id)
        raise

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

# ------------------------------------------------------
# CELERY ENTRYPOINT
# ------------------------------------------------------
@celery_app.task(name="process_pdf")
def process_pdf(pdf_id: str, object_key: str, use_spacy: bool = True):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(
            _process_pdf_async(pdf_id, object_key, use_spacy=use_spacy)
        )
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
