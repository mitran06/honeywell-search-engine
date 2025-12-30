from typing import Dict, Sequence
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.qdrant.qdrant_search import semantic_search
from app.services.search.utils import split_query_sentences, extract_terms

SEMANTIC_K = 30
LEXICAL_K = 50
TRIPLE_K = 30


def semantic_channel(query_vector, pdf_ids, query):
    hits = semantic_search(query_vector, top_k=SEMANTIC_K, pdf_ids=pdf_ids)

    out = []
    for i, h in enumerate(hits):
        out.append({
            "chunk_id": h["chunk_id"],
            "parent_chunk_id": h.get("parent_chunk_id"),
            "pdf_id": h["pdf_id"],
            "page": h["page"],
            "chunk_index": h["chunk_index"],
            "text": h["text"],
            "parent_text": h.get("parent_text"),
            "semantic_rank": i + 1,
            "semantic_score": float(h["score"]),
            "has_semantic": True,
        })
    return out


async def lexical_channel(db: AsyncSession, query: str, pdf_ids: Sequence[UUID]):
    sql = text("""
        SELECT id, parent_chunk_id, pdf_metadata_id, page_num,
               chunk_index, chunk_text,
               ts_rank_cd(lexical_tsv, websearch_to_tsquery('english', :q)) AS score
        FROM pdf_chunks
        WHERE pdf_metadata_id = ANY(:ids)
          AND lexical_tsv @@ websearch_to_tsquery('english', :q)
        ORDER BY score DESC
        LIMIT :k
    """)

    rows = (await db.execute(
        sql, {"q": query, "ids": list(pdf_ids), "k": LEXICAL_K}
    )).fetchall()

    return [{
        "chunk_id": str(r.id),
        "parent_chunk_id": str(r.parent_chunk_id) if r.parent_chunk_id else None,
        "pdf_id": str(r.pdf_metadata_id),
        "page": r.page_num,
        "chunk_index": r.chunk_index,
        "text": r.chunk_text,
        "lexical_rank": i + 1,
        "lexical_score": float(r.score or 0),
        "has_lexical": True,
    } for i, r in enumerate(rows)]


async def triple_channel(db: AsyncSession, query: str, pdf_ids: Sequence[UUID]):
    sentences = split_query_sentences(query)
    if not sentences:
        return []

    terms = extract_terms(sentences)
    if not terms:
        return []

    tsq = " | ".join(terms)

    sql = text("""
        SELECT t.chunk_id, c.parent_chunk_id, t.pdf_metadata_id,
               t.page_num, t.chunk_index,
               c.chunk_text
        FROM pdf_triples t
        JOIN pdf_chunks c ON c.id = t.chunk_id
        WHERE t.pdf_metadata_id = ANY(:ids)
          AND t.triple_tsv @@ to_tsquery('english', :tsq)
        LIMIT :k
    """)

    rows = (await db.execute(
        sql, {"tsq": tsq, "ids": list(pdf_ids), "k": TRIPLE_K}
    )).fetchall()

    return [{
        "chunk_id": str(r.chunk_id),
        "parent_chunk_id": str(r.parent_chunk_id) if r.parent_chunk_id else None,
        "pdf_id": str(r.pdf_metadata_id),
        "page": r.page_num,
        "chunk_index": r.chunk_index,
        "text": r.chunk_text,
        "has_oie": True,
    } for r in rows]


def fuse_results(semantic, lexical, triples):
    by_parent: Dict[str, Dict] = {}

    def key(h):
        return h.get("parent_chunk_id") or h["chunk_id"]

    for group in (semantic, lexical, triples):
        for h in group:
            k = key(h)
            if k not in by_parent:
                by_parent[k] = {}
            by_parent[k].update(h)

    return list(by_parent.values())
