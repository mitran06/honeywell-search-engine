"""
Hybrid Search Fusion Module

Implements:
- Semantic search via Qdrant
- Lexical search via PostgreSQL full-text
- Triple search via PostgreSQL
- Reciprocal Rank Fusion (RRF) for combining results
- Cross-encoder reranking for top results
"""
import logging
import re
from typing import Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.qdrant.qdrant_search import semantic_search

logger = logging.getLogger(__name__)

# ------------------------------------------------------
# Configuration
# ------------------------------------------------------

# Top-K per channel before fusion
SEMANTIC_K = 50
LEXICAL_K = 50
TRIPLE_K = 30

# RRF constant (standard value from literature)
RRF_K = 60

# Channel weights for weighted RRF
SEMANTIC_WEIGHT = 1.0
LEXICAL_WEIGHT = 1.2  # Slightly favor exact matches
TRIPLE_WEIGHT = 0.8

# Reranking config
RERANK_TOP_K = 20  # Number of candidates to rerank
USE_CROSS_ENCODER = True

# Lazy-loaded cross-encoder
_cross_encoder = None


def _get_cross_encoder():
    """Lazy load cross-encoder model for reranking."""
    global _cross_encoder
    if _cross_encoder is None:
        try:
            from sentence_transformers import CrossEncoder
            _cross_encoder = CrossEncoder(
                "cross-encoder/ms-marco-MiniLM-L-6-v2",
                max_length=512
            )
            logger.info("Cross-encoder loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load cross-encoder: {e}")
            _cross_encoder = "unavailable"
    return _cross_encoder if _cross_encoder != "unavailable" else None


# ------------------------------------------------------
# Utility Functions
# ------------------------------------------------------

def _normalize_query(query: str) -> str:
    """Normalize query for matching."""
    return " ".join(query.lower().split())


def _extract_snippet(text: str, query: str, window: int = 150) -> str:
    """Extract a snippet around the best match location."""
    if not text or not query:
        return text[:300] if text else ""
    
    query_lower = query.lower()
    text_lower = text.lower()
    
    # Try to find exact phrase first
    pos = text_lower.find(query_lower)
    
    # If not found, try finding any query word
    if pos == -1:
        words = query_lower.split()
        for word in words:
            if len(word) > 3:  # Skip short words
                pos = text_lower.find(word)
                if pos != -1:
                    break
    
    if pos == -1:
        return text[:300]
    
    # Extract window around match
    start = max(0, pos - window)
    end = min(len(text), pos + len(query) + window)
    
    snippet = text[start:end]
    
    # Add ellipsis if truncated
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    
    return snippet


def _highlight_matches(text: str, query: str) -> List[Dict]:
    """Find match positions for highlighting."""
    highlights = []
    if not text or not query:
        return highlights
    
    text_lower = text.lower()
    
    # Highlight exact phrase
    query_lower = query.lower()
    start = 0
    while True:
        pos = text_lower.find(query_lower, start)
        if pos == -1:
            break
        highlights.append({
            "text": text[pos:pos + len(query)],
            "startOffset": pos,
            "endOffset": pos + len(query),
        })
        start = pos + 1
    
    # Also highlight individual significant words
    words = [w for w in query.lower().split() if len(w) > 3]
    for word in words:
        start = 0
        while True:
            pos = text_lower.find(word, start)
            if pos == -1:
                break
            # Avoid overlapping with phrase highlights
            overlaps = any(
                h["startOffset"] <= pos < h["endOffset"] or
                h["startOffset"] < pos + len(word) <= h["endOffset"]
                for h in highlights
            )
            if not overlaps:
                highlights.append({
                    "text": text[pos:pos + len(word)],
                    "startOffset": pos,
                    "endOffset": pos + len(word),
                })
            start = pos + 1
    
    return sorted(highlights, key=lambda h: h["startOffset"])


# ------------------------------------------------------
# Search Channels
# ------------------------------------------------------

