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
    Date,
)
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid as uuid_pkg
import enum

from app.db.database import Base
from app.models.user import GUID


class ReportType(str, enum.Enum):
    MONTHLY = "monthly"
    WEEKLY = "weekly"
    CUSTOM = "custom"


class ReportFormat(str, enum.Enum):
    PDF = "pdf"
    EXCEL = "excel"
    HTML = "html"


class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class MarketingReport(Base):
    """마케팅 리포트"""
    __tablename__ = "marketing_reports"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)

    # 리포트 정보
    report_type = Column(Enum(ReportType), nullable=False)
    title = Column(String(200), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    # 리포트 데이터 (JSON)
    report_data = Column(JSON, nullable=True)
    # {
    #   "summary": {
    #     "total_posts": 10,
    #     "published_posts": 8,
    #     "avg_persuasion_score": 75.5,
    #     "total_views": 1500,
    #     "total_inquiries": 25
    #   },
    #   "persuasion_trend": [
    #     {"date": "2024-01-01", "score": 72.5},
    #     ...
    #   ],
    #   "keyword_analysis": {
    #     "top_keywords": [...],
    #     "keyword_performance": {...}
    #   },
    #   "top_posts": [...],
    #   "recommendations": [...]
    # }

    # 파일 정보
    pdf_url = Column(String(500), nullable=True)
    pdf_file_path = Column(String(500), nullable=True)
    excel_url = Column(String(500), nullable=True)
    excel_file_path = Column(String(500), nullable=True)

    # 이메일 발송
    email_sent = Column(Boolean, default=False)
    email_sent_at = Column(DateTime, nullable=True)
    email_recipients = Column(JSON, nullable=True)  # ["email1@...", ...]

    # 상태
    status = Column(Enum(ReportStatus), default=ReportStatus.PENDING)
    error_message = Column(Text, nullable=True)
    generated_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="reports")


class ReportSubscription(Base):
    """리포트 자동 구독 설정"""
    __tablename__ = "report_subscriptions"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, unique=True)

    # 자동 생성 설정
    auto_monthly = Column(Boolean, default=False)
    auto_weekly = Column(Boolean, default=False)
    generation_day = Column(Integer, default=1)  # 월간: 매월 N일, 주간: 요일 (0=일요일)

    # 이메일 설정
    email_enabled = Column(Boolean, default=False)
    email_recipients = Column(JSON, nullable=True)  # ["email1@...", ...]

    # 포맷 설정
    preferred_format = Column(Enum(ReportFormat), default=ReportFormat.PDF)
    include_recommendations = Column(Boolean, default=True)
    include_detailed_analysis = Column(Boolean, default=True)

    # 알림 설정
    notify_on_generation = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="report_subscription")
