"""
네이버 블로그 영업 자동화 시스템 모델
"""
import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.db.database import Base


class BlogCategory(str, Enum):
    """블로그 카테고리"""
    BEAUTY = "beauty"           # 뷰티/패션
    FOOD = "food"               # 맛집/카페
    TRAVEL = "travel"           # 여행
    PARENTING = "parenting"     # 육아/교육
    LIVING = "living"           # 리빙/인테리어
    HEALTH = "health"           # 건강/의료
    IT = "it"                   # IT/테크
    FINANCE = "finance"         # 재테크/금융
    LIFESTYLE = "lifestyle"     # 라이프스타일
    OTHER = "other"


class LeadGrade(str, Enum):
    """리드 등급"""
    A = "A"  # 최우선 타겟 (80+)
    B = "B"  # 우선 타겟 (60-79)
    C = "C"  # 일반 타겟 (40-59)
    D = "D"  # 후순위 (0-39)


class BlogStatus(str, Enum):
    """블로그 상태"""
    NEW = "new"                 # 신규 수집
    CONTACT_FOUND = "contact_found"  # 연락처 발견
    CONTACTED = "contacted"     # 연락함
    RESPONDED = "responded"     # 회신받음
    CONVERTED = "converted"     # 전환됨
    NOT_INTERESTED = "not_interested"  # 관심없음
    INVALID = "invalid"         # 유효하지 않음


class ContactSource(str, Enum):
    """연락처 출처"""
    PROFILE = "profile"         # 블로그 프로필
    POST = "post"               # 포스팅 본문
    WIDGET = "widget"           # 위젯/사이드바
    INSTAGRAM = "instagram"     # 인스타그램
    YOUTUBE = "youtube"         # 유튜브
    OTHER = "other"


class CampaignStatus(str, Enum):
    """캠페인 상태"""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class EmailStatus(str, Enum):
    """이메일 상태"""
    PENDING = "pending"
    SENT = "sent"
    OPENED = "opened"
    CLICKED = "clicked"
    REPLIED = "replied"
    BOUNCED = "bounced"
    UNSUBSCRIBED = "unsubscribed"


class NaverBlog(Base):
    """수집된 네이버 블로그"""
    __tablename__ = "naver_blogs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # 블로그 기본 정보
    blog_id = Column(String(100), nullable=False)  # 네이버 블로그 ID
    blog_url = Column(String(500), nullable=False)
    blog_name = Column(String(200))
    owner_nickname = Column(String(100))
    profile_image = Column(String(500))
    introduction = Column(Text)  # 블로그 소개글

    # 메트릭스
    visitor_daily = Column(Integer, default=0)  # 일일 방문자
    visitor_total = Column(Integer, default=0)  # 총 방문자
    neighbor_count = Column(Integer, default=0)  # 이웃 수
    post_count = Column(Integer, default=0)  # 총 포스팅 수

    # 최근 활동
    last_post_date = Column(DateTime)
    last_post_title = Column(String(500))

    # 분류
    category = Column(SQLEnum(BlogCategory), default=BlogCategory.OTHER)
    tags = Column(JSON)  # 관련 태그들
    keywords = Column(JSON)  # 매칭된 키워드들

    # 리드 스코어링
    lead_score = Column(Float, default=0)
    lead_grade = Column(SQLEnum(LeadGrade), default=LeadGrade.D)
    influence_score = Column(Float, default=0)  # 영향력 점수
    activity_score = Column(Float, default=0)   # 활동성 점수
    relevance_score = Column(Float, default=0)  # 관련성 점수

    # 상태
    status = Column(SQLEnum(BlogStatus), default=BlogStatus.NEW)
    is_influencer = Column(Boolean, default=False)
    has_contact = Column(Boolean, default=False)

    # 메모
    notes = Column(Text)

    collected_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="naver_blogs")
    contacts = relationship("BlogContact", back_populates="blog", cascade="all, delete-orphan")
    email_logs = relationship("EmailLog", back_populates="blog")


class BlogContact(Base):
    """블로그 연락처"""
    __tablename__ = "blog_contacts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    blog_id = Column(String(36), ForeignKey("naver_blogs.id"), nullable=False)

    # 연락처 정보
    email = Column(String(200))
    phone = Column(String(50))
    instagram = Column(String(100))
    youtube = Column(String(200))
    kakao_channel = Column(String(100))
    other_contact = Column(Text)

    # 메타 정보
    source = Column(SQLEnum(ContactSource), default=ContactSource.PROFILE)
    source_url = Column(String(500))  # 발견된 URL
    is_primary = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)

    extracted_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    blog = relationship("NaverBlog", back_populates="contacts")


class EmailTemplate(Base):
    """이메일 템플릿"""
    __tablename__ = "email_templates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    name = Column(String(200), nullable=False)
    description = Column(String(500))

    # 템플릿 유형
    template_type = Column(String(50), default="introduction")  # introduction, follow_up, reminder

    # 템플릿 내용
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)

    # 변수 정의
    variables = Column(JSON)  # [{name, description, default_value}]

    # 설정
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)

    # 통계
    usage_count = Column(Integer, default=0)
    open_rate = Column(Float)
    reply_rate = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="email_templates")


