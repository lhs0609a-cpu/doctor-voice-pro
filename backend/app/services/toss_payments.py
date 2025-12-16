"""
토스페이먼츠 결제 연동 서비스
"""

import httpx
import base64
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from app.core.config import settings


class TossPaymentsService:
    """토스페이먼츠 결제 서비스"""

    BASE_URL = "https://api.tosspayments.com/v1"

    def __init__(self):
        # 시크릿 키 (서버용)
        self.secret_key = getattr(settings, 'TOSS_SECRET_KEY', '')
        # 클라이언트 키 (프론트엔드용)
        self.client_key = getattr(settings, 'TOSS_CLIENT_KEY', '')

        # Basic Auth 헤더 생성
        if self.secret_key:
            auth_string = f"{self.secret_key}:"
            self.auth_header = base64.b64encode(auth_string.encode()).decode()
        else:
            self.auth_header = None

    def _get_headers(self) -> Dict[str, str]:
        """API 요청 헤더"""
        return {
            "Authorization": f"Basic {self.auth_header}",
            "Content-Type": "application/json"
        }

    def generate_order_id(self, prefix: str = "order") -> str:
        """고유 주문 ID 생성"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"{prefix}_{timestamp}_{unique_id}"

    async def confirm_payment(
        self,
        payment_key: str,
        order_id: str,
        amount: int
    ) -> Dict[str, Any]:
        """
        결제 승인
        프론트엔드에서 결제 완료 후 호출
        """
        if not self.auth_header:
            return {"success": False, "error": "토스페이먼츠 API 키가 설정되지 않았습니다."}

        url = f"{self.BASE_URL}/payments/confirm"
        payload = {
            "paymentKey": payment_key,
            "orderId": order_id,
            "amount": amount
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "data": data,
                        "payment_key": data.get("paymentKey"),
                        "order_id": data.get("orderId"),
                        "status": data.get("status"),
                        "method": data.get("method"),
                        "total_amount": data.get("totalAmount"),
                        "receipt_url": data.get("receipt", {}).get("url"),
                        "approved_at": data.get("approvedAt")
                    }
                else:
                    error_data = response.json()
                    return {
                        "success": False,
                        "error": error_data.get("message", "결제 승인 실패"),
                        "code": error_data.get("code")
                    }
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def cancel_payment(
        self,
        payment_key: str,
        cancel_reason: str,
        cancel_amount: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        결제 취소/환불
        """
        if not self.auth_header:
            return {"success": False, "error": "토스페이먼츠 API 키가 설정되지 않았습니다."}

        url = f"{self.BASE_URL}/payments/{payment_key}/cancel"
        payload = {"cancelReason": cancel_reason}

        if cancel_amount:
            payload["cancelAmount"] = cancel_amount

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "data": data,
                        "cancel_amount": data.get("cancels", [{}])[0].get("cancelAmount"),
                        "cancelled_at": data.get("cancels", [{}])[0].get("canceledAt")
                    }
                else:
                    error_data = response.json()
                    return {
                        "success": False,
                        "error": error_data.get("message", "결제 취소 실패"),
                        "code": error_data.get("code")
                    }
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def get_payment(self, payment_key: str) -> Dict[str, Any]:
        """결제 정보 조회"""
        if not self.auth_header:
            return {"success": False, "error": "토스페이먼츠 API 키가 설정되지 않았습니다."}

        url = f"{self.BASE_URL}/payments/{payment_key}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    headers=self._get_headers(),
                    timeout=30.0
                )

                if response.status_code == 200:
                    return {"success": True, "data": response.json()}
                else:
                    error_data = response.json()
                    return {
                        "success": False,
                        "error": error_data.get("message", "조회 실패")
                    }
            except Exception as e:
                return {"success": False, "error": str(e)}

    # ==================== 빌링 (정기결제) ====================

    async def issue_billing_key(
        self,
        customer_key: str,
        auth_key: str
    ) -> Dict[str, Any]:
        """
        빌링키 발급 (카드 등록)
        프론트엔드에서 카드 인증 후 authKey를 받아 호출
        """
        if not self.auth_header:
            return {"success": False, "error": "토스페이먼츠 API 키가 설정되지 않았습니다."}

        url = f"{self.BASE_URL}/billing/authorizations/issue"
        payload = {
            "customerKey": customer_key,
            "authKey": auth_key
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "billing_key": data.get("billingKey"),
                        "customer_key": data.get("customerKey"),
                        "card_company": data.get("card", {}).get("issuerCode"),
                        "card_number": data.get("card", {}).get("number"),
                        "card_type": data.get("card", {}).get("cardType")
                    }
                else:
                    error_data = response.json()
                    return {
                        "success": False,
                        "error": error_data.get("message", "빌링키 발급 실패")
                    }
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def billing_payment(
        self,
        billing_key: str,
        customer_key: str,
        amount: int,
        order_id: str,
        order_name: str
    ) -> Dict[str, Any]:
        """
        빌링키로 자동 결제
        정기결제 실행 시 호출
        """
        if not self.auth_header:
            return {"success": False, "error": "토스페이먼츠 API 키가 설정되지 않았습니다."}

        url = f"{self.BASE_URL}/billing/{billing_key}"
        payload = {
            "customerKey": customer_key,
            "amount": amount,
            "orderId": order_id,
            "orderName": order_name
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "data": data,
                        "payment_key": data.get("paymentKey"),
                        "order_id": data.get("orderId"),
                        "status": data.get("status"),
                        "total_amount": data.get("totalAmount"),
                        "approved_at": data.get("approvedAt")
                    }
                else:
                    error_data = response.json()
                    return {
                        "success": False,
                        "error": error_data.get("message", "결제 실패"),
                        "code": error_data.get("code")
                    }
            except Exception as e:
                return {"success": False, "error": str(e)}


