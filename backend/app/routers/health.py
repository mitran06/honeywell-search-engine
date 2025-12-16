from fastapi import APIRouter

from app.config import settings
from app.services.qdrant.qdrant_client import client, COLLECTION_NAME, VECTOR_SIZE

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/qdrant")
async def qdrant_health():
    """Check Qdrant connectivity and collection vector size."""
    info = client.get_collection(COLLECTION_NAME)
    vector_size = info.config.params.vectors.size

    return {
        "status": "ok",
        "collection": COLLECTION_NAME,
        "vector_size": vector_size,
        "expected_vector_size": VECTOR_SIZE,
        "host": settings.qdrant_host,
        "port": settings.qdrant_port,
        "match": vector_size == VECTOR_SIZE,
    }
