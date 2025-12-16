from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    Float,
    ForeignKey,
    Text,
    JSON,
    Enum,
    Boolean,
    Time,
    Date,
)
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid as uuid_pkg
import enum

from app.db.database import Base
from app.models.user import GUID


class ScheduleType(str, enum.Enum):
    ONE_TIME = "one_time"      # 1회성 예약
    RECURRING = "recurring"     # 반복 발행


class RecurrencePattern(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class ScheduleStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ExecutionStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class PublishSchedule(Base):
    """예약 발행 스케줄"""
    __tablename__ = "publish_schedules"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    post_id = Column(GUID(), ForeignKey("posts.id"), nullable=True)  # 1회성용

    # 스케줄 이름
    name = Column(String(200), nullable=True)

    # 스케줄 타입
    schedule_type = Column(Enum(ScheduleType), nullable=False)

    # 발행 시간 설정
    scheduled_time = Column(Time, nullable=False)  # 발행 시각 (HH:MM)
    scheduled_date = Column(Date, nullable=True)   # 1회성용 날짜

    # 반복 설정
    recurrence_pattern = Column(Enum(RecurrencePattern), nullable=True)
    days_of_week = Column(JSON, nullable=True)  # [0,1,2,3,4,5,6] = 일~토
    day_of_month = Column(Integer, nullable=True)  # 월간 반복용 (1-31)

    # 콘텐츠 소스 설정
    content_source = Column(String(50), default="existing")  # "existing", "draft_pool"
    draft_pool_tag_id = Column(GUID(), ForeignKey("tags.id"), nullable=True)  # 특정 태그의 글 풀

    # 네이버 발행 설정
    category_no = Column(String(50), nullable=True)
    open_type = Column(String(10), default="0")  # 0: 전체공개, 1: 이웃공개, 2: 비공개
    auto_hashtags = Column(Boolean, default=True)

    # 상태
    status = Column(Enum(ScheduleStatus), default=ScheduleStatus.ACTIVE)
    last_executed_at = Column(DateTime, nullable=True)
    next_execution_at = Column(DateTime, nullable=True)
    execution_count = Column(Integer, default=0)
    max_executions = Column(Integer, nullable=True)  # 최대 실행 횟수 (null=무제한)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="schedules")
    post = relationship("Post", backref="schedules")
    executions = relationship("ScheduleExecution", back_populates="schedule", cascade="all, delete")


class ScheduleExecution(Base):
    """예약 실행 로그"""
    __tablename__ = "schedule_executions"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    schedule_id = Column(GUID(), ForeignKey("publish_schedules.id"), nullable=False)
    post_id = Column(GUID(), ForeignKey("posts.id"), nullable=True)

    # 실행 결과
    status = Column(Enum(ExecutionStatus), default=ExecutionStatus.PENDING)
    executed_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # 발행 결과
    naver_post_url = Column(String(500), nullable=True)
    naver_post_id = Column(String(100), nullable=True)

    # 에러 정보
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)

    # Relationships
    schedule = relationship("PublishSchedule", back_populates="executions")
    post = relationship("Post")


class OptimalTimeRecommendation(Base):
    """최적 발행 시간 추천 데이터"""
    __tablename__ = "optimal_time_recommendations"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)

    # 카테고리별 추천
    category = Column(String(100), nullable=True)  # 의료 분야별 (null=전체)

    # 추천 시간대
    day_of_week = Column(Integer, nullable=False)  # 0-6 (일-토)
    recommended_hour = Column(Integer, nullable=False)  # 0-23
    recommended_minute = Column(Integer, default=0)  # 0-59

    # 추천 점수
    engagement_score = Column(Float, default=0.0)  # 예상 참여율
    confidence_score = Column(Float, default=0.0)  # 신뢰도

    # 근거 데이터
    sample_count = Column(Integer, default=0)  # 분석에 사용된 샘플 수
    based_on = Column(JSON, nullable=True)  # 분석 근거 데이터

    # Timestamps
    calculated_at = Column(DateTime, default=datetime.utcnow)
    valid_until = Column(DateTime, nullable=True)  # 추천 유효 기간

    # Relationships
    user = relationship("User", backref="optimal_times")
