import time
import uuid
import re
import numpy as np
from typing import Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sentence_transformers.util import cos_sim

from app.database import get_db
from app.dependencies import get_current_user
from app.models import PDFMetadata
from app.models.search_history import SearchHistory
from app.models.user import User
from app.schemas import ApiResponse

from app.services.embeddings.embedder import embed_query
from app.services.search.fusion import (
    semantic_channel,
    lexical_channel,
    triple_channel,
    fuse_results,
)
from app.services.search.utils import split_query_sentences

router = APIRouter(prefix="/search", tags=["Search"])

_SENT_SPLIT = re.compile(r'(?<=[.!?])\s+')
_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")

_STOPWORDS = {
    "the","is","are","was","were","of","on","in","for","to",
    "with","using","use","based","by","and","or","from"
}

def tokens(text):
    return [
        t for t in _TOKEN_RE.findall(text.lower())
        if t not in _STOPWORDS and len(t) > 2
    ]


def lexical_sentence_score(sentence: str, query: str) -> float:
    s = set(tokens(sentence))
    q = set(tokens(query))
    if not q:
        return 0.0
    overlap = len(s & q) / len(q)
    if overlap >= 0.9:
        return 1.0
    if overlap >= 0.75:
        return 0.7
    if overlap >= 0.5:
        return 0.5
    return 0.0


async def best_sentence_score(text: str, query_vec):
    sents = [s.strip() for s in _SENT_SPLIT.split(text) if len(s.strip()) > 20]
    if not sents:
        return "", 0.0

    sent_vecs = await embed_query(sents)
    sims = cos_sim(np.array(query_vec), np.array(sent_vecs))[0]
    idx = int(np.argmax(sims))
    return sents[idx], float(sims[idx])


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(default=5, ge=1, le=50)


@router.post("", response_model=ApiResponse)
async def search_documents(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start = time.perf_counter()

    docs = (
        await db.execute(
            select(PDFMetadata).where(
                PDFMetadata.uploaded_by == current_user.id,
                PDFMetadata.status == "COMPLETED",
            )
        )
    ).scalars().all()

    if not docs:
        return ApiResponse(success=True, data={"results": []})

    allowed_ids = [str(d.id) for d in docs]
    id_map = {str(d.id): d for d in docs}

    query_sents = split_query_sentences(request.query)

    # 🔒 CRITICAL: sentence-wise semantic fan-out, NO regression
    if len(query_sents) >= 2:
        query_vecs = await embed_query(query_sents)
    else:
        query_vecs = [await embed_query(request.query)]

    semantic_hits = []
    for qv in query_vecs:
        semantic_hits.extend(
            semantic_channel(qv, allowed_ids, request.query)
        )

    lexical_hits = await lexical_channel(
        db, request.query, [uuid.UUID(i) for i in allowed_ids]
    )

    triple_hits = await triple_channel(
        db, request.query, [uuid.UUID(i) for i in allowed_ids]
    )

    fused = fuse_results(semantic_hits, lexical_hits, triple_hits)

    pages: Dict[int, list] = {}
    for h in fused:
        pages.setdefault(h["page"], []).append(h)

    candidates = []

    for page, hits in pages.items():
        for h in hits:
            text = h.get("text") or h.get("parent_text") or ""

            best_sent = ""
            best_sem = 0.0
            best_lex = 0.0

            # 🔒 sentence-aligned semantic + lexical
            for i, qv in enumerate(query_vecs):
                sent, sem = await best_sentence_score(text, qv)
                if sem > best_sem:
                    best_sem = sem
                    best_sent = sent

                if i < len(query_sents):
                    best_lex = max(
                        best_lex,
                        lexical_sentence_score(sent, query_sents[i])
                    )

            # 🔒 delayed guardrail, OIE can rescue
            if len(query_sents) >= 2:
                if best_sem < 0.4 and best_lex < 0.5 and not h.get("has_oie"):
                    continue

            oie = 1.0 if h.get("has_oie") else 0.0
            confidence = min(1.0, 0.55*best_sem + 0.35*best_lex + 0.10*oie)

            candidates.append({
                "documentId": h["pdf_id"],
                "documentName": id_map[h["pdf_id"]].filename,
                "pageNumber": page,
                "snippet": best_sent,
                "highlightTokens": list(set(tokens(best_sent)) & set(tokens(request.query)))[:8],
                "confidenceScore": int(confidence * 100),
                "hasOie": bool(h.get("has_oie")),
                "scores": {
                    "semantic": round(best_sem, 3),
                    "lexical": round(best_lex, 3),
                },
            })

    # 🔒 semantic fallback for long queries
    if len(query_sents) >= 2 and not candidates:
        for page, hits in pages.items():
            for h in hits:
                text = h.get("text") or h.get("parent_text") or ""
                sent, sem = await best_sentence_score(text, query_vecs[0])

                candidates.append({
                    "documentId": h["pdf_id"],
                    "documentName": id_map[h["pdf_id"]].filename,
                    "pageNumber": page,
                    "snippet": sent,
                    "highlightTokens": tokens(sent)[:8],
                    "confidenceScore": int(min(1.0, sem) * 100),
                    "hasOie": bool(h.get("has_oie")),
                    "scores": {
                        "semantic": round(sem, 3),
                        "lexical": 0.0,
                    },
                })

    candidates.sort(key=lambda x: x["confidenceScore"], reverse=True)

    db.add(SearchHistory(
        user_id=current_user.id,
        query=request.query[:500]
    ))
    await db.commit()

    return ApiResponse(
        success=True,
        data={
            "results": candidates[:request.limit],
            "totalResults": len(candidates),
            "searchTime": round(time.perf_counter() - start, 3),
        },
    )
