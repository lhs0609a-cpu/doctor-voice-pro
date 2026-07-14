"""
평판 모니터링 시스템 모델
- 전 플랫폼 리뷰/멘션 수집, AI 감성분석, 위험도 평가, 대응 답변 생성
"""
import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.db.database import Base


# ==================== Enums ====================

class MentionPlatform(str, Enum):
    """멘션 플랫폼"""
    NAVER_PLACE = "naver_place"
    GOOGLE_MAPS = "google_maps"
    KAKAO_MAP = "kakao_map"
    NAVER_BLOG = "naver_blog"
    NAVER_CAFE = "naver_cafe"
    DCINSIDE = "dcinside"
    FMKOREA = "fmkorea"
    THEQOO = "theqoo"
    BLIND = "blind"
    DANGGEUN = "danggeun"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    BAEMIN = "baemin"
    YOGIYO = "yogiyo"
    GANGNAM_UNNI = "gangnam_unni"
    BABITALK = "babitalk"
    OTHER = "other"


class MentionSentiment(str, Enum):
    """감성 분류"""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"


class RiskLevel(str, Enum):
    """위험도 수준"""
    CRITICAL = "critical"      # 즉시 대응 필요 (명예훼손, 허위사실 등)
    WARNING = "warning"        # 주의 필요 (부정적 리뷰, 불만 표현)
    NORMAL = "normal"          # 일반적 멘션
    POSITIVE = "positive"      # 긍정적 멘션


class MentionStatus(str, Enum):
    """멘션 대응 상태"""
    NEW = "new"                # 새로운 멘션
    READ = "read"              # 읽음
    RESPONDING = "responding"  # 대응 중
    RESPONDED = "responded"    # 대응 완료
    ESCALATED = "escalated"    # 에스컬레이션됨
    RESOLVED = "resolved"      # 해결됨
    IGNORED = "ignored"        # 무시


class ResponseStyle(str, Enum):
    """대응 답변 스타일"""
    APOLOGETIC = "apologetic"    # 사과형
    EXPLANATORY = "explanatory"  # 설명형
    COMPENSATORY = "compensatory"  # 보상형


