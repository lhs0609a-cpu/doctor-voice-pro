"""
바이럴 마케팅 공통 모델
- 다중 계정 관리
- 성과 추적
- 알림 설정
- 프록시 관리
- A/B 테스트
"""

import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON, Date
from sqlalchemy.orm import relationship
from app.db.database import Base


# ==================== Enums ====================

class AccountStatus(str, Enum):
    """계정 상태"""
    ACTIVE = "active"           # 활성
    WARMING = "warming"         # 워밍업 중
    RESTING = "resting"         # 휴식 중
    BLOCKED = "blocked"         # 차단됨
    DISABLED = "disabled"       # 비활성화


class NotificationType(str, Enum):
    """알림 유형"""
    SLACK = "slack"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    KAKAO = "kakao"
    EMAIL = "email"
    WEBHOOK = "webhook"


class ProxyType(str, Enum):
    """프록시 유형"""
    HTTP = "http"
    HTTPS = "https"
    SOCKS5 = "socks5"


class ABTestStatus(str, Enum):
    """A/B 테스트 상태"""
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


class PerformanceEventType(str, Enum):
    """성과 이벤트 유형"""
    # 지식인
    ANSWER_POSTED = "answer_posted"
    ANSWER_ADOPTED = "answer_adopted"
    ANSWER_LIKED = "answer_liked"
    ANSWER_REPORTED = "answer_reported"
    # 카페
    COMMENT_POSTED = "comment_posted"
    COMMENT_LIKED = "comment_liked"
    COMMENT_REPLIED = "comment_replied"
    POST_CREATED = "post_created"
    POST_LIKED = "post_liked"
    POST_VIEWED = "post_viewed"
    # 공통
    LINK_CLICKED = "link_clicked"
    PROFILE_VISITED = "profile_visited"


# ==================== 다중 계정 관리 ====================

class NaverAccount(Base):
    """네이버 계정 관리"""
    __tablename__ = "naver_accounts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # 계정 정보
    account_id = Column(String(100), nullable=False)  # 네이버 아이디
    account_name = Column(String(100))  # 별칭
    encrypted_password = Column(Text)  # 암호화된 비밀번호

    # 상태
    status = Column(String(20), default=AccountStatus.ACTIVE.value)
    last_login_at = Column(DateTime)
    last_activity_at = Column(DateTime)
    login_fail_count = Column(Integer, default=0)

    # 활동 제한
    daily_answer_limit = Column(Integer, default=10)
    daily_comment_limit = Column(Integer, default=20)
    daily_post_limit = Column(Integer, default=3)
    min_activity_interval = Column(Integer, default=300)  # 초

    # 오늘 활동량
    today_answers = Column(Integer, default=0)
    today_comments = Column(Integer, default=0)
    today_posts = Column(Integer, default=0)
    last_reset_date = Column(Date)

    # 워밍업 설정
    is_warming_up = Column(Boolean, default=False)
    warming_start_date = Column(Date)
    warming_day = Column(Integer, default=0)  # 워밍업 며칠차

    # 성과
    total_answers = Column(Integer, default=0)
    total_adoptions = Column(Integer, default=0)
    total_comments = Column(Integer, default=0)
    total_likes = Column(Integer, default=0)
    adoption_rate = Column(Float, default=0.0)

    # 프록시 설정
    proxy_id = Column(String(36), ForeignKey("proxy_servers.id"), nullable=True)

    # 쿠키/세션
    session_cookies = Column(Text)  # JSON 형태로 저장
    session_expires_at = Column(DateTime)

    # 용도 구분
    use_for_knowledge = Column(Boolean, default=True)
    use_for_cafe = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="naver_accounts")
    proxy = relationship("ProxyServer", back_populates="accounts")
    performance_events = relationship("PerformanceEvent", back_populates="account")


# ==================== 프록시 관리 ====================

class ProxyServer(Base):
    """프록시 서버"""
    __tablename__ = "proxy_servers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # 프록시 정보
    name = Column(String(100))
    proxy_type = Column(String(20), default=ProxyType.HTTP.value)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    username = Column(String(100))
    encrypted_password = Column(Text)

    # 상태
    is_active = Column(Boolean, default=True)
    last_checked_at = Column(DateTime)
    last_success_at = Column(DateTime)
    fail_count = Column(Integer, default=0)
    avg_response_time = Column(Float)  # 밀리초

    # 위치 정보
    country = Column(String(50))
    city = Column(String(100))
    ip_address = Column(String(50))

    # 사용량
    total_requests = Column(Integer, default=0)
    success_requests = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="proxy_servers")
    accounts = relationship("NaverAccount", back_populates="proxy")


# ==================== 성과 추적 ====================

class PerformanceEvent(Base):
    """성과 이벤트"""
    __tablename__ = "performance_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    account_id = Column(String(36), ForeignKey("naver_accounts.id"), nullable=True)

    # 이벤트 정보
    event_type = Column(String(50), nullable=False)
    platform = Column(String(20), nullable=False)  # knowledge / cafe

    # 대상 정보
    target_id = Column(String(100))  # 답변 ID 또는 댓글 ID
    target_url = Column(Text)
    target_title = Column(String(500))

    # 상세 데이터
    event_data = Column(JSON)  # 추가 데이터

    # 관련 링크 클릭 추적
    blog_link = Column(Text)
    place_link = Column(Text)
    link_clicks = Column(Integer, default=0)

    # A/B 테스트 관련
    ab_test_id = Column(String(36), ForeignKey("ab_tests.id"), nullable=True)
    ab_variant = Column(String(50))  # A, B, C...

    event_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="performance_events")
    account = relationship("NaverAccount", back_populates="performance_events")
    ab_test = relationship("ABTest", back_populates="events")


