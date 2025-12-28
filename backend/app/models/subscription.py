"""
구독 및 결제 관련 모델
"""

from sqlalchemy import Column, String, DateTime, Integer, Float, Boolean, ForeignKey, Text, Enum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid as uuid_pkg

from app.db.database import Base
from app.models.user import GUID


class PlanType(str, enum.Enum):
    """플랜 타입"""
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    BUSINESS = "business"


class PaymentStatus(str, enum.Enum):
    """결제 상태"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class SubscriptionStatus(str, enum.Enum):
    """구독 상태"""
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PAST_DUE = "past_due"
    TRIALING = "trialing"


class UsageType(str, enum.Enum):
    """사용량 타입"""
    POST_GENERATION = "post_generation"  # 글 생성
    TOP_POST_ANALYSIS = "top_post_analysis"  # 상위노출 분석
    KEYWORD_RESEARCH = "keyword_research"  # 키워드 연구
    AI_REWRITE = "ai_rewrite"  # AI 리라이트


class Plan(Base):
    """구독 플랜 정의"""
    __tablename__ = "plans"

    id = Column(String(50), primary_key=True)  # free, starter, pro, business
    name = Column(String(100), nullable=False)  # 표시 이름
    description = Column(Text)

    # 가격
    price_monthly = Column(Integer, default=0)  # 월 가격 (원)
    price_yearly = Column(Integer, default=0)  # 연 가격 (원)

    # 기능 제한
    posts_per_month = Column(Integer, default=3)  # 월 글 생성 수
    analysis_per_month = Column(Integer, default=10)  # 월 상위노출 분석 수
    keywords_per_month = Column(Integer, default=20)  # 월 키워드 연구 수

    # 추가 기능
    has_api_access = Column(Boolean, default=False)  # API 접근 권한
    has_priority_support = Column(Boolean, default=False)  # 우선 지원
    has_advanced_analytics = Column(Boolean, default=False)  # 고급 분석
    has_team_features = Column(Boolean, default=False)  # 팀 기능

    # 초과 사용 가격
    extra_post_price = Column(Integer, default=500)  # 추가 글당 가격
    extra_analysis_price = Column(Integer, default=100)  # 추가 분석당 가격

    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    subscriptions = relationship("Subscription", back_populates="plan")


class Subscription(Base):
    """사용자 구독 정보"""
    __tablename__ = "subscriptions"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    plan_id = Column(String(50), ForeignKey("plans.id"), nullable=False)

    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE)

    # 구독 기간
    current_period_start = Column(DateTime, nullable=False)
    current_period_end = Column(DateTime, nullable=False)

    # 결제 정보
    payment_method = Column(String(50))  # card, bank_transfer, etc.
    billing_key = Column(String(255))  # 정기결제용 빌링키
    customer_key = Column(String(255))  # 토스페이먼츠 고객키

    # 카드 정보 (표시용)
    card_company = Column(String(50))  # 카드사
    card_number_last4 = Column(String(4))  # 카드 끝 4자리

    # 취소 관련
    cancel_at_period_end = Column(Boolean, default=False)
    cancelled_at = Column(DateTime)

    # 트라이얼
    trial_start = Column(DateTime)
    trial_end = Column(DateTime)

    # 정기결제 재시도
    retry_count = Column(Integer, default=0)  # 결제 재시도 횟수
    last_retry_at = Column(DateTime)  # 마지막 재시도 시간

    # 결제 예정 알림
    renewal_notice_sent = Column(Boolean, default=False)
    renewal_notice_sent_at = Column(DateTime)

    # 메타데이터
    extra_data = Column(JSON)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", backref="subscriptions")
    plan = relationship("Plan", back_populates="subscriptions")
    payments = relationship("Payment", back_populates="subscription")


class UsageLog(Base):
    """사용량 기록"""
    __tablename__ = "usage_logs"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    subscription_id = Column(GUID(), ForeignKey("subscriptions.id"))

    usage_type = Column(Enum(UsageType), nullable=False)
    quantity = Column(Integer, default=1)

    # 관련 리소스 ID
    resource_id = Column(String(255))  # 글 ID, 분석 ID 등
    resource_type = Column(String(50))  # post, analysis, keyword

    # 비용 (초과 사용 시)
    cost = Column(Integer, default=0)  # 원
    is_extra = Column(Boolean, default=False)  # 초과 사용 여부

    # 기간 정보
    period_start = Column(DateTime)
    period_end = Column(DateTime)

    extra_data = Column(JSON)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", backref="usage_logs")
    subscription = relationship("Subscription", backref="usage_logs")


class UsageSummary(Base):
    """월별 사용량 요약"""
    __tablename__ = "usage_summaries"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    subscription_id = Column(GUID(), ForeignKey("subscriptions.id"))

    # 기간
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)

    # 사용량
    posts_used = Column(Integer, default=0)
    posts_limit = Column(Integer, default=0)
    analysis_used = Column(Integer, default=0)
    analysis_limit = Column(Integer, default=0)
    keywords_used = Column(Integer, default=0)
    keywords_limit = Column(Integer, default=0)

    # 초과 사용
    extra_posts = Column(Integer, default=0)
    extra_analysis = Column(Integer, default=0)
    extra_cost = Column(Integer, default=0)  # 총 초과 비용

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", backref="usage_summaries")


class Payment(Base):
    """결제 내역"""
    __tablename__ = "payments"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    subscription_id = Column(GUID(), ForeignKey("subscriptions.id"))

    # 결제 정보
    amount = Column(Integer, nullable=False)  # 결제 금액 (원)
    currency = Column(String(10), default="KRW")
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)

    # 결제 수단
    payment_method = Column(String(50))  # card, bank_transfer, etc.
    payment_method_detail = Column(String(100))  # 카드사, 은행명 등

    # PG사 정보 (토스페이먼츠)
    pg_provider = Column(String(50), default="tosspayments")
    pg_payment_key = Column(String(255))  # 토스 paymentKey
    pg_order_id = Column(String(255), unique=True)  # 주문 ID
    pg_transaction_id = Column(String(255))  # 거래 ID

    # 결제 상세
    description = Column(String(500))
    receipt_url = Column(String(500))

    # 환불 정보
    refunded_amount = Column(Integer, default=0)
    refunded_at = Column(DateTime)
    refund_reason = Column(String(500))

    # 메타데이터
    extra_data = Column(JSON)

    paid_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", backref="payments")
    subscription = relationship("Subscription", back_populates="payments")


class CreditTransaction(Base):
    """크레딧 거래 내역 (추가 구매용)"""
    __tablename__ = "credit_transactions"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    payment_id = Column(GUID(), ForeignKey("payments.id"))

    # 거래 정보
    transaction_type = Column(String(20))  # purchase, use, refund, expire
    credit_type = Column(String(20))  # post, analysis
    amount = Column(Integer, nullable=False)  # 크레딧 수량 (양수: 충전, 음수: 사용)
    balance_after = Column(Integer)  # 거래 후 잔액

    description = Column(String(500))
    expires_at = Column(DateTime)  # 만료일 (충전 시)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", backref="credit_transactions")
    payment = relationship("Payment", backref="credit_transactions")


class UserCredit(Base):
    """사용자 크레딧 잔액"""
    __tablename__ = "user_credits"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, unique=True)

    # 크레딧 잔액
    post_credits = Column(Integer, default=0)  # 글 생성 크레딧
    analysis_credits = Column(Integer, default=0)  # 분석 크레딧

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", backref="credits", uselist=False)
