"""
카페 확장 모델
- 대댓글 자동화
- 게시판 타겟팅
- 이미지 포함 글 작성
- 인기글 분석
- 팔로우/좋아요 활동
"""

import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON, Date
from sqlalchemy.orm import relationship
from app.db.database import Base


# ==================== Enums ====================

class ReplyStatus(str, Enum):
    """대댓글 상태"""
    PENDING = "pending"
    REPLIED = "replied"
    SKIPPED = "skipped"
    FAILED = "failed"


class EngagementType(str, Enum):
    """활동 유형"""
    LIKE = "like"
    SAVE = "save"
    FOLLOW = "follow"
    SHARE = "share"


class PopularPostCategory(str, Enum):
    """인기글 카테고리"""
    HOT = "hot"           # 핫글
    BEST = "best"         # 베스트
    WEEKLY = "weekly"     # 주간 인기
    MONTHLY = "monthly"   # 월간 인기


# ==================== 게시판 타겟팅 ====================

class CafeBoard(Base):
    """카페 게시판"""
    __tablename__ = "cafe_boards"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    cafe_id = Column(String(36), ForeignKey("cafe_communities.id"), nullable=False)

    # 게시판 정보
    board_id = Column(String(100), nullable=False)
    board_name = Column(String(200), nullable=False)
    board_url = Column(Text)

    # 타겟팅 설정
    is_target = Column(Boolean, default=True)
    priority = Column(Integer, default=1)  # 1-5

    # 활동 설정
    allow_comment = Column(Boolean, default=True)
    allow_post = Column(Boolean, default=False)
    allow_reply = Column(Boolean, default=True)

    # 일일 제한
    daily_comment_limit = Column(Integer, default=10)
    daily_post_limit = Column(Integer, default=2)

    # 통계
    total_comments = Column(Integer, default=0)
    total_posts = Column(Integer, default=0)
    total_likes = Column(Integer, default=0)

    # 키워드 필터
    include_keywords = Column(JSON)  # 포함해야 할 키워드
    exclude_keywords = Column(JSON)  # 제외할 키워드

    # 게시판 특성
    avg_post_length = Column(Integer)
    avg_comment_count = Column(Float)
    activity_level = Column(String(20))  # high, medium, low

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="cafe_boards")


# ==================== 대댓글 자동화 ====================

class CommentReply(Base):
    """대댓글 추적"""
    __tablename__ = "comment_replies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    original_content_id = Column(String(36), ForeignKey("cafe_contents.id"), nullable=False)

    # 원본 댓글 정보
    original_comment_id = Column(String(100))
    original_post_url = Column(Text)

    # 수신된 대댓글
    reply_id = Column(String(100))
    reply_author = Column(String(100))
    reply_author_id = Column(String(100))
    reply_content = Column(Text)
    reply_at = Column(DateTime)

    # 상태
    status = Column(String(20), default=ReplyStatus.PENDING.value)

    # 자동 응답
    auto_reply_content = Column(Text)  # 생성된 응답
    auto_reply_tone = Column(String(50))
    is_replied = Column(Boolean, default=False)
    replied_at = Column(DateTime)
    reply_url = Column(Text)

    # AI 분석
    sentiment = Column(String(20))  # positive, negative, neutral
    requires_response = Column(Boolean, default=True)
    urgency = Column(String(20))  # high, medium, low

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="comment_replies")


class ReplyTemplate(Base):
    """대댓글 템플릿"""
    __tablename__ = "reply_templates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # 템플릿 정보
    name = Column(String(200), nullable=False)
    category = Column(String(100))  # 감사, 추가정보, 공감

    # 조건
    trigger_keywords = Column(JSON)  # 트리거 키워드
    trigger_sentiment = Column(String(20))  # 특정 감정에만 반응

    # 템플릿 내용
    template_content = Column(Text, nullable=False)
    variables = Column(JSON)  # ["작성자명", "원글제목"]

    # 설정
    tone = Column(String(50), default="friendly")
    include_promotion = Column(Boolean, default=False)

    # 사용 통계
    usage_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="reply_templates")


# ==================== 이미지 포함 글 작성 ====================

class CafePostImage(Base):
    """카페 글 이미지"""
    __tablename__ = "cafe_post_images"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    content_id = Column(String(36), ForeignKey("cafe_contents.id"), nullable=True)

    # 이미지 정보
    image_type = Column(String(50))  # photo, infographic, screenshot
    image_url = Column(Text, nullable=False)
    thumbnail_url = Column(Text)
    original_filename = Column(String(255))

    # 크기
    width = Column(Integer)
    height = Column(Integer)
    file_size = Column(Integer)

    # 위치
    position = Column(Integer, default=0)  # 글 내 순서
    insert_after = Column(Text)  # 이 텍스트 다음에 삽입

    # 설명
    alt_text = Column(String(500))
    caption = Column(Text)

    # 소스
    is_stock = Column(Boolean, default=False)  # 스톡 이미지 여부
    source_url = Column(Text)
    is_ai_generated = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="cafe_post_images")


class ImageLibrary(Base):
    """이미지 라이브러리"""
    __tablename__ = "image_library"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # 이미지 정보
    name = Column(String(200), nullable=False)
    category = Column(String(100))
    tags = Column(JSON)

    # URL
    image_url = Column(Text, nullable=False)
    thumbnail_url = Column(Text)

    # 메타
    width = Column(Integer)
    height = Column(Integer)
    file_size = Column(Integer)

    # 사용
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime)

    # 설정
    is_favorite = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="image_library")