class PerformanceDaily(Base):
    """일별 성과 통계"""
    __tablename__ = "performance_daily"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False)
    platform = Column(String(20), nullable=False)  # knowledge / cafe / all

    # 지식인 성과
    answers_posted = Column(Integer, default=0)
    answers_adopted = Column(Integer, default=0)
    answer_likes = Column(Integer, default=0)

    # 카페 성과
    comments_posted = Column(Integer, default=0)
    comment_likes = Column(Integer, default=0)
    comment_replies = Column(Integer, default=0)
    posts_created = Column(Integer, default=0)
    post_likes = Column(Integer, default=0)

    # 링크 클릭
    blog_clicks = Column(Integer, default=0)
    place_clicks = Column(Integer, default=0)

    # 계정별 상세
    account_breakdown = Column(JSON)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="performance_daily")


# ==================== 알림 설정 ====================

class NotificationChannel(Base):
    """알림 채널"""
    __tablename__ = "notification_channels"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # 채널 정보
    name = Column(String(100), nullable=False)
    channel_type = Column(String(20), nullable=False)

    # 설정 (채널별로 다름)
    # Slack: webhook_url
    # Telegram: bot_token, chat_id
    # Discord: webhook_url
    # Kakao: access_token
    # Email: email_address
    config = Column(JSON, nullable=False)

    # 활성화
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    # 알림 유형별 설정
    notify_adoption = Column(Boolean, default=True)  # 채택 알림
    notify_daily_report = Column(Boolean, default=True)  # 일일 리포트
    notify_warning = Column(Boolean, default=True)  # 경고 알림
    notify_error = Column(Boolean, default=True)  # 오류 알림

    # 사용 통계
    total_sent = Column(Integer, default=0)
    last_sent_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="notification_channels")
    logs = relationship("NotificationLog", back_populates="channel")


class NotificationLog(Base):
    """알림 로그"""
    __tablename__ = "notification_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    channel_id = Column(String(36), ForeignKey("notification_channels.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # 알림 내용
    title = Column(String(255))
    message = Column(Text, nullable=False)
    notification_type = Column(String(50))  # adoption, daily_report, warning, error

    # 상태
    is_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime)
    error_message = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    channel = relationship("NotificationChannel", back_populates="logs")
    user = relationship("User", back_populates="notification_logs")


# ==================== A/B 테스트 ====================

class ABTest(Base):
    """A/B 테스트"""
    __tablename__ = "ab_tests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # 테스트 정보
    name = Column(String(200), nullable=False)
    description = Column(Text)
    platform = Column(String(20), nullable=False)  # knowledge / cafe

    # 테스트 대상
    test_type = Column(String(50))  # tone, length, promotion, template

    # 변형 설정
    variants = Column(JSON, nullable=False)
    # 예: [
    #   {"name": "A", "tone": "friendly", "weight": 50},
    #   {"name": "B", "tone": "professional", "weight": 50}
    # ]

    # 상태
    status = Column(String(20), default=ABTestStatus.DRAFT.value)
    start_date = Column(DateTime)
    end_date = Column(DateTime)

    # 목표
    target_metric = Column(String(50))  # adoption_rate, like_rate, click_rate
    target_sample_size = Column(Integer, default=100)

    # 결과
    current_sample_size = Column(Integer, default=0)
    winner_variant = Column(String(50))
    confidence_level = Column(Float)  # 통계적 신뢰도

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="ab_tests")
    events = relationship("PerformanceEvent", back_populates="ab_test")
    results = relationship("ABTestResult", back_populates="test")


class ABTestResult(Base):
    """A/B 테스트 결과"""
    __tablename__ = "ab_test_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_id = Column(String(36), ForeignKey("ab_tests.id"), nullable=False)

    # 변형
    variant = Column(String(50), nullable=False)

    # 샘플
    sample_size = Column(Integer, default=0)

    # 지표
    total_impressions = Column(Integer, default=0)
    total_conversions = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0.0)

    # 세부 지표
    adoptions = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    replies = Column(Integer, default=0)

    # 통계
    avg_quality_score = Column(Float)
    avg_response_time = Column(Float)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    test = relationship("ABTest", back_populates="results")


# ==================== 일일 리포트 ====================

class DailyReport(Base):
    """일일 리포트"""
    __tablename__ = "daily_reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    report_date = Column(Date, nullable=False)

    # 요약
    summary = Column(JSON)
    # {
    #   "total_activities": 50,
    #   "knowledge": {"answers": 10, "adoptions": 3, "adoption_rate": 30},
    #   "cafe": {"comments": 30, "posts": 2, "likes": 15},
    #   "performance_change": 5.2  # 전일 대비 %
    # }

    # 상세 데이터
    knowledge_details = Column(JSON)
    cafe_details = Column(JSON)
    account_details = Column(JSON)
    top_performers = Column(JSON)  # 상위 성과 콘텐츠
    recommendations = Column(JSON)  # AI 추천사항

    # 발송 상태
    is_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime)
    sent_channels = Column(JSON)  # 발송된 채널 목록

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="daily_reports")
