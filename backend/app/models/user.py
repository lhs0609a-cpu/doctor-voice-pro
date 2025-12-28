from sqlalchemy import Column, String, DateTime, Enum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator, CHAR
from datetime import datetime
import uuid as uuid_pkg
import enum

from app.db.database import Base


class GUID(TypeDecorator):
    """Platform-independent GUID type that uses CHAR(36) for SQLite."""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif isinstance(value, uuid_pkg.UUID):
            return str(value)
        else:
            return str(uuid_pkg.UUID(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            return uuid_pkg.UUID(value)


class SubscriptionTier(str, enum.Enum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class User(Base):
    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(100))
    hospital_name = Column(String(200))
    specialty = Column(String(50))
    subscription_tier = Column(
        Enum(SubscriptionTier), default=SubscriptionTier.FREE, nullable=False
    )
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_approved = Column(Boolean, default=False)  # 관리자 승인 여부
    is_admin = Column(Boolean, default=False)  # 관리자 여부
    subscription_start_date = Column(DateTime, nullable=True)  # 사용 시작일
    subscription_end_date = Column(DateTime, nullable=True)  # 사용 종료일
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    profile = relationship("DoctorProfile", back_populates="user", uselist=False)
    posts = relationship("Post", back_populates="user")
    naver_connection = relationship("NaverConnection", back_populates="user", uselist=False)
    tags = relationship("Tag", back_populates="user")
    writing_requests = relationship("WritingRequest", back_populates="user")

    # Knowledge relationships
    knowledge_keywords = relationship("KnowledgeKeyword", back_populates="user")
    knowledge_questions = relationship("KnowledgeQuestion", back_populates="user")
    knowledge_answers = relationship("KnowledgeAnswer", back_populates="user")
    answer_templates = relationship("AnswerTemplate", back_populates="user")
    auto_answer_settings = relationship("AutoAnswerSetting", back_populates="user", uselist=False)
    knowledge_stats = relationship("KnowledgeStats", back_populates="user")

    # Cafe relationships
    cafe_communities = relationship("CafeCommunity", back_populates="user")
    cafe_keywords = relationship("CafeKeyword", back_populates="user")
    cafe_posts = relationship("CafePost", back_populates="user")
    cafe_contents = relationship("CafeContent", back_populates="user")
    cafe_auto_settings = relationship("CafeAutoSetting", back_populates="user", uselist=False)
    cafe_stats = relationship("CafeStats", back_populates="user")
    cafe_templates = relationship("CafeTemplate", back_populates="user")

    # Viral Common relationships (다중 계정, 성과 추적, 알림 등)
    naver_accounts = relationship("NaverAccount", back_populates="user")
    proxy_servers = relationship("ProxyServer", back_populates="user")
    performance_events = relationship("PerformanceEvent", back_populates="user")
    performance_daily = relationship("PerformanceDaily", back_populates="user")
    notification_channels = relationship("NotificationChannel", back_populates="user")
    notification_logs = relationship("NotificationLog", back_populates="user")
    ab_tests = relationship("ABTest", back_populates="user")
    daily_reports = relationship("DailyReport", back_populates="user")

    # Knowledge Extended relationships (채택 추적, 경쟁 분석 등)
    answer_adoptions = relationship("AnswerAdoption", back_populates="user")
    competitor_answers = relationship("CompetitorAnswer", back_populates="user")
    answer_strategies = relationship("AnswerStrategy", back_populates="user")
    answer_images = relationship("AnswerImage", back_populates="user")
    image_templates = relationship("ImageTemplate", back_populates="user")
    questioner_profiles = relationship("QuestionerProfile", back_populates="user")
    reward_priority_rules = relationship("RewardPriorityRule", back_populates="user")
    answer_performances = relationship("AnswerPerformance", back_populates="user")

    # Cafe Extended relationships (대댓글, 게시판 타겟팅 등)
    cafe_boards = relationship("CafeBoard", back_populates="user")
    comment_replies = relationship("CommentReply", back_populates="user")
    reply_templates = relationship("ReplyTemplate", back_populates="user")
    cafe_post_images = relationship("CafePostImage", back_populates="user")
    image_library = relationship("ImageLibrary", back_populates="user")
    cafe_popular_posts = relationship("PopularPost", back_populates="user")
    popular_post_patterns = relationship("PopularPostPattern", back_populates="user")
    engagement_activities = relationship("EngagementActivity", back_populates="user")
    engagement_schedules = relationship("EngagementSchedule", back_populates="user")
    content_performances = relationship("ContentPerformance", back_populates="user")
