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


@router.post("", response_model=ApiResponse)
async def search_documents(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    print(">>> SEARCH ENDPOINT HIT")
    print("QUERY =", request.query)
    print("USER =", current_user.id)

    start = time.perf_counter()

    doc_query = select(PDFMetadata).where(
        PDFMetadata.uploaded_by == current_user.id,
        PDFMetadata.status == "COMPLETED",
    )

    result = await db.execute(doc_query)
    docs = result.scalars().all()

    print("DOC COUNT =", len(docs))

    if not docs:
        return ApiResponse(
            success=True,
            data={
                "results": [],
                "totalResults": 0,
                "searchTime": 0.0,
            },
            message=None,
        )

    allowed_ids = [str(doc.id) for doc in docs]
    id_to_name = {str(doc.id): doc.filename for doc in docs}

    query_vector = await embed_query(request.query)

    semantic_hits = semantic_channel(query_vector, allowed_ids)
    lexical_hits = await lexical_channel(
        db, request.query, [uuid.UUID(pid) for pid in allowed_ids]
    )
    triple_hits = await triple_channel(
        db, request.query, [uuid.UUID(pid) for pid in allowed_ids]
    )

    fused = fuse_results(
        semantic_hits,
        lexical_hits,
        triple_hits,
        request.limit,
        query=request.query,
    )

    results = []
    for h in fused:
        pdf_id = h.get("pdf_id")
        if pdf_id not in id_to_name:
            continue

        results.append(
            {
                "documentId": pdf_id,
                "documentName": id_to_name[pdf_id],
                "pageNumber": h.get("page") or 0,
                "snippet": h.get("snippet") or "",
                "confidenceScore": max(0.0, min(100.0, (h.get("fusion_score") or 0) * 100)),
                "scores": {
                    "fusion": h.get("fusion_score", 0),
                    "semantic": h.get("semantic_score", 0),
                    "lexical": h.get("lexical_score", 0),
                    "triple": h.get("triple_score", 0),
                },
            }
        )

    duration = time.perf_counter() - start

    db.add(SearchHistory(user_id=current_user.id, query=request.query))
    await db.commit()

    return ApiResponse(
        success=True,
        data={
            "results": results,
            "totalResults": len(results),
            "searchTime": duration,
        },
        message=None,
    )
