"""
빌링(정기결제) API
토스페이먼츠 빌링키 기반 자동결제 관리
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timedelta
import uuid

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionStatus, Payment, PaymentStatus
from app.services.toss_payments import TossPaymentsService

router = APIRouter(prefix="/billing", tags=["빌링(정기결제)"])

toss_service = TossPaymentsService()


# ==================== Schemas ====================

class BillingSetupRequest(BaseModel):
    """빌링키 발급 요청"""
    auth_key: str = Field(..., description="토스페이먼츠 인증키")
    subscription_id: Optional[str] = Field(None, description="연결할 구독 ID")


class BillingSetupResponse(BaseModel):
    """빌링키 발급 응답"""
    success: bool
    billing_key: Optional[str] = None
    card_company: Optional[str] = None
    card_number: Optional[str] = None
    message: Optional[str] = None


class CardInfoResponse(BaseModel):
    """등록된 카드 정보"""
    has_card: bool
    card_company: Optional[str] = None
    card_number_last4: Optional[str] = None
    registered_at: Optional[datetime] = None


class SubscriptionManageResponse(BaseModel):
    """구독 관리 정보"""
    id: str
    plan_name: str
    plan_price: int
    status: str
    current_period_start: datetime
    current_period_end: datetime
    next_billing_date: Optional[datetime]
    cancel_at_period_end: bool
    has_card: bool
    card_company: Optional[str]
    card_number_last4: Optional[str]
    trial_end: Optional[datetime]
    is_trialing: bool


class CancelSubscriptionRequest(BaseModel):
    """구독 해지 요청"""
    reason: Optional[str] = None
    immediate: bool = Field(False, description="즉시 해지 여부 (True: 즉시 해지+환불, False: 기간 종료 시 해지)")


class CancelSubscriptionResponse(BaseModel):
    """구독 해지 응답"""
    success: bool
    message: str
    refund_amount: Optional[int] = None
    cancel_at: Optional[datetime] = None


# ==================== 빌링키 관리 API ====================

@router.post("/setup-card", response_model=BillingSetupResponse)
async def setup_billing_card(
    request: BillingSetupRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    카드 등록 (빌링키 발급)

    토스페이먼츠에서 인증 완료 후 받은 authKey로 빌링키를 발급받습니다.
    """
    # 고객 키 생성 (사용자별 고유)
    customer_key = f"user_{current_user.id}_{int(datetime.utcnow().timestamp())}"

    # 빌링키 발급
    result = await toss_service.issue_billing_key(
        customer_key=customer_key,
        auth_key=request.auth_key
    )

    if not result.get("success"):
        return BillingSetupResponse(
            success=False,
            message=result.get("error", "빌링키 발급에 실패했습니다.")
        )

    billing_key = result.get("billing_key")
    card_company = result.get("card_company")
    card_number = result.get("card_number", "")
    card_number_last4 = card_number[-4:] if len(card_number) >= 4 else card_number

    # 구독에 빌링키 연결
    if request.subscription_id:
        stmt = select(Subscription).where(
            Subscription.id == request.subscription_id,
            Subscription.user_id == current_user.id
        )
        result_sub = await db.execute(stmt)
        subscription = result_sub.scalar_one_or_none()

        if subscription:
            subscription.billing_key = billing_key
            subscription.customer_key = customer_key
            subscription.card_company = card_company
            subscription.card_number_last4 = card_number_last4
            subscription.payment_method = "card"
            await db.commit()
    else:
        # 활성 구독 찾아서 연결
        stmt = select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING])
        )
        result_sub = await db.execute(stmt)
        subscription = result_sub.scalar_one_or_none()

        if subscription:
            subscription.billing_key = billing_key
            subscription.customer_key = customer_key
            subscription.card_company = card_company
            subscription.card_number_last4 = card_number_last4
            subscription.payment_method = "card"
            await db.commit()

    return BillingSetupResponse(
        success=True,
        billing_key=billing_key,
        card_company=card_company,
        card_number=f"****{card_number_last4}"
    )


