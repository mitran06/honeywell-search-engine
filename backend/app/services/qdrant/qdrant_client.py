from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
from app.config import settings

COLLECTION_NAME = settings.qdrant_collection
VECTOR_SIZE = settings.embedding_dim  # must align with embedding model

client = QdrantClient(
    host=settings.qdrant_host,
    port=settings.qdrant_port,
)

def ensure_collection():
    collections = client.get_collections().collections
    names = [c.name for c in collections]

    if COLLECTION_NAME not in names:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
        )
        print(f"[QDRANT] Created collection '{COLLECTION_NAME}' with dim={VECTOR_SIZE}")
    else:
        print(f"[QDRANT] Collection '{COLLECTION_NAME}' already exists")

def upsert_points(points: list[dict]):
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
        wait=True,
    )