# 크레딧 팩 정의
CREDIT_PACKS = {
    "post_10": {
        "id": "post_10",
        "name": "글 생성 크레딧 10회",
        "credit_type": "post",
        "amount": 10,
        "price": 9900,
        "discount_rate": 0
    },
    "post_50": {
        "id": "post_50",
        "name": "글 생성 크레딧 50회",
        "credit_type": "post",
        "amount": 50,
        "price": 39900,
        "discount_rate": 20,
        "original_price": 49500
    },
    "post_100": {
        "id": "post_100",
        "name": "글 생성 크레딧 100회",
        "credit_type": "post",
        "amount": 100,
        "price": 69900,
        "discount_rate": 30,
        "original_price": 99000
    },
    "analysis_50": {
        "id": "analysis_50",
        "name": "분석 크레딧 50회",
        "credit_type": "analysis",
        "amount": 50,
        "price": 9900,
        "discount_rate": 0
    },
    "analysis_200": {
        "id": "analysis_200",
        "name": "분석 크레딧 200회",
        "credit_type": "analysis",
        "amount": 200,
        "price": 29900,
        "discount_rate": 25,
        "original_price": 39600
    }
}


# 플랜 정의
PLANS = {
    "free": {
        "id": "free",
        "name": "무료",
        "description": "기본 기능을 무료로 체험해보세요",
        "price_monthly": 0,
        "price_yearly": 0,
        "posts_per_month": 3,
        "analysis_per_month": 10,
        "keywords_per_month": 20,
        "features": [
            "월 3회 글 생성",
            "월 10회 상위노출 분석",
            "월 20회 키워드 연구",
            "기본 SEO 분석"
        ],
        "has_api_access": False,
        "has_priority_support": False,
        "has_advanced_analytics": False,
        "has_team_features": False
    },
    "starter": {
        "id": "starter",
        "name": "스타터",
        "description": "개인 병원 마케팅에 적합한 플랜",
        "price_monthly": 29000,
        "price_yearly": 290000,
        "posts_per_month": 30,
        "analysis_per_month": 50,
        "keywords_per_month": 100,
        "features": [
            "월 30회 글 생성",
            "월 50회 상위노출 분석",
            "월 100회 키워드 연구",
            "SNS 연동",
            "예약 발행",
            "이메일 지원"
        ],
        "has_api_access": False,
        "has_priority_support": False,
        "has_advanced_analytics": True,
        "has_team_features": False
    },
    "pro": {
        "id": "pro",
        "name": "프로",
        "description": "전문적인 마케팅이 필요한 병원에 추천",
        "price_monthly": 79000,
        "price_yearly": 790000,
        "posts_per_month": 100,
        "analysis_per_month": -1,  # 무제한
        "keywords_per_month": -1,  # 무제한
        "features": [
            "월 100회 글 생성",
            "무제한 상위노출 분석",
            "무제한 키워드 연구",
            "플레이스 최적화",
            "ROI 추적",
            "경쟁사 분석",
            "리뷰 관리",
            "우선 지원"
        ],
        "has_api_access": False,
        "has_priority_support": True,
        "has_advanced_analytics": True,
        "has_team_features": False,
        "recommended": True
    },
    "enterprise": {
        "id": "enterprise",
        "name": "엔터프라이즈",
        "description": "대형 병원 및 네트워크에 최적화",
        "price_monthly": 199000,
        "price_yearly": 1990000,
        "posts_per_month": -1,  # 무제한
        "analysis_per_month": -1,
        "keywords_per_month": -1,
        "features": [
            "무제한 글 생성",
            "무제한 모든 분석",
            "API 연동",
            "전담 매니저",
            "커스텀 리포트",
            "팀 협업 기능",
            "멀티 브랜드 관리",
            "SLA 보장"
        ],
        "has_api_access": True,
        "has_priority_support": True,
        "has_advanced_analytics": True,
        "has_team_features": True
    }
}
