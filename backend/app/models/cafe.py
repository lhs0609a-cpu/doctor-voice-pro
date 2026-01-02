"""
네이버 카페 바이럴 자동화 시스템 모델
"""
import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.db.database import Base


class CafePostStatus(str, Enum):
    """게시글 상태"""
    NEW = "new"
    ANALYZED = "analyzed"
    COMMENTED = "commented"
    SKIPPED = "skipped"


class ContentType(str, Enum):
    """콘텐츠 유형"""
    POST = "post"          # 새 글 작성
    COMMENT = "comment"    # 댓글
    REPLY = "reply"        # 대댓글


class ContentStatus(str, Enum):
    """콘텐츠 상태"""
    DRAFT = "draft"
    APPROVED = "approved"
    POSTED = "posted"
    REJECTED = "rejected"
    FAILED = "failed"


class CafeTone(str, Enum):
    """댓글/글 어조"""
    FRIENDLY = "friendly"        # 친근한
    CASUAL = "casual"            # 캐주얼
    INFORMATIVE = "informative"  # 정보성
    EMPATHETIC = "empathetic"    # 공감하는
    ENTHUSIASTIC = "enthusiastic" # 열정적


class CafeCategory(str, Enum):
    """카페 카테고리"""
    MOM = "mom"           # 맘카페
    BEAUTY = "beauty"     # 뷰티/성형
    HEALTH = "health"     # 건강/의료
    REGION = "region"     # 지역 커뮤니티
    HOBBY = "hobby"       # 취미
    OTHER = "other"


class CafeCommunity(Base):
    """타겟 카페"""
    __tablename__ = "cafe_communities"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # 카페 정보
    cafe_id = Column(String(100), nullable=False)  # 네이버 카페 ID (URL의 카페명)
    cafe_name = Column(String(200), nullable=False)  # 카페 이름
    cafe_url = Column(String(500))  # 카페 URL
    category = Column(SQLEnum(CafeCategory), default=CafeCategory.OTHER)
    description = Column(String(500))  # 카페 설명
    member_count = Column(Integer, default=0)  # 회원수

    # 설정
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=1)  # 우선순위 1-5
    posting_enabled = Column(Boolean, default=False)  # 글 작성 허용
    commenting_enabled = Column(Boolean, default=True)  # 댓글 허용

    # 제한
    daily_post_limit = Column(Integer, default=2)  # 일일 글 작성 한도
    daily_comment_limit = Column(Integer, default=10)  # 일일 댓글 한도
    min_interval_minutes = Column(Integer, default=30)  # 활동 간 최소 간격

    # 타겟 게시판
    target_boards = Column(JSON)  # [{"board_id": "xxx", "name": "자유게시판"}]

    # 통계
    total_posts = Column(Integer, default=0)
    total_comments = Column(Integer, default=0)
    total_likes = Column(Integer, default=0)
    last_activity_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="cafe_communities")
    posts = relationship("CafePost", back_populates="cafe", cascade="all, delete-orphan")
    keywords = relationship("CafeKeyword", back_populates="cafe")


class CafeKeyword(Base):
    """모니터링 키워드"""
    __tablename__ = "cafe_keywords"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    cafe_id = Column(String(36), ForeignKey("cafe_communities.id"), nullable=True)  # 특정 카페만 적용

    keyword = Column(String(100), nullable=False)
    category = Column(String(50))  # 카테고리 분류
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=1)  # 우선순위 1-5

    # 매칭 설정
    match_title = Column(Boolean, default=True)  # 제목에서 매칭
    match_content = Column(Boolean, default=True)  # 본문에서 매칭

    # 통계
    matched_count = Column(Integer, default=0)
    commented_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="cafe_keywords")
    cafe = relationship("CafeCommunity", back_populates="keywords")


