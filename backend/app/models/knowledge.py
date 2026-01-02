"""
네이버 지식인 자동 답변 시스템 모델
"""
import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.db.database import Base


class QuestionStatus(str, Enum):
    NEW = "new"
    REVIEWING = "reviewing"
    ANSWERED = "answered"
    SKIPPED = "skipped"
    EXPIRED = "expired"


class AnswerStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    POSTED = "posted"
    REJECTED = "rejected"


class AnswerTone(str, Enum):
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    EMPATHETIC = "empathetic"
    FORMAL = "formal"


class Urgency(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class KnowledgeKeyword(Base):
    """모니터링 키워드"""
    __tablename__ = "knowledge_keywords"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    keyword = Column(String(100), nullable=False)  # 검색 키워드
    category = Column(String(50))  # 의료, 뷰티, 건강 등
    sub_category = Column(String(50))  # 세부 카테고리

    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=1)  # 우선순위 1-5

    # 통계
    question_count = Column(Integer, default=0)  # 발견된 질문 수
    answer_count = Column(Integer, default=0)  # 답변한 수

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="knowledge_keywords")
    questions = relationship("KnowledgeQuestion", back_populates="matched_keyword")


class KnowledgeQuestion(Base):
    """수집된 지식인 질문"""
    __tablename__ = "knowledge_questions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    keyword_id = Column(String(36), ForeignKey("knowledge_keywords.id"), nullable=True)

    # 네이버 지식인 정보
    naver_question_id = Column(String(50), unique=True)  # 네이버 질문 고유 ID
    title = Column(String(500), nullable=False)
    content = Column(Text)
    category = Column(String(100))  # 지식인 카테고리
    url = Column(String(500))

    # 질문자 정보
    author_name = Column(String(100))
    author_level = Column(String(50))  # 지식인 등급

    # 질문 상태
    view_count = Column(Integer, default=0)
    answer_count = Column(Integer, default=0)  # 기존 답변 수
    is_chosen = Column(Boolean, default=False)  # 채택 완료 여부
    reward_points = Column(Integer, default=0)  # 내공 점수

    # AI 분석 결과
    matched_keywords = Column(JSON)  # 매칭된 키워드 목록
    relevance_score = Column(Float, default=0)  # 관련성 점수 0-100
    urgency = Column(SQLEnum(Urgency), default=Urgency.MEDIUM)
    answer_difficulty = Column(String(20))  # easy, medium, hard
    recommended_tone = Column(String(50))  # 추천 답변 톤
    key_points = Column(JSON)  # 핵심 포인트

    # 처리 상태
    status = Column(SQLEnum(QuestionStatus), default=QuestionStatus.NEW)
    skip_reason = Column(String(200))  # 건너뛴 이유

    # 시간
    question_date = Column(DateTime)  # 질문 등록일
    collected_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="knowledge_questions")
    matched_keyword = relationship("KnowledgeKeyword", back_populates="questions")
    answers = relationship("KnowledgeAnswer", back_populates="question", cascade="all, delete-orphan")


class KnowledgeAnswer(Base):
    """생성된 답변"""
    __tablename__ = "knowledge_answers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    question_id = Column(String(36), ForeignKey("knowledge_questions.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    posted_account_id = Column(String(36), ForeignKey("naver_accounts.id"), nullable=True)  # 게시에 사용된 계정

    # 답변 내용
    content = Column(Text, nullable=False)  # AI 생성 원본
    edited_content = Column(Text)  # 수정된 내용
    final_content = Column(Text)  # 최종 답변 (수정됐으면 수정본, 아니면 원본)

    # 답변 스타일
    tone = Column(SQLEnum(AnswerTone), default=AnswerTone.PROFESSIONAL)
    include_promotion = Column(Boolean, default=True)
    promotion_text = Column(Text)  # 삽입된 홍보 문구

    # 링크
    blog_link = Column(String(500))  # 관련 블로그 링크
    place_link = Column(String(500))  # 플레이스 링크
    related_post_id = Column(String(36))  # 관련 블로그 글 ID

    # 품질 평가
    quality_score = Column(Float)  # AI 품질 점수 0-100
    professionalism_score = Column(Float)  # 전문성 점수
    readability_score = Column(Float)  # 가독성 점수

    # 상태
    status = Column(SQLEnum(AnswerStatus), default=AnswerStatus.DRAFT)
    rejection_reason = Column(String(200))  # 반려 사유

    # 발행 정보
    posted_at = Column(DateTime)
    naver_answer_id = Column(String(50))  # 등록된 답변 ID
    naver_answer_url = Column(String(500))

    # 성과 추적
    is_chosen = Column(Boolean, default=False)  # 채택 여부
    helpful_count = Column(Integer, default=0)  # 도움됐어요 수

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    question = relationship("KnowledgeQuestion", back_populates="answers")
    user = relationship("User", back_populates="knowledge_answers")
    posted_account = relationship("NaverAccount", backref="knowledge_answers")


