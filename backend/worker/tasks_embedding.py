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

        # Only embed CHILD chunks - they are optimized for vector search
        # Parent chunks are kept for context/reranking but not embedded
        rows = db.execute(
            text("""
                SELECT c.id, c.chunk_text, c.page_num, c.chunk_index, c.parent_chunk_id,
                       COALESCE(p.chunk_text, c.chunk_text) as parent_text
                FROM pdf_chunks c
                LEFT JOIN pdf_chunks p ON c.parent_chunk_id = p.id
                WHERE c.pdf_metadata_id = :pid
                  AND c.embedded = FALSE
                  AND c.chunk_type = 'CHILD'
            """),
            {"pid": pdf_id}
        ).fetchall()

        if not rows:
            logger.info("No child chunks to embed for %s", pdf_id)
            # Mark as completed if everything is already embedded
            db.execute(
                text("UPDATE pdf_metadata SET status='COMPLETED' WHERE id=:id"),
                {"id": pdf_id},
            )
            db.commit()
            return

        chunk_ids = []
        texts = []
        payloads = []

        for r in rows:
            chunk_ids.append(r.id)          # keep UUID type
            texts.append(r.chunk_text)
            payloads.append({
                "chunk_id": str(r.id),
                "pdf_id": pdf_id,
                "page": r.page_num,
                "chunk_index": r.chunk_index,
                "text": r.chunk_text,
                # Include parent text for expanded context in search results
                "parent_text": r.parent_text,
                "parent_chunk_id": str(r.parent_chunk_id) if r.parent_chunk_id else None,
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

        # Insert into Qdrant
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
