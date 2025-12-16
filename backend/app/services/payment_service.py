"""
토스페이먼츠 결제 서비스
"""

import httpx
import base64
from datetime import datetime
from typing import Optional, Dict
from sqlalchemy.orm import Session
import uuid
import os

from app.models.subscription import (
    Payment, PaymentStatus, Subscription, SubscriptionStatus
)
from app.services.subscription_service import SubscriptionService


# 토스페이먼츠 API 설정
TOSS_API_URL = "https://api.tosspayments.com/v1"
TOSS_SECRET_KEY = os.getenv("TOSS_SECRET_KEY", "")
TOSS_CLIENT_KEY = os.getenv("TOSS_CLIENT_KEY", "")


class PaymentService:
    """토스페이먼츠 결제 서비스"""

    def __init__(self, db: Session):
        self.db = db
        self.subscription_service = SubscriptionService(db)
        self._auth_header = self._get_auth_header()

    def _get_auth_header(self) -> str:
        """인증 헤더 생성"""
        if not TOSS_SECRET_KEY:
            return ""
        encoded = base64.b64encode(f"{TOSS_SECRET_KEY}:".encode()).decode()
        return f"Basic {encoded}"

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: dict = None,
        idempotency_key: str = None
    ) -> Dict:
        """토스페이먼츠 API 요청"""
        headers = {
            "Authorization": self._auth_header,
            "Content-Type": "application/json"
        }

        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        url = f"{TOSS_API_URL}{endpoint}"

        async with httpx.AsyncClient() as client:
            if method == "GET":
                response = await client.get(url, headers=headers)
            elif method == "POST":
                response = await client.post(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")

            if response.status_code >= 400:
                error_data = response.json()
                raise PaymentError(
                    code=error_data.get("code", "UNKNOWN"),
                    message=error_data.get("message", "결제 처리 중 오류가 발생했습니다")
                )

            return response.json()

    # ==================== 결제 생성 ====================

    def create_payment_intent(
        self,
        user_id: str,
        amount: int,
        order_name: str,
        subscription_id: str = None,
        metadata: dict = None
    ) -> Payment:
        """결제 의도 생성 (클라이언트에서 결제 전 호출)"""
        order_id = f"order_{uuid.uuid4().hex[:20]}"

        payment = Payment(
            user_id=user_id,
            subscription_id=subscription_id,
            amount=amount,
            status=PaymentStatus.PENDING,
            pg_provider="tosspayments",
            pg_order_id=order_id,
            description=order_name,
            metadata=metadata
        )

        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)

        return payment

    async def confirm_payment(
        self,
        payment_key: str,
        order_id: str,
        amount: int
    ) -> Payment:
        """결제 승인 (클라이언트 결제 완료 후 호출)"""
        # 결제 승인 요청
        data = {
            "paymentKey": payment_key,
            "orderId": order_id,
            "amount": amount
        }

        result = await self._request("POST", "/payments/confirm", data)

        # DB에서 결제 조회
        payment = self.db.query(Payment).filter(
            Payment.pg_order_id == order_id
        ).first()

        if not payment:
            raise PaymentError("PAYMENT_NOT_FOUND", "결제 정보를 찾을 수 없습니다")

        # 결제 정보 업데이트
        payment.pg_payment_key = payment_key
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

        # 구독 처리
        if payment.subscription_id:
            self._activate_subscription(payment)

        self.db.commit()
        self.db.refresh(payment)

        return payment

    def _activate_subscription(self, payment: Payment):
        """결제 완료 후 구독 활성화"""
        subscription = self.db.query(Subscription).filter(
            Subscription.id == payment.subscription_id
        ).first()

        if subscription:
            subscription.status = SubscriptionStatus.ACTIVE
            if subscription.trial_end and datetime.utcnow() < subscription.trial_end:
                # 트라이얼 중 결제 시 트라이얼 종료
                subscription.trial_end = datetime.utcnow()

    # ==================== 결제 취소/환불 ====================

    async def cancel_payment(
        self,
        payment_id: str,
        cancel_reason: str,
        refund_amount: int = None
    ) -> Payment:
        """결제 취소"""
        payment = self.db.query(Payment).filter(Payment.id == payment_id).first()

        if not payment:
            raise PaymentError("PAYMENT_NOT_FOUND", "결제 정보를 찾을 수 없습니다")

        if payment.status != PaymentStatus.COMPLETED:
            raise PaymentError("INVALID_STATUS", "완료된 결제만 취소할 수 있습니다")

        # 환불 금액 (없으면 전액)
        refund_amount = refund_amount or (payment.amount - payment.refunded_amount)

        data = {
            "cancelReason": cancel_reason
        }

        if refund_amount < payment.amount - payment.refunded_amount:
            data["cancelAmount"] = refund_amount

        result = await self._request(
            "POST",
            f"/payments/{payment.pg_payment_key}/cancel",
            data
        )

        # 환불 정보 업데이트
        payment.refunded_amount += refund_amount
        payment.refunded_at = datetime.utcnow()
        payment.refund_reason = cancel_reason

        if payment.refunded_amount >= payment.amount:
            payment.status = PaymentStatus.REFUNDED

        self.db.commit()
        self.db.refresh(payment)

        return payment

    # ==================== 정기결제 (빌링) ====================

    async def issue_billing_key(
        self,
        customer_key: str,
        auth_key: str
    ) -> Dict:
        """빌링키 발급 (정기결제용)"""
        data = {
            "customerKey": customer_key,
            "authKey": auth_key
        }

        result = await self._request("POST", "/billing/authorizations/issue", data)

        return {
            "billing_key": result.get("billingKey"),
            "card_company": result.get("card", {}).get("company"),
            "card_number": result.get("card", {}).get("number"),
            "customer_key": customer_key
        }

    async def charge_billing(
        self,
        user_id: str,
        billing_key: str,
        amount: int,
        order_name: str,
        customer_key: str
    ) -> Payment:
        """빌링키로 자동결제"""
        order_id = f"billing_{uuid.uuid4().hex[:16]}"

        # 결제 레코드 생성
        payment = Payment(
            user_id=user_id,
            amount=amount,
            status=PaymentStatus.PENDING,
            pg_provider="tosspayments",
            pg_order_id=order_id,
            description=order_name,
            payment_method="card"
        )
        self.db.add(payment)
        self.db.commit()

        try:
            data = {
                "customerKey": customer_key,
                "amount": amount,
                "orderId": order_id,
                "orderName": order_name
            }

            result = await self._request(
                "POST",
                f"/billing/{billing_key}",
                data,
                idempotency_key=order_id
            )

            # 결제 성공
            payment.pg_payment_key = result.get("paymentKey")
            payment.pg_transaction_id = result.get("transactionKey")
            payment.status = PaymentStatus.COMPLETED
            payment.paid_at = datetime.utcnow()
            payment.receipt_url = result.get("receipt", {}).get("url")

            card = result.get("card", {})
            payment.payment_method_detail = f"{card.get('company')} {card.get('number', '')[-4:]}"

        except PaymentError as e:
            payment.status = PaymentStatus.FAILED
            payment.metadata = {"error": {"code": e.code, "message": e.message}}

        self.db.commit()
        self.db.refresh(payment)

        return payment

    # ==================== 결제 조회 ====================

    def get_payment(self, payment_id: str) -> Optional[Payment]:
        """결제 조회"""
        return self.db.query(Payment).filter(Payment.id == payment_id).first()

    def get_payment_by_order_id(self, order_id: str) -> Optional[Payment]:
        """주문 ID로 결제 조회"""
        return self.db.query(Payment).filter(Payment.pg_order_id == order_id).first()

    def get_user_payments(
        self,
        user_id: str,
        status: PaymentStatus = None,
        limit: int = 20,
        offset: int = 0
    ) -> list:
        """사용자 결제 내역 조회"""
        query = self.db.query(Payment).filter(Payment.user_id == user_id)

        if status:
            query = query.filter(Payment.status == status)

        return query.order_by(Payment.created_at.desc()).offset(offset).limit(limit).all()

    async def get_payment_from_toss(self, payment_key: str) -> Dict:
        """토스에서 결제 정보 조회"""
        return await self._request("GET", f"/payments/{payment_key}")


class PaymentError(Exception):
    """결제 오류"""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def get_payment_service(db: Session) -> PaymentService:
    """서비스 인스턴스 생성"""
    return PaymentService(db)
