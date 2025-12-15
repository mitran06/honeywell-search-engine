from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .celery_app import celery_app
from app.config import settings
from app.services.embeddings.embedder import generate_embeddings
from app.services.qdrant.qdrant_client import ensure_collection, upsert_points

import logging
import uuid

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
                SELECT id, chunk_text, page_num, chunk_index
                FROM pdf_chunks
                WHERE pdf_metadata_id = :pid
                  AND embedded = FALSE
            """),
            {"pid": pdf_id}
        ).fetchall()

        if not rows:
            logger.info("No chunks to embed for %s", pdf_id)
            return

        chunk_ids = []
        texts = []
        payloads = []

        for r in rows:
            chunk_ids.append(r.id)          # keep UUID type
            texts.append(r.chunk_text)
            payloads.append({
                "pdf_id": pdf_id,
                "page": r.page_num,
                "chunk_index": r.chunk_index,
            })

        embeddings = generate_embeddings(texts)

        points = [
            {
                "id": str(chunk_ids[i]),    # Qdrant needs string
                "vector": embeddings[i],
                "payload": payloads[i],
            }
            for i in range(len(chunk_ids))
        ]

        # 🔥 Insert into Qdrant
        upsert_points(points)

        # Mark chunks as embedded
        for cid in chunk_ids:
            db.execute(
                text("UPDATE pdf_chunks SET embedded = TRUE WHERE id = :id"),
                {"id": cid},
            )

        # Mark PDF as embedded/completed
        db.execute(
            text("UPDATE pdf_metadata SET status='COMPLETED' WHERE id=:id"),
            {"id": pdf_id},
        )

        db.commit()

        logger.info(
            "Embedded %d chunks for PDF %s",
            len(chunk_ids),
            pdf_id
        )

    except Exception:
        db.rollback()
        db.execute(
            text("UPDATE pdf_metadata SET status='EMBED_FAILED', error_message='embedding failed' WHERE id=:id"),
            {"id": pdf_id},
        )
        db.commit()
        logger.exception("Embedding failed for %s", pdf_id)
        raise

    finally:
        db.close()