def semantic_channel(query_vector: List[float], pdf_ids: Sequence[str]) -> List[Dict]:
    """Semantic search via Qdrant vector similarity."""
    hits = semantic_search(query_vector, top_k=SEMANTIC_K, pdf_ids=pdf_ids)
    results = []
    for rank, h in enumerate(hits):
        results.append({
            "chunk_id": h.get("chunk_id"),
            "pdf_id": h.get("pdf_id"),
            "page": h.get("page"),
            "chunk_index": h.get("chunk_index"),
            "text": h.get("text"),
            "parent_text": h.get("parent_text"),
            "semantic_score": float(h.get("score") or 0.0),
            "semantic_rank": rank + 1,
        })
    return results


async def lexical_channel(db: AsyncSession, query: str, pdf_ids: Sequence[UUID]) -> List[Dict]:
    """Full-text search via PostgreSQL tsvector."""
    
    # Primary: PostgreSQL full-text search with websearch syntax
    ts_sql = text(
        """
        SELECT id, pdf_metadata_id, page_num, chunk_index, chunk_text,
               ts_rank_cd(lexical_tsv, websearch_to_tsquery('english', :q)) AS lexical_score
        FROM pdf_chunks
        WHERE pdf_metadata_id = ANY(:ids)
          AND lexical_tsv @@ websearch_to_tsquery('english', :q)
        ORDER BY lexical_score DESC
        LIMIT :limit
        """
    )
    
    rows = (await db.execute(ts_sql, {"q": query, "ids": list(pdf_ids), "limit": LEXICAL_K})).fetchall()
    
    results = []
    seen_ids = set()
    
    for rank, r in enumerate(rows):
        chunk_id = str(r.id)
        seen_ids.add(chunk_id)
        results.append({
            "chunk_id": chunk_id,
            "pdf_id": str(r.pdf_metadata_id),
            "page": r.page_num,
            "chunk_index": r.chunk_index,
            "text": r.chunk_text,
            "lexical_score": float(r.lexical_score or 0.0),
            "lexical_rank": rank + 1,
        })
    
    # Fallback: Exact phrase match using ILIKE (handles hyphenation issues)
    phrase = _normalize_query(query)
    if phrase:
        phrase_sql = text(
            """
            SELECT id, pdf_metadata_id, page_num, chunk_index, chunk_text
            FROM pdf_chunks
            WHERE pdf_metadata_id = ANY(:ids)
              AND lower(regexp_replace(chunk_text, E'(\\\\w)-\\\\s+(\\\\w)', E'\\\\1\\\\2', 'g')) 
                  ILIKE :pattern
            ORDER BY page_num, chunk_index
            LIMIT :limit
            """
        )
        phrase_rows = (await db.execute(
            phrase_sql, 
            {"ids": list(pdf_ids), "pattern": f"%{phrase}%", "limit": 20}
        )).fetchall()
        
        # Add phrase matches not already in results
        for r in phrase_rows:
            chunk_id = str(r.id)
            if chunk_id not in seen_ids:
                seen_ids.add(chunk_id)
                # Assign high score for exact phrase match
                results.append({
                    "chunk_id": chunk_id,
                    "pdf_id": str(r.pdf_metadata_id),
                    "page": r.page_num,
                    "chunk_index": r.chunk_index,
                    "text": r.chunk_text,
                    "lexical_score": 1.0,  # Strong evidence
                    "lexical_rank": len(results) + 1,
                })
            else:
                # Boost existing result that has exact phrase
                for res in results:
                    if res["chunk_id"] == chunk_id:
                        res["lexical_score"] = max(res.get("lexical_score", 0), 1.0)
                        break
        
        # Fallback: Wildcard pattern for partial matches
        keywords = [w for w in phrase.split() if len(w) > 2]
        if len(keywords) >= 2:
            wildcard = "%".join(keywords)
            wildcard_sql = text(
                """
                SELECT id, pdf_metadata_id, page_num, chunk_index, chunk_text
                FROM pdf_chunks
                WHERE pdf_metadata_id = ANY(:ids)
                  AND lower(chunk_text) LIKE lower(:pattern)
                ORDER BY page_num, chunk_index
                LIMIT :limit
                """
            )
            wildcard_rows = (await db.execute(
                wildcard_sql,
                {"ids": list(pdf_ids), "pattern": f"%{wildcard}%", "limit": 10}
            )).fetchall()
            
            for r in wildcard_rows:
                chunk_id = str(r.id)
                if chunk_id not in seen_ids:
                    seen_ids.add(chunk_id)
                    results.append({
                        "chunk_id": chunk_id,
                        "pdf_id": str(r.pdf_metadata_id),
                        "page": r.page_num,
                        "chunk_index": r.chunk_index,
                        "text": r.chunk_text,
                        "lexical_score": 0.5,  # Partial match
                        "lexical_rank": len(results) + 1,
                    })
    
    return results


