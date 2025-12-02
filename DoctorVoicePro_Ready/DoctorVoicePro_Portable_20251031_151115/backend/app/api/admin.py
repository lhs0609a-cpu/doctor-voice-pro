"""
Admin API Router
관리자 전용 API
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime
from uuid import UUID

from app.db.database import get_db
from app.schemas.user import UserResponse
from app.schemas.admin import UserApprovalRequest, UserSubscriptionRequest
from app.api.deps import get_current_user
from app.models import User

router = APIRouter()


async def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """현재 사용자가 관리자인지 확인"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다"
        )
    return current_user


@router.get("/users", response_model=List[UserResponse])
async def get_users(
    is_approved: Optional[bool] = Query(None, description="승인 상태 필터"),
    is_active: Optional[bool] = Query(None, description="활성화 상태 필터"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user)
):
    """
    사용자 목록 조회 (관리자 전용)

    - **is_approved**: 승인 상태로 필터링 (선택)
    - **is_active**: 활성화 상태로 필터링 (선택)
    - **skip**: 건너뛸 개수
    - **limit**: 조회할 최대 개수
    """
    query = select(User)

    if is_approved is not None:
        query = query.where(User.is_approved == is_approved)

    if is_active is not None:
        query = query.where(User.is_active == is_active)

    query = query.offset(skip).limit(limit).order_by(User.created_at.desc())

    result = await db.execute(query)
    users = result.scalars().all()

    return users


@router.post("/users/approve", response_model=UserResponse)
async def approve_user(
    request: UserApprovalRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user)
):
    """
    사용자 승인/거부 (관리자 전용)

    - **user_id**: 승인할 사용자 ID
    - **is_approved**: 승인 여부 (true: 승인, false: 거부)
    """
    # 사용자 조회
    result = await db.execute(select(User).where(User.id == UUID(request.user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다"
        )

    # 승인 상태 업데이트
    user.is_approved = request.is_approved
    user.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(user)

    return user


@router.post("/users/subscription", response_model=UserResponse)
async def set_user_subscription(
    request: UserSubscriptionRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user)
):
    """
    사용자 구독 기간 설정 (관리자 전용)

    - **user_id**: 사용자 ID
    - **subscription_start_date**: 구독 시작일 (선택)
    - **subscription_end_date**: 구독 종료일 (선택)
    """
    # 사용자 조회
    result = await db.execute(select(User).where(User.id == UUID(request.user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다"
        )

    # 구독 기간 업데이트
    if request.subscription_start_date:
        user.subscription_start_date = request.subscription_start_date

    if request.subscription_end_date:
        user.subscription_end_date = request.subscription_end_date

    user.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(user)

    return user


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_detail(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user)
):
    """
    특정 사용자 상세 정보 조회 (관리자 전용)
    """
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다"
        )

    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user)
):
    """
    사용자 삭제 (관리자 전용)
    """
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다"
        )

    # 관리자는 삭제할 수 없음
    if user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 계정은 삭제할 수 없습니다"
        )

    await db.delete(user)
    await db.commit()

    return None
