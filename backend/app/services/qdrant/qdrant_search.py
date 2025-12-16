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
        results = qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=top_k,
            with_payload=True,
            query_filter=q_filter,
        )
        # qdrant_client>=1.16 returns QueryResponse with .points
        if hasattr(results, "points"):
            results = results.points
    except Exception:
        logger.exception("Qdrant search failed")
        return []

    formatted = []
    for r in results:
        payload = r.payload if hasattr(r, "payload") else {}
        score = r.score if hasattr(r, "score") else r[1] if isinstance(r, tuple) and len(r) > 1 else None
        formatted.append({
            "score": score,
            "pdf_id": payload.get("pdf_id") if payload else None,
            "page": payload.get("page") if payload else None,
            "chunk_index": payload.get("chunk_index") if payload else None,
            "text": payload.get("text") if payload else None,
        })

    return formatted
