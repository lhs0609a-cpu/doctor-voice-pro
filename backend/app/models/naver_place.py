"""네이버 플레이스 모델 - 플레이스 기본 정보 및 최적화"""
from sqlalchemy import Column, String, DateTime, Integer, Float, Text, ForeignKey, Enum, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid as uuid_pkg
import enum

from app.db.database import Base
from app.models.user import GUID


class OptimizationStatus(str, enum.Enum):
    """최적화 체크 상태"""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"


class NaverPlace(Base):
    """네이버 플레이스 기본 정보"""
    __tablename__ = "naver_places"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)

    # 플레이스 기본 정보
    place_id = Column(String(100), nullable=False, index=True)  # 네이버 플레이스 ID
    place_name = Column(String(200), nullable=False)
    place_url = Column(String(500), nullable=True)

    # 카테고리 및 위치
    category = Column(String(100), nullable=True)  # 의료기관 > 피부과 등
    sub_category = Column(String(100), nullable=True)
    address = Column(String(500), nullable=True)
    road_address = Column(String(500), nullable=True)  # 도로명 주소
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # 연락처
    phone = Column(String(50), nullable=True)

    # 운영 정보
    business_hours = Column(JSON, default=dict)  # {"월": "09:00-18:00", ...}
    holidays = Column(JSON, default=list)  # ["일요일", "공휴일"]

    # 미디어
    images = Column(JSON, default=list)  # 이미지 URL 목록
    thumbnail_url = Column(String(500), nullable=True)

    # 소개
    description = Column(Text, nullable=True)
    short_description = Column(String(500), nullable=True)
    tags = Column(JSON, default=list)  # 태그 목록

    # 통계
    review_count = Column(Integer, default=0)
    visitor_review_count = Column(Integer, default=0)  # 방문자 리뷰
    blog_review_count = Column(Integer, default=0)  # 블로그 리뷰
    avg_rating = Column(Float, default=0)
    save_count = Column(Integer, default=0)  # 저장 수

    # 최적화 점수
    optimization_score = Column(Integer, default=0)  # 0-100
    optimization_details = Column(JSON, default=dict)  # 각 항목별 점수

    # 연동 상태
    is_connected = Column(Boolean, default=False)
    connection_method = Column(String(50), nullable=True)  # manual, api
    last_synced_at = Column(DateTime, nullable=True)
    sync_error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="naver_places")
    optimization_checks = relationship("PlaceOptimizationCheck", back_populates="place", cascade="all, delete-orphan")


class PlaceOptimizationCheck(Base):
    """플레이스 최적화 체크리스트"""
    __tablename__ = "place_optimization_checks"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    place_id = Column(GUID(), ForeignKey("naver_places.id"), nullable=False, index=True)

    # 체크 항목
    check_type = Column(String(50), nullable=False)  # basic_info, photos, description, hours, etc.
    check_name = Column(String(200), nullable=False)  # 표시명

    # 상태
    status = Column(Enum(OptimizationStatus), nullable=False)
    score = Column(Integer, default=0)  # 해당 항목 점수

    # 상세
    message = Column(String(500), nullable=True)  # 현재 상태 메시지
    suggestion = Column(Text, nullable=True)  # 개선 제안
    priority = Column(Integer, default=0)  # 우선순위 (높을수록 중요)

    # AI 추천
    ai_suggestion = Column(Text, nullable=True)  # AI 생성 개선안
    ai_example = Column(Text, nullable=True)  # AI 생성 예시

    checked_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    place = relationship("NaverPlace", back_populates="optimization_checks")


class PlaceDescription(Base):
    """AI 생성 소개글 저장"""
    __tablename__ = "place_descriptions"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    place_id = Column(GUID(), ForeignKey("naver_places.id"), nullable=False, index=True)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)

    # 생성된 소개글
    description = Column(Text, nullable=False)
    tone = Column(String(50), nullable=True)  # professional, friendly, casual
    length = Column(String(20), nullable=True)  # short, medium, long

    # 키워드
    keywords_used = Column(JSON, default=list)  # 사용된 키워드
    specialty_focus = Column(String(100), nullable=True)  # 강조된 전문 분야

    # 메타
    is_applied = Column(Boolean, default=False)  # 실제 적용 여부
    applied_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    place = relationship("NaverPlace", backref="generated_descriptions")
    user = relationship("User", backref="place_descriptions")


class PlaceTag(Base):
    """플레이스 태그 추천"""
    __tablename__ = "place_tags"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    place_id = Column(GUID(), ForeignKey("naver_places.id"), nullable=False, index=True)

    tag = Column(String(100), nullable=False)
    category = Column(String(50), nullable=True)  # specialty, service, location, etc.

    # 추천 정보
    search_volume = Column(Integer, default=0)  # 예상 검색량
    competition = Column(String(20), nullable=True)  # low, medium, high
    relevance_score = Column(Float, default=0)  # 관련성 점수 0-1

    # 상태
    is_applied = Column(Boolean, default=False)  # 적용 여부
    is_recommended = Column(Boolean, default=True)  # AI 추천 태그 여부

    source = Column(String(50), nullable=True)  # ai_recommended, competitor, trending
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    place = relationship("NaverPlace", backref="recommended_tags")
