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
    Table,
)
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid as uuid_pkg
import enum

from app.db.database import Base
from app.models.user import GUID


class PostStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    SCHEDULED = "scheduled"


# Association table for many-to-many relationship between posts and tags
post_tags = Table(
    "post_tags",
    Base.metadata,
    Column("post_id", GUID(), ForeignKey("posts.id"), primary_key=True),
    Column("tag_id", GUID(), ForeignKey("tags.id"), primary_key=True),
)


class Post(Base):
    __tablename__ = "posts"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=True)  # 익명 사용 허용

    # Content
    title = Column(String(500))
    original_content = Column(Text, nullable=False)
    generated_content = Column(Text)

    # Metadata
    persuasion_score = Column(Float, default=0.0)
    medical_law_check = Column(JSON, nullable=True)
    # {
    #   "is_compliant": true,
    #   "violations": [],
    #   "warnings": []
    # }

    # SEO
    seo_keywords = Column(JSON, nullable=True)
    hashtags = Column(JSON, nullable=True)
    meta_description = Column(Text)

    # Status & Features
    status = Column(Enum(PostStatus), default=PostStatus.DRAFT, nullable=False)
    is_favorited = Column(Boolean, default=False, nullable=False)

    # Publishing
    published_at = Column(DateTime, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)  # For scheduled publishing
    naver_blog_url = Column(String(500), nullable=True)

    # Additional metadata
    suggested_titles = Column(JSON, nullable=True)  # 추천 제목 5개
    # ["제목1", "제목2", ...]

    suggested_subtitles = Column(JSON, nullable=True)  # 추천 소제목 4개
    # ["소제목1", "소제목2", ...]

    content_analysis = Column(JSON, nullable=True)  # 콘텐츠 분석 결과
    # {
    #   "character_count": {...},
    #   "keywords": [...],
    #   "sentence_count": 10,
    #   ...
    # }

    forbidden_words_check = Column(JSON, nullable=True)  # 금칙어 검사 결과
    # {
    #   "found_words": [...],
    #   "replacements": [...]
    # }

    dia_crank_analysis = Column(JSON, nullable=True)  # DIA/CRANK 점수 분석 결과
    # {
    #   "dia_score": {...},
    #   "crank_score": {...},
    #   "overall_grade": "A+",
    #   "estimated_ranking": "상위 5%"
    # }

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="posts")
    versions = relationship("PostVersion", back_populates="post", cascade="all, delete")
    analytics = relationship(
        "PostAnalytics", back_populates="post", uselist=False, cascade="all, delete"
    )
    tags = relationship("Tag", secondary=post_tags, back_populates="posts")


class PostVersion(Base):
    __tablename__ = "post_versions"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    post_id = Column(GUID(), ForeignKey("posts.id"), nullable=False)

    version_number = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    persuasion_score = Column(Float, default=0.0)

    # Configuration used for this version
    generation_config = Column(JSON, nullable=True)
    # {
    #   "framework": "AIDA",
    #   "persuasion_level": 4,
    #   "tone": "friendly"
    # }

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    post = relationship("Post", back_populates="versions")


class PostAnalytics(Base):
    __tablename__ = "post_analytics"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    post_id = Column(GUID(), ForeignKey("posts.id"), nullable=False)

    # Metrics
    views = Column(Integer, default=0)
    avg_time_spent = Column(Integer, default=0)  # in seconds
    inquiries = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0.0)

    # Timestamps
    measured_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    post = relationship("Post", back_populates="analytics")
