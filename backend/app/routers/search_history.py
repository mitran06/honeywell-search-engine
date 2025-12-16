from uuid import UUID
from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.search_history import SearchHistory


router = APIRouter(prefix="/search", tags=["search-history"])


class SearchHistoryItem(BaseModel):
    id: str
    query: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class SearchHistoryResponse(BaseModel):
    success: bool
    data: List[SearchHistoryItem]


class AddSearchRequest(BaseModel):
    query: str


@router.get("/history", response_model=SearchHistoryResponse)
async def get_search_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 10,
):
    """Get recent search history for the current user."""
    result = await db.execute(
        select(SearchHistory)
        .where(SearchHistory.user_id == current_user.id)
        .order_by(SearchHistory.created_at.desc())
        .limit(limit)
    )
    history = result.scalars().all()
    
    return {
        "success": True,
        "data": [
            SearchHistoryItem(
                id=str(h.id),
                query=h.query,
                created_at=h.created_at,
            )
            for h in history
        ],
    }


@router.post("/history", status_code=status.HTTP_201_CREATED)
async def add_search_history(
    request: AddSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a search query to history."""
    # Check if same query exists recently, avoid duplicates
    existing = await db.execute(
        select(SearchHistory)
        .where(SearchHistory.user_id == current_user.id)
        .where(SearchHistory.query == request.query)
        .order_by(SearchHistory.created_at.desc())
        .limit(1)
    )
    existing_item = existing.scalar_one_or_none()
    
    if existing_item:
        # Update timestamp instead of creating duplicate
        existing_item.created_at = datetime.utcnow()
        await db.commit()
    else:
        # Create new entry
        history_item = SearchHistory(
            user_id=current_user.id,
            query=request.query,
        )
        db.add(history_item)
        await db.commit()
    
    return {"success": True, "message": "Search added to history"}


@router.delete("/history/{history_id}")
async def delete_search_history(
    history_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a search history item."""
    result = await db.execute(
        select(SearchHistory)
        .where(SearchHistory.id == history_id)
        .where(SearchHistory.user_id == current_user.id)
    )
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="History item not found",
        )
    
    await db.delete(item)
    await db.commit()
    
    return {"success": True, "message": "History item deleted"}


@router.delete("/history")
async def clear_search_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clear all search history for the current user."""
    await db.execute(
        delete(SearchHistory).where(SearchHistory.user_id == current_user.id)
    )
    await db.commit()
    
    return {"success": True, "message": "Search history cleared"}
