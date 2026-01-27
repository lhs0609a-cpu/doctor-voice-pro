"""
Profiles API Router
프로필 및 업종 설정 관리
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from pydantic import BaseModel

from app.db.database import get_db
from app.schemas.doctor_profile import (
    DoctorProfileCreate,
    DoctorProfileUpdate,
    DoctorProfileResponse,
)
from app.models import User, DoctorProfile
from app.models.user import IndustryType
from app.api.deps import get_current_user
from app.services.industry_config import get_industry_config, get_all_industries

router = APIRouter()


# ==================== 업종 관련 API ====================

class IndustryUpdateRequest(BaseModel):
    industry_type: str
    business_name: Optional[str] = None
    specialty: Optional[str] = None


@router.get("/industries")
async def get_industries():
    """
    지원되는 모든 업종 목록 조회
    """
    return {
        "industries": get_all_industries()
    }


@router.get("/industries/{industry_type}")
async def get_industry_detail(industry_type: str):
    """
    특정 업종의 상세 설정 조회
    """
    try:
        industry = IndustryType(industry_type)
        config = get_industry_config(industry)
        return {
            "industry_type": industry_type,
            **config
        }
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid industry type: {industry_type}"
        )


@router.get("/me/industry")
async def get_my_industry(
    current_user: User = Depends(get_current_user),
):
    """
    내 업종 설정 조회
    """
    config = get_industry_config(current_user.industry_type)
    return {
        "industry_type": current_user.industry_type.value,
        "business_name": current_user.business_name or current_user.hospital_name,
        "specialty": current_user.specialty,
        "config": config
    }


@router.put("/me/industry")
async def update_my_industry(
    request: IndustryUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    내 업종 설정 업데이트
    """
    try:
        industry = IndustryType(request.industry_type)
        current_user.industry_type = industry

        if request.business_name is not None:
            current_user.business_name = request.business_name
            # 레거시 호환성을 위해 hospital_name도 업데이트
            if industry == IndustryType.MEDICAL:
                current_user.hospital_name = request.business_name

        if request.specialty is not None:
            current_user.specialty = request.specialty

        await db.commit()
        await db.refresh(current_user)

        config = get_industry_config(industry)
        return {
            "success": True,
            "industry_type": current_user.industry_type.value,
            "business_name": current_user.business_name,
            "specialty": current_user.specialty,
            "config": config
        }
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid industry type: {request.industry_type}"
        )


# ==================== 프로필 API ====================


@router.get("/me", response_model=DoctorProfileResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    내 프로필 조회 (없으면 자동 생성)
    """
    result = await db.execute(
        select(DoctorProfile).where(DoctorProfile.user_id == current_user.id)
    )

    profile = result.scalar_one_or_none()

    if not profile:
        # 프로필이 없으면 기본값으로 자동 생성
        import uuid
        profile = DoctorProfile(
            id=uuid.uuid4(),
            user_id=current_user.id,
            writing_style={
                "formality": 5,
                "friendliness": 5,
                "technical_depth": 5,
                "storytelling": 5,
                "emotion": 5,
            },
            signature_phrases=[],
            sample_posts=[],
            target_audience={
                "age_range": "",
                "gender": "",
                "concerns": [],
            },
            preferred_structure="story_problem_solution",
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)

    return profile


@router.put("/me", response_model=DoctorProfileResponse)
async def update_my_profile(
    profile_update: DoctorProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    프로필 업데이트

    **Parameters:**
    - **writing_style**: 글쓰기 스타일 설정 (선택)
      - formality: 격식 수준 (1-10)
      - friendliness: 친근함 (1-10)
      - technical_depth: 전문성 (1-10)
      - storytelling: 스토리텔링 (1-10)
      - emotion: 감정 표현 (1-10)
    - **signature_phrases**: 자주 쓰는 표현 리스트 (선택)
    - **sample_posts**: 학습용 샘플 글 리스트 (선택)
    - **target_audience**: 타겟 독자 설정 (선택)
    - **preferred_structure**: 선호하는 글 구조 (선택)
    """
    result = await db.execute(
        select(DoctorProfile).where(DoctorProfile.user_id == current_user.id)
    )

    profile = result.scalar_one_or_none()

    if not profile:
        # 프로필이 없으면 기본값으로 자동 생성
        import uuid
        profile = DoctorProfile(
            id=uuid.uuid4(),
            user_id=current_user.id,
            writing_style={
                "formality": 5,
                "friendliness": 5,
                "technical_depth": 5,
                "storytelling": 5,
                "emotion": 5,
            },
            signature_phrases=[],
            sample_posts=[],
            target_audience={
                "age_range": "",
                "gender": "",
                "concerns": [],
            },
            preferred_structure="story_problem_solution",
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)

    # 업데이트
    if profile_update.writing_style is not None:
        profile.writing_style = profile_update.writing_style.dict()

    if profile_update.signature_phrases is not None:
        profile.signature_phrases = profile_update.signature_phrases

    if profile_update.sample_posts is not None:
        profile.sample_posts = profile_update.sample_posts

    if profile_update.target_audience is not None:
        profile.target_audience = profile_update.target_audience.dict()

    if profile_update.preferred_structure is not None:
        profile.preferred_structure = profile_update.preferred_structure

    await db.commit()
    await db.refresh(profile)

    return profile
