"""플레이스 검색 순위 추적 모델"""
from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid as uuid_pkg

from app.db.database import Base
from app.models.user import GUID


class PlaceKeyword(Base):
    """추적 키워드"""
    __tablename__ = "place_keywords"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    place_id = Column(GUID(), ForeignKey("naver_places.id"), nullable=False, index=True)

    # 키워드 정보
    keyword = Column(String(200), nullable=False, index=True)
    search_type = Column(String(50), default="place")  # place, blog, integrated

    # 키워드 분류
    category = Column(String(100), nullable=True)  # specialty, location, service, etc.
    priority = Column(Integer, default=0)  # 중요도

    # 현재 순위 (최근 체크 기준)
    current_rank = Column(Integer, nullable=True)  # null이면 순위권 밖
    best_rank = Column(Integer, nullable=True)  # 역대 최고 순위
    worst_rank = Column(Integer, nullable=True)  # 역대 최저 순위

    # 변동
    rank_change = Column(Integer, default=0)  # 전일 대비 변동 (+/-)
    trend = Column(String(20), default="stable")  # up, down, stable, new

    # 검색량 추정
    estimated_search_volume = Column(Integer, default=0)  # 월간 예상 검색량
    competition_level = Column(String(20), nullable=True)  # low, medium, high

    # 상태
    is_active = Column(Boolean, default=True)

    # 마지막 체크
    last_checked_at = Column(DateTime, nullable=True)
    check_frequency = Column(String(20), default="daily")  # hourly, daily, weekly

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="place_keywords")
    place = relationship("NaverPlace", backref="tracked_keywords")
    rankings = relationship("PlaceRanking", back_populates="keyword", cascade="all, delete-orphan")
    alerts = relationship("RankingAlert", back_populates="keyword", cascade="all, delete-orphan")


class PlaceRanking(Base):
    """순위 기록"""
    __tablename__ = "place_rankings"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    keyword_id = Column(GUID(), ForeignKey("place_keywords.id"), nullable=False, index=True)

    # 순위
    rank = Column(Integer, nullable=True)  # null이면 100위 밖
    total_results = Column(Integer, default=0)  # 전체 검색 결과 수

    # 상위 경쟁사
    top_competitors = Column(JSON, default=list)  # 상위 10개 플레이스 정보

    # 검색 메타
    search_type = Column(String(50), nullable=True)  # pc, mobile
    region = Column(String(100), nullable=True)  # 검색 지역

    # 상세 정보
    snippet = Column(String(500), nullable=True)  # 검색 결과 스니펫
    display_info = Column(JSON, default=dict)  # 표시 정보 (이미지, 태그 등)

    checked_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    keyword = relationship("PlaceKeyword", back_populates="rankings")


class RankingAlert(Base):
    """순위 변동 알림"""
    __tablename__ = "ranking_alerts"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    keyword_id = Column(GUID(), ForeignKey("place_keywords.id"), nullable=False, index=True)

    # 변동 정보
    previous_rank = Column(Integer, nullable=True)
    current_rank = Column(Integer, nullable=True)
    change = Column(Integer, nullable=False)  # 변동량 (양수: 순위 하락, 음수: 순위 상승)

    # 알림 유형
    alert_type = Column(String(50), nullable=False)  # rank_up, rank_down, entered_top10, dropped_out

    # 메시지
    message = Column(String(500), nullable=False)

    # 상태
    is_read = Column(Boolean, default=False)
    is_notified = Column(Boolean, default=False)  # 알림 발송 여부
    notified_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    keyword = relationship("PlaceKeyword", back_populates="alerts")


class KeywordRecommendation(Base):
    """키워드 추천"""
    __tablename__ = "keyword_recommendations"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    place_id = Column(GUID(), ForeignKey("naver_places.id"), nullable=True, index=True)

    # 키워드 정보
    keyword = Column(String(200), nullable=False)
    category = Column(String(100), nullable=True)

    # 추천 이유
    recommendation_reason = Column(String(500), nullable=True)
    source = Column(String(50), nullable=True)  # competitor, trending, related, ai

    # 예상 지표
    estimated_search_volume = Column(Integer, default=0)
    estimated_competition = Column(String(20), nullable=True)  # low, medium, high
    estimated_difficulty = Column(Float, default=0)  # 상위 노출 난이도 0-100
    relevance_score = Column(Float, default=0)  # 관련성 점수 0-1

    # 현재 상태
    current_my_rank = Column(Integer, nullable=True)  # 현재 내 순위
    top_rank_place = Column(JSON, default=dict)  # 1위 플레이스 정보

    # 상태
    is_tracked = Column(Boolean, default=False)  # 추적 중 여부
    is_dismissed = Column(Boolean, default=False)  # 무시됨

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)  # 추천 만료일

    # Relationships
    user = relationship("User", backref="keyword_recommendations")
    place = relationship("NaverPlace", backref="keyword_recommendations")


class RankingSummary(Base):
    """순위 요약 (일별)"""
    __tablename__ = "ranking_summaries"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    place_id = Column(GUID(), ForeignKey("naver_places.id"), nullable=False, index=True)

    # 날짜
    summary_date = Column(DateTime, nullable=False, index=True)

    # 전체 통계
    total_keywords = Column(Integer, default=0)
    keywords_in_top10 = Column(Integer, default=0)
    keywords_in_top30 = Column(Integer, default=0)
    keywords_out_of_rank = Column(Integer, default=0)

    # 평균 순위
    avg_rank = Column(Float, nullable=True)
    best_rank = Column(Integer, nullable=True)
    worst_rank = Column(Integer, nullable=True)

    # 변동
    improved_count = Column(Integer, default=0)  # 순위 상승 키워드 수
    declined_count = Column(Integer, default=0)  # 순위 하락 키워드 수
    stable_count = Column(Integer, default=0)  # 순위 유지 키워드 수

    # 키워드별 상세
    keyword_ranks = Column(JSON, default=dict)  # {"키워드": {"rank": 5, "change": -2}}

    # 경쟁사 대비
    competitive_position = Column(JSON, default=dict)  # {"avg_competitor_rank": 10, ...}

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="ranking_summaries")
    place = relationship("NaverPlace", backref="ranking_summaries")