# ==================== 인기글 분석 ====================

class PopularPost(Base):
    """인기글"""
    __tablename__ = "cafe_popular_posts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    cafe_id = Column(String(36), ForeignKey("cafe_communities.id"), nullable=False)

    # 게시글 정보
    post_id = Column(String(100), nullable=False)
    article_id = Column(String(100))
    board_id = Column(String(100))
    title = Column(String(500), nullable=False)
    content = Column(Text)
    url = Column(Text)

    # 작성자
    author_name = Column(String(100))
    author_id = Column(String(100))

    # 인기 지표
    category = Column(String(20))  # hot, best, weekly, monthly
    view_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    save_count = Column(Integer, default=0)

    # AI 분석
    topic = Column(String(200))
    keywords = Column(JSON)
    structure = Column(JSON)  # 글 구조 분석
    tone = Column(String(50))
    content_length = Column(Integer)
    image_count = Column(Integer, default=0)

    # 성공 요인 분석
    success_factors = Column(JSON)
    # ["눈길끄는 제목", "상세한 정보", "적절한 이미지"]

    # 참고 점수
    reference_score = Column(Float)  # 참고할 만한 정도

    posted_at = Column(DateTime)
    collected_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="cafe_popular_posts")


class PopularPostPattern(Base):
    """인기글 패턴"""
    __tablename__ = "popular_post_patterns"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    cafe_id = Column(String(36), ForeignKey("cafe_communities.id"), nullable=True)

    # 분석 대상
    board_id = Column(String(100))
    category = Column(String(100))
    analysis_period = Column(String(20))  # week, month

    # 제목 패턴
    title_patterns = Column(JSON)
    # {"avg_length": 25, "common_words": ["추천", "후기", "정보"],
    #  "question_rate": 0.3, "emoji_rate": 0.2}

    # 본문 패턴
    content_patterns = Column(JSON)
    # {"avg_length": 500, "paragraph_count": 5, "image_count": 3}

    # 시간 패턴
    time_patterns = Column(JSON)
    # {"best_hour": 14, "best_day": 2, "worst_hour": 3}

    # 성공 요인
    success_factors = Column(JSON)
    recommendations = Column(JSON)

    # 샘플 수
    sample_count = Column(Integer, default=0)

    analyzed_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="popular_post_patterns")


# ==================== 팔로우/좋아요 활동 ====================

class EngagementActivity(Base):
    """활동 기록 (좋아요, 팔로우 등)"""
    __tablename__ = "engagement_activities"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    account_id = Column(String(36), ForeignKey("naver_accounts.id"), nullable=True)
    cafe_id = Column(String(36), ForeignKey("cafe_communities.id"), nullable=True)

    # 활동 유형
    activity_type = Column(String(20), nullable=False)  # like, save, follow, share

    # 대상
    target_type = Column(String(20))  # post, comment, user
    target_id = Column(String(100))
    target_url = Column(Text)
    target_author = Column(String(100))

    # 상태
    is_success = Column(Boolean, default=False)
    error_message = Column(Text)

    # 시간
    scheduled_at = Column(DateTime)
    executed_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="engagement_activities")


class EngagementSchedule(Base):
    """활동 스케줄"""
    __tablename__ = "engagement_schedules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # 스케줄 정보
    name = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True)

    # 활동 유형
    activity_types = Column(JSON)  # ["like", "save"]

    # 대상 설정
    target_cafes = Column(JSON)  # 대상 카페 ID 목록
    target_boards = Column(JSON)  # 대상 게시판 ID 목록
    target_keywords = Column(JSON)  # 대상 키워드

    # 일일 제한
    daily_like_limit = Column(Integer, default=30)
    daily_save_limit = Column(Integer, default=10)
    daily_follow_limit = Column(Integer, default=5)

    # 간격 설정
    min_interval_seconds = Column(Integer, default=60)
    max_interval_seconds = Column(Integer, default=300)

    # 업무 시간
    working_hours = Column(JSON)  # {"start": "09:00", "end": "22:00"}
    working_days = Column(JSON)  # [1, 2, 3, 4, 5, 6, 7]

    # 통계
    total_likes = Column(Integer, default=0)
    total_saves = Column(Integer, default=0)
    total_follows = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="engagement_schedules")


# ==================== 콘텐츠 성과 상세 ====================

class ContentPerformance(Base):
    """콘텐츠 성과 상세"""
    __tablename__ = "content_performances"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    content_id = Column(String(36), ForeignKey("cafe_contents.id"), nullable=False)
    account_id = Column(String(36), ForeignKey("naver_accounts.id"), nullable=True)

    # 게시 정보
    posted_at = Column(DateTime)
    posted_url = Column(Text)

    # 성과 지표
    like_count = Column(Integer, default=0)
    reply_count = Column(Integer, default=0)
    view_count = Column(Integer, default=0)

    # 링크 클릭
    blog_clicks = Column(Integer, default=0)
    place_clicks = Column(Integer, default=0)
    last_click_at = Column(DateTime)

    # A/B 테스트
    ab_test_id = Column(String(36))
    ab_variant = Column(String(50))

    # 추적 상태
    last_checked_at = Column(DateTime)
    check_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="content_performances")