class CafePost(Base):
    """수집된 게시글"""
    __tablename__ = "cafe_posts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    cafe_id = Column(String(36), ForeignKey("cafe_communities.id"), nullable=False)

    # 게시글 정보
    naver_post_id = Column(String(50))  # 네이버 게시글 고유 ID
    article_id = Column(String(50))  # 글 번호
    board_id = Column(String(50))  # 게시판 ID
    board_name = Column(String(100))  # 게시판 이름
    title = Column(String(500), nullable=False)
    content = Column(Text)
    url = Column(String(500))

    # 작성자 정보
    author_name = Column(String(100))
    author_id = Column(String(100))
    author_level = Column(String(50))  # 등급

    # 메타 정보
    view_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    posted_at = Column(DateTime)  # 게시글 작성일

    # AI 분석 결과
    matched_keywords = Column(JSON)  # 매칭된 키워드 목록
    relevance_score = Column(Float, default=0)  # 관련성 점수 0-100
    sentiment = Column(String(20))  # positive/negative/neutral
    topic_tags = Column(JSON)  # 주제 태그
    comment_context = Column(Text)  # 기존 댓글 요약 (댓글 생성 시 참고)

    # 처리 상태
    status = Column(SQLEnum(CafePostStatus), default=CafePostStatus.NEW)
    skip_reason = Column(String(200))

    collected_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="cafe_posts")
    cafe = relationship("CafeCommunity", back_populates="posts")
    contents = relationship("CafeContent", back_populates="target_post", cascade="all, delete-orphan")


class CafeContent(Base):
    """생성된 콘텐츠 (댓글/글)"""
    __tablename__ = "cafe_contents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    target_post_id = Column(String(36), ForeignKey("cafe_posts.id"), nullable=True)  # 댓글 대상 게시글
    target_cafe_id = Column(String(36), ForeignKey("cafe_communities.id"), nullable=True)  # 글 작성 대상 카페

    # 콘텐츠 정보
    content_type = Column(SQLEnum(ContentType), nullable=False)
    title = Column(String(500))  # 글 작성 시 제목
    content = Column(Text, nullable=False)
    target_comment_id = Column(String(50))  # 대댓글 대상 댓글 ID

    # AI 생성 정보
    tone = Column(SQLEnum(CafeTone), default=CafeTone.FRIENDLY)
    prompt_used = Column(Text)  # 사용된 프롬프트 (디버깅용)
    generation_model = Column(String(50), default="claude")

    # 품질 점수
    quality_score = Column(Float)  # 종합 품질 0-100
    naturalness_score = Column(Float)  # 자연스러움 0-100
    relevance_score = Column(Float)  # 관련성 0-100

    # 홍보 요소
    include_promotion = Column(Boolean, default=False)
    promotion_text = Column(Text)  # 홍보 문구
    blog_link = Column(String(500))
    place_link = Column(String(500))

    # 상태
    status = Column(SQLEnum(ContentStatus), default=ContentStatus.DRAFT)
    rejection_reason = Column(String(200))
    error_message = Column(Text)  # 등록 실패 시 에러 메시지

    # 발행 정보
    posted_at = Column(DateTime)
    posted_url = Column(String(500))  # 등록된 댓글/글 URL
    naver_content_id = Column(String(50))  # 등록된 콘텐츠 ID
    posted_account_id = Column(String(36), ForeignKey("naver_accounts.id"), nullable=True)  # 게시에 사용된 계정

    # 성과 추적
    likes_received = Column(Integer, default=0)
    replies_received = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="cafe_contents")
    target_post = relationship("CafePost", back_populates="contents")
    target_cafe = relationship("CafeCommunity")
    posted_account = relationship("NaverAccount", backref="cafe_contents")


