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
