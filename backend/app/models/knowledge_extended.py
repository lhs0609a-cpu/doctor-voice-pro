"""
지식인 확장 모델
- 채택률 추적
- 경쟁 답변 분석
- 이미지 첨부
- 질문자 분석
"""

import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON, Date
from sqlalchemy.orm import relationship
from app.db.database import Base


# ==================== Enums ====================

class AdoptionStatus(str, Enum):
    """채택 상태"""
    PENDING = "pending"       # 대기중
    ADOPTED = "adopted"       # 채택됨
    NOT_ADOPTED = "not_adopted"  # 미채택
    EXPIRED = "expired"       # 마감됨


class QuestionerType(str, Enum):
    """질문자 유형"""
    POTENTIAL_CUSTOMER = "potential_customer"  # 잠재 고객
    INFORMATION_SEEKER = "information_seeker"  # 정보 탐색자
    COMPETITOR = "competitor"    # 경쟁사
    SPAMMER = "spammer"          # 스팸
    UNKNOWN = "unknown"          # 알 수 없음


# ==================== 채택 추적 ====================

class AnswerAdoption(Base):
    """답변 채택 추적"""
    __tablename__ = "answer_adoptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    answer_id = Column(String(36), ForeignKey("knowledge_answers.id"), nullable=False)
    question_id = Column(String(36), ForeignKey("knowledge_questions.id"), nullable=False)

    # 상태
    status = Column(String(20), default=AdoptionStatus.PENDING.value)
    checked_at = Column(DateTime)
    check_count = Column(Integer, default=0)

    # 채택 정보
    is_adopted = Column(Boolean, default=False)
    adopted_at = Column(DateTime)
    adoption_rank = Column(Integer)  # 몇 번째로 채택되었는지

    # 경쟁 정보
    total_answers = Column(Integer, default=0)
    competitor_answers = Column(Integer, default=0)  # 경쟁 답변 수

    # 질문 마감
    question_closed = Column(Boolean, default=False)
    question_closed_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="answer_adoptions")


# ==================== 경쟁 답변 분석 ====================

class CompetitorAnswer(Base):
    """경쟁 답변"""
    __tablename__ = "competitor_answers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    question_id = Column(String(36), ForeignKey("knowledge_questions.id"), nullable=False)

    # 답변 정보
    answer_id = Column(String(100), nullable=False)  # 네이버 답변 ID
    author_name = Column(String(100))
    author_id = Column(String(100))
    author_level = Column(String(50))  # 등급

    # 내용
    content = Column(Text)
    content_length = Column(Integer)
    has_image = Column(Boolean, default=False)
    has_link = Column(Boolean, default=False)
    image_count = Column(Integer, default=0)

    # 성과
    is_adopted = Column(Boolean, default=False)
    like_count = Column(Integer, default=0)

    # AI 분석
    quality_score = Column(Float)
    tone = Column(String(50))
    strengths = Column(JSON)  # ["전문적", "친절", "상세"]
    weaknesses = Column(JSON)
    key_points = Column(JSON)  # 핵심 포인트

    # 참고 여부
    is_reference = Column(Boolean, default=False)  # 참고할 만한 답변인지

    collected_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="competitor_answers")


class AnswerStrategy(Base):
    """답변 전략 (경쟁 분석 기반)"""
    __tablename__ = "answer_strategies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    question_id = Column(String(36), ForeignKey("knowledge_questions.id"), nullable=False)

    # 경쟁 분석 요약
    competitor_count = Column(Integer, default=0)
    avg_content_length = Column(Integer)
    image_usage_rate = Column(Float)  # 이미지 사용률
    link_usage_rate = Column(Float)

    # AI 추천 전략
    recommended_length = Column(Integer)
    recommended_tone = Column(String(50))
    recommended_structure = Column(JSON)  # ["인사", "공감", "정보", "추천"]
    include_image = Column(Boolean, default=False)
    include_link = Column(Boolean, default=True)

    # 차별화 포인트
    differentiation_points = Column(JSON)
    # ["더 상세한 설명", "실제 사례 포함", "이미지 추가"]

    # 예상 채택 확률
    adoption_probability = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="answer_strategies")


# ==================== 이미지 첨부 ====================

