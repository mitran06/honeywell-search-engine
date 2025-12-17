import math
import logging
from typing import Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.qdrant.qdrant_search import semantic_search

logger = logging.getLogger(__name__)

# Weights tuned for throughput + quality
SEMANTIC_WEIGHT = 0.6
LEXICAL_WEIGHT = 0.25
TRIPLE_WEIGHT = 0.15

# Top-K per channel before fusion
SEMANTIC_K = 20
LEXICAL_K = 30
TRIPLE_K = 20


def _normalize_scores(results: List[Dict], key: str) -> None:
    values = [r.get(key, 0.0) or 0.0 for r in results]
    if not values:
        return
    mn, mx = min(values), max(values)
    if math.isclose(mx, mn):
        for r in results:
            r[f"norm_{key}"] = 1.0
        return
    for r in results:
        r[f"norm_{key}"] = (r.get(key, 0.0) - mn) / (mx - mn)


def semantic_channel(query_vector: List[float], pdf_ids: Sequence[str]) -> List[Dict]:
    hits = semantic_search(query_vector, top_k=SEMANTIC_K, pdf_ids=pdf_ids)
    results = []
    for h in hits:
        results.append({
            "chunk_id": h.get("chunk_id"),
            "pdf_id": h.get("pdf_id"),
            "page": h.get("page"),
            "chunk_index": h.get("chunk_index"),
            "text": h.get("text"),
            "parent_text": h.get("parent_text"),
            "semantic_score": float(h.get("score") or 0.0),
        })
    _normalize_scores(results, "semantic_score")
    return results


async def lexical_channel(db: AsyncSession, query: str, pdf_ids: Sequence[UUID]) -> List[Dict]:
    # Use plainto_tsquery for simplicity; could switch to websearch_to_tsquery for richer operators
    sql = text(
        """
        SELECT id, pdf_metadata_id, page_num, chunk_index, chunk_text,
               ts_rank_cd(lexical_tsv, plainto_tsquery('english', :q)) AS lexical_score
        FROM pdf_chunks
        WHERE pdf_metadata_id = ANY(:ids)
          AND lexical_tsv @@ plainto_tsquery('english', :q)
        ORDER BY lexical_score DESC
        LIMIT :limit
        """
    )
    rows = (await db.execute(sql, {"q": query, "ids": list(pdf_ids), "limit": LEXICAL_K})).fetchall()
    results = []
    for r in rows:
        results.append({
            "chunk_id": str(r.id),
            "pdf_id": str(r.pdf_metadata_id),
            "page": r.page_num,
            "chunk_index": r.chunk_index,
            "text": r.chunk_text,
            "lexical_score": float(r.lexical_score or 0.0),
        })
    _normalize_scores(results, "lexical_score")
    return results


async def triple_channel(db: AsyncSession, query: str, pdf_ids: Sequence[UUID]) -> List[Dict]:
    sql = text(
        """
        SELECT t.chunk_id, t.pdf_metadata_id, t.page_num, t.chunk_index,
               c.chunk_text,
               ts_rank_cd(t.triple_tsv, plainto_tsquery('english', :q)) AS triple_score
        FROM pdf_triples t
        JOIN pdf_chunks c ON c.id = t.chunk_id
        WHERE t.pdf_metadata_id = ANY(:ids)
          AND t.triple_tsv @@ plainto_tsquery('english', :q)
        ORDER BY triple_score DESC
        LIMIT :limit
        """
    )
    rows = (await db.execute(sql, {"q": query, "ids": list(pdf_ids), "limit": TRIPLE_K})).fetchall()
    results = []
    for r in rows:
        results.append({
            "chunk_id": str(r.chunk_id),
            "pdf_id": str(r.pdf_metadata_id),
            "page": r.page_num,
            "chunk_index": r.chunk_index,
            "text": r.chunk_text,
            "triple_score": float(r.triple_score or 0.0),
        })
    _normalize_scores(results, "triple_score")
    return results


def fuse_results(semantic: List[Dict], lexical: List[Dict], triples: List[Dict], limit: int) -> List[Dict]:
    by_chunk: Dict[str, Dict] = {}

    def merge_channel(items: List[Dict]):
        for it in items:
            cid = str(it.get("chunk_id"))
            if not cid:
                continue
            target = by_chunk.setdefault(cid, {
                "chunk_id": cid,
                "pdf_id": it.get("pdf_id"),
                "page": it.get("page"),
                "chunk_index": it.get("chunk_index"),
                "text": it.get("text"),
                "parent_text": it.get("parent_text"),
                "semantic_score": 0.0,
                "norm_semantic_score": 0.0,
                "lexical_score": 0.0,
                "norm_lexical_score": 0.0,
                "triple_score": 0.0,
                "norm_triple_score": 0.0,
            })
            for k, v in it.items():
                target[k] = v

    merge_channel(semantic)
    merge_channel(lexical)
    merge_channel(triples)

    fused = []
    for r in by_chunk.values():
        fusion = (
            (r.get("norm_semantic_score", 0.0) * SEMANTIC_WEIGHT) +
            (r.get("norm_lexical_score", 0.0) * LEXICAL_WEIGHT) +
            (r.get("norm_triple_score", 0.0) * TRIPLE_WEIGHT)
        )
        r["fusion_score"] = fusion
        fused.append(r)

    fused.sort(key=lambda x: x.get("fusion_score", 0.0), reverse=True)
    return fused[:limit]
