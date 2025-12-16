"""
ROI 트래커 API
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import date
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.roi_tracker import EventType
from app.services.roi_service import ROIService

router = APIRouter()
roi_service = ROIService()


# ==================== Schemas ====================

class EventCreateRequest(BaseModel):
    event_type: EventType
    event_date: str = Field(..., description="YYYY-MM-DD 형식")
    keyword: Optional[str] = None
    post_id: Optional[str] = None
    source: Optional[str] = None
    channel: Optional[str] = None
    revenue: Optional[int] = None
    cost: Optional[int] = None
    customer_id: Optional[str] = None
    notes: Optional[str] = None


class BulkEventCreateRequest(BaseModel):
    events: List[EventCreateRequest]


class MarketingCostRequest(BaseModel):
    date: str = Field(..., description="YYYY-MM-DD 형식")
    channel: str
    cost: int
    description: Optional[str] = None
    cost_type: Optional[str] = None
    campaign_name: Optional[str] = None


class EventResponse(BaseModel):
    id: str
    event_type: str
    event_date: str
    keyword: Optional[str]
    source: Optional[str]
    channel: Optional[str]
    revenue: Optional[int]
    cost: Optional[int]
    created_at: str

    class Config:
        from_attributes = True


class FunnelStageResponse(BaseModel):
    name: str
    count: int
    rate: float


class DashboardResponse(BaseModel):
    period: dict
    stats: dict
    channel_breakdown: List[dict]
    source_breakdown: List[dict]
    daily_trend: List[dict]
    funnel: dict
    top_keywords: List[dict]
    roi_percentage: float


# ==================== Helper Functions ====================

def _parse_date(date_str: str) -> date:
    """날짜 문자열 파싱"""
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")


# ==================== Routes ====================

@router.post("/events", response_model=dict)
async def create_event(
    request: EventCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """전환 이벤트 기록"""
    event_date = _parse_date(request.event_date)

    event = await roi_service.create_event(
        db=db,
        user_id=str(current_user.id),
        event_type=request.event_type,
        event_date=event_date,
        keyword=request.keyword,
        post_id=request.post_id,
        source=request.source,
        channel=request.channel,
        revenue=request.revenue,
        cost=request.cost,
        customer_id=request.customer_id,
        notes=request.notes,
    )

    return {
        "id": str(event.id),
        "event_type": event.event_type.value,
        "event_date": event.event_date.isoformat(),
        "message": "Event created successfully",
    }


@router.post("/events/bulk", response_model=dict)
async def create_bulk_events(
    request: BulkEventCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """여러 전환 이벤트 일괄 기록"""
    events_data = []
    for event in request.events:
        events_data.append({
            "event_type": event.event_type,
            "event_date": _parse_date(event.event_date),
            "keyword": event.keyword,
            "post_id": event.post_id,
            "source": event.source,
            "channel": event.channel,
            "revenue": event.revenue,
            "cost": event.cost,
            "customer_id": event.customer_id,
            "notes": event.notes,
        })

    created = await roi_service.create_bulk_events(
        db=db,
        user_id=str(current_user.id),
        events=events_data,
    )

    return {
        "created_count": len(created),
        "message": "Events created successfully",
    }


@router.get("/events", response_model=List[dict])
async def get_events(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    event_type: Optional[EventType] = None,
    source: Optional[str] = None,
    channel: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """전환 이벤트 조회"""
    events = await roi_service.get_events(
        db=db,
        user_id=str(current_user.id),
        start_date=_parse_date(start_date) if start_date else None,
        end_date=_parse_date(end_date) if end_date else None,
        event_type=event_type,
        source=source,
        channel=channel,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )

    return [
        {
            "id": str(e.id),
            "event_type": e.event_type.value,
            "event_date": e.event_date.isoformat(),
            "keyword": e.keyword,
            "source": e.source,
            "channel": e.channel,
            "revenue": e.revenue,
            "cost": e.cost,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ROI 대시보드 데이터"""
    dashboard = await roi_service.get_dashboard(
        db=db,
        user_id=str(current_user.id),
        start_date=_parse_date(start_date) if start_date else None,
        end_date=_parse_date(end_date) if end_date else None,
    )

    return dashboard


@router.get("/keywords", response_model=List[dict])
async def get_keyword_roi(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """키워드별 ROI 분석"""
    keywords = await roi_service.get_keyword_roi(
        db=db,
        user_id=str(current_user.id),
        start_date=_parse_date(start_date) if start_date else None,
        end_date=_parse_date(end_date) if end_date else None,
        limit=limit,
    )

    return keywords


@router.get("/funnel", response_model=dict)
async def get_funnel(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """전환 퍼널 분석"""
    dashboard = await roi_service.get_dashboard(
        db=db,
        user_id=str(current_user.id),
        start_date=_parse_date(start_date) if start_date else None,
        end_date=_parse_date(end_date) if end_date else None,
    )

    return dashboard["funnel"]


@router.get("/trends", response_model=List[dict])
async def get_trends(
    months: int = Query(6, ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """월별 트렌드 분석"""
    trends = await roi_service.get_trends(
        db=db,
        user_id=str(current_user.id),
        months=months,
    )

    return trends


@router.post("/costs", response_model=dict)
async def add_marketing_cost(
    request: MarketingCostRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """마케팅 비용 기록"""
    cost_date = _parse_date(request.date)

    cost = await roi_service.add_marketing_cost(
        db=db,
        user_id=str(current_user.id),
        cost_date=cost_date,
        channel=request.channel,
        cost=request.cost,
        description=request.description,
        cost_type=request.cost_type,
        campaign_name=request.campaign_name,
    )

    return {
        "id": str(cost.id),
        "date": cost.date.isoformat(),
        "channel": cost.channel,
        "cost": cost.cost,
        "message": "Marketing cost added successfully",
    }


@router.get("/costs", response_model=List[dict])
async def get_marketing_costs(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """마케팅 비용 조회"""
    costs = await roi_service.get_marketing_costs(
        db=db,
        user_id=str(current_user.id),
        start_date=_parse_date(start_date) if start_date else None,
        end_date=_parse_date(end_date) if end_date else None,
    )

    return [
        {
            "id": str(c.id),
            "date": c.date.isoformat(),
            "channel": c.channel,
            "cost": c.cost,
            "description": c.description,
            "cost_type": c.cost_type,
            "campaign_name": c.campaign_name,
        }
        for c in costs
    ]


@router.post("/calculate", response_model=dict)
async def calculate_monthly_summary(
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """월별 ROI 요약 계산"""
    summary = await roi_service.calculate_monthly_summary(
        db=db,
        user_id=str(current_user.id),
        year=year,
        month=month,
    )

    return {
        "id": str(summary.id),
        "year": summary.year,
        "month": summary.month,
        "roi_percentage": summary.roi_percentage,
        "total_revenue": summary.total_revenue,
        "total_cost": summary.total_cost,
        "calculated_at": summary.calculated_at.isoformat(),
    }
