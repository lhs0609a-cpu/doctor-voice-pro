"""
리뷰 캠페인 관리 API
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import date
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.review_campaign import CampaignStatus, RewardType
from app.services.campaign_service import CampaignService

router = APIRouter()
campaign_service = CampaignService()


# ==================== Schemas ====================

class CampaignCreateRequest(BaseModel):
    name: str
    reward_type: RewardType
    reward_description: str
    start_date: str = Field(..., description="YYYY-MM-DD")
    end_date: str = Field(..., description="YYYY-MM-DD")
    place_db_id: Optional[str] = None
    description: Optional[str] = None
    terms: Optional[str] = None
    reward_value: Optional[int] = None
    target_count: int = 0
    min_rating: int = 1
    min_content_length: int = 0
    require_photo: bool = False
    total_budget: int = 0


class CampaignUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    terms: Optional[str] = None
    reward_description: Optional[str] = None
    reward_value: Optional[int] = None
    target_count: Optional[int] = None
    min_rating: Optional[int] = None
    min_content_length: Optional[int] = None
    require_photo: Optional[bool] = None
    total_budget: Optional[int] = None


class ParticipateRequest(BaseModel):
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    source: str = "link"


class VerifyRequest(BaseModel):
    review_url: Optional[str] = None
    review_content: Optional[str] = None
    review_rating: Optional[int] = None
    verification_method: str = "manual"


class RewardRequest(BaseModel):
    reward_amount: Optional[int] = None
    notes: Optional[str] = None


class CampaignResponse(BaseModel):
    id: str
    name: str
    reward_type: str
    reward_description: str
    start_date: str
    end_date: str
    status: str
    target_count: int
    current_count: int
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
async def get_campaigns(
    status: Optional[CampaignStatus] = None,
    place_db_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """캠페인 목록 조회"""
    campaigns = await campaign_service.get_campaigns(
        db=db,
        user_id=str(current_user.id),
        status=status,
        place_db_id=place_db_id,
    )

    return [
        {
            "id": str(c.id),
            "name": c.name,
            "description": c.description,
            "reward_type": c.reward_type.value,
            "reward_description": c.reward_description,
            "reward_value": c.reward_value,
            "start_date": c.start_date.isoformat(),
            "end_date": c.end_date.isoformat(),
            "status": c.status.value,
            "target_count": c.target_count,
            "current_count": c.current_count,
            "verified_count": c.verified_count,
            "short_url": c.short_url,
            "total_budget": c.total_budget,
            "spent_budget": c.spent_budget,
            "created_at": c.created_at.isoformat(),
        }
        for c in campaigns
    ]


@router.post("/", response_model=dict)
async def create_campaign(
    request: CampaignCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """캠페인 생성"""
    campaign = await campaign_service.create_campaign(
        db=db,
        user_id=str(current_user.id),
        name=request.name,
        reward_type=request.reward_type,
        reward_description=request.reward_description,
        start_date=_parse_date(request.start_date),
        end_date=_parse_date(request.end_date),
        place_db_id=request.place_db_id,
        description=request.description,
        terms=request.terms,
        reward_value=request.reward_value,
        target_count=request.target_count,
        min_rating=request.min_rating,
        min_content_length=request.min_content_length,
        require_photo=request.require_photo,
        total_budget=request.total_budget,
    )

    return {
        "id": str(campaign.id),
        "name": campaign.name,
        "short_url": campaign.short_url,
        "status": campaign.status.value,
        "message": "Campaign created successfully",
    }


@router.get("/{campaign_id}", response_model=dict)
async def get_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """캠페인 상세 조회"""
    campaign = await campaign_service.get_campaign(
        db=db,
        campaign_id=campaign_id,
    )

    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return {
        "id": str(campaign.id),
        "name": campaign.name,
        "description": campaign.description,
        "terms": campaign.terms,
        "reward_type": campaign.reward_type.value,
        "reward_description": campaign.reward_description,
        "reward_value": campaign.reward_value,
        "start_date": campaign.start_date.isoformat(),
        "end_date": campaign.end_date.isoformat(),
        "status": campaign.status.value,
        "target_count": campaign.target_count,
        "current_count": campaign.current_count,
        "verified_count": campaign.verified_count,
        "min_rating": campaign.min_rating,
        "min_content_length": campaign.min_content_length,
        "require_photo": campaign.require_photo,
        "short_url": campaign.short_url,
        "qr_code_url": campaign.qr_code_url,
        "landing_page_url": campaign.landing_page_url,
        "total_budget": campaign.total_budget,
        "spent_budget": campaign.spent_budget,
        "total_views": campaign.total_views,
        "total_clicks": campaign.total_clicks,
        "participations_count": len(campaign.participations) if campaign.participations else 0,
        "created_at": campaign.created_at.isoformat(),
        "updated_at": campaign.updated_at.isoformat(),
    }


@router.put("/{campaign_id}", response_model=dict)
async def update_campaign(
    campaign_id: str,
    request: CampaignUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """캠페인 수정"""
    update_data = request.model_dump(exclude_unset=True)

    campaign = await campaign_service.update_campaign(
        db=db,
        campaign_id=campaign_id,
        **update_data,
    )

    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return {
        "id": str(campaign.id),
        "name": campaign.name,
        "message": "Campaign updated successfully",
    }


@router.post("/{campaign_id}/activate", response_model=dict)
async def activate_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """캠페인 활성화"""
    campaign = await campaign_service.update_status(
        db=db,
        campaign_id=campaign_id,
        status=CampaignStatus.ACTIVE,
    )

    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return {
        "id": str(campaign.id),
        "status": campaign.status.value,
        "message": "Campaign activated successfully",
    }


@router.post("/{campaign_id}/pause", response_model=dict)
async def pause_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """캠페인 일시정지"""
    campaign = await campaign_service.update_status(
        db=db,
        campaign_id=campaign_id,
        status=CampaignStatus.PAUSED,
    )

    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return {
        "id": str(campaign.id),
        "status": campaign.status.value,
        "message": "Campaign paused successfully",
    }


@router.post("/{campaign_id}/end", response_model=dict)
async def end_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """캠페인 종료"""
    campaign = await campaign_service.update_status(
        db=db,
        campaign_id=campaign_id,
        status=CampaignStatus.ENDED,
    )

    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return {
        "id": str(campaign.id),
        "status": campaign.status.value,
        "message": "Campaign ended successfully",
    }


@router.delete("/{campaign_id}", response_model=dict)
async def delete_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """캠페인 삭제"""
    success = await campaign_service.delete_campaign(
        db=db,
        campaign_id=campaign_id,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return {"message": "Campaign deleted successfully"}


@router.get("/{campaign_id}/qr", response_model=dict)
async def generate_qr_code(
    campaign_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """QR 코드 생성"""
    base_url = str(request.base_url).rstrip("/")

    result = await campaign_service.generate_qr_code(
        db=db,
        campaign_id=campaign_id,
        base_url=base_url,
    )

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.get("/{campaign_id}/stats", response_model=dict)
async def get_campaign_stats(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """캠페인 통계"""
    stats = await campaign_service.get_stats(
        db=db,
        campaign_id=campaign_id,
    )

    if "error" in stats:
        raise HTTPException(status_code=404, detail=stats["error"])

    return stats


@router.post("/{campaign_id}/participate", response_model=dict)
async def participate(
    campaign_id: str,
    request: ParticipateRequest,
    db: AsyncSession = Depends(get_db),
):
    """캠페인 참여 (인증 불필요)"""
    participation = await campaign_service.participate(
        db=db,
        campaign_id=campaign_id,
        customer_name=request.customer_name,
        customer_phone=request.customer_phone,
        customer_email=request.customer_email,
        source=request.source,
    )

    return {
        "id": str(participation.id),
        "participation_code": participation.participation_code,
        "status": participation.status,
        "message": "Participation recorded successfully",
    }


@router.get("/{campaign_id}/participations", response_model=List[dict])
async def get_participations(
    campaign_id: str,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """참여 목록 조회"""
    participations = await campaign_service.get_participations(
        db=db,
        campaign_id=campaign_id,
        status=status,
        limit=limit,
        offset=offset,
    )

    return [
        {
            "id": str(p.id),
            "participation_code": p.participation_code,
            "customer_name": p.customer_name,
            "source": p.source,
            "review_url": p.review_url,
            "review_rating": p.review_rating,
            "is_verified": p.is_verified,
            "verified_at": p.verified_at.isoformat() if p.verified_at else None,
            "reward_given": p.reward_given,
            "reward_given_at": p.reward_given_at.isoformat() if p.reward_given_at else None,
            "status": p.status,
            "participated_at": p.participated_at.isoformat(),
        }
        for p in participations
    ]


@router.post("/participations/{participation_id}/verify", response_model=dict)
async def verify_participation(
    participation_id: str,
    request: VerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """참여 검증"""
    try:
        participation = await campaign_service.verify_participation(
            db=db,
            participation_id=participation_id,
            review_url=request.review_url,
            review_content=request.review_content,
            review_rating=request.review_rating,
            verification_method=request.verification_method,
        )

        return {
            "id": str(participation.id),
            "is_verified": participation.is_verified,
            "status": participation.status,
            "message": "Participation verified successfully",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/participations/{participation_id}/reward", response_model=dict)
async def give_reward(
    participation_id: str,
    request: RewardRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """보상 지급"""
    try:
        participation = await campaign_service.give_reward(
            db=db,
            user_id=str(current_user.id),
            participation_id=participation_id,
            reward_amount=request.reward_amount,
            notes=request.notes,
        )

        return {
            "id": str(participation.id),
            "reward_given": participation.reward_given,
            "status": participation.status,
            "message": "Reward given successfully",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/templates/list", response_model=List[dict])
async def get_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """캠페인 템플릿 조회"""
    templates = await campaign_service.get_templates(
        db=db,
        user_id=str(current_user.id),
    )

    return [
        {
            "id": str(t.id),
            "name": t.name,
            "description": t.description,
            "category": t.category,
            "default_duration_days": t.default_duration_days,
            "default_reward_type": t.default_reward_type.value if t.default_reward_type else None,
            "default_reward_description": t.default_reward_description,
            "thumbnail_url": t.thumbnail_url,
            "usage_count": t.usage_count,
            "is_public": t.is_public,
        }
        for t in templates
    ]
