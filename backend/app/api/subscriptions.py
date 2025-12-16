"""
구독 관리 API
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from app.db.database import get_db
from app.api.deps import get_current_user
from app.models import User
from app.models.subscription import (
    Plan, Subscription, UsageLog, UsageSummary, UserCredit,
    PlanType, SubscriptionStatus, UsageType
)

router = APIRouter()


# ==================== Schemas ====================

class PlanResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    price_monthly: int
    price_yearly: int
    posts_per_month: int
    analysis_per_month: int
    keywords_per_month: int
    has_api_access: bool
    has_priority_support: bool
    has_advanced_analytics: bool
    has_team_features: bool
    extra_post_price: int
    extra_analysis_price: int

    class Config:
        from_attributes = True


class SubscriptionResponse(BaseModel):
    id: UUID
    plan_id: str
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    trial_end: Optional[datetime]
    plan: Optional[PlanResponse]

    class Config:
        from_attributes = True


class UsageSummaryResponse(BaseModel):
    posts_used: int
    posts_limit: int
    analysis_used: int
    analysis_limit: int
    keywords_used: int
    keywords_limit: int
    extra_posts: int
    extra_analysis: int
    extra_cost: int

    class Config:
        from_attributes = True


class UserCreditResponse(BaseModel):
    post_credits: int
    analysis_credits: int

    class Config:
        from_attributes = True


class CreateSubscriptionRequest(BaseModel):
    plan_id: str
    payment_method: Optional[str] = None


class ChangeSubscriptionRequest(BaseModel):
    new_plan_id: str


# ==================== Endpoints ====================

@router.get("/plans", response_model=List[PlanResponse])
async def get_plans(
    db: AsyncSession = Depends(get_db)
):
    """사용 가능한 플랜 목록 조회"""
    result = await db.execute(
        select(Plan)
        .where(Plan.is_active == True)
        .order_by(Plan.sort_order)
    )
    plans = result.scalars().all()
    return plans


@router.get("/current", response_model=Optional[SubscriptionResponse])
async def get_current_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """현재 사용자의 구독 정보 조회"""
    result = await db.execute(
        select(Subscription)
        .where(
            and_(
                Subscription.user_id == current_user.id,
                Subscription.status.in_([
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.TRIALING,
                    SubscriptionStatus.PAST_DUE
                ])
            )
        )
        .order_by(Subscription.created_at.desc())
    )
    subscription = result.scalar_one_or_none()

    if subscription:
        # Eager load plan
        plan_result = await db.execute(
            select(Plan).where(Plan.id == subscription.plan_id)
        )
        subscription.plan = plan_result.scalar_one_or_none()

    return subscription


@router.get("/usage", response_model=UsageSummaryResponse)
async def get_usage_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """현재 월 사용량 조회"""
    now = datetime.utcnow()
    year = now.year
    month = now.month

    # 사용량 요약 조회
    result = await db.execute(
        select(UsageSummary)
        .where(
            and_(
                UsageSummary.user_id == current_user.id,
                UsageSummary.year == year,
                UsageSummary.month == month
            )
        )
    )
    summary = result.scalar_one_or_none()

    if not summary:
        # 구독 정보에서 기본값 가져오기
        sub_result = await db.execute(
            select(Subscription)
            .where(
                and_(
                    Subscription.user_id == current_user.id,
                    Subscription.status.in_([
                        SubscriptionStatus.ACTIVE,
                        SubscriptionStatus.TRIALING
                    ])
                )
            )
        )
        subscription = sub_result.scalar_one_or_none()

        if subscription:
            plan_result = await db.execute(
                select(Plan).where(Plan.id == subscription.plan_id)
            )
            plan = plan_result.scalar_one_or_none()

            return UsageSummaryResponse(
                posts_used=0,
                posts_limit=plan.posts_per_month if plan else 3,
                analysis_used=0,
                analysis_limit=plan.analysis_per_month if plan else 10,
                keywords_used=0,
                keywords_limit=plan.keywords_per_month if plan else 20,
                extra_posts=0,
                extra_analysis=0,
                extra_cost=0
            )

        # 무료 플랜 기본값
        return UsageSummaryResponse(
            posts_used=0,
            posts_limit=3,
            analysis_used=0,
            analysis_limit=10,
            keywords_used=0,
            keywords_limit=20,
            extra_posts=0,
            extra_analysis=0,
            extra_cost=0
        )

    return summary


@router.get("/credits", response_model=UserCreditResponse)
async def get_user_credits(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """사용자 크레딧 잔액 조회"""
    result = await db.execute(
        select(UserCredit)
        .where(UserCredit.user_id == current_user.id)
    )
    credits = result.scalar_one_or_none()

    if not credits:
        return UserCreditResponse(
            post_credits=0,
            analysis_credits=0
        )

    return credits


@router.post("/subscribe", response_model=SubscriptionResponse)
async def create_subscription(
    request: CreateSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """새 구독 생성"""
    # 플랜 확인
    plan_result = await db.execute(
        select(Plan).where(Plan.id == request.plan_id)
    )
    plan = plan_result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="플랜을 찾을 수 없습니다"
        )

    # 기존 활성 구독 확인
    existing_result = await db.execute(
        select(Subscription)
        .where(
            and_(
                Subscription.user_id == current_user.id,
                Subscription.status.in_([
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.TRIALING
                ])
            )
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 활성 구독이 있습니다. 플랜 변경을 이용해주세요."
        )

    # 구독 기간 계산
    from dateutil.relativedelta import relativedelta
    now = datetime.utcnow()
    period_end = now + relativedelta(months=1)

    # 무료 플랜은 바로 활성화
    # 유료 플랜은 결제 후 활성화 (pending 상태로 생성)
    subscription_status = SubscriptionStatus.ACTIVE if plan.price_monthly == 0 else SubscriptionStatus.TRIALING

    subscription = Subscription(
        user_id=current_user.id,
        plan_id=request.plan_id,
        status=subscription_status,
        current_period_start=now,
        current_period_end=period_end,
        payment_method=request.payment_method,
        trial_start=now if subscription_status == SubscriptionStatus.TRIALING else None,
        trial_end=now + relativedelta(days=7) if subscription_status == SubscriptionStatus.TRIALING else None
    )

    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)

    subscription.plan = plan
    return subscription


@router.post("/cancel")
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """구독 취소 (기간 종료 시 취소)"""
    result = await db.execute(
        select(Subscription)
        .where(
            and_(
                Subscription.user_id == current_user.id,
                Subscription.status.in_([
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.TRIALING
                ])
            )
        )
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="활성 구독을 찾을 수 없습니다"
        )

    subscription.cancel_at_period_end = True
    subscription.cancelled_at = datetime.utcnow()

    await db.commit()

    return {"message": "구독이 현재 기간 종료 시 취소됩니다", "period_end": subscription.current_period_end}


@router.post("/change-plan", response_model=SubscriptionResponse)
async def change_plan(
    request: ChangeSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """플랜 변경"""
    # 새 플랜 확인
    new_plan_result = await db.execute(
        select(Plan).where(Plan.id == request.new_plan_id)
    )
    new_plan = new_plan_result.scalar_one_or_none()

    if not new_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="플랜을 찾을 수 없습니다"
        )

    # 현재 구독 확인
    result = await db.execute(
        select(Subscription)
        .where(
            and_(
                Subscription.user_id == current_user.id,
                Subscription.status.in_([
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.TRIALING
                ])
            )
        )
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="활성 구독을 찾을 수 없습니다"
        )

    # 플랜 변경
    subscription.plan_id = request.new_plan_id
    subscription.cancel_at_period_end = False
    subscription.cancelled_at = None

    await db.commit()
    await db.refresh(subscription)

    subscription.plan = new_plan
    return subscription


@router.get("/history")
async def get_subscription_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 10,
    offset: int = 0
):
    """구독 내역 조회"""
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == current_user.id)
        .order_by(Subscription.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    subscriptions = result.scalars().all()

    return subscriptions


@router.get("/usage-logs")
async def get_usage_logs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    usage_type: Optional[UsageType] = None,
    limit: int = 50,
    offset: int = 0
):
    """사용량 기록 조회"""
    query = select(UsageLog).where(UsageLog.user_id == current_user.id)

    if usage_type:
        query = query.where(UsageLog.usage_type == usage_type)

    result = await db.execute(
        query.order_by(UsageLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    logs = result.scalars().all()

    return logs