@router.get("/card", response_model=CardInfoResponse)
async def get_registered_card(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """등록된 카드 정보 조회"""
    stmt = select(Subscription).where(
        Subscription.user_id == current_user.id,
        Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING])
    )
    result = await db.execute(stmt)
    subscription = result.scalar_one_or_none()

    if not subscription or not subscription.billing_key:
        return CardInfoResponse(has_card=False)

    return CardInfoResponse(
        has_card=True,
        card_company=subscription.card_company,
        card_number_last4=subscription.card_number_last4,
        registered_at=subscription.updated_at
    )


@router.delete("/card")
async def delete_billing_card(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """등록된 카드 삭제"""
    stmt = select(Subscription).where(
        Subscription.user_id == current_user.id,
        Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING])
    )
    result = await db.execute(stmt)
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(status_code=404, detail="활성 구독이 없습니다.")

    if not subscription.billing_key:
        raise HTTPException(status_code=400, detail="등록된 카드가 없습니다.")

    # 카드 정보 삭제
    subscription.billing_key = None
    subscription.customer_key = None
    subscription.card_company = None
    subscription.card_number_last4 = None

    await db.commit()

    return {"success": True, "message": "카드가 삭제되었습니다."}


@router.post("/change-card", response_model=BillingSetupResponse)
async def change_billing_card(
    request: BillingSetupRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """카드 변경 (기존 카드 삭제 후 새 카드 등록)"""
    # 새 카드 등록과 동일한 로직
    return await setup_billing_card(request, db, current_user)


# ==================== 구독 관리 API ====================

@router.get("/subscription", response_model=SubscriptionManageResponse)
async def get_subscription_manage(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """구독 관리 정보 조회"""
    stmt = select(Subscription).where(
        Subscription.user_id == current_user.id,
        Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING, SubscriptionStatus.PAST_DUE])
    )
    result = await db.execute(stmt)
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(status_code=404, detail="활성 구독이 없습니다.")

    # 플랜 정보 로드
    await db.refresh(subscription, ["plan"])

    is_trialing = (
        subscription.status == SubscriptionStatus.TRIALING or
        (subscription.trial_end and datetime.utcnow() < subscription.trial_end)
    )

    next_billing_date = None
    if not subscription.cancel_at_period_end and subscription.billing_key:
        next_billing_date = subscription.current_period_end

    return SubscriptionManageResponse(
        id=str(subscription.id),
        plan_name=subscription.plan.name if subscription.plan else "Unknown",
        plan_price=subscription.plan.price_monthly if subscription.plan else 0,
        status=subscription.status.value,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        next_billing_date=next_billing_date,
        cancel_at_period_end=subscription.cancel_at_period_end,
        has_card=subscription.billing_key is not None,
        card_company=subscription.card_company,
        card_number_last4=subscription.card_number_last4,
        trial_end=subscription.trial_end,
        is_trialing=is_trialing
    )


