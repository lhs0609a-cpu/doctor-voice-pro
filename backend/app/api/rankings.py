"""
플레이스 검색 순위 추적 API
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.ranking_service import RankingService

router = APIRouter()
ranking_service = RankingService()


# ==================== Schemas ====================

class KeywordAddRequest(BaseModel):
    place_db_id: str
    keyword: str
    category: Optional[str] = None
    priority: int = 0


class RankingCheckRequest(BaseModel):
    keyword_id: str
    rank: Optional[int] = None
    total_results: int = 0
    top_competitors: Optional[List[dict]] = None


class KeywordResponse(BaseModel):
    id: str
    keyword: str
    category: Optional[str]
    current_rank: Optional[int]
    rank_change: int
    trend: str
    best_rank: Optional[int]
    worst_rank: Optional[int]
    is_active: bool
    last_checked_at: Optional[str]

    class Config:
        from_attributes = True


# ==================== Routes ====================

@router.get("/keywords", response_model=List[dict])
async def get_keywords(
    place_db_id: Optional[str] = None,
    is_active: Optional[bool] = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """추적 키워드 목록 조회"""
    keywords = await ranking_service.get_keywords(
        db=db,
        user_id=str(current_user.id),
        place_db_id=place_db_id,
        is_active=is_active,
    )

    return [
        {
            "id": str(kw.id),
            "keyword": kw.keyword,
            "category": kw.category,
            "priority": kw.priority,
            "current_rank": kw.current_rank,
            "rank_change": kw.rank_change or 0,
            "trend": kw.trend or "stable",
            "best_rank": kw.best_rank,
            "worst_rank": kw.worst_rank,
            "estimated_search_volume": kw.estimated_search_volume or 0,
            "competition_level": kw.competition_level,
            "is_active": kw.is_active,
            "check_frequency": kw.check_frequency,
            "last_checked_at": kw.last_checked_at.isoformat() if kw.last_checked_at else None,
            "created_at": kw.created_at.isoformat(),
        }
        for kw in keywords
    ]


@router.post("/keywords", response_model=dict)
async def add_keyword(
    request: KeywordAddRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """추적 키워드 추가"""
    keyword = await ranking_service.add_keyword(
        db=db,
        user_id=str(current_user.id),
        place_db_id=request.place_db_id,
        keyword=request.keyword,
        category=request.category,
        priority=request.priority,
    )

    return {
        "id": str(keyword.id),
        "keyword": keyword.keyword,
        "message": "Keyword added successfully",
    }


@router.delete("/keywords/{keyword_id}", response_model=dict)
async def remove_keyword(
    keyword_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """추적 키워드 제거"""
    success = await ranking_service.remove_keyword(
        db=db,
        keyword_id=keyword_id,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Keyword not found")

    return {"message": "Keyword removed successfully"}


@router.get("/history/{keyword_id}", response_model=List[dict])
async def get_ranking_history(
    keyword_id: str,
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """순위 히스토리 조회"""
    history = await ranking_service.get_ranking_history(
        db=db,
        keyword_id=keyword_id,
        days=days,
    )

    return [
        {
            "id": str(r.id),
            "rank": r.rank,
            "total_results": r.total_results,
            "top_competitors": r.top_competitors or [],
            "checked_at": r.checked_at.isoformat(),
        }
        for r in history
    ]


@router.get("/current", response_model=List[dict])
async def get_current_rankings(
    place_db_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """현재 순위 조회"""
    rankings = await ranking_service.get_current_rankings(
        db=db,
        user_id=str(current_user.id),
        place_db_id=place_db_id,
    )

    return rankings


@router.post("/check", response_model=dict)
async def check_ranking(
    request: RankingCheckRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """순위 즉시 체크"""
    ranking = await ranking_service.check_ranking(
        db=db,
        keyword_id=request.keyword_id,
        rank=request.rank,
        total_results=request.total_results,
        top_competitors=request.top_competitors,
    )

    return {
        "id": str(ranking.id),
        "rank": ranking.rank,
        "total_results": ranking.total_results,
        "checked_at": ranking.checked_at.isoformat(),
        "message": "Ranking checked successfully",
    }


@router.get("/recommendations", response_model=List[dict])
async def get_recommendations(
    place_db_id: str = Query(...),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """키워드 추천"""
    recommendations = await ranking_service.get_recommendations(
        db=db,
        user_id=str(current_user.id),
        place_db_id=place_db_id,
        limit=limit,
    )

    return recommendations


@router.get("/summary", response_model=dict)
async def get_summary(
    place_db_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """순위 요약 조회"""
    summary = await ranking_service.get_summary(
        db=db,
        user_id=str(current_user.id),
        place_db_id=place_db_id,
    )

    return summary


@router.get("/alerts", response_model=List[dict])
async def get_alerts(
    unread_only: bool = False,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """순위 변동 알림 조회"""
    alerts = await ranking_service.get_alerts(
        db=db,
        user_id=str(current_user.id),
        unread_only=unread_only,
        limit=limit,
    )

    return [
        {
            "id": str(a.id),
            "keyword_id": str(a.keyword_id),
            "alert_type": a.alert_type,
            "previous_rank": a.previous_rank,
            "current_rank": a.current_rank,
            "change": a.change,
            "message": a.message,
            "is_read": a.is_read,
            "created_at": a.created_at.isoformat(),
        }
        for a in alerts
    ]