async def triple_channel(db: AsyncSession, query: str, pdf_ids: Sequence[UUID]) -> List[Dict]:
    """Search extracted triples for relation-aware matching."""
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
    for rank, r in enumerate(rows):
        results.append({
            "chunk_id": str(r.chunk_id),
            "pdf_id": str(r.pdf_metadata_id),
            "page": r.page_num,
            "chunk_index": r.chunk_index,
            "text": r.chunk_text,
            "triple_score": float(r.triple_score or 0.0),
            "triple_rank": rank + 1,
        })
    return results


# ------------------------------------------------------
# Reciprocal Rank Fusion
# ------------------------------------------------------

def reciprocal_rank_fusion(
    semantic: List[Dict],
    lexical: List[Dict],
    triples: List[Dict],
) -> Dict[str, Dict]:
    """
    Combine results from multiple channels using RRF.
    
    RRF score = sum over channels of: weight / (k + rank)
    
    This is more robust than score-based fusion as it doesn't
    require score normalization across different scales.
    """
    by_chunk: Dict[str, Dict] = {}
    
    def add_channel(items: List[Dict], rank_key: str, weight: float):
        for item in items:
            cid = str(item.get("chunk_id"))
            if not cid:
                continue
            
            if cid not in by_chunk:
                by_chunk[cid] = {
                    "chunk_id": cid,
                    "pdf_id": item.get("pdf_id"),
                    "page": item.get("page"),
                    "chunk_index": item.get("chunk_index"),
                    "text": item.get("text"),
                    "parent_text": item.get("parent_text"),
                    "rrf_score": 0.0,
                    "semantic_score": 0.0,
                    "semantic_rank": None,
                    "lexical_score": 0.0,
                    "lexical_rank": None,
                    "triple_score": 0.0,
                    "triple_rank": None,
                    "channels": [],
                }
            
            # Copy all fields from item
            for k, v in item.items():
                if k not in ("rrf_score", "channels") and v is not None:
                    by_chunk[cid][k] = v
            
            # Calculate RRF contribution
            rank = item.get(rank_key)
            if rank:
                rrf_contribution = weight / (RRF_K + rank)
                by_chunk[cid]["rrf_score"] += rrf_contribution
                by_chunk[cid]["channels"].append(rank_key.replace("_rank", ""))
    
    # Add each channel with its weight
    add_channel(semantic, "semantic_rank", SEMANTIC_WEIGHT)
    add_channel(lexical, "lexical_rank", LEXICAL_WEIGHT)
    add_channel(triples, "triple_rank", TRIPLE_WEIGHT)
    
    return by_chunk


# ------------------------------------------------------
# Cross-Encoder Reranking
# ------------------------------------------------------

def rerank_with_cross_encoder(
    query: str,
    candidates: List[Dict],
    top_k: int = RERANK_TOP_K,
) -> List[Dict]:
    """
    Rerank top candidates using cross-encoder for better accuracy.
    
    Cross-encoders are more accurate than bi-encoders because they
    process query and document together, capturing interactions.
    """
    if not candidates or not USE_CROSS_ENCODER:
        return candidates
    
    cross_encoder = _get_cross_encoder()
    if not cross_encoder:
        return candidates
    
    # Only rerank top candidates
    to_rerank = candidates[:top_k]
    remaining = candidates[top_k:]
    
    # Prepare pairs for cross-encoder
    pairs = []
    for c in to_rerank:
        # Use parent text if available for more context
        doc_text = c.get("parent_text") or c.get("text") or ""
        pairs.append([query, doc_text[:512]])  # Truncate to max length
    
    try:
        scores = cross_encoder.predict(pairs)
        
        # Update scores
        for i, c in enumerate(to_rerank):
            c["rerank_score"] = float(scores[i])
        
        # Sort by rerank score
        to_rerank.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
        
        # Combine reranked with remaining
        return to_rerank + remaining
        
    except Exception as e:
        logger.warning(f"Cross-encoder reranking failed: {e}")
        return candidates