class CrawlJobStatus(str, Enum):
    """크롤링 작업 상태"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AlertSeverity(str, Enum):
    """알림 심각도"""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class SpreadStatus(str, Enum):
    """확산 사건 상태"""
    MONITORING = "monitoring"   # 모니터링 중
    SPREADING = "spreading"     # 확산 중
    CONTAINED = "contained"     # 억제됨
    RESOLVED = "resolved"       # 해결됨


class GuideCategory(str, Enum):
    """가이드 카테고리"""
    REPORT = "report"           # 신고
    DELETE_REQUEST = "delete_request"  # 삭제 요청
    LEGAL = "legal"             # 법적 대응
    REPLY = "reply"             # 답변 작성
    PREVENTION = "prevention"   # 예방


# ==================== Models ====================

class MonitorProfile(Base):
    """사업장별 모니터링 설정"""
    __tablename__ = "reputation_monitor_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # 사업장 기본 정보
    business_name = Column(String(200), nullable=False)  # 상호명
    business_type = Column(String(100))  # 업종 (병원, 음식점, 카페 등)
    address = Column(String(500))  # 주소
    phone = Column(String(50))

    # 플랫폼 ID 매핑
    naver_place_id = Column(String(100))  # 네이버 플레이스 ID
    google_place_id = Column(String(200))  # 구글 플레이스 ID
    kakao_place_id = Column(String(100))  # 카카오맵 ID
    baemin_store_id = Column(String(100))  # 배민 매장 ID
    yogiyo_store_id = Column(String(100))  # 요기요 매장 ID

    # 모니터링 키워드
    keywords = Column(JSON)  # ["상호명", "원장님", "대표메뉴" 등]
    negative_keywords = Column(JSON)  # 부정 키워드 알림 트리거

    # 크롤링 설정
    crawl_interval_minutes = Column(Integer, default=60)  # 크롤링 주기 (분)
    enabled_platforms = Column(JSON)  # ["naver_place", "google_maps", ...]
    is_active = Column(Boolean, default=True)

    # 알림 설정
    alert_email = Column(String(200))
    alert_phone = Column(String(50))
    alert_kakao = Column(String(100))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", backref="monitor_profiles")
    mentions = relationship("Mention", back_populates="profile", cascade="all, delete-orphan")
    snapshots = relationship("ReputationSnapshot", back_populates="profile", cascade="all, delete-orphan")
    crawl_jobs = relationship("ReputationCrawlJob", back_populates="profile", cascade="all, delete-orphan")
    competitors = relationship("ReputationCompetitor", back_populates="profile", cascade="all, delete-orphan")
    alert_rules = relationship("ReputationAlertRule", back_populates="profile", cascade="all, delete-orphan")


class Mention(Base):
    """수집된 멘션/리뷰 (모든 플랫폼 통합)"""
    __tablename__ = "reputation_mentions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id = Column(String(36), ForeignKey("reputation_monitor_profiles.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # 플랫폼 정보
    platform = Column(SQLEnum(MentionPlatform), nullable=False)
    platform_post_id = Column(String(200))  # 플랫폼 내 고유 ID (중복 방지)
    source_url = Column(String(1000))  # 원본 URL

    # 콘텐츠
    author_name = Column(String(200))
    author_id = Column(String(200))  # 플랫폼 내 작성자 ID
    title = Column(String(500))  # 제목 (게시글인 경우)
    content = Column(Text, nullable=False)  # 본문
    rating = Column(Float)  # 별점 (리뷰인 경우, 1-5)
    images = Column(JSON)  # 이미지 URL 목록

    # AI 분석 결과
    sentiment = Column(SQLEnum(MentionSentiment))
    sentiment_score = Column(Float)  # -1.0 ~ 1.0
    risk_level = Column(SQLEnum(RiskLevel), default=RiskLevel.NORMAL)
    risk_score = Column(Integer, default=0)  # 0-100
    issues = Column(JSON)  # ["서비스", "가격", "청결"] 등 추출된 이슈
    spread_potential = Column(Float, default=0)  # 확산 가능성 0-100
    is_defamation = Column(Boolean, default=False)  # 명예훼손 여부
    ai_summary = Column(Text)  # AI 요약

    # 플랫폼별 추가 데이터 (JSON으로 유연하게)
    platform_data = Column(JSON)  # 좋아요 수, 댓글 수, 조회수 등

    # 상태 관리
    status = Column(SQLEnum(MentionStatus), default=MentionStatus.NEW)
    is_bookmarked = Column(Boolean, default=False)
    note = Column(Text)  # 관리자 메모

    # 확산 추적
    spread_incident_id = Column(String(36), ForeignKey("reputation_spread_incidents.id"), nullable=True)

    # 타임스탬프
    published_at = Column(DateTime)  # 원본 게시 시간
    collected_at = Column(DateTime, default=datetime.utcnow)
    analyzed_at = Column(DateTime)
    responded_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    profile = relationship("MonitorProfile", back_populates="mentions")
    responses = relationship("GeneratedMentionResponse", back_populates="mention", cascade="all, delete-orphan")
    spread_incident = relationship("SpreadIncident", back_populates="mentions")


class GeneratedMentionResponse(Base):
    """AI 생성 대응 답변"""
    __tablename__ = "reputation_generated_responses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mention_id = Column(String(36), ForeignKey("reputation_mentions.id"), nullable=False)

    # 답변 내용
    style = Column(SQLEnum(ResponseStyle), nullable=False)
    content = Column(Text, nullable=False)

    # 메타
    is_selected = Column(Boolean, default=False)  # 사용자가 선택한 답변
    is_posted = Column(Boolean, default=False)  # 실제 게시 여부
    edited_content = Column(Text)  # 사용자가 수정한 내용

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    mention = relationship("Mention", back_populates="responses")


class ReputationAlertRule(Base):
    """알림 규칙"""
    __tablename__ = "reputation_alert_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id = Column(String(36), ForeignKey("reputation_monitor_profiles.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # 규칙 이름
    name = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True)

    # 조건
    severity = Column(SQLEnum(AlertSeverity), nullable=False)  # critical, warning, info
    platforms = Column(JSON)  # 대상 플랫폼 목록 (null이면 전체)
    keyword_contains = Column(JSON)  # 포함 키워드
    min_risk_score = Column(Integer)  # 최소 위험도 점수
    sentiment_filter = Column(JSON)  # ["negative", "mixed"]
    min_rating = Column(Float)  # 이하 별점 알림 (예: 2.0 이하)
    max_rating = Column(Float)

    # 알림 채널
    notify_email = Column(Boolean, default=True)
    notify_sms = Column(Boolean, default=False)
    notify_kakao = Column(Boolean, default=False)
    notify_webhook_url = Column(String(500))

    # 쿨다운 (같은 규칙 반복 알림 방지)
    cooldown_minutes = Column(Integer, default=30)
    last_triggered_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    profile = relationship("MonitorProfile", back_populates="alert_rules")
    logs = relationship("ReputationAlertLog", back_populates="rule", cascade="all, delete-orphan")


class ReputationAlertLog(Base):
    """알림 발송 기록"""
    __tablename__ = "reputation_alert_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_id = Column(String(36), ForeignKey("reputation_alert_rules.id"), nullable=False)
    mention_id = Column(String(36), ForeignKey("reputation_mentions.id"), nullable=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # 알림 내용
    severity = Column(SQLEnum(AlertSeverity), nullable=False)
    title = Column(String(500), nullable=False)
    message = Column(Text, nullable=False)
    channel = Column(String(50))  # email, sms, kakao, webhook

    # 발송 결과
    is_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime)
    error_message = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    rule = relationship("ReputationAlertRule", back_populates="logs")


class SpreadIncident(Base):
    """확산 사건 추적"""
    __tablename__ = "reputation_spread_incidents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    profile_id = Column(String(36), ForeignKey("reputation_monitor_profiles.id"), nullable=False)

    # 사건 정보
    title = Column(String(500), nullable=False)
    description = Column(Text)
    status = Column(SQLEnum(SpreadStatus), default=SpreadStatus.MONITORING)

    # 확산 데이터
    first_detected_at = Column(DateTime, default=datetime.utcnow)
    platform_count = Column(Integer, default=1)  # 확산된 플랫폼 수
    mention_count = Column(Integer, default=1)  # 관련 멘션 수
    estimated_reach = Column(Integer, default=0)  # 추정 노출 수
    timeline = Column(JSON)  # [{time, platform, event, url}] 타임라인

    # 대응
    response_plan = Column(Text)  # 대응 계획
    resolved_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    mentions = relationship("Mention", back_populates="spread_incident")


class ReputationSnapshot(Base):
    """일별 평판 점수 기록"""
    __tablename__ = "reputation_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id = Column(String(36), ForeignKey("reputation_monitor_profiles.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # 날짜
    snapshot_date = Column(DateTime, nullable=False)

    # 종합 점수
    reputation_score = Column(Float)  # 0-100 종합 평판 점수
    avg_rating = Column(Float)  # 평균 별점

    # 감성 분포
    positive_count = Column(Integer, default=0)
    neutral_count = Column(Integer, default=0)
    negative_count = Column(Integer, default=0)
    mixed_count = Column(Integer, default=0)

    # 플랫폼별 통계
    platform_stats = Column(JSON)  # {platform: {count, avg_rating, sentiment_dist}}

    # 주요 이슈
    top_issues = Column(JSON)  # [{issue, count, sentiment}]
    top_keywords = Column(JSON)  # [{keyword, count}]

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    profile = relationship("MonitorProfile", back_populates="snapshots")


class ReputationCompetitor(Base):
    """경쟁사 정보"""
    __tablename__ = "reputation_competitors"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id = Column(String(36), ForeignKey("reputation_monitor_profiles.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # 경쟁사 정보
    business_name = Column(String(200), nullable=False)
    naver_place_id = Column(String(100))
    google_place_id = Column(String(200))
    address = Column(String(500))

    # 현재 지표
    current_rating = Column(Float)
    review_count = Column(Integer, default=0)
    reputation_score = Column(Float)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    profile = relationship("MonitorProfile", back_populates="competitors")
    snapshots = relationship("ReputationCompetitorSnapshot", back_populates="competitor", cascade="all, delete-orphan")


class ReputationCompetitorSnapshot(Base):
    """경쟁사 일별 점수"""
    __tablename__ = "reputation_competitor_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    competitor_id = Column(String(36), ForeignKey("reputation_competitors.id"), nullable=False)

    snapshot_date = Column(DateTime, nullable=False)
    avg_rating = Column(Float)
    review_count = Column(Integer, default=0)
    reputation_score = Column(Float)
    new_review_count = Column(Integer, default=0)
    sentiment_distribution = Column(JSON)  # {positive, neutral, negative}

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    competitor = relationship("ReputationCompetitor", back_populates="snapshots")


class ReputationCrawlJob(Base):
    """크롤링 작업 로그"""
    __tablename__ = "reputation_crawl_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id = Column(String(36), ForeignKey("reputation_monitor_profiles.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # 작업 정보
    platform = Column(SQLEnum(MentionPlatform), nullable=False)
    status = Column(SQLEnum(CrawlJobStatus), default=CrawlJobStatus.PENDING)
    trigger_type = Column(String(50), default="scheduled")  # scheduled, manual

    # 결과
    mentions_found = Column(Integer, default=0)
    mentions_new = Column(Integer, default=0)
    error_message = Column(Text)

    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    profile = relationship("MonitorProfile", back_populates="crawl_jobs")


class PlatformGuide(Base):
    """플랫폼별 대응 가이드"""
    __tablename__ = "reputation_platform_guides"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 가이드 분류
    platform = Column(SQLEnum(MentionPlatform), nullable=False)
    category = Column(SQLEnum(GuideCategory), nullable=False)
    title = Column(String(500), nullable=False)

    # 가이드 내용
    description = Column(Text)
    steps = Column(JSON)  # [{step_number, title, description, image_url}]
    legal_basis = Column(JSON)  # [{law, article, description}]
    tips = Column(JSON)  # ["팁1", "팁2"]
    template_text = Column(Text)  # 내용증명, 신고 양식 등 템플릿

    # 메타
    difficulty = Column(String(20))  # easy, medium, hard
    estimated_days = Column(Integer)  # 예상 소요 일수
    success_rate = Column(Float)  # 성공률

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
