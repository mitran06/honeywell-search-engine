import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

from app.services.embeddings.embedder import embed_text_async
from app.services.qdrant.qdrant_client import upsert_embeddings
from app.config import settings

logger = logging.getLogger("pipeline")

engine = create_async_engine(settings.database_url, echo=False, future=True)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def run_embedding_pipeline(pdf_id: str):
    async with Session() as session:
        rows = await session.execute(
            text("SELECT id, chunk_text FROM pdf_chunks WHERE pdf_metadata_id=:pid"),
            {"pid": pdf_id}
        )
        chunks = rows.fetchall()

    vectors = []
    for chunk_id, text_data in chunks:
        vector = await embed_text_async(text_data)
        vectors.append((chunk_id, vector))

    await upsert_embeddings(pdf_id, vectors)

    async with Session() as session:
        await session.execute(
            text("UPDATE pdf_metadata SET status='EMBEDDED' WHERE id=:id"),
            {"id": pdf_id}
        )
        await session.commit()