class AnswerImage(Base):
    """답변 이미지"""
    __tablename__ = "answer_images"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    answer_id = Column(String(36), ForeignKey("knowledge_answers.id"), nullable=True)

    # 이미지 정보
    image_type = Column(String(50))  # diagram, infographic, example, logo
    image_url = Column(Text, nullable=False)
    thumbnail_url = Column(Text)
    original_filename = Column(String(255))

    # 크기
    width = Column(Integer)
    height = Column(Integer)
    file_size = Column(Integer)  # bytes

    # 설명
    alt_text = Column(String(500))
    caption = Column(Text)

    # AI 생성 여부
    is_ai_generated = Column(Boolean, default=False)
    generation_prompt = Column(Text)

    # 사용 통계
    usage_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="answer_images")


class ImageTemplate(Base):
    """이미지 템플릿"""
    __tablename__ = "image_templates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # 템플릿 정보
    name = Column(String(200), nullable=False)
    category = Column(String(100))  # 의료, 뷰티, 건강
    template_type = Column(String(50))  # diagram, chart, infographic

    # 이미지
    base_image_url = Column(Text)
    preview_url = Column(Text)

    # 설정
    variables = Column(JSON)  # ["병원명", "시술명", "가격"]
    default_values = Column(JSON)

    # 사용 통계
    usage_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="image_templates")


# ==================== 질문자 분석 ====================

class QuestionerProfile(Base):
    """질문자 프로필"""
    __tablename__ = "questioner_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # 질문자 정보
    questioner_id = Column(String(100), nullable=False)  # 네이버 ID
    questioner_name = Column(String(100))

    # 활동 분석
    total_questions = Column(Integer, default=0)
    question_categories = Column(JSON)  # {"의료": 5, "뷰티": 3}
    avg_reward_points = Column(Float)
    adoption_rate = Column(Float)  # 채택률

    # 행동 패턴
    question_frequency = Column(String(50))  # high, medium, low
    typical_question_time = Column(JSON)  # {"hour": 14, "day_of_week": 2}
    prefers_detailed_answer = Column(Boolean)
    prefers_image = Column(Boolean)

    # 분류
    questioner_type = Column(String(50), default=QuestionerType.UNKNOWN.value)
    is_potential_customer = Column(Boolean, default=False)
    customer_score = Column(Float)  # 잠재 고객 점수 (0-100)

    # AI 분석
    interests = Column(JSON)  # ["피부관리", "여드름", "레이저"]
    concerns = Column(JSON)  # ["가격", "부작용", "효과"]
    location_hints = Column(JSON)  # 위치 관련 힌트

    # 주의 사항
    is_competitor = Column(Boolean, default=False)
    is_blacklisted = Column(Boolean, default=False)
    blacklist_reason = Column(Text)

    first_seen_at = Column(DateTime)
    last_seen_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="questioner_profiles")


# ==================== 내공 우선순위 ====================

class RewardPriorityRule(Base):
    """내공 우선순위 규칙"""
    __tablename__ = "reward_priority_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # 규칙 이름
    name = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True)

    # 우선순위 설정
    min_reward_points = Column(Integer, default=0)
    max_reward_points = Column(Integer)
    priority_boost = Column(Float, default=1.0)  # 우선순위 배수

    # 추가 조건
    categories = Column(JSON)  # 적용 카테고리
    keywords = Column(JSON)  # 포함 키워드
    exclude_keywords = Column(JSON)  # 제외 키워드

    # 시간 조건
    max_question_age_hours = Column(Integer)  # 질문 최대 경과 시간
    max_existing_answers = Column(Integer)  # 기존 답변 최대 수

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="reward_priority_rules")


# ==================== 답변 성과 상세 ====================

class AnswerPerformance(Base):
    """답변 성과 상세"""
    __tablename__ = "answer_performances"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    answer_id = Column(String(36), ForeignKey("knowledge_answers.id"), nullable=False)
    account_id = Column(String(36), ForeignKey("naver_accounts.id"), nullable=True)

    # 게시 정보
    posted_at = Column(DateTime)
    posted_url = Column(Text)

    # 채택
    is_adopted = Column(Boolean, default=False)
    adopted_at = Column(DateTime)
    adoption_check_count = Column(Integer, default=0)
    last_checked_at = Column(DateTime)

    # 성과 지표
    like_count = Column(Integer, default=0)
    view_count = Column(Integer, default=0)

    # 링크 클릭
    blog_clicks = Column(Integer, default=0)
    place_clicks = Column(Integer, default=0)
    last_click_at = Column(DateTime)

    # A/B 테스트
    ab_test_id = Column(String(36))
    ab_variant = Column(String(50))

    # 경쟁 상황
    competitor_count_at_post = Column(Integer)  # 게시 시점 경쟁 답변 수
    final_rank = Column(Integer)  # 최종 순위

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="answer_performances")
