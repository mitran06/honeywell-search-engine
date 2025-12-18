from qdrant_client import QdrantClient

<<<<<<< Updated upstream
qdrant = QdrantClient(url="http://localhost:6333")
=======
from app.config import settings
from app.services.search.lexical_score import lexical_overlap_score
from app.services.search.filters import is_valid_chunk

logger = logging.getLogger(__name__)
>>>>>>> Stashed changes

COLLECTION_NAME = "pdf_chunks"


<<<<<<< Updated upstream
def semantic_search(query_vector: list[float], top_k: int = 5):
    results = qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=top_k,
        with_payload=True,
    )

    formatted = []
    for r in results:
        formatted.append({
            "score": r.score,
            "pdf_id": r.payload.get("pdf_id"),
            "page": r.payload.get("page"),
            "chunk_index": r.payload.get("chunk_index"),
            "text": r.payload.get("text"),
=======
# --------------------------------------------------
# 1️⃣ SEMANTIC SEARCH
# --------------------------------------------------
def semantic_search(
    query_vector: list[float],
    top_k: int = 20,
    pdf_ids: Optional[Sequence[str]] = None,
):
    q_filter = None
    if pdf_ids:
        q_filter = Filter(
            should=[
                FieldCondition(key="pdf_id", match=MatchValue(value=pid))
                for pid in pdf_ids
            ]
        )

    try:
        results = qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=top_k,
            with_payload=True,
            query_filter=q_filter,
        )

        if hasattr(results, "points"):
            results = results.points

    except Exception:
        logger.exception("Qdrant search failed")
        return []

    formatted = []
    for r in results:
        payload = r.payload or {}
        formatted.append({
            "semantic_score": float(r.score or 0.0),
            "pdf_id": payload.get("pdf_id"),
            "page": payload.get("page"),
            "chunk_index": payload.get("chunk_index"),
            "text": payload.get("text"),
>>>>>>> Stashed changes
        })

    return formatted

# --------------------------------------------------
# 2️⃣ HYBRID RERANKING (GENERAL & UNBIASED)
# --------------------------------------------------
def hybrid_rerank(
    query: str,
    results: list[dict],
    semantic_weight: float = 0.6,
    lexical_weight: float = 0.4,
):
    reranked = []

    for r in results:
        text = r.get("text", "")
        semantic = float(r.get("semantic_score", 0.0))

        if not is_valid_chunk(text):
            continue

        lexical = lexical_overlap_score(query, text)

        # Base score for ranking
        base_score = (
            semantic_weight * semantic +
            lexical_weight * lexical
        )

        # 🔥 NEAR-DUPLICATE BOOST (GENERAL FIX)
        # Applies when sentence meaning + wording strongly align
        if semantic > 0.45 and lexical > 0.55:
            base_score = max(base_score, 0.9)

        # Structural soft signal (never dominant)
        if r.get("page") == 1:
            base_score += 0.03

        r["lexical_score"] = round(lexical, 3)
        r["final_score"] = round(min(base_score, 0.95), 3)

        reranked.append(r)

    return sorted(reranked, key=lambda x: x["final_score"], reverse=True)


# --------------------------------------------------
# 3️⃣ PUBLIC SEARCH API
# --------------------------------------------------
def hybrid_search(
    query: str,
    query_vector: list[float],
    top_k: int = 10,
    pdf_ids: Optional[Sequence[str]] = None,
):
    semantic_results = semantic_search(
        query_vector=query_vector,
        top_k=top_k * 2,
        pdf_ids=pdf_ids,
    )

    return hybrid_rerank(query, semantic_results)[:top_k]