class CafeAutoSetting(Base):
    """카페 자동화 설정"""
    __tablename__ = "cafe_auto_settings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, unique=True)

    # 자동화 활성화
    is_enabled = Column(Boolean, default=False)
    auto_collect = Column(Boolean, default=True)  # 자동 수집
    auto_generate = Column(Boolean, default=False)  # 자동 생성
    auto_post = Column(Boolean, default=False)  # 자동 등록

    # 수집 설정
    collect_interval_minutes = Column(Integer, default=30)  # 수집 주기
    posts_per_collect = Column(Integer, default=20)  # 수집당 게시글 수
    min_relevance_score = Column(Float, default=60.0)  # 최소 관련성 점수

    # 생성 설정
    default_tone = Column(SQLEnum(CafeTone), default=CafeTone.FRIENDLY)
    max_content_length = Column(Integer, default=200)  # 댓글 최대 글자수
    include_emoji = Column(Boolean, default=True)  # 이모지 포함

    # 등록 설정
    auto_approve_threshold = Column(Float, default=85.0)  # 자동 승인 품질 점수
    posting_delay_seconds = Column(Integer, default=300)  # 등록 간 딜레이 (5분)

    # 일일 제한
    daily_post_limit = Column(Integer, default=5)  # 일일 글 작성 한도
    daily_comment_limit = Column(Integer, default=30)  # 일일 댓글 한도

    # 업무 시간
    working_hours = Column(JSON, default={"start": "09:00", "end": "22:00"})
    working_days = Column(JSON, default=[1, 2, 3, 4, 5, 6, 7])  # 매일

    # 홍보 설정
    default_blog_link = Column(String(500))
    default_place_link = Column(String(500))
    promotion_frequency = Column(Float, default=0.2)  # 20% 확률로 홍보 포함

    # 제외 설정
    exclude_keywords = Column(JSON)  # 제외할 키워드
    exclude_authors = Column(JSON)  # 제외할 작성자

    # 네이버 계정 (암호화 필요)
    naver_id_encrypted = Column(Text)
    naver_pw_encrypted = Column(Text)

    # 알림 설정
    notification_enabled = Column(Boolean, default=True)
    notify_on_error = Column(Boolean, default=True)
    notify_on_daily_summary = Column(Boolean, default=True)

    # 통계
    total_collected = Column(Integer, default=0)
    total_commented = Column(Integer, default=0)
    total_posted = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="cafe_auto_settings")


class CafeStats(Base):
    """일별 통계"""
    __tablename__ = "cafe_stats"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    stat_date = Column(DateTime, nullable=False)

    # 수집 통계
    posts_collected = Column(Integer, default=0)
    high_relevance_count = Column(Integer, default=0)  # 고관련성 게시글 수

    # 생성 통계
    contents_generated = Column(Integer, default=0)
    contents_approved = Column(Integer, default=0)

    # 발행 통계
    posts_published = Column(Integer, default=0)  # 글 작성
    comments_published = Column(Integer, default=0)  # 댓글 작성
    replies_published = Column(Integer, default=0)  # 대댓글 작성

    # 성과
    total_likes = Column(Integer, default=0)
    total_replies = Column(Integer, default=0)

    # 카페별 통계
    cafe_breakdown = Column(JSON)  # {cafe_id: {collected, commented, posted}}
    # 키워드별 통계
    keyword_breakdown = Column(JSON)  # {keyword: {matched, commented}}

    # 에러 통계
    error_count = Column(Integer, default=0)
    error_details = Column(JSON)  # [{type, message, timestamp}]

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="cafe_stats")


class CafeTemplate(Base):
    """댓글/글 템플릿"""
    __tablename__ = "cafe_templates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    name = Column(String(100), nullable=False)
    description = Column(String(500))
    content_type = Column(SQLEnum(ContentType), default=ContentType.COMMENT)
    category = Column(SQLEnum(CafeCategory))

    # 템플릿 내용
    template_content = Column(Text, nullable=False)
    variables = Column(JSON)  # [{name, description, example}]

    # 스타일
    tone = Column(SQLEnum(CafeTone), default=CafeTone.FRIENDLY)
    include_emoji = Column(Boolean, default=True)

    # 매칭 조건
    trigger_keywords = Column(JSON)  # 이 키워드가 있으면 이 템플릿 사용

    # 통계
    usage_count = Column(Integer, default=0)
    success_rate = Column(Float)  # 성공률

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="cafe_templates")
