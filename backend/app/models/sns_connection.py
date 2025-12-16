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
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid as uuid_pkg
import enum

from app.db.database import Base
from app.models.user import GUID


class SNSPlatform(str, enum.Enum):
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    THREADS = "threads"
    TWITTER = "twitter"


class SNSPostStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


class SNSContentType(str, enum.Enum):
    POST = "post"           # 일반 포스트
    REEL = "reel"           # 인스타 릴스
    STORY = "story"         # 스토리
    SHORT = "short"         # 숏폼 (유튜브 쇼츠 등)


class SNSConnection(Base):
    """SNS 연동 정보"""
    __tablename__ = "sns_connections"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)

    # 플랫폼 정보
    platform = Column(Enum(SNSPlatform), nullable=False)

    # OAuth 토큰
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)

    # 플랫폼별 사용자 정보
    platform_user_id = Column(String(100), nullable=True)
    platform_username = Column(String(100), nullable=True)
    profile_image_url = Column(String(500), nullable=True)

    # 인스타그램/페이스북용 페이지/비즈니스 계정 ID
    page_id = Column(String(100), nullable=True)
    page_name = Column(String(200), nullable=True)
    page_access_token = Column(Text, nullable=True)

    # 상태
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime, nullable=True)
    connection_status = Column(String(50), default="connected")  # connected, expired, error

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Unique constraint: 한 사용자당 플랫폼별 하나의 연동만 허용
    __table_args__ = (
        UniqueConstraint('user_id', 'platform', name='uq_user_platform'),
    )

    # Relationships
    user = relationship("User", backref="sns_connections")


class SNSPost(Base):
    """SNS 포스트"""
    __tablename__ = "sns_posts"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    original_post_id = Column(GUID(), ForeignKey("posts.id"), nullable=True)  # 원본 블로그 글

    # 플랫폼 & 콘텐츠 타입
    platform = Column(Enum(SNSPlatform), nullable=False)
    content_type = Column(Enum(SNSContentType), default=SNSContentType.POST)

    # 콘텐츠
    caption = Column(Text, nullable=True)
    hashtags = Column(JSON, nullable=True)  # ["#해시태그1", "#해시태그2", ...]
    media_urls = Column(JSON, nullable=True)  # ["url1", "url2", ...]
    thumbnail_url = Column(String(500), nullable=True)

    # 숏폼용 스크립트
    script = Column(Text, nullable=True)  # 릴스/숏츠 스크립트
    script_duration = Column(Integer, nullable=True)  # 초 단위
    script_sections = Column(JSON, nullable=True)  # [{"time": "0-5초", "text": "..."}, ...]

    # 발행 정보
    status = Column(Enum(SNSPostStatus), default=SNSPostStatus.DRAFT)
    scheduled_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)

    # 플랫폼 발행 정보
    platform_post_id = Column(String(100), nullable=True)
    platform_post_url = Column(String(500), nullable=True)

    # 에러 정보
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="sns_posts")
    original_post = relationship("Post", backref="sns_posts")


class HashtagRecommendation(Base):
    """해시태그 추천 데이터"""
    __tablename__ = "hashtag_recommendations"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)

    # 카테고리
    category = Column(String(100), nullable=False)  # "의료", "피부과", "정형외과" 등
    subcategory = Column(String(100), nullable=True)

    # 해시태그 정보
    hashtag = Column(String(100), nullable=False)
    hashtag_clean = Column(String(100), nullable=False)  # # 제거한 버전

    # 메트릭스
    popularity_score = Column(Float, default=0.0)  # 인기도 (0-100)
    engagement_rate = Column(Float, default=0.0)   # 참여율
    post_count = Column(Integer, default=0)        # 사용 게시물 수
    avg_likes = Column(Integer, default=0)
    avg_comments = Column(Integer, default=0)

    # 추천 우선순위
    priority = Column(Integer, default=0)  # 높을수록 추천 우선

    # 플랫폼별 적합성
    platforms = Column(JSON, nullable=True)  # ["instagram", "facebook"]

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
