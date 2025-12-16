"""경쟁 병원 분석 모델"""
from sqlalchemy import Column, String, DateTime, Integer, Float, Text, ForeignKey, Date, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid as uuid_pkg

from app.db.database import Base
from app.models.user import GUID


class Competitor(Base):
    """경쟁 병원"""
    __tablename__ = "competitors"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)

    # 플레이스 기본 정보
    place_id = Column(String(100), nullable=False, index=True)  # 경쟁사 플레이스 ID
    place_name = Column(String(200), nullable=False)
    place_url = Column(String(500), nullable=True)

    # 카테고리 및 위치
    category = Column(String(100), nullable=True)
    address = Column(String(500), nullable=True)
    phone = Column(String(50), nullable=True)

    # 거리
    distance_km = Column(Float, nullable=True)  # 내 병원과의 거리
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # 기본 통계 (최근 스냅샷)
    review_count = Column(Integer, default=0)
    avg_rating = Column(Float, default=0)
    visitor_review_count = Column(Integer, default=0)
    blog_review_count = Column(Integer, default=0)
    save_count = Column(Integer, default=0)

    # 탐지 정보
    is_auto_detected = Column(Boolean, default=False)  # 자동 탐지 여부
    detection_reason = Column(String(200), nullable=True)  # 탐지 이유 (동일 지역, 동일 진료과 등)
    similarity_score = Column(Float, default=0)  # 유사도 점수

    # 모니터링 설정
    is_active = Column(Boolean, default=True)  # 모니터링 활성화
    priority = Column(Integer, default=0)  # 우선순위 (높을수록 중요)

    # 분석 메모
    notes = Column(Text, nullable=True)
    strengths = Column(JSON, default=list)  # 강점
    weaknesses = Column(JSON, default=list)  # 약점

    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="competitors")
    snapshots = relationship("CompetitorSnapshot", back_populates="competitor", cascade="all, delete-orphan")
    alerts = relationship("CompetitorAlert", back_populates="competitor", cascade="all, delete-orphan")


class CompetitorSnapshot(Base):
    """경쟁사 스냅샷 - 주기적 수집"""
    __tablename__ = "competitor_snapshots"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    competitor_id = Column(GUID(), ForeignKey("competitors.id"), nullable=False, index=True)

    # 기본 통계
    review_count = Column(Integer, default=0)
    avg_rating = Column(Float, default=0)
    visitor_review_count = Column(Integer, default=0)
    blog_review_count = Column(Integer, default=0)
    save_count = Column(Integer, default=0)

    # 변동 (전일 대비)
    review_count_change = Column(Integer, default=0)
    rating_change = Column(Float, default=0)

    # 최근 리뷰 요약
    recent_reviews = Column(JSON, default=list)  # 최근 5개 리뷰 요약
    recent_positive_keywords = Column(JSON, default=list)  # 최근 긍정 키워드
    recent_negative_keywords = Column(JSON, default=list)  # 최근 부정 키워드

    # 랭킹 (해당 키워드 검색 시)
    ranking_data = Column(JSON, default=dict)  # {"키워드": 순위}

    snapshot_date = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    competitor = relationship("Competitor", back_populates="snapshots")


class CompetitorAlert(Base):
    """경쟁사 변동 알림"""
    __tablename__ = "competitor_alerts"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    competitor_id = Column(GUID(), ForeignKey("competitors.id"), nullable=False, index=True)

    # 알림 유형
    alert_type = Column(String(50), nullable=False)  # review_surge, rating_change, new_event, ranking_change

    # 알림 내용
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    data = Column(JSON, default=dict)  # 상세 데이터

    # 중요도
    severity = Column(String(20), default="info")  # info, warning, critical

    # 상태
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    competitor = relationship("Competitor", back_populates="alerts")


class CompetitorComparison(Base):
    """경쟁사 비교 분석 리포트"""
    __tablename__ = "competitor_comparisons"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)

    # 비교 대상
    my_place_id = Column(GUID(), ForeignKey("naver_places.id"), nullable=True)
    competitor_ids = Column(JSON, default=list)  # 비교 대상 경쟁사 ID 목록

    # 기간
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    # 비교 결과
    comparison_data = Column(JSON, default=dict)  # 상세 비교 데이터

    # 점수 비교
    my_score = Column(JSON, default=dict)  # {"rating": 4.5, "reviews": 100, ...}
    competitor_scores = Column(JSON, default=dict)  # {"competitor_id": {"rating": 4.2, ...}}

    # 랭킹
    overall_ranking = Column(Integer, nullable=True)  # 전체 순위
    category_ranking = Column(Integer, nullable=True)  # 카테고리 내 순위

    # AI 분석
    strengths_analysis = Column(JSON, default=list)  # 강점 분석
    weaknesses_analysis = Column(JSON, default=list)  # 약점 분석
    opportunities = Column(JSON, default=list)  # 기회 요소
    threats = Column(JSON, default=list)  # 위협 요소
    recommendations = Column(JSON, default=list)  # 개선 권고사항

    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="competitor_comparisons")
    my_place = relationship("NaverPlace", backref="comparisons")


class WeeklyCompetitorReport(Base):
    """주간 경쟁 리포트"""
    __tablename__ = "weekly_competitor_reports"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)

    # 기간
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)
    year = Column(Integer, nullable=False)
    week_number = Column(Integer, nullable=False)

    # 요약
    summary = Column(Text, nullable=True)  # AI 생성 요약

    # 주요 변동사항
    significant_changes = Column(JSON, default=list)  # 중요 변동사항 목록

    # 통계 비교
    my_stats = Column(JSON, default=dict)
    competitor_stats = Column(JSON, default=dict)
    market_average = Column(JSON, default=dict)  # 시장 평균

    # 리뷰 트렌드
    review_trends = Column(JSON, default=dict)
    sentiment_comparison = Column(JSON, default=dict)

    # 키워드 분석
    trending_keywords = Column(JSON, default=list)  # 트렌딩 키워드
    competitor_keywords = Column(JSON, default=list)  # 경쟁사 주요 키워드

    # 권고사항
    action_items = Column(JSON, default=list)

    # 이메일 발송 상태
    is_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)

    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="weekly_competitor_reports")
