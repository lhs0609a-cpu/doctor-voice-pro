"""
API Dependencies
공통 의존성 함수들
"""

from typing import Optional
from uuid import UUID
from datetime import datetime
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.exc import IntegrityError

from app.db.database import get_db
from app.models import User
from app.models.subscription import (
    Subscription, SubscriptionStatus, Plan, UsageSummary, UsageLog,
    UserCredit, UsageType
)
from app.core.security import decode_token

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    현재 로그인한 사용자 가져오기

    JWT 토큰을 검증하고 사용자 정보를 반환합니다.
    """
    # 토큰 디코드
    token = credentials.credentials
    payload = decode_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다",
        )

    # 사용자 ID 추출
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다",
        )

    # 사용자 조회
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 사용자 ID입니다",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    활성화된 사용자만 허용

    비활성화된 계정은 접근을 거부합니다.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다",
        )

    return current_user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    현재 로그인한 사용자 가져오기 (선택적)

    로그인하지 않은 경우 None 반환
    """
    if not credentials:
        return None

    try:
        # 토큰 디코드
        token = credentials.credentials
        payload = decode_token(token)

        if not payload:
            return None

        # 사용자 ID 추출
        user_id_str = payload.get("sub")
        if not user_id_str:
            return None

        # 사용자 조회
        user_id = UUID(user_id_str)
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        return user
    except Exception:
        return None


# ==================== 사용량 체크 의존성 ====================

class UsageLimitExceeded(HTTPException):
    """사용량 초과 예외"""
    def __init__(self, usage_type: str, limit: int, used: int):
        detail = {
            "error": "usage_limit_exceeded",
            "usage_type": usage_type,
            "limit": limit,
            "used": used,
            "message": f"월 {usage_type} 한도를 초과했습니다. (사용: {used}/{limit})"
        }
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


async def get_user_subscription(
    user: User,
    db: AsyncSession
) -> tuple[Optional[Subscription], Optional[Plan]]:
    """사용자의 현재 구독과 플랜 조회"""
    result = await db.execute(
        select(Subscription)
        .where(
            and_(
                Subscription.user_id == user.id,
                Subscription.status.in_([
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.TRIALING
                ])
            )
        )
        .order_by(Subscription.created_at.desc())
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        return None, None

    plan_result = await db.execute(
        select(Plan).where(Plan.id == subscription.plan_id)
    )
    plan = plan_result.scalar_one_or_none()

    return subscription, plan


async def get_or_create_usage_summary(
    user: User,
    subscription: Optional[Subscription],
    plan: Optional[Plan],
    db: AsyncSession
) -> UsageSummary:
    """
    현재 월 사용량 요약 조회 또는 생성

    P0 Fix: Race Condition 방지
    - UniqueConstraint(user_id, year, month) + IntegrityError 처리로
    - 동시 요청 시에도 중복 레코드 생성 방지
    """
    now = datetime.utcnow()
    year = now.year
    month = now.month

    result = await db.execute(
        select(UsageSummary)
        .where(
            and_(
                UsageSummary.user_id == user.id,
                UsageSummary.year == year,
                UsageSummary.month == month
            )
        )
    )
    summary = result.scalar_one_or_none()

    if not summary:
        # 기본값 (무료 플랜)
        posts_limit = 3
        analysis_limit = 10
        keywords_limit = 20

        if plan:
            posts_limit = plan.posts_per_month
            analysis_limit = plan.analysis_per_month
            keywords_limit = plan.keywords_per_month

        summary = UsageSummary(
            user_id=user.id,
            subscription_id=subscription.id if subscription else None,
            year=year,
            month=month,
            posts_limit=posts_limit,
            analysis_limit=analysis_limit,
            keywords_limit=keywords_limit
        )
        db.add(summary)

        try:
            await db.flush()
        except IntegrityError:
            # P0 Fix: 동시 요청으로 인한 중복 삽입 시
            # 롤백 후 기존 레코드 재조회
            await db.rollback()
            result = await db.execute(
                select(UsageSummary)
                .where(
                    and_(
                        UsageSummary.user_id == user.id,
                        UsageSummary.year == year,
                        UsageSummary.month == month
                    )
                )
            )
            summary = result.scalar_one_or_none()
            if not summary:
                # 그래도 없으면 에러 (거의 발생하지 않음)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="사용량 정보를 생성할 수 없습니다. 잠시 후 다시 시도해주세요."
                )

    return summary