class EmailCampaign(Base):
    """이메일 캠페인"""
    __tablename__ = "email_campaigns"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    name = Column(String(200), nullable=False)
    description = Column(Text)

    # 타겟 조건
    target_grades = Column(JSON)  # ["A", "B"]
    target_categories = Column(JSON)  # ["beauty", "food"]
    target_keywords = Column(JSON)  # 추가 키워드 필터
    min_score = Column(Float, default=0)
    max_contacts = Column(Integer)  # 최대 발송 수

    # 템플릿 시퀀스
    templates = Column(JSON)  # [{template_id, delay_days, condition}]

    # 발송 설정
    daily_limit = Column(Integer, default=50)
    sending_hours_start = Column(Integer, default=9)  # 09:00
    sending_hours_end = Column(Integer, default=18)   # 18:00
    sending_days = Column(JSON, default=[1, 2, 3, 4, 5])  # 월~금

    # 상태
    status = Column(SQLEnum(CampaignStatus), default=CampaignStatus.DRAFT)

    # 통계
    total_targets = Column(Integer, default=0)
    total_sent = Column(Integer, default=0)
    total_opened = Column(Integer, default=0)
    total_clicked = Column(Integer, default=0)
    total_replied = Column(Integer, default=0)
    total_bounced = Column(Integer, default=0)

    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="email_campaigns")
    email_logs = relationship("EmailLog", back_populates="campaign")


class EmailLog(Base):
    """이메일 발송 기록"""
    __tablename__ = "email_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    campaign_id = Column(String(36), ForeignKey("email_campaigns.id"), nullable=True)
    blog_id = Column(String(36), ForeignKey("naver_blogs.id"), nullable=False)
    contact_id = Column(String(36), ForeignKey("blog_contacts.id"), nullable=True)
    template_id = Column(String(36), ForeignKey("email_templates.id"), nullable=True)

    # 이메일 내용
    to_email = Column(String(200), nullable=False)
    to_name = Column(String(100))
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)

    # 발송 정보
    from_email = Column(String(200))
    from_name = Column(String(100))

    # 추적 정보
    tracking_id = Column(String(100), unique=True)  # 오픈/클릭 추적용

    # 상태
    status = Column(SQLEnum(EmailStatus), default=EmailStatus.PENDING)
    error_message = Column(Text)

    # 타임스탬프
    scheduled_at = Column(DateTime)
    sent_at = Column(DateTime)
    opened_at = Column(DateTime)
    clicked_at = Column(DateTime)
    replied_at = Column(DateTime)
    bounced_at = Column(DateTime)

    # 시퀀스 정보
    sequence_number = Column(Integer, default=1)  # 몇 번째 이메일인지

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="email_logs")
    campaign = relationship("EmailCampaign", back_populates="email_logs")
    blog = relationship("NaverBlog", back_populates="email_logs")


class BlogSearchKeyword(Base):
    """블로그 검색 키워드"""
    __tablename__ = "blog_search_keywords"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    keyword = Column(String(200), nullable=False)
    category = Column(SQLEnum(BlogCategory))

    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=1)

    # 수집 통계
    total_collected = Column(Integer, default=0)
    last_collected_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="blog_search_keywords")


class OutreachSetting(Base):
    """영업 자동화 설정"""
    __tablename__ = "outreach_settings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, unique=True)

    # 발신자 정보
    sender_name = Column(String(100))
    sender_email = Column(String(200))
    company_name = Column(String(200))
    service_name = Column(String(200))
    service_description = Column(Text)

    # SMTP 설정
    smtp_host = Column(String(200))
    smtp_port = Column(Integer, default=587)
    smtp_username = Column(String(200))
    smtp_password_encrypted = Column(Text)
    smtp_use_tls = Column(Boolean, default=True)

    # 발송 설정
    daily_limit = Column(Integer, default=50)
    hourly_limit = Column(Integer, default=10)
    min_interval_seconds = Column(Integer, default=300)  # 5분

    # 리드 스코어링 가중치
    weight_influence = Column(Float, default=0.4)
    weight_activity = Column(Float, default=0.3)
    weight_relevance = Column(Float, default=0.3)

    # 자동화 설정
    auto_collect = Column(Boolean, default=False)
    auto_extract_contact = Column(Boolean, default=True)
    auto_score = Column(Boolean, default=True)

    # 추적 설정
    track_opens = Column(Boolean, default=True)
    track_clicks = Column(Boolean, default=True)

    # 수신거부 문구
    unsubscribe_text = Column(Text, default="이 이메일 수신을 원치 않으시면 회신해 주세요.")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="outreach_settings")


class OutreachStats(Base):
    """일별 영업 통계"""
    __tablename__ = "outreach_stats"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    stat_date = Column(DateTime, nullable=False)

    # 수집 통계
    blogs_collected = Column(Integer, default=0)
    contacts_extracted = Column(Integer, default=0)

    # 발송 통계
    emails_sent = Column(Integer, default=0)
    emails_opened = Column(Integer, default=0)
    emails_clicked = Column(Integer, default=0)
    emails_replied = Column(Integer, default=0)
    emails_bounced = Column(Integer, default=0)

    # 비율
    open_rate = Column(Float)
    click_rate = Column(Float)
    reply_rate = Column(Float)

    # 카테고리별 통계
    category_breakdown = Column(JSON)
    grade_breakdown = Column(JSON)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="outreach_stats")
