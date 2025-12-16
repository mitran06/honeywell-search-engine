import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

from app.services.embeddings.embedder import embed_text_async
from app.services.qdrant.qdrant_client import ensure_collection, upsert_points
from app.config import settings

logger = logging.getLogger("pipeline")

engine = create_async_engine(settings.database_url, echo=False, future=True)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def run_embedding_pipeline(pdf_id: str):
    async with Session() as session:
        rows = await session.execute(
            text("SELECT id, chunk_text, page_num, chunk_index FROM pdf_chunks WHERE pdf_metadata_id=:pid"),
            {"pid": pdf_id}
        )
        chunks = rows.fetchall()

    if not chunks:
        async with Session() as session:
            await session.execute(
                text("UPDATE pdf_metadata SET status='COMPLETED' WHERE id=:id"),
                {"id": pdf_id}
            )
            await session.commit()
        return

    vectors = []
    payloads = []
    for chunk_id, text_data, page_num, chunk_index in chunks:
        vector = await embed_text_async(text_data)
        vectors.append((chunk_id, vector))
        payloads.append({
            "pdf_id": pdf_id,
            "page": page_num,
            "chunk_index": chunk_index,
            "text": text_data,
        })

    ensure_collection()

    points = [
        {"id": str(vectors[i][0]), "vector": vectors[i][1], "payload": payloads[i]}
        for i in range(len(vectors))
    ]

    upsert_points(points)

    async with Session() as session:
        await session.execute(
            text("UPDATE pdf_chunks SET embedded=TRUE WHERE pdf_metadata_id=:id"),
            {"id": pdf_id},
        )
        await session.execute(
            text("UPDATE pdf_metadata SET status='COMPLETED' WHERE id=:id"),
            {"id": pdf_id}
        )
        await session.commit()
