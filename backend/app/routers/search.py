import time
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


router = APIRouter(prefix="/search", tags=["Search"])


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    documentIds: Optional[List[str]] = None
    limit: int = Field(default=5, ge=1, le=50)


class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class TextHighlight(BaseModel):
    text: str
    startOffset: int
    endOffset: int
    boundingBox: Optional[BoundingBox] = None


class SearchResult(BaseModel):
    documentId: str
    documentName: str
    pageNumber: int
    snippet: str
    confidenceScore: float
    highlights: List[TextHighlight]
    scores: dict


class SearchResponse(BaseModel):
    results: List[SearchResult]
    totalResults: int
    searchTime: float


@router.post("", response_model=ApiResponse)
async def search_documents(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start = time.perf_counter()

    # Resolve the set of documents this user can search
    doc_query = select(PDFMetadata).where(PDFMetadata.uploaded_by == current_user.id)

    if request.documentIds:
        try:
            requested_ids = [uuid.UUID(did) for did in request.documentIds]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid documentIds")
        doc_query = doc_query.where(PDFMetadata.id.in_(requested_ids))

    result = await db.execute(doc_query)
    docs = result.scalars().all()

    if not docs:
        raise HTTPException(status_code=404, detail="No documents available for this user")

    allowed_ids = [str(doc.id) for doc in docs]
    id_to_name = {str(doc.id): doc.filename for doc in docs}

    # Embed query
    query_vector = await embed_query(request.query)

    # Channel searches
    semantic_hits = semantic_channel(query_vector, allowed_ids)
    lexical_hits = await lexical_channel(db, request.query, [uuid.UUID(pid) for pid in allowed_ids])
    triple_hits = await triple_channel(db, request.query, [uuid.UUID(pid) for pid in allowed_ids])

    fused = fuse_results(semantic_hits, lexical_hits, triple_hits, request.limit)

    results: List[SearchResult] = []
    for h in fused:
        pdf_id = h.get("pdf_id")
        if pdf_id not in id_to_name:
            continue

        parent_text = h.get("parent_text") or ""
        child_text = h.get("text") or ""
        snippet_source = parent_text if parent_text else child_text
        snippet = snippet_source[:300]

        fusion_score = float(h.get("fusion_score") or 0.0)
        semantic_score = float(h.get("semantic_score") or 0.0)
        lexical_score = float(h.get("lexical_score") or 0.0)
        triple_score = float(h.get("triple_score") or 0.0)

        results.append(
            SearchResult(
                documentId=pdf_id,
                documentName=id_to_name[pdf_id],
                pageNumber=h.get("page") or 0,
                snippet=snippet,
                confidenceScore=max(0.0, min(100.0, fusion_score * 100.0)),
                highlights=[],
                scores={
                    "fusion": fusion_score,
                    "semantic": semantic_score,
                    "lexical": lexical_score,
                    "triple": triple_score,
                },
            )
        )

    results.sort(key=lambda r: r.confidenceScore, reverse=True)

    duration = time.perf_counter() - start

    # Persist search history (best effort)
    history = SearchHistory(user_id=current_user.id, query=request.query)
    db.add(history)
    await db.commit()

    return ApiResponse(
        success=True,
        data=SearchResponse(
            results=results,
            totalResults=len(results),
            searchTime=duration,
        ),
        message=None,
    )