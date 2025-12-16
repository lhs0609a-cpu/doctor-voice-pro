"""ROI 트래커 모델 - 전환 추적 및 ROI 분석"""
from sqlalchemy import Column, String, DateTime, Integer, Float, Text, ForeignKey, Enum, Date, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid as uuid_pkg
import enum

from app.db.database import Base
from app.models.user import GUID


class EventType(str, enum.Enum):
    """전환 이벤트 유형"""
    VIEW = "view"              # 조회
    INQUIRY = "inquiry"        # 상담 문의
    VISIT = "visit"            # 내원
    RESERVATION = "reservation" # 예약


class ConversionEvent(Base):
    """전환 이벤트 - 조회, 상담, 내원 등 추적"""
    __tablename__ = "conversion_events"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    post_id = Column(GUID(), ForeignKey("posts.id"), nullable=True, index=True)

    keyword = Column(String(200), nullable=True, index=True)  # 관련 키워드
    event_type = Column(Enum(EventType), nullable=False, index=True)
    source = Column(String(50), nullable=True)  # blog, place, sns
    channel = Column(String(50), nullable=True)  # naver_blog, naver_place, instagram, etc.

    revenue = Column(Integer, nullable=True)  # 매출액 (원)
    cost = Column(Integer, nullable=True)  # 마케팅 비용 (원)

    customer_id = Column(String(100), nullable=True)  # 익명화된 고객 ID
    notes = Column(Text, nullable=True)  # 메모

    event_date = Column(Date, nullable=False, index=True)  # 이벤트 발생일
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="conversion_events")
    post = relationship("Post", backref="conversion_events")


class ROISummary(Base):
    """ROI 요약 - 월별 집계"""
    __tablename__ = "roi_summaries"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)

    year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False, index=True)

    # 전환 수치
    total_views = Column(Integer, default=0)
    total_inquiries = Column(Integer, default=0)
    total_visits = Column(Integer, default=0)
    total_reservations = Column(Integer, default=0)

    # 재무 수치
    total_revenue = Column(Integer, default=0)  # 총 매출
    total_cost = Column(Integer, default=0)  # 총 마케팅 비용

    # 전환율
    conversion_rate_view_to_inquiry = Column(Float, default=0)  # 조회→상담
    conversion_rate_inquiry_to_visit = Column(Float, default=0)  # 상담→내원
    conversion_rate_visit_to_reservation = Column(Float, default=0)  # 내원→예약
    overall_conversion_rate = Column(Float, default=0)  # 전체 전환율

    # ROI
    roi_percentage = Column(Float, default=0)  # (매출-비용)/비용 * 100

    # 분석 데이터 (JSON)
    top_keywords = Column(JSON, default=list)  # 상위 전환 키워드
    channel_breakdown = Column(JSON, default=dict)  # 채널별 분석
    source_breakdown = Column(JSON, default=dict)  # 소스별 분석
    daily_breakdown = Column(JSON, default=list)  # 일별 분석

    calculated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="roi_summaries")


class KeywordROI(Base):
    """키워드별 ROI 분석"""
    __tablename__ = "keyword_rois"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)

    keyword = Column(String(200), nullable=False, index=True)

    # 기간
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    # 전환 수치
    views = Column(Integer, default=0)
    inquiries = Column(Integer, default=0)
    visits = Column(Integer, default=0)
    reservations = Column(Integer, default=0)

    # 재무 수치
    revenue = Column(Integer, default=0)
    cost = Column(Integer, default=0)

    # ROI
    roi_percentage = Column(Float, default=0)  # (매출-비용)/비용 * 100
    revenue_per_conversion = Column(Float, default=0)  # 전환당 매출
    cost_per_conversion = Column(Float, default=0)  # 전환당 비용

    # 전환율
    conversion_rate = Column(Float, default=0)  # 조회→최종전환

    # 분석
    rank = Column(Integer, nullable=True)  # 성과 순위
    trend = Column(String(20), nullable=True)  # up, down, stable

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="keyword_rois")


class FunnelStage(Base):
    """퍼널 단계별 데이터"""
    __tablename__ = "funnel_stages"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)

    date = Column(Date, nullable=False, index=True)

    # 각 단계별 수치
    stage_view = Column(Integer, default=0)
    stage_inquiry = Column(Integer, default=0)
    stage_visit = Column(Integer, default=0)
    stage_reservation = Column(Integer, default=0)

    # 단계별 이탈률
    drop_off_view_inquiry = Column(Float, default=0)
    drop_off_inquiry_visit = Column(Float, default=0)
    drop_off_visit_reservation = Column(Float, default=0)

    # 채널별 분류
    channel = Column(String(50), nullable=True, index=True)
    source = Column(String(50), nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="funnel_stages")


class MarketingCost(Base):
    """마케팅 비용 기록"""
    __tablename__ = "marketing_costs"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)

    date = Column(Date, nullable=False, index=True)
    channel = Column(String(50), nullable=False, index=True)  # naver_blog, place_ad, etc.

    cost = Column(Integer, default=0)  # 비용 (원)
    description = Column(String(500), nullable=True)  # 설명

    # 분류
    cost_type = Column(String(50), nullable=True)  # ad, content, agency, etc.
    campaign_name = Column(String(200), nullable=True)  # 캠페인명

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="marketing_costs")
