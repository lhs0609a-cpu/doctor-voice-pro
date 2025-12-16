"""
플레이스 리뷰 관리 API
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import date
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.place_review import Sentiment
from app.services.review_service import ReviewService

router = APIRouter()
review_service = ReviewService()


# ==================== Schemas ====================

class ReplyRequest(BaseModel):
    reply_content: str


class GenerateReplyRequest(BaseModel):
    tone: str = Field("professional", description="professional, friendly, empathetic")


class AlertSettingsRequest(BaseModel):
    place_db_id: str
    alert_type: str
    is_active: bool = True
    channels: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    rating_threshold: int = 3


class TemplateCreateRequest(BaseModel):
    name: str
    template_content: str
    sentiment_type: Optional[Sentiment] = None
    category: Optional[str] = None
    variables: Optional[List[str]] = None


class ReviewResponse(BaseModel):
    id: str
    review_id: str
    author_name: Optional[str]
    rating: Optional[int]
    content: Optional[str]
    sentiment: Optional[str]
    sentiment_score: float
    is_replied: bool
    reply_content: Optional[str]
    is_urgent: bool
    written_at: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


# ==================== Helper Functions ====================

def _parse_date(date_str: str) -> date:
    """날짜 문자열 파싱"""
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")


# ==================== Routes ====================

@router.get("/", response_model=List[dict])
async def get_reviews(
    place_db_id: str = Query(...),
    sentiment: Optional[Sentiment] = None,
    is_replied: Optional[bool] = None,
    is_urgent: Optional[bool] = None,
    min_rating: Optional[int] = Query(None, ge=1, le=5),
    max_rating: Optional[int] = Query(None, ge=1, le=5),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """리뷰 목록 조회"""
    reviews = await review_service.get_reviews(
        db=db,
        place_db_id=place_db_id,
        sentiment=sentiment,
        is_replied=is_replied,
        is_urgent=is_urgent,
        min_rating=min_rating,
        max_rating=max_rating,
        start_date=_parse_date(start_date) if start_date else None,
        end_date=_parse_date(end_date) if end_date else None,
        search=search,
        limit=limit,
        offset=offset,
    )

    return [
        {
            "id": str(r.id),
            "review_id": r.review_id,
            "author_name": r.author_name,
            "rating": r.rating,
            "content": r.content,
            "images": r.images or [],
            "sentiment": r.sentiment.value if r.sentiment else None,
            "sentiment_score": r.sentiment_score or 0,
            "keywords": r.keywords or [],
            "is_replied": r.is_replied,
            "reply_content": r.reply_content,
            "replied_at": r.replied_at.isoformat() if r.replied_at else None,
            "is_urgent": r.is_urgent,
            "needs_attention": r.needs_attention,
            "review_type": r.review_type,
            "visit_date": r.visit_date.isoformat() if r.visit_date else None,
            "written_at": r.written_at.isoformat() if r.written_at else None,
            "created_at": r.created_at.isoformat(),
        }
        for r in reviews
    ]


@router.get("/{review_db_id}", response_model=dict)
async def get_review(
    review_db_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """리뷰 상세 조회"""
    review = await review_service.get_review(
        db=db,
        review_db_id=review_db_id,
    )

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    return {
        "id": str(review.id),
        "review_id": review.review_id,
        "author_name": review.author_name,
        "rating": review.rating,
        "content": review.content,
        "images": review.images or [],
        "sentiment": review.sentiment.value if review.sentiment else None,
        "sentiment_score": review.sentiment_score or 0,
        "keywords": review.keywords or [],
        "topics": review.topics or [],
        "is_replied": review.is_replied,
        "reply_content": review.reply_content,
        "replied_at": review.replied_at.isoformat() if review.replied_at else None,
        "reply_by": review.reply_by,
        "is_urgent": review.is_urgent,
        "needs_attention": review.needs_attention,
        "review_type": review.review_type,
        "visit_date": review.visit_date.isoformat() if review.visit_date else None,
        "written_at": review.written_at.isoformat() if review.written_at else None,
        "created_at": review.created_at.isoformat(),
    }


@router.post("/{review_db_id}/reply", response_model=dict)
async def reply_to_review(
    review_db_id: str,
    request: ReplyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """리뷰 답변 등록"""
    try:
        review = await review_service.reply_to_review(
            db=db,
            review_db_id=review_db_id,
            reply_content=request.reply_content,
            reply_by=current_user.name or current_user.email,
        )

        return {
            "id": str(review.id),
            "is_replied": review.is_replied,
            "reply_content": review.reply_content,
            "replied_at": review.replied_at.isoformat() if review.replied_at else None,
            "message": "Reply submitted successfully",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{review_db_id}/generate-reply", response_model=dict)
async def generate_reply(
    review_db_id: str,
    request: GenerateReplyRequest = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 답변 생성"""
    if request is None:
        request = GenerateReplyRequest()

    try:
        generated = await review_service.generate_reply(
            db=db,
            review_db_id=review_db_id,
            user_id=str(current_user.id),
            tone=request.tone,
        )

        return {
            "id": str(generated.id),
            "generated_content": generated.generated_content,
            "tone": generated.tone,
            "message": "Reply generated successfully",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/analytics/summary", response_model=dict)
async def get_analytics(
    place_db_id: str = Query(...),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """리뷰 분석 통계"""
    analytics = await review_service.get_analytics(
        db=db,
        place_db_id=place_db_id,
        start_date=_parse_date(start_date) if start_date else None,
        end_date=_parse_date(end_date) if end_date else None,
    )

    return analytics


@router.get("/alerts/settings", response_model=List[dict])
async def get_alert_settings(
    place_db_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """알림 설정 조회"""
    alerts = await review_service.get_alert_settings(
        db=db,
        user_id=str(current_user.id),
        place_db_id=place_db_id,
    )

    return [
        {
            "id": str(a.id),
            "place_id": str(a.place_id) if a.place_id else None,
            "alert_type": a.alert_type,
            "channels": a.channels or [],
            "keywords": a.keywords or [],
            "rating_threshold": a.rating_threshold,
            "is_active": a.is_active,
        }
        for a in alerts
    ]


@router.put("/alerts/settings", response_model=dict)
async def update_alert_settings(
    request: AlertSettingsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """알림 설정 업데이트"""
    alert = await review_service.update_alert_settings(
        db=db,
        user_id=str(current_user.id),
        place_db_id=request.place_db_id,
        alert_type=request.alert_type,
        is_active=request.is_active,
        channels=request.channels,
        keywords=request.keywords,
        rating_threshold=request.rating_threshold,
    )

    return {
        "id": str(alert.id),
        "alert_type": alert.alert_type,
        "is_active": alert.is_active,
        "message": "Alert settings updated successfully",
    }


@router.get("/templates/list", response_model=List[dict])
async def get_templates(
    sentiment_type: Optional[Sentiment] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """답변 템플릿 조회"""
    templates = await review_service.get_templates(
        db=db,
        user_id=str(current_user.id),
        sentiment_type=sentiment_type,
    )

    return [
        {
            "id": str(t.id),
            "name": t.name,
            "sentiment_type": t.sentiment_type.value if t.sentiment_type else None,
            "category": t.category,
            "template_content": t.template_content,
            "variables": t.variables or [],
            "usage_count": t.usage_count,
            "is_default": t.is_default,
        }
        for t in templates
    ]


@router.post("/templates", response_model=dict)
async def create_template(
    request: TemplateCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """답변 템플릿 생성"""
    template = await review_service.create_template(
        db=db,
        user_id=str(current_user.id),
        name=request.name,
        template_content=request.template_content,
        sentiment_type=request.sentiment_type,
        category=request.category,
        variables=request.variables,
    )

    return {
        "id": str(template.id),
        "name": template.name,
        "message": "Template created successfully",
    }
