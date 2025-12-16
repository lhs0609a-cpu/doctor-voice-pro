"""플레이스 리뷰 관리 모델"""
from sqlalchemy import Column, String, DateTime, Integer, Float, Text, ForeignKey, Enum, Date, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid as uuid_pkg
import enum

from app.db.database import Base
from app.models.user import GUID


class Sentiment(str, enum.Enum):
    """감성 분석 결과"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class PlaceReview(Base):
    """플레이스 리뷰"""
    __tablename__ = "place_reviews"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    place_id = Column(GUID(), ForeignKey("naver_places.id"), nullable=False, index=True)

    # 리뷰 기본 정보
    review_id = Column(String(100), nullable=False, unique=True, index=True)  # 네이버 리뷰 ID
    author_name = Column(String(100), nullable=True)
    author_id = Column(String(100), nullable=True)  # 익명화된 작성자 ID

    # 리뷰 내용
    rating = Column(Integer, nullable=True)  # 1-5
    content = Column(Text, nullable=True)
    images = Column(JSON, default=list)  # 리뷰 이미지 URL

    # 방문 정보
    visit_date = Column(Date, nullable=True)
    written_at = Column(DateTime, nullable=True)

    # 감성 분석
    sentiment = Column(Enum(Sentiment), nullable=True)
    sentiment_score = Column(Float, default=0)  # -1 to 1
    keywords = Column(JSON, default=list)  # 추출된 키워드
    topics = Column(JSON, default=list)  # 주제 (서비스, 시설, 직원 등)

    # 답변
    is_replied = Column(Boolean, default=False)
    reply_content = Column(Text, nullable=True)
    replied_at = Column(DateTime, nullable=True)
    reply_by = Column(String(100), nullable=True)  # 답변 작성자

    # 플래그
    is_urgent = Column(Boolean, default=False)  # 부정 리뷰 긴급 플래그
    is_pinned = Column(Boolean, default=False)  # 고정된 리뷰
    is_hidden = Column(Boolean, default=False)  # 숨김 처리
    needs_attention = Column(Boolean, default=False)  # 관리자 확인 필요

    # 리뷰 유형
    review_type = Column(String(50), default="visitor")  # visitor, blog

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    place = relationship("NaverPlace", backref="reviews")


class ReviewAlert(Base):
    """리뷰 알림 설정"""
    __tablename__ = "review_alerts"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    place_id = Column(GUID(), ForeignKey("naver_places.id"), nullable=True, index=True)

    # 알림 유형
    alert_type = Column(String(50), nullable=False)  # new_review, negative_review, keyword_mention, rating_drop

    # 알림 채널
    channels = Column(JSON, default=list)  # ["email", "kakao", "sms", "push"]

    # 조건 설정
    keywords = Column(JSON, default=list)  # 모니터링 키워드
    rating_threshold = Column(Integer, default=3)  # 알림 기준 별점 (이하일 때)

    # 상태
    is_active = Column(Boolean, default=True)

    # 통계
    last_triggered_at = Column(DateTime, nullable=True)
    trigger_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="review_alerts")
    place = relationship("NaverPlace", backref="review_alerts")


class ReviewReplyTemplate(Base):
    """리뷰 답변 템플릿"""
    __tablename__ = "review_reply_templates"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)

    # 템플릿 정보
    name = Column(String(100), nullable=False)
    sentiment_type = Column(Enum(Sentiment), nullable=True)  # 해당 감성에 사용
    category = Column(String(50), nullable=True)  # 카테고리 (감사, 사과, 설명 등)

    # 템플릿 내용
    template_content = Column(Text, nullable=False)
    variables = Column(JSON, default=list)  # {customer_name}, {visit_date}, {specialty} 등

    # 사용 통계
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)

    # 상태
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)  # 기본 템플릿 여부

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="review_templates")


class ReviewAnalytics(Base):
    """리뷰 분석 통계"""
    __tablename__ = "review_analytics"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    place_id = Column(GUID(), ForeignKey("naver_places.id"), nullable=False, index=True)

    # 기간
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    # 기본 통계
    total_reviews = Column(Integer, default=0)
    new_reviews = Column(Integer, default=0)
    avg_rating = Column(Float, default=0)
    rating_change = Column(Float, default=0)  # 이전 대비 변화

    # 감성 분포
    positive_count = Column(Integer, default=0)
    negative_count = Column(Integer, default=0)
    neutral_count = Column(Integer, default=0)

    # 답변 통계
    replied_count = Column(Integer, default=0)
    reply_rate = Column(Float, default=0)  # 답변율
    avg_reply_time_hours = Column(Float, default=0)  # 평균 답변 시간

    # 키워드/주제 분석
    top_keywords = Column(JSON, default=list)  # 상위 키워드
    top_topics = Column(JSON, default=dict)  # 주제별 빈도
    top_complaints = Column(JSON, default=list)  # 주요 불만사항

    # 트렌드
    rating_trend = Column(JSON, default=list)  # 일별/주별 평점 트렌드
    review_trend = Column(JSON, default=list)  # 일별/주별 리뷰 수 트렌드

    calculated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    place = relationship("NaverPlace", backref="review_analytics")


class GeneratedReply(Base):
    """AI 생성 답변 기록"""
    __tablename__ = "generated_replies"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    review_id = Column(GUID(), ForeignKey("place_reviews.id"), nullable=False, index=True)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)

    # 생성된 답변
    generated_content = Column(Text, nullable=False)
    tone = Column(String(50), nullable=True)  # professional, friendly, empathetic

    # AI 분석
    detected_issues = Column(JSON, default=list)  # 감지된 문제점
    suggested_actions = Column(JSON, default=list)  # 제안된 후속 조치

    # 사용 여부
    is_used = Column(Boolean, default=False)
    used_at = Column(DateTime, nullable=True)
    modified_content = Column(Text, nullable=True)  # 수정 후 사용된 내용

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    review = relationship("PlaceReview", backref="generated_replies")
    user = relationship("User", backref="generated_replies")
