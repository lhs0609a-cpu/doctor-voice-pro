"""
경쟁 병원 분석 API
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.competitor_service import CompetitorService

router = APIRouter()
competitor_service = CompetitorService()


# ==================== Schemas ====================

class CompetitorAddRequest(BaseModel):
    place_id: str
    place_name: str
    place_url: Optional[str] = None
    category: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    distance_km: Optional[float] = None
    priority: int = 0
    notes: Optional[str] = None


class CompetitorResponse(BaseModel):
    id: str
    place_id: str
    place_name: str
    place_url: Optional[str]
    category: Optional[str]
    address: Optional[str]
    distance_km: Optional[float]
    review_count: int
    avg_rating: float
    is_active: bool
    priority: int
    created_at: str

    class Config:
        from_attributes = True


# ==================== Routes ====================

@router.get("/", response_model=List[dict])
async def get_competitors(
    is_active: Optional[bool] = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """경쟁사 목록 조회"""
    competitors = await competitor_service.get_competitors(
        db=db,
        user_id=str(current_user.id),
        is_active=is_active,
    )

    return [
        {
            "id": str(c.id),
            "place_id": c.place_id,
            "place_name": c.place_name,
            "place_url": c.place_url,
            "category": c.category,
            "address": c.address,
            "distance_km": c.distance_km,
            "review_count": c.review_count or 0,
            "avg_rating": c.avg_rating or 0,
            "visitor_review_count": c.visitor_review_count or 0,
            "blog_review_count": c.blog_review_count or 0,
            "is_active": c.is_active,
            "priority": c.priority,
            "is_auto_detected": c.is_auto_detected,
            "similarity_score": c.similarity_score or 0,
            "strengths": c.strengths or [],
            "weaknesses": c.weaknesses or [],
            "notes": c.notes,
            "last_synced_at": c.last_synced_at.isoformat() if c.last_synced_at else None,
            "created_at": c.created_at.isoformat(),
        }
        for c in competitors
    ]


@router.post("/", response_model=dict)
async def add_competitor(
    request: CompetitorAddRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """경쟁사 추가"""
    competitor = await competitor_service.add_competitor(
        db=db,
        user_id=str(current_user.id),
        place_id=request.place_id,
        place_name=request.place_name,
        place_url=request.place_url,
        category=request.category,
        address=request.address,
        phone=request.phone,
        distance_km=request.distance_km,
        priority=request.priority,
        notes=request.notes,
    )

    return {
        "id": str(competitor.id),
        "place_id": competitor.place_id,
        "place_name": competitor.place_name,
        "message": "Competitor added successfully",
    }


@router.delete("/{competitor_id}", response_model=dict)
async def remove_competitor(
    competitor_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """경쟁사 제거"""
    success = await competitor_service.remove_competitor(
        db=db,
        competitor_id=competitor_id,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Competitor not found")

    return {"message": "Competitor removed successfully"}


@router.get("/{competitor_id}", response_model=dict)
async def get_competitor(
    competitor_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """경쟁사 상세 조회"""
    competitor = await competitor_service.get_competitor(
        db=db,
        competitor_id=competitor_id,
    )

    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    return {
        "id": str(competitor.id),
        "place_id": competitor.place_id,
        "place_name": competitor.place_name,
        "place_url": competitor.place_url,
        "category": competitor.category,
        "address": competitor.address,
        "phone": competitor.phone,
        "distance_km": competitor.distance_km,
        "review_count": competitor.review_count or 0,
        "avg_rating": competitor.avg_rating or 0,
        "visitor_review_count": competitor.visitor_review_count or 0,
        "blog_review_count": competitor.blog_review_count or 0,
        "is_active": competitor.is_active,
        "priority": competitor.priority,
        "is_auto_detected": competitor.is_auto_detected,
        "detection_reason": competitor.detection_reason,
        "similarity_score": competitor.similarity_score or 0,
        "strengths": competitor.strengths or [],
        "weaknesses": competitor.weaknesses or [],
        "notes": competitor.notes,
        "snapshots_count": len(competitor.snapshots) if competitor.snapshots else 0,
        "alerts_count": len([a for a in competitor.alerts if not a.is_read]) if competitor.alerts else 0,
        "last_synced_at": competitor.last_synced_at.isoformat() if competitor.last_synced_at else None,
        "created_at": competitor.created_at.isoformat(),
    }


@router.post("/auto-detect", response_model=List[dict])
async def auto_detect_competitors(
    place_db_id: str = Query(...),
    radius_km: float = Query(3.0, ge=0.5, le=10.0),
    limit: int = Query(10, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """경쟁사 자동 탐지"""
    detected = await competitor_service.auto_detect_competitors(
        db=db,
        user_id=str(current_user.id),
        place_db_id=place_db_id,
        radius_km=radius_km,
        limit=limit,
    )

    return detected


@router.get("/comparison/summary", response_model=dict)
async def get_comparison(
    my_place_db_id: str = Query(...),
    competitor_ids: Optional[str] = Query(None, description="Comma-separated competitor IDs"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """경쟁사 비교 분석"""
    ids = competitor_ids.split(",") if competitor_ids else None

    comparison = await competitor_service.get_comparison(
        db=db,
        user_id=str(current_user.id),
        my_place_db_id=my_place_db_id,
        competitor_ids=ids,
    )

    if "error" in comparison:
        raise HTTPException(status_code=404, detail=comparison["error"])

    return comparison


@router.get("/{competitor_id}/reviews", response_model=dict)
async def get_competitor_reviews(
    competitor_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """경쟁사 리뷰 분석"""
    analysis = await competitor_service.get_competitor_reviews_analysis(
        db=db,
        competitor_id=competitor_id,
    )

    return analysis


@router.get("/report/weekly", response_model=dict)
async def get_weekly_report(
    week_start: Optional[str] = Query(None, description="YYYY-MM-DD (Monday)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """주간 경쟁 리포트 조회"""
    from datetime import date as date_type

    start_date = None
    if week_start:
        try:
            start_date = date_type.fromisoformat(week_start)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    report = await competitor_service.get_weekly_report(
        db=db,
        user_id=str(current_user.id),
        week_start=start_date,
    )

    if not report:
        return {"message": "No report available for this week"}

    return {
        "id": str(report.id),
        "week_start": report.week_start.isoformat(),
        "week_end": report.week_end.isoformat(),
        "year": report.year,
        "week_number": report.week_number,
        "summary": report.summary,
        "significant_changes": report.significant_changes or [],
        "my_stats": report.my_stats or {},
        "competitor_stats": report.competitor_stats or {},
        "action_items": report.action_items or [],
        "is_sent": report.is_sent,
        "generated_at": report.generated_at.isoformat() if report.generated_at else None,
    }


@router.post("/report/generate", response_model=dict)
async def generate_weekly_report(
    place_db_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """주간 경쟁 리포트 생성"""
    report = await competitor_service.generate_weekly_report(
        db=db,
        user_id=str(current_user.id),
        place_db_id=place_db_id,
    )

    return {
        "id": str(report.id),
        "week_start": report.week_start.isoformat(),
        "week_end": report.week_end.isoformat(),
        "summary": report.summary,
        "message": "Weekly report generated successfully",
    }


@router.get("/alerts/list", response_model=List[dict])
async def get_alerts(
    unread_only: bool = False,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """경쟁사 알림 조회"""
    alerts = await competitor_service.get_alerts(
        db=db,
        user_id=str(current_user.id),
        unread_only=unread_only,
        limit=limit,
    )

    return [
        {
            "id": str(a.id),
            "competitor_id": str(a.competitor_id),
            "alert_type": a.alert_type,
            "title": a.title,
            "message": a.message,
            "data": a.data or {},
            "severity": a.severity,
            "is_read": a.is_read,
            "created_at": a.created_at.isoformat(),
        }
        for a in alerts
    ]


@router.post("/alerts/{alert_id}/read", response_model=dict)
async def mark_alert_read(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """알림 읽음 처리"""
    success = await competitor_service.mark_alert_read(
        db=db,
        alert_id=alert_id,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")

    return {"message": "Alert marked as read"}
