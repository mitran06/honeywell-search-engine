from qdrant_client import QdrantClient
from qdrant_client.http import models
from typing import List, Dict, Any
import logging

logger = logging.getLogger("indexer")

# ------------------------------------------------------------
# Qdrant Indexer for storing and managing embeddings
# ------------------------------------------------------------

class QdrantIndexer:
    def __init__(self, host: str = "localhost", port: int = 6333):
        logger.info(f"Connecting to Qdrant at {host}:{port}")
        self.client = QdrantClient(host=host, port=port)
        self.collection_name = "chunks_index"
        self.vector_size = 1024  # BGE-M3 embedding dimension

        self._ensure_collection()

    # --------------------------------------------------------
    # Ensure collection exists
    # --------------------------------------------------------
    def _ensure_collection(self):
        collections = self.client.get_collections().collections

        names = [c.name for c in collections]
        if self.collection_name in names:
            logger.info(f"Collection '{self.collection_name}' already exists.")
            return

        logger.info(f"Creating Qdrant collection '{self.collection_name}'...")

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=self.vector_size,
                distance=models.Distance.COSINE
            ),
            # Enable payload indexing for filters
            optimizers_config=models.OptimizersConfigDiff(indexing_threshold=0)
        )

        logger.info("Collection created.")

    # --------------------------------------------------------
    # Upsert embeddings with payload
    # --------------------------------------------------------
    def upsert_embeddings(self, vectors: List[List[float]], payloads: List[Dict[str, Any]]):
        """
        Insert or update embeddings.
        Each vector must have a matching payload.
        """
        if len(vectors) != len(payloads):
            raise ValueError("Vectors and payloads length mismatch")

        logger.info(f"Upserting {len(vectors)} embeddings into Qdrant...")

        points = []
        for idx, (vec, payload) in enumerate(zip(vectors, payloads)):
            points.append(
                models.PointStruct(
                    id=payload.get("point_id", idx),
                    vector=vec,
                    payload=payload
                )
            )

        self.client.upsert(collection_name=self.collection_name, points=points)
        logger.info("Upsert completed.")

    # --------------------------------------------------------
    # Delete embeddings belonging to a PDF
    # --------------------------------------------------------
    def delete_pdf(self, pdf_id: str):
        logger.info(f"Deleting vectors for pdf_id={pdf_id}")

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[models.FieldCondition(key="pdf_id", match=models.MatchValue(value=pdf_id))]
                )
            )
        )

        logger.info("Delete completed.")

    # --------------------------------------------------------
    # Search vectors
    # --------------------------------------------------------
    def search(self, query_vector: List[float], limit: int = 5, pdf_id: str = None):
        conditions = []
        if pdf_id:
            conditions.append(
                models.FieldCondition(key="pdf_id", match=models.MatchValue(value=pdf_id))
            )

        search_filter = models.Filter(must=conditions) if conditions else None

        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit,
            search_filter=search_filter
        )

        return results