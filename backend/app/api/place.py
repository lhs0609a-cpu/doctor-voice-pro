"""
네이버 플레이스 관리 API
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.place_service import PlaceService

router = APIRouter()
place_service = PlaceService()


# ==================== Schemas ====================

class PlaceConnectRequest(BaseModel):
    place_id: str
    place_name: str
    place_url: Optional[str] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    address: Optional[str] = None
    road_address: Optional[str] = None
    phone: Optional[str] = None
    business_hours: Optional[dict] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None


class PlaceUpdateRequest(BaseModel):
    place_name: Optional[str] = None
    place_url: Optional[str] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    address: Optional[str] = None
    road_address: Optional[str] = None
    phone: Optional[str] = None
    business_hours: Optional[dict] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    images: Optional[List[str]] = None


class GenerateDescriptionRequest(BaseModel):
    tone: str = Field("professional", description="professional, friendly, casual")
    keywords: Optional[List[str]] = None
    specialty_focus: Optional[str] = None


class PlaceResponse(BaseModel):
    id: str
    place_id: str
    place_name: str
    place_url: Optional[str]
    category: Optional[str]
    address: Optional[str]
    phone: Optional[str]
    review_count: int
    avg_rating: float
    optimization_score: int
    is_connected: bool
    created_at: str

    class Config:
        from_attributes = True


class OptimizationCheckResponse(BaseModel):
    type: str
    name: str
    status: str
    score: int
    message: Optional[str]
    suggestion: Optional[str]
    priority: int


class OptimizationResponse(BaseModel):
    optimization_score: int
    checks: List[OptimizationCheckResponse]


# ==================== Routes ====================

@router.post("/connect", response_model=dict)
async def connect_place(
    request: PlaceConnectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """플레이스 연동"""
    place = await place_service.connect_place(
        db=db,
        user_id=str(current_user.id),
        place_id=request.place_id,
        place_name=request.place_name,
        place_url=request.place_url,
        category=request.category,
        sub_category=request.sub_category,
        address=request.address,
        road_address=request.road_address,
        phone=request.phone,
        business_hours=request.business_hours,
        description=request.description,
        tags=request.tags,
    )

    return {
        "id": str(place.id),
        "place_id": place.place_id,
        "place_name": place.place_name,
        "optimization_score": place.optimization_score,
        "message": "Place connected successfully",
    }


@router.get("/", response_model=List[dict])
async def get_places(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """연결된 플레이스 목록 조회"""
    places = await place_service.get_places(
        db=db,
        user_id=str(current_user.id),
    )

    return [
        {
            "id": str(p.id),
            "place_id": p.place_id,
            "place_name": p.place_name,
            "place_url": p.place_url,
            "category": p.category,
            "address": p.address,
            "review_count": p.review_count or 0,
            "avg_rating": p.avg_rating or 0,
            "optimization_score": p.optimization_score or 0,
            "is_connected": p.is_connected,
            "last_synced_at": p.last_synced_at.isoformat() if p.last_synced_at else None,
            "created_at": p.created_at.isoformat(),
        }
        for p in places
    ]


@router.get("/info", response_model=dict)
async def get_place_info(
    place_db_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """플레이스 정보 조회"""
    place = await place_service.get_place(
        db=db,
        user_id=str(current_user.id),
        place_db_id=place_db_id,
    )

    if not place:
        raise HTTPException(status_code=404, detail="Place not found")

    return {
        "id": str(place.id),
        "place_id": place.place_id,
        "place_name": place.place_name,
        "place_url": place.place_url,
        "category": place.category,
        "sub_category": place.sub_category,
        "address": place.address,
        "road_address": place.road_address,
        "phone": place.phone,
        "business_hours": place.business_hours,
        "description": place.description,
        "short_description": place.short_description,
        "tags": place.tags or [],
        "images": place.images or [],
        "review_count": place.review_count or 0,
        "visitor_review_count": place.visitor_review_count or 0,
        "blog_review_count": place.blog_review_count or 0,
        "avg_rating": place.avg_rating or 0,
        "save_count": place.save_count or 0,
        "optimization_score": place.optimization_score or 0,
        "optimization_details": place.optimization_details or {},
        "is_connected": place.is_connected,
        "last_synced_at": place.last_synced_at.isoformat() if place.last_synced_at else None,
        "created_at": place.created_at.isoformat(),
    }


@router.put("/info/{place_db_id}", response_model=dict)
async def update_place_info(
    place_db_id: str,
    request: PlaceUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """플레이스 정보 수정"""
    update_data = request.model_dump(exclude_unset=True)

    place = await place_service.update_place(
        db=db,
        place_db_id=place_db_id,
        **update_data,
    )

    if not place:
        raise HTTPException(status_code=404, detail="Place not found")

    return {
        "id": str(place.id),
        "place_name": place.place_name,
        "message": "Place updated successfully",
    }


@router.get("/optimization", response_model=OptimizationResponse)
async def get_optimization(
    place_db_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """최적화 점수 및 체크리스트 조회"""
    result = await place_service.run_optimization_check(
        db=db,
        place_db_id=place_db_id,
    )

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.post("/optimization/refresh", response_model=OptimizationResponse)
async def refresh_optimization(
    place_db_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """최적화 점수 재계산"""
    result = await place_service.run_optimization_check(
        db=db,
        place_db_id=place_db_id,
    )

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.post("/generate-description", response_model=dict)
async def generate_description(
    place_db_id: str = Query(...),
    request: GenerateDescriptionRequest = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 소개글 생성"""
    if request is None:
        request = GenerateDescriptionRequest()

    try:
        description = await place_service.generate_description(
            db=db,
            place_db_id=place_db_id,
            user_id=str(current_user.id),
            tone=request.tone,
            keywords=request.keywords,
            specialty_focus=request.specialty_focus,
        )

        return {
            "id": str(description.id),
            "description": description.description,
            "tone": description.tone,
            "keywords_used": description.keywords_used,
            "message": "Description generated successfully",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/tag-recommendations", response_model=List[dict])
async def get_tag_recommendations(
    place_db_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """태그 추천"""
    recommendations = await place_service.get_tag_recommendations(
        db=db,
        place_db_id=place_db_id,
    )

    return recommendations