async def check_usage_limit(
    user: User,
    db: AsyncSession,
    usage_type: UsageType,
    quantity: int = 1
) -> tuple[bool, UsageSummary, Optional[Plan]]:
    """
    사용량 한도 체크

    Returns:
        (can_use, summary, plan) - 사용 가능 여부, 사용량 요약, 플랜 정보
    """
    # 관리자 부여 무제한 권한 체크 (글 생성에만 적용)
    if usage_type == UsageType.POST_GENERATION and getattr(user, 'has_unlimited_posts', False):
        subscription, plan = await get_user_subscription(user, db)
        summary = await get_or_create_usage_summary(user, subscription, plan, db)
        return True, summary, plan

    subscription, plan = await get_user_subscription(user, db)
    summary = await get_or_create_usage_summary(user, subscription, plan, db)

    # 사용량 체크
    if usage_type == UsageType.POST_GENERATION:
        limit = summary.posts_limit
        used = summary.posts_used
    elif usage_type == UsageType.TOP_POST_ANALYSIS:
        limit = summary.analysis_limit
        used = summary.analysis_used
    elif usage_type == UsageType.KEYWORD_RESEARCH:
        limit = summary.keywords_limit
        used = summary.keywords_used
    else:
        # 기타 타입은 제한 없음
        return True, summary, plan

    # 무제한 체크 (-1은 무제한)
    if limit == -1:
        return True, summary, plan

    # 크레딧 확인
    credit_result = await db.execute(
        select(UserCredit).where(UserCredit.user_id == user.id)
    )
    user_credit = credit_result.scalar_one_or_none()

    available_credits = 0
    if user_credit:
        if usage_type == UsageType.POST_GENERATION:
            available_credits = user_credit.post_credits
        elif usage_type in [UsageType.TOP_POST_ANALYSIS, UsageType.KEYWORD_RESEARCH]:
            available_credits = user_credit.analysis_credits

    # 기본 한도 + 크레딧으로 사용 가능 여부 확인
    if used + quantity <= limit:
        return True, summary, plan
    elif available_credits >= quantity:
        return True, summary, plan  # 크레딧으로 커버 가능
    else:
        return False, summary, plan


async def record_usage(
    user: User,
    db: AsyncSession,
    usage_type: UsageType,
    quantity: int = 1,
    resource_id: str = None,
    resource_type: str = None
) -> UsageLog:
    """
    사용량 기록

    한도 초과 시 크레딧 사용, 크레딧도 없으면 초과 비용 발생
    """
    subscription, plan = await get_user_subscription(user, db)
    summary = await get_or_create_usage_summary(user, subscription, plan, db)

    # 현재 사용량 확인
    if usage_type == UsageType.POST_GENERATION:
        limit = summary.posts_limit
        used = summary.posts_used
    elif usage_type == UsageType.TOP_POST_ANALYSIS:
        limit = summary.analysis_limit
        used = summary.analysis_used
    elif usage_type == UsageType.KEYWORD_RESEARCH:
        limit = summary.keywords_limit
        used = summary.keywords_used
    else:
        limit = -1  # 무제한
        used = 0

    is_extra = False
    cost = 0
    use_credits = False

    # 무제한이 아니고 한도 초과 시
    if limit != -1 and used >= limit:
        # 크레딧 확인
        credit_result = await db.execute(
            select(UserCredit).where(UserCredit.user_id == user.id)
        )
        user_credit = credit_result.scalar_one_or_none()

        if user_credit:
            if usage_type == UsageType.POST_GENERATION and user_credit.post_credits >= quantity:
                use_credits = True
                user_credit.post_credits -= quantity
            elif usage_type in [UsageType.TOP_POST_ANALYSIS, UsageType.KEYWORD_RESEARCH] and user_credit.analysis_credits >= quantity:
                use_credits = True
                user_credit.analysis_credits -= quantity

        if not use_credits:
            is_extra = True
            # 초과 비용 계산
            if plan:
                if usage_type == UsageType.POST_GENERATION:
                    cost = plan.extra_post_price * quantity
                else:
                    cost = plan.extra_analysis_price * quantity

    # 사용량 로그 기록
    log = UsageLog(
        user_id=user.id,
        subscription_id=subscription.id if subscription else None,
        usage_type=usage_type,
        quantity=quantity,
        resource_id=resource_id,
        resource_type=resource_type,
        cost=cost,
        is_extra=is_extra,
        period_start=datetime(summary.year, summary.month, 1),
        metadata={"used_credits": use_credits}
    )
    db.add(log)

    # 요약 업데이트
    if usage_type == UsageType.POST_GENERATION:
        summary.posts_used += quantity
        if is_extra:
            summary.extra_posts += quantity
    elif usage_type == UsageType.TOP_POST_ANALYSIS:
        summary.analysis_used += quantity
        if is_extra:
            summary.extra_analysis += quantity
    elif usage_type == UsageType.KEYWORD_RESEARCH:
        summary.keywords_used += quantity

    if is_extra:
        summary.extra_cost += cost

    await db.flush()
    return log


def require_usage_check(usage_type: UsageType, quantity: int = 1):
    """
    사용량 체크 의존성 팩토리

    Usage:
        @router.post("/posts")
        async def create_post(
            ...,
            _: None = Depends(require_usage_check(UsageType.POST_GENERATION))
        ):
    """
    async def dependency(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        can_use, summary, plan = await check_usage_limit(
            current_user, db, usage_type, quantity
        )

        if not can_use:
            if usage_type == UsageType.POST_GENERATION:
                limit = summary.posts_limit
                used = summary.posts_used
                type_name = "글 생성"
            elif usage_type == UsageType.TOP_POST_ANALYSIS:
                limit = summary.analysis_limit
                used = summary.analysis_used
                type_name = "상위노출 분석"
            elif usage_type == UsageType.KEYWORD_RESEARCH:
                limit = summary.keywords_limit
                used = summary.keywords_used
                type_name = "키워드 연구"
            else:
                type_name = "기능"
                limit = 0
                used = 0

            raise UsageLimitExceeded(type_name, limit, used)

        return None

    return dependency
