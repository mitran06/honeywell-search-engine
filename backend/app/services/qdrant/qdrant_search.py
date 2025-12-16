import logging
from typing import Optional, Sequence

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from app.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "pdf_chunks"

qdrant = QdrantClient(
    host=settings.qdrant_host,
    port=settings.qdrant_port,
)


def semantic_search(
    query_vector: list[float],
    top_k: int = 5,
    pdf_ids: Optional[Sequence[str]] = None,
):
    """Search Qdrant for similar chunks. Optional filter by pdf_ids."""
    q_filter = None
    if pdf_ids:
        q_filter = Filter(should=[FieldCondition(key="pdf_id", match=MatchValue(value=pid)) for pid in pdf_ids])

    try:
        results = qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=top_k,
            with_payload=True,
            query_filter=q_filter,
        )
    except Exception:
        logger.exception("Qdrant search failed")
        return []

    formatted = []
    for r in results:
        formatted.append({
            "score": r.score,
            "pdf_id": r.payload.get("pdf_id"),
            "page": r.payload.get("page"),
            "chunk_index": r.payload.get("chunk_index"),
            "text": r.payload.get("text"),
        })

    return formatted