@router.post("/subscription/cancel", response_model=CancelSubscriptionResponse)
async def cancel_subscription(
    request: CancelSubscriptionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    구독 해지

    - immediate=False: 기간 종료 시 해지 (기본값)
    - immediate=True: 즉시 해지 + 미사용 기간 환불
    """
    stmt = select(Subscription).where(
        Subscription.user_id == current_user.id,
        Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING])
    )
    result = await db.execute(stmt)
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(status_code=404, detail="활성 구독이 없습니다.")

    now = datetime.utcnow()

    if request.immediate:
        # 즉시 해지 + 환불
        refund_amount = 0

        # 환불 금액 계산 (일할 계산)
        if subscription.plan:
            total_days = (subscription.current_period_end - subscription.current_period_start).days
            used_days = (now - subscription.current_period_start).days
            remaining_days = max(0, total_days - used_days)

            if remaining_days > 0 and total_days > 0:
                daily_price = subscription.plan.price_monthly / 30
                refund_amount = int(daily_price * remaining_days)

        # 구독 즉시 해지
        subscription.status = SubscriptionStatus.CANCELLED
        subscription.cancelled_at = now
        subscription.current_period_end = now

        # TODO: 실제 환불 처리 (가장 최근 결제 찾아서 환불)

        await db.commit()

        return CancelSubscriptionResponse(
            success=True,
            message="구독이 즉시 해지되었습니다.",
            refund_amount=refund_amount,
            cancel_at=now
        )
    else:
        # 기간 종료 시 해지
        subscription.cancel_at_period_end = True
        subscription.cancelled_at = now

        # 다음 알림에서 자동결제 안 되도록
        subscription.renewal_notice_sent = True

        await db.commit()

        return CancelSubscriptionResponse(
            success=True,
            message=f"구독이 {subscription.current_period_end.strftime('%Y년 %m월 %d일')}에 해지됩니다.",
            cancel_at=subscription.current_period_end
        )


@router.post("/subscription/reactivate")
async def reactivate_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """해지 예정 구독 재활성화"""
    stmt = select(Subscription).where(
        Subscription.user_id == current_user.id,
        Subscription.cancel_at_period_end == True,
        Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING])
    )
    result = await db.execute(stmt)
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(status_code=404, detail="해지 예정인 구독이 없습니다.")

    subscription.cancel_at_period_end = False
    subscription.cancelled_at = None
    subscription.renewal_notice_sent = False

    await db.commit()

    return {"success": True, "message": "구독이 재활성화되었습니다."}


# ==================== 정기결제 수동 실행 (관리자용) ====================

@router.post("/charge/{subscription_id}")
async def manual_charge_subscription(
    subscription_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    수동 정기결제 실행 (관리자 또는 테스트용)
    """
    # 관리자 확인
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")

    stmt = select(Subscription).where(Subscription.id == subscription_id)
    result = await db.execute(stmt)
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(status_code=404, detail="구독을 찾을 수 없습니다.")

    if not subscription.billing_key:
        raise HTTPException(status_code=400, detail="등록된 결제수단이 없습니다.")

    # 플랜 정보 로드
    await db.refresh(subscription, ["plan"])

    if not subscription.plan:
        raise HTTPException(status_code=400, detail="플랜 정보를 찾을 수 없습니다.")

    # 결제 실행
    order_id = f"renewal_{subscription.id}_{int(datetime.utcnow().timestamp())}"

    charge_result = await toss_service.billing_payment(
        billing_key=subscription.billing_key,
        customer_key=subscription.customer_key,
        amount=subscription.plan.price_monthly,
        order_id=order_id,
        order_name=f"{subscription.plan.name} 플랜 정기결제"
    )

    if charge_result.get("success"):
        # 결제 성공
        now = datetime.utcnow()

        # 구독 기간 갱신
        subscription.current_period_start = now
        subscription.current_period_end = now + timedelta(days=30)
        subscription.retry_count = 0
        subscription.renewal_notice_sent = False
        subscription.status = SubscriptionStatus.ACTIVE

        # 결제 기록
        payment = Payment(
            id=uuid.uuid4(),
            user_id=subscription.user_id,
            subscription_id=subscription.id,
            amount=subscription.plan.price_monthly,
            status=PaymentStatus.COMPLETED,
            payment_method="card",
            payment_method_detail=f"{subscription.card_company} {subscription.card_number_last4}",
            pg_provider="tosspayments",
            pg_payment_key=charge_result.get("payment_key"),
            pg_order_id=order_id,
            description=f"{subscription.plan.name} 플랜 정기결제",
            paid_at=now
        )
        db.add(payment)

        await db.commit()

        return {
            "success": True,
            "message": "정기결제가 완료되었습니다.",
            "payment_key": charge_result.get("payment_key"),
            "amount": subscription.plan.price_monthly
        }
    else:
        # 결제 실패
        subscription.retry_count += 1
        subscription.last_retry_at = datetime.utcnow()

        if subscription.retry_count >= 3:
            subscription.status = SubscriptionStatus.PAST_DUE

        await db.commit()

        return {
            "success": False,
            "message": charge_result.get("error", "결제에 실패했습니다."),
            "retry_count": subscription.retry_count
        }