# ------------------------------------------------------
# Main Fusion Function
# ------------------------------------------------------

def _deduplicate_by_page(results: List[Dict]) -> List[Dict]:
    """
    Deduplicate results by (pdf_id, page).
    
    When multiple chunks from the same page match, keep only the one
    with the highest fusion score. This prevents showing the same
    content multiple times (e.g., parent and child chunks).
    """
    by_page: Dict[str, Dict] = {}
    
    for r in results:
        key = f"{r.get('pdf_id')}:{r.get('page')}"
        
        if key not in by_page:
            by_page[key] = r
        else:
            existing = by_page[key]
            # Keep the one with higher fusion score
            if r.get("fusion_score", 0) > existing.get("fusion_score", 0):
                by_page[key] = r
            else:
                # Merge channel information from the duplicate
                existing_channels = set(existing.get("channels", []))
                new_channels = set(r.get("channels", []))
                existing["channels"] = list(existing_channels | new_channels)
                
                # Keep the better scores from each channel
                for score_key in ("semantic_score", "lexical_score", "triple_score"):
                    existing[score_key] = max(
                        existing.get(score_key, 0) or 0,
                        r.get(score_key, 0) or 0
                    )
    
    return list(by_page.values())


def fuse_results(
    semantic: List[Dict],
    lexical: List[Dict],
    triples: List[Dict],
    limit: int,
    query: str = "",
) -> List[Dict]:
    """
    Fuse results from all channels using RRF and optionally rerank.
    
    Returns fused results with scores and metadata.
    """
    # Combine with RRF
    by_chunk = reciprocal_rank_fusion(semantic, lexical, triples)
    
    # Convert to list and sort by RRF score
    fused = list(by_chunk.values())
    fused.sort(key=lambda x: x.get("rrf_score", 0), reverse=True)
    
    # Apply cross-encoder reranking to top candidates
    if query and USE_CROSS_ENCODER:
        fused = rerank_with_cross_encoder(query, fused)
    
    # Compute final fusion score
    # Priority: exact lexical matches > combined RRF + rerank
    for r in fused:
        rrf = r.get("rrf_score", 0)
        lexical_score = r.get("lexical_score", 0)
        rerank = r.get("rerank_score")
        
        # Base score from RRF (already in [0, ~0.1] range typically)
        # Normalize RRF to roughly [0, 1] by multiplying by 10
        base_score = rrf * 10
        
        # Boost for exact lexical matches (lexical_score >= 1.0 means exact phrase match)
        if lexical_score >= 1.0:
            base_score += 2.0  # Strong boost for exact matches
        elif lexical_score > 0:
            base_score += lexical_score * 0.5
        
        # Add rerank contribution if available
        # Cross-encoder ms-marco outputs roughly [-10, +10] range
        # Normalize to [-0.5, +0.5] and add as adjustment
        if rerank is not None:
            # Sigmoid normalization: maps (-inf, +inf) to (0, 1)
            import math
            rerank_normalized = 1 / (1 + math.exp(-rerank / 3))  # Scale factor of 3
            base_score += rerank_normalized * 0.5
        
        r["fusion_score"] = base_score
    
    # Sort by final fusion score
    fused.sort(key=lambda x: x.get("fusion_score", 0), reverse=True)
    
    # Deduplicate by page - keep only the best result per page
    fused = _deduplicate_by_page(fused)
    
    # Re-sort after deduplication
    fused.sort(key=lambda x: x.get("fusion_score", 0), reverse=True)
    
    # Normalize fusion scores to [0, 1] for confidence display
    max_score = max((r.get("fusion_score", 0) for r in fused), default=1.0)
    if max_score > 0:
        for r in fused:
            r["fusion_score"] = r["fusion_score"] / max_score
    
    # Extract snippets and highlights
    for r in fused[:limit]:
        r["snippet"] = _extract_snippet(
            r.get("parent_text") or r.get("text", ""),
            query
        )
        r["highlights"] = _highlight_matches(
            r.get("text", ""),
            query
        )
    
    return fused[:limit]
