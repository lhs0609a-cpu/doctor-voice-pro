"""
Profiles API Router
의사 프로필 관리
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.schemas.doctor_profile import (
    DoctorProfileCreate,
    DoctorProfileUpdate,
    DoctorProfileResponse,
)
from app.models import User, DoctorProfile
from app.api.deps import get_current_user

router = APIRouter()


@router.get("/me", response_model=DoctorProfileResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    내 프로필 조회
    """
    result = await db.execute(
        select(DoctorProfile).where(DoctorProfile.user_id == current_user.id)
    )

    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="프로필을 찾을 수 없습니다"
        )

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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="프로필을 찾을 수 없습니다"
        )

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
