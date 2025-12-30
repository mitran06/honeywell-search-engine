from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .celery_app import celery_app
from app.config import settings
from app.services.embeddings.embedder import generate_embeddings
from app.services.qdrant.qdrant_client import ensure_collection, upsert_points

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("embedder")

# ------------------------------------------------------
# SYNC DATABASE (REQUIRED FOR CELERY ON WINDOWS)
# ------------------------------------------------------
SYNC_DB_URL = settings.database_url.replace("+asyncpg", "")
engine = create_engine(SYNC_DB_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

# ------------------------------------------------------
# CELERY TASK
# ------------------------------------------------------
@celery_app.task(name="embed_pdf")
def embed_pdf(pdf_id: str):
    logger.info("Starting embedding for PDF: %s", pdf_id)
    db = SessionLocal()

    try:
        ensure_collection()

        rows = db.execute(
            text("""
                SELECT c.id, c.chunk_text, c.page_num, c.chunk_index, c.parent_chunk_id,
                       COALESCE(p.chunk_text, c.chunk_text) AS parent_text
                FROM pdf_chunks c
                LEFT JOIN pdf_chunks p ON c.parent_chunk_id = p.id
                WHERE c.pdf_metadata_id = :pid
                  AND c.embedded = FALSE
                  AND c.chunk_type = 'CHILD'
            """),
            {"pid": pdf_id}
        ).fetchall()

        # ONLY CHANGE: do NOT mark COMPLETED here
        if not rows:
            logger.info("No child chunks to embed for %s", pdf_id)
            return

        texts = []
        payloads = []
        ids = []

        for r in rows:
            composite_text = (
                f"{r.parent_text.strip() if r.parent_text else ''}\n"
                f"{r.chunk_text.strip()}"
            )

            ids.append(str(r.id))
            texts.append(composite_text)

            payloads.append({
                "chunk_id": str(r.id),
                "pdf_id": pdf_id,
                "page": r.page_num,
                "chunk_index": r.chunk_index,
                "text": r.chunk_text,
                "parent_text": r.parent_text,
                "composite_text": composite_text,
                "parent_chunk_id": str(r.parent_chunk_id) if r.parent_chunk_id else None,
            })

        embeddings = generate_embeddings(texts)

        points = [
            {
                "id": ids[i],
                "vector": embeddings[i],
                "payload": payloads[i],
            }
            for i in range(len(ids))
        ]

        upsert_points(points)

        db.execute(
            text("""
                UPDATE pdf_chunks
                SET embedded = TRUE
                WHERE pdf_metadata_id = :pid
            """),
            {"pid": pdf_id},
        )

        # COMPLETED is set ONLY after embeddings + Qdrant upsert
        db.execute(
            text("UPDATE pdf_metadata SET status='COMPLETED' WHERE id=:id"),
            {"id": pdf_id},
        )

        db.commit()
        logger.info("Embedded %d chunks for PDF %s", len(ids), pdf_id)

    except Exception:
        db.rollback()
        db.execute(
            text("""
                UPDATE pdf_metadata
                SET status='EMBED_FAILED', error_message='embedding failed'
                WHERE id=:id
            """),
            {"id": pdf_id},
        )
        db.commit()
        raise

    finally:
        db.close()
