"""리뷰 이벤트/캠페인 관리 모델"""
from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey, Enum, Date, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid as uuid_pkg
import enum

from app.db.database import Base
from app.models.user import GUID


class CampaignStatus(str, enum.Enum):
    """캠페인 상태"""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


class RewardType(str, enum.Enum):
    """보상 유형"""
    DISCOUNT = "discount"  # 할인
    GIFT = "gift"  # 사은품
    POINT = "point"  # 포인트
    CASH = "cash"  # 현금
    COUPON = "coupon"  # 쿠폰


class ReviewCampaign(Base):
    """리뷰 이벤트/캠페인"""
    __tablename__ = "review_campaigns"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    place_id = Column(GUID(), ForeignKey("naver_places.id"), nullable=True, index=True)

    # 캠페인 기본 정보
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    terms = Column(Text, nullable=True)  # 참여 약관

    # 보상 정보
    reward_type = Column(Enum(RewardType), nullable=False)
    reward_description = Column(String(500), nullable=False)
    reward_value = Column(Integer, nullable=True)  # 보상 금액/수량

    # 기간
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    # 목표
    target_count = Column(Integer, default=0)  # 목표 리뷰 수
    current_count = Column(Integer, default=0)  # 현재 리뷰 수
    verified_count = Column(Integer, default=0)  # 검증된 리뷰 수

    # 참여 조건
    min_rating = Column(Integer, default=1)  # 최소 별점
    min_content_length = Column(Integer, default=0)  # 최소 글자 수
    require_photo = Column(Boolean, default=False)  # 사진 필수 여부

    # QR/링크
    qr_code_url = Column(String(500), nullable=True)
    short_url = Column(String(200), nullable=True)
    landing_page_url = Column(String(500), nullable=True)

    # 상태
    status = Column(Enum(CampaignStatus), default=CampaignStatus.DRAFT)

    # 통계
    total_views = Column(Integer, default=0)  # 페이지 조회수
    total_clicks = Column(Integer, default=0)  # 클릭수
    conversion_rate = Column(Integer, default=0)  # 전환율

    # 예산
    total_budget = Column(Integer, default=0)  # 총 예산
    spent_budget = Column(Integer, default=0)  # 사용 예산

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="review_campaigns")
    place = relationship("NaverPlace", backref="review_campaigns")
    participations = relationship("CampaignParticipation", back_populates="campaign", cascade="all, delete-orphan")


class CampaignParticipation(Base):
    """캠페인 참여"""
    __tablename__ = "campaign_participations"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    campaign_id = Column(GUID(), ForeignKey("review_campaigns.id"), nullable=False, index=True)

    # 참여자 정보 (익명화)
    customer_name = Column(String(100), nullable=True)
    customer_phone_hash = Column(String(256), nullable=True)  # 해시 처리된 전화번호
    customer_email_hash = Column(String(256), nullable=True)  # 해시 처리된 이메일

    # 참여 정보
    participation_code = Column(String(50), nullable=True, unique=True)  # 참여 코드
    source = Column(String(50), nullable=True)  # qr, link, direct

    # 리뷰 정보
    review_url = Column(String(500), nullable=True)
    review_content = Column(Text, nullable=True)  # 리뷰 내용 (검증용)
    review_rating = Column(Integer, nullable=True)
    review_date = Column(DateTime, nullable=True)

    # 검증
    is_verified = Column(Boolean, default=False)
    verified_at = Column(DateTime, nullable=True)
    verification_method = Column(String(50), nullable=True)  # auto, manual
    verification_notes = Column(Text, nullable=True)

    # 보상
    reward_given = Column(Boolean, default=False)
    reward_given_at = Column(DateTime, nullable=True)
    reward_amount = Column(Integer, nullable=True)
    reward_notes = Column(String(500), nullable=True)

    # 상태
    status = Column(String(50), default="pending")  # pending, verified, rejected, rewarded

    participated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    campaign = relationship("ReviewCampaign", back_populates="participations")


class CampaignTemplate(Base):
    """캠페인 템플릿"""
    __tablename__ = "campaign_templates"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=True, index=True)  # null이면 시스템 템플릿

    # 템플릿 정보
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)  # seasonal, special, regular

    # 기본 설정
    default_duration_days = Column(Integer, default=30)
    default_reward_type = Column(Enum(RewardType), nullable=True)
    default_reward_description = Column(String(500), nullable=True)

    # 디자인
    template_data = Column(JSON, default=dict)  # 디자인/설정 데이터
    thumbnail_url = Column(String(500), nullable=True)

    # 사용 통계
    usage_count = Column(Integer, default=0)

    # 상태
    is_active = Column(Boolean, default=True)
    is_public = Column(Boolean, default=False)  # 공개 템플릿 여부

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="campaign_templates")


class CampaignAnalytics(Base):
    """캠페인 분석"""
    __tablename__ = "campaign_analytics"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    campaign_id = Column(GUID(), ForeignKey("review_campaigns.id"), nullable=False, index=True)

    # 날짜
    date = Column(Date, nullable=False, index=True)

    # 트래픽
    views = Column(Integer, default=0)
    unique_visitors = Column(Integer, default=0)
    clicks = Column(Integer, default=0)

    # 참여
    participations = Column(Integer, default=0)
    verifications = Column(Integer, default=0)
    rewards_given = Column(Integer, default=0)

    # 전환율
    click_rate = Column(Integer, default=0)  # 조회 대비 클릭률
    conversion_rate = Column(Integer, default=0)  # 클릭 대비 참여율
    verification_rate = Column(Integer, default=0)  # 참여 대비 검증률

    # 소스별 분석
    source_breakdown = Column(JSON, default=dict)  # {"qr": 10, "link": 5}

    # 시간대별 분석
    hourly_breakdown = Column(JSON, default=dict)  # {"09": 5, "10": 3}

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    campaign = relationship("ReviewCampaign", backref="analytics")


class ReviewRewardHistory(Base):
    """리뷰 보상 이력"""
    __tablename__ = "review_reward_histories"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    campaign_id = Column(GUID(), ForeignKey("review_campaigns.id"), nullable=True, index=True)
    participation_id = Column(GUID(), ForeignKey("campaign_participations.id"), nullable=True, index=True)

    # 보상 정보
    reward_type = Column(Enum(RewardType), nullable=False)
    reward_description = Column(String(500), nullable=False)
    reward_value = Column(Integer, nullable=True)

    # 수령자 정보
    recipient_name = Column(String(100), nullable=True)
    recipient_contact = Column(String(100), nullable=True)

    # 지급 상태
    status = Column(String(50), default="pending")  # pending, completed, cancelled
    completed_at = Column(DateTime, nullable=True)

    # 비용 처리
    cost = Column(Integer, default=0)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="reward_histories")
    campaign = relationship("ReviewCampaign", backref="reward_histories")
    participation = relationship("CampaignParticipation", backref="reward_history")