class AnswerTemplate(Base):
    """답변 템플릿"""
    __tablename__ = "answer_templates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    name = Column(String(100), nullable=False)
    description = Column(String(500))
    category = Column(String(50))  # 질문 카테고리

    # 매칭 조건
    question_patterns = Column(JSON)  # 질문 패턴 목록
    keywords = Column(JSON)  # 관련 키워드

    # 템플릿 내용
    template_content = Column(Text, nullable=False)
    variables = Column(JSON)  # 변수 목록 [{name, description, default}]

    # 스타일
    tone = Column(SQLEnum(AnswerTone), default=AnswerTone.PROFESSIONAL)
    include_greeting = Column(Boolean, default=True)
    include_closing = Column(Boolean, default=True)

    # 통계
    usage_count = Column(Integer, default=0)
    success_rate = Column(Float)  # 채택률

    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="answer_templates")


class AutoAnswerSetting(Base):
    """자동 답변 설정"""
    __tablename__ = "auto_answer_settings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, unique=True)

    # 활성화 설정
    is_enabled = Column(Boolean, default=False)
    auto_collect = Column(Boolean, default=True)  # 자동 수집
    auto_generate = Column(Boolean, default=False)  # 자동 답변 생성
    auto_approve = Column(Boolean, default=False)  # 자동 승인 (위험)

    # 필터링 조건
    min_relevance_score = Column(Float, default=70.0)  # 최소 관련성 점수
    auto_approve_threshold = Column(Float, default=90.0)  # 자동 승인 기준
    min_reward_points = Column(Integer, default=0)  # 최소 내공
    max_existing_answers = Column(Integer, default=5)  # 최대 기존 답변 수

    # 제한 설정
    daily_collect_limit = Column(Integer, default=100)  # 일일 수집 제한
    daily_answer_limit = Column(Integer, default=20)  # 일일 답변 제한

    # 시간 설정
    working_hours = Column(JSON)  # {"start": "09:00", "end": "18:00"}
    working_days = Column(JSON)  # [1,2,3,4,5] (월-금)

    # 제외 설정
    exclude_keywords = Column(JSON)  # 제외할 키워드
    exclude_categories = Column(JSON)  # 제외할 카테고리
    exclude_authors = Column(JSON)  # 제외할 작성자

    # 답변 스타일 기본값
    default_tone = Column(SQLEnum(AnswerTone), default=AnswerTone.PROFESSIONAL)
    default_include_promotion = Column(Boolean, default=True)
    default_blog_link = Column(String(500))
    default_place_link = Column(String(500))

    # 알림 설정
    notification_enabled = Column(Boolean, default=True)
    notification_channels = Column(JSON)  # ["email", "kakao"]
    notify_on_new_question = Column(Boolean, default=True)
    notify_on_high_relevance = Column(Boolean, default=True)
    notify_on_answer_chosen = Column(Boolean, default=True)

    # 통계
    total_collected = Column(Integer, default=0)
    total_answered = Column(Integer, default=0)
    total_chosen = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="auto_answer_settings")


class KnowledgeStats(Base):
    """일별 통계"""
    __tablename__ = "knowledge_stats"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    stat_date = Column(DateTime, nullable=False)

    # 수집 통계
    questions_collected = Column(Integer, default=0)
    high_relevance_count = Column(Integer, default=0)  # 고관련성 질문 수

    # 답변 통계
    answers_generated = Column(Integer, default=0)
    answers_approved = Column(Integer, default=0)
    answers_posted = Column(Integer, default=0)
    answers_chosen = Column(Integer, default=0)

    # 성과
    total_views = Column(Integer, default=0)  # 답변 조회수
    total_helpful = Column(Integer, default=0)  # 도움됐어요 총합

    # 키워드별 통계
    keyword_breakdown = Column(JSON)  # {keyword: {collected, answered, chosen}}
    category_breakdown = Column(JSON)  # {category: {collected, answered}}

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="knowledge_stats")
