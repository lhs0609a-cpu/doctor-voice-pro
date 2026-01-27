"""
결제 API (토스페이먼츠 연동)
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID
import httpx
import base64
import os
import uuid as uuid_pkg

from app.db.database import get_db
from app.api.deps import get_current_user
from app.models import User
from app.models.subscription import (
    Payment, PaymentStatus, Subscription, SubscriptionStatus,
    CreditTransaction, UserCredit
)

router = APIRouter()

# 토스페이먼츠 설정
TOSS_API_URL = "https://api.tosspayments.com/v1"
TOSS_SECRET_KEY = os.getenv("TOSS_SECRET_KEY", "")
TOSS_CLIENT_KEY = os.getenv("TOSS_CLIENT_KEY", "")


def get_toss_auth_header() -> str:
    """토스 인증 헤더 생성"""
    if not TOSS_SECRET_KEY:
        return ""
    encoded = base64.b64encode(f"{TOSS_SECRET_KEY}:".encode()).decode()
    return f"Basic {encoded}"


def _get_user_friendly_payment_error(error_code: str, original_message: str) -> tuple[str, bool]:
    """
    P0-4 Fix: 토스 에러 코드를 사용자 친화적 메시지로 변환

    Returns:
        (user_message, can_retry) - 사용자 메시지와 재시도 가능 여부
    """
    # 토스페이먼츠 에러 코드별 처리
    # 참고: https://docs.tosspayments.com/reference/error-codes
    error_messages = {
        # 카드 관련 에러
        "CARD_DECLINED": ("카드 승인이 거절되었습니다. 다른 카드로 시도해주세요.", True),
        "CARD_LIMIT_EXCEEDED": ("카드 한도가 초과되었습니다. 한도를 확인하거나 다른 카드를 사용해주세요.", True),
        "CARD_LOST_OR_STOLEN": ("분실 또는 도난 신고된 카드입니다. 카드사에 문의해주세요.", False),
        "CARD_RESTRICTED": ("사용이 제한된 카드입니다. 카드사에 문의해주세요.", False),
        "CARD_COMPANY_ERROR": ("카드사 시스템 오류입니다. 잠시 후 다시 시도해주세요.", True),
        "INVALID_CARD_NUMBER": ("카드 번호가 올바르지 않습니다. 다시 확인해주세요.", True),
        "INVALID_EXPIRY_DATE": ("카드 유효기간이 올바르지 않습니다. 다시 확인해주세요.", True),
        "INVALID_PASSWORD": ("카드 비밀번호가 올바르지 않습니다.", True),

        # 결제 관련 에러
        "ALREADY_PROCESSED_PAYMENT": ("이미 처리된 결제입니다.", False),
        "EXCEED_MAX_AMOUNT": ("결제 금액이 최대 한도를 초과했습니다.", False),
        "BELOW_MIN_AMOUNT": ("결제 금액이 최소 금액 미만입니다.", False),
        "INVALID_REQUEST": ("잘못된 요청입니다. 다시 시도해주세요.", True),
        "NOT_FOUND_PAYMENT": ("결제 정보를 찾을 수 없습니다.", False),
        "CANCELED_PAYMENT": ("취소된 결제입니다.", False),

        # 인증 관련 에러
        "UNAUTHORIZED_KEY": ("인증에 실패했습니다. 관리자에게 문의해주세요.", False),
        "INVALID_API_KEY": ("결제 설정 오류입니다. 관리자에게 문의해주세요.", False),

        # 일반 에러
        "PROVIDER_ERROR": ("결제사 시스템 오류입니다. 잠시 후 다시 시도해주세요.", True),
        "FAILED_INTERNAL_SYSTEM_PROCESSING": ("시스템 오류가 발생했습니다. 잠시 후 다시 시도해주세요.", True),
    }

    if error_code in error_messages:
        return error_messages[error_code]

    # 알 수 없는 에러 코드인 경우
    if "카드" in original_message or "card" in original_message.lower():
        return (f"카드 결제에 실패했습니다: {original_message}", True)
    elif "한도" in original_message or "limit" in original_message.lower():
        return ("결제 한도를 초과했습니다. 다른 결제 수단을 이용해주세요.", True)

    return (f"결제에 실패했습니다: {original_message}", True)


# ==================== Schemas ====================

class PaymentIntentRequest(BaseModel):
    amount: int
    order_name: str
    subscription_id: Optional[str] = None
    metadata: Optional[dict] = None


class PaymentIntentResponse(BaseModel):
    payment_id: UUID
    order_id: str
    amount: int
    order_name: str
    client_key: str


class ConfirmPaymentRequest(BaseModel):
    payment_key: str
    order_id: str
    amount: int


class PaymentResponse(BaseModel):
    id: UUID
    amount: int
    status: PaymentStatus
    payment_method: Optional[str]
    payment_method_detail: Optional[str]
    description: Optional[str]
    receipt_url: Optional[str]
    paid_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class CancelPaymentRequest(BaseModel):
    cancel_reason: str
    refund_amount: Optional[int] = None


class BillingKeyRequest(BaseModel):
    customer_key: str
    auth_key: str


class BillingChargeRequest(BaseModel):
    billing_key: str
    amount: int
    order_name: str
    customer_key: str


class CreditPurchaseRequest(BaseModel):
    credit_type: str  # 'post' or 'analysis'
    amount: int  # 구매할 크레딧 수량


# ==================== Endpoints ====================

@router.get("/config")
async def get_payment_config():
    """결제 설정 정보 (클라이언트용)"""
    return {
        "client_key": TOSS_CLIENT_KEY,
        "success_url": os.getenv("PAYMENT_SUCCESS_URL", "http://localhost:3000/payment/success"),
        "fail_url": os.getenv("PAYMENT_FAIL_URL", "http://localhost:3000/payment/fail")
    }


@router.post("/intent", response_model=PaymentIntentResponse)
async def create_payment_intent(
    request: PaymentIntentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """결제 의도 생성 (클라이언트에서 결제 전 호출)"""
    order_id = f"order_{uuid_pkg.uuid4().hex[:20]}"

    payment = Payment(
        user_id=current_user.id,
        subscription_id=UUID(request.subscription_id) if request.subscription_id else None,
        amount=request.amount,
        status=PaymentStatus.PENDING,
        pg_provider="tosspayments",
        pg_order_id=order_id,
        description=request.order_name,
        extra_data=request.metadata  # P0-4 Fix: Model uses extra_data, not metadata
    )

    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    return PaymentIntentResponse(
        payment_id=payment.id,
        order_id=order_id,
        amount=request.amount,
        order_name=request.order_name,
        client_key=TOSS_CLIENT_KEY
    )


@router.post("/confirm", response_model=PaymentResponse)
async def confirm_payment(
    request: ConfirmPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """결제 승인 (클라이언트 결제 완료 후 호출)"""
    # 먼저 DB에서 결제 조회하여 금액 검증 (금액 변조 방지)
    payment_result = await db.execute(
        select(Payment)
        .where(
            and_(
                Payment.pg_order_id == request.order_id,
                Payment.user_id == current_user.id
            )
        )
    )
    payment = payment_result.scalar_one_or_none()

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="결제 정보를 찾을 수 없습니다"
        )

    # 금액 검증 (클라이언트에서 전송된 금액과 DB의 원본 금액 비교)
    if payment.amount != request.amount:
        # P0-4 Fix: 금액 불일치 시 결제 상태 업데이트
        payment.status = PaymentStatus.FAILED
        payment.extra_data = {"error": "amount_mismatch", "expected": payment.amount, "received": request.amount}
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "amount_mismatch",
                "message": "결제 금액이 일치하지 않습니다. 다시 시도해주세요.",
                "can_retry": True
            }
        )

    # 이미 완료된 결제인지 확인 (중복 처리 방지)
    if payment.status == PaymentStatus.COMPLETED:
        return payment

    # P0-4 Fix: 이미 실패한 결제는 재시도 불가
    if payment.status == PaymentStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "payment_already_failed",
                "message": "이 결제는 이미 실패했습니다. 새로운 결제를 시도해주세요.",
                "can_retry": False
            }
        )

    # 토스페이먼츠에 결제 승인 요청
    headers = {
        "Authorization": get_toss_auth_header(),
        "Content-Type": "application/json"
    }

    data = {
        "paymentKey": request.payment_key,
        "orderId": request.order_id,
        "amount": request.amount
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{TOSS_API_URL}/payments/confirm",
                headers=headers,
                json=data
            )
        except httpx.TimeoutException:
            # P0-4 Fix: 타임아웃 시 결제 상태를 PENDING으로 유지하고 재시도 허용
            payment.extra_data = {"error": "timeout", "message": "결제 확인 중 타임아웃이 발생했습니다"}
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail={
                    "error": "payment_timeout",
                    "message": "결제 처리 중 응답이 지연되고 있습니다. 잠시 후 결제 내역을 확인해주세요.",
                    "can_retry": True,
                    "check_status_url": f"/api/payments/{payment.id}"
                }
            )
        except httpx.RequestError as e:
            # P0-4 Fix: 네트워크 오류 시
            payment.extra_data = {"error": "network_error", "message": str(e)}
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": "payment_network_error",
                    "message": "결제 서버와의 통신에 문제가 발생했습니다. 잠시 후 다시 시도해주세요.",
                    "can_retry": True
                }
            )

        if response.status_code >= 400:
            error_data = response.json()
            # P0-4 Fix: 토스 에러 코드에 따른 상세 처리
            toss_error_code = error_data.get("code", "UNKNOWN")
            toss_error_message = error_data.get("message", "결제 승인에 실패했습니다")

            # 결제 실패 상태 업데이트
            payment.status = PaymentStatus.FAILED
            payment.extra_data = {
                "error": toss_error_code,
                "message": toss_error_message,
                "toss_response": error_data
            }
            await db.commit()

            # 사용자 친화적 에러 메시지 생성
            user_message, can_retry = _get_user_friendly_payment_error(toss_error_code, toss_error_message)

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": toss_error_code,
                    "message": user_message,
                    "can_retry": can_retry,
                    "original_message": toss_error_message
                }
            )

        result = response.json()

    # 결제 정보 업데이트
    payment.pg_payment_key = request.payment_key
    payment.pg_transaction_id = result.get("transactionKey")
    payment.status = PaymentStatus.COMPLETED
    payment.paid_at = datetime.utcnow()
    payment.receipt_url = result.get("receipt", {}).get("url")

    # 결제 수단 정보
    method = result.get("method")
    payment.payment_method = method

    if method == "카드":
        card = result.get("card", {})
        payment.payment_method_detail = f"{card.get('company')} {card.get('number', '')[-4:]}"
    elif method == "가상계좌":
        va = result.get("virtualAccount", {})
        payment.payment_method_detail = f"{va.get('bankCode')} {va.get('accountNumber')}"

    # 구독이 연결된 경우 활성화
    if payment.subscription_id:
        sub_result = await db.execute(
            select(Subscription)
            .where(Subscription.id == payment.subscription_id)
        )
        subscription = sub_result.scalar_one_or_none()

        if subscription:
            subscription.status = SubscriptionStatus.ACTIVE
            if subscription.trial_end and datetime.utcnow() < subscription.trial_end:
                subscription.trial_end = datetime.utcnow()

    await db.commit()
    await db.refresh(payment)

    return payment


@router.post("/{payment_id}/cancel", response_model=PaymentResponse)
async def cancel_payment(
    payment_id: UUID,
    request: CancelPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """결제 취소/환불"""
    # 결제 조회
    payment_result = await db.execute(
        select(Payment)
        .where(
            and_(
                Payment.id == payment_id,
                Payment.user_id == current_user.id
            )
        )
    )
    payment = payment_result.scalar_one_or_none()

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="결제 정보를 찾을 수 없습니다"
        )

    if payment.status != PaymentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="완료된 결제만 취소할 수 있습니다"
        )

    # 환불 금액 검증
    refund_amount = request.refund_amount or (payment.amount - payment.refunded_amount)

    if refund_amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="환불 금액은 0보다 커야 합니다"
        )

    max_refundable = payment.amount - payment.refunded_amount
    if refund_amount > max_refundable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"환불 가능 금액({max_refundable}원)을 초과했습니다"
        )

    # 토스페이먼츠에 취소 요청
    headers = {
        "Authorization": get_toss_auth_header(),
        "Content-Type": "application/json"
    }

    data = {"cancelReason": request.cancel_reason}
    if refund_amount < payment.amount - payment.refunded_amount:
        data["cancelAmount"] = refund_amount

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{TOSS_API_URL}/payments/{payment.pg_payment_key}/cancel",
            headers=headers,
            json=data
        )

        if response.status_code >= 400:
            error_data = response.json()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_data.get("message", "결제 취소에 실패했습니다")
            )

    # 환불 정보 업데이트
    payment.refunded_amount += refund_amount
    payment.refunded_at = datetime.utcnow()
    payment.refund_reason = request.cancel_reason

    if payment.refunded_amount >= payment.amount:
        payment.status = PaymentStatus.REFUNDED

    await db.commit()
    await db.refresh(payment)

    return payment


@router.get("/history", response_model=List[PaymentResponse])
async def get_payment_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[PaymentStatus] = None,
    limit: int = 20,
    offset: int = 0
):
    """결제 내역 조회"""
    query = select(Payment).where(Payment.user_id == current_user.id)

    if status_filter:
        query = query.where(Payment.status == status_filter)

    result = await db.execute(
        query.order_by(Payment.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    payments = result.scalars().all()

    return payments


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """결제 상세 조회"""
    result = await db.execute(
        select(Payment)
        .where(
            and_(
                Payment.id == payment_id,
                Payment.user_id == current_user.id
            )
        )
    )
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="결제 정보를 찾을 수 없습니다"
        )

    return payment


# ==================== 빌링 (정기결제) ====================

@router.post("/billing/issue")
async def issue_billing_key(
    request: BillingKeyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """빌링키 발급 (정기결제용)"""
    headers = {
        "Authorization": get_toss_auth_header(),
        "Content-Type": "application/json"
    }

    data = {
        "customerKey": request.customer_key,
        "authKey": request.auth_key
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{TOSS_API_URL}/billing/authorizations/issue",
            headers=headers,
            json=data
        )

        if response.status_code >= 400:
            error_data = response.json()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_data.get("message", "빌링키 발급에 실패했습니다")
            )

        result = response.json()

    return {
        "billing_key": result.get("billingKey"),
        "card_company": result.get("card", {}).get("company"),
        "card_number": result.get("card", {}).get("number"),
        "customer_key": request.customer_key
    }


@router.post("/billing/charge", response_model=PaymentResponse)
async def charge_billing(
    request: BillingChargeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """빌링키로 자동결제"""
    order_id = f"billing_{uuid_pkg.uuid4().hex[:16]}"

    # 결제 레코드 생성
    payment = Payment(
        user_id=current_user.id,
        amount=request.amount,
        status=PaymentStatus.PENDING,
        pg_provider="tosspayments",
        pg_order_id=order_id,
        description=request.order_name,
        payment_method="card"
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    # 토스페이먼츠에 결제 요청
    headers = {
        "Authorization": get_toss_auth_header(),
        "Content-Type": "application/json",
        "Idempotency-Key": order_id
    }

    data = {
        "customerKey": request.customer_key,
        "amount": request.amount,
        "orderId": order_id,
        "orderName": request.order_name
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TOSS_API_URL}/billing/{request.billing_key}",
                headers=headers,
                json=data
            )

            if response.status_code >= 400:
                error_data = response.json()
                payment.status = PaymentStatus.FAILED
                payment.extra_data = {"error": error_data}
                await db.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_data.get("message", "자동결제에 실패했습니다")
                )

            result = response.json()

        # 결제 성공
        payment.pg_payment_key = result.get("paymentKey")
        payment.pg_transaction_id = result.get("transactionKey")
        payment.status = PaymentStatus.COMPLETED
        payment.paid_at = datetime.utcnow()
        payment.receipt_url = result.get("receipt", {}).get("url")

        card = result.get("card", {})
        payment.payment_method_detail = f"{card.get('company')} {card.get('number', '')[-4:]}"

    except HTTPException:
        raise
    except Exception as e:
        payment.status = PaymentStatus.FAILED
        payment.extra_data = {"error": str(e)}

    await db.commit()
    await db.refresh(payment)

    return payment


# ==================== 크레딧 구매 ====================

@router.post("/credits/purchase")
async def purchase_credits(
    request: CreditPurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """크레딧 구매 정보 생성"""
    # 크레딧 가격 (개당)
    CREDIT_PRICES = {
        "post": 500,  # 글 생성 크레딧
        "analysis": 100  # 분석 크레딧
    }

    if request.credit_type not in CREDIT_PRICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 크레딧 타입입니다"
        )

    price_per_credit = CREDIT_PRICES[request.credit_type]
    total_amount = price_per_credit * request.amount

    order_id = f"credit_{uuid_pkg.uuid4().hex[:16]}"

    # 결제 레코드 생성 (P0-4 Fix: metadata -> extra_data로 수정)
    payment = Payment(
        user_id=current_user.id,
        amount=total_amount,
        status=PaymentStatus.PENDING,
        pg_provider="tosspayments",
        pg_order_id=order_id,
        description=f"{'글 생성' if request.credit_type == 'post' else '분석'} 크레딧 {request.amount}개",
        extra_data={
            "credit_type": request.credit_type,
            "credit_amount": request.amount
        }
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    return {
        "payment_id": str(payment.id),
        "order_id": order_id,
        "amount": total_amount,
        "order_name": payment.description,
        "client_key": TOSS_CLIENT_KEY,
        "credit_type": request.credit_type,
        "credit_amount": request.amount
    }


@router.post("/credits/confirm")
async def confirm_credit_purchase(
    request: ConfirmPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """크레딧 구매 결제 승인"""
    # P0-4 Fix: 결제 정보 먼저 조회
    payment_result = await db.execute(
        select(Payment)
        .where(
            and_(
                Payment.pg_order_id == request.order_id,
                Payment.user_id == current_user.id
            )
        )
    )
    payment = payment_result.scalar_one_or_none()

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="결제 정보를 찾을 수 없습니다"
        )

    # 이미 완료된 결제인지 확인
    if payment.status == PaymentStatus.COMPLETED:
        # 이미 크레딧이 지급된 상태
        credit_result = await db.execute(
            select(UserCredit)
            .where(UserCredit.user_id == current_user.id)
        )
        user_credit = credit_result.scalar_one_or_none()
        return {
            "success": True,
            "credit_type": payment.extra_data.get("credit_type") if payment.extra_data else "unknown",
            "credit_added": payment.extra_data.get("credit_amount") if payment.extra_data else 0,
            "new_balance": user_credit.post_credits if payment.extra_data.get("credit_type") == "post" else user_credit.analysis_credits if user_credit else 0,
            "receipt_url": payment.receipt_url,
            "message": "이미 처리된 결제입니다."
        }

    # 결제 승인
    headers = {
        "Authorization": get_toss_auth_header(),
        "Content-Type": "application/json"
    }

    data = {
        "paymentKey": request.payment_key,
        "orderId": request.order_id,
        "amount": request.amount
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{TOSS_API_URL}/payments/confirm",
                headers=headers,
                json=data
            )
        except httpx.TimeoutException:
            # P0-4 Fix: 타임아웃 처리
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail={
                    "error": "payment_timeout",
                    "message": "결제 처리 중 응답이 지연되고 있습니다. 잠시 후 결제 내역을 확인해주세요.",
                    "can_retry": True
                }
            )
        except httpx.RequestError as e:
            # P0-4 Fix: 네트워크 오류
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": "payment_network_error",
                    "message": "결제 서버와의 통신에 문제가 발생했습니다. 잠시 후 다시 시도해주세요.",
                    "can_retry": True
                }
            )

        if response.status_code >= 400:
            error_data = response.json()
            # P0-4 Fix: 결제 실패 상태 업데이트
            toss_error_code = error_data.get("code", "UNKNOWN")
            toss_error_message = error_data.get("message", "결제 승인에 실패했습니다")

            payment.status = PaymentStatus.FAILED
            payment.extra_data = {
                **(payment.extra_data or {}),
                "error": toss_error_code,
                "error_message": toss_error_message
            }
            await db.commit()

            user_message, can_retry = _get_user_friendly_payment_error(toss_error_code, toss_error_message)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": toss_error_code,
                    "message": user_message,
                    "can_retry": can_retry
                }
            )

        result = response.json()

    # 결제 정보 업데이트 (payment 객체는 이미 조회됨)
    payment.pg_payment_key = request.payment_key
    payment.pg_transaction_id = result.get("transactionKey")
    payment.status = PaymentStatus.COMPLETED
    payment.paid_at = datetime.utcnow()
    payment.receipt_url = result.get("receipt", {}).get("url")

    method = result.get("method")
    payment.payment_method = method

    if method == "카드":
        card = result.get("card", {})
        payment.payment_method_detail = f"{card.get('company')} {card.get('number', '')[-4:]}"

    # 크레딧 추가 (P0-4 Fix: extra_data에서 조회하도록 통일)
    credit_type = (payment.extra_data or {}).get("credit_type")
    credit_amount = (payment.extra_data or {}).get("credit_amount")

    # UserCredit 조회 또는 생성
    credit_result = await db.execute(
        select(UserCredit)
        .where(UserCredit.user_id == current_user.id)
    )
    user_credit = credit_result.scalar_one_or_none()

    if not user_credit:
        user_credit = UserCredit(user_id=current_user.id)
        db.add(user_credit)
        await db.flush()

    # 크레딧 추가
    if credit_type == "post":
        user_credit.post_credits += credit_amount
        balance_after = user_credit.post_credits
    else:
        user_credit.analysis_credits += credit_amount
        balance_after = user_credit.analysis_credits

    # 거래 기록
    transaction = CreditTransaction(
        user_id=current_user.id,
        payment_id=payment.id,
        transaction_type="purchase",
        credit_type=credit_type,
        amount=credit_amount,
        balance_after=balance_after,
        description=f"크레딧 구매 ({credit_amount}개)"
    )
    db.add(transaction)

    await db.commit()

    return {
        "success": True,
        "credit_type": credit_type,
        "credit_added": credit_amount,
        "new_balance": balance_after,
        "receipt_url": payment.receipt_url
    }


# ==================== 웹훅 (토스페이먼츠 콜백) ====================

import hmac
import hashlib

TOSS_WEBHOOK_SECRET = os.getenv("TOSS_WEBHOOK_SECRET", "")


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """토스페이먼츠 웹훅 서명 검증"""
    if not TOSS_WEBHOOK_SECRET:
        # 시크릿이 설정되지 않은 경우 (개발 환경)
        return True

    expected = hmac.new(
        TOSS_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


@router.post("/webhook")
async def toss_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """토스페이먼츠 웹훅 처리"""
    # 웹훅 서명 검증
    body = await request.body()
    signature = request.headers.get("Toss-Signature", "")

    if TOSS_WEBHOOK_SECRET and not verify_webhook_signature(body, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON"
        )

    event_type = data.get("eventType")
    payment_key = data.get("data", {}).get("paymentKey")
    order_id = data.get("data", {}).get("orderId")

    if not order_id:
        return {"status": "ignored"}

    # 결제 조회
    payment_result = await db.execute(
        select(Payment)
        .where(Payment.pg_order_id == order_id)
    )
    payment = payment_result.scalar_one_or_none()

    if not payment:
        return {"status": "payment_not_found"}

    # 이벤트 처리
    if event_type == "PAYMENT_STATUS_CHANGED":
        status_data = data.get("data", {}).get("status")

        if status_data == "DONE":
            payment.status = PaymentStatus.COMPLETED
            payment.paid_at = datetime.utcnow()
        elif status_data == "CANCELED":
            payment.status = PaymentStatus.CANCELLED
        elif status_data == "PARTIAL_CANCELED":
            pass  # refunded_amount는 cancel API에서 처리
        elif status_data == "ABORTED" or status_data == "EXPIRED":
            payment.status = PaymentStatus.FAILED

    elif event_type == "VIRTUAL_ACCOUNT_DEPOSIT_COMPLETED":
        # 가상계좌 입금 완료
        payment.status = PaymentStatus.COMPLETED
        payment.paid_at = datetime.utcnow()

        # 구독 활성화
        if payment.subscription_id:
            sub_result = await db.execute(
                select(Subscription)
                .where(Subscription.id == payment.subscription_id)
            )
            subscription = sub_result.scalar_one_or_none()

            if subscription:
                subscription.status = SubscriptionStatus.ACTIVE

    await db.commit()

    return {"status": "ok"}
