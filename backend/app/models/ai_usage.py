"""
AI 사용량 추적 모델
각 AI 호출에 대한 토큰 사용량과 비용을 기록
"""
from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator, CHAR
from datetime import datetime
import uuid as uuid_pkg

from app.db.database import Base


class GUID(TypeDecorator):
    """Platform-independent GUID type that uses CHAR(36) for SQLite."""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif isinstance(value, uuid_pkg.UUID):
            return str(value)
        else:
            return str(uuid_pkg.UUID(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            return uuid_pkg.UUID(value)


class AIUsage(Base):
    """AI API 사용량 기록 테이블"""
    __tablename__ = "ai_usage"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=True)  # 비로그인 사용 가능

    # AI 정보
    ai_provider = Column(String(50), nullable=False)  # claude, gpt, gemini
    ai_model = Column(String(100), nullable=False)  # 모델명

    # 토큰 사용량
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)

    # 비용 (USD)
    cost_usd = Column(Float, default=0.0)
    # 비용 (KRW) - 환율 1,350원 기준
    cost_krw = Column(Float, default=0.0)

    # 요청 정보
    request_type = Column(String(50), default="content_generation")  # 요청 유형
    content_length = Column(Integer, default=0)  # 생성된 콘텐츠 글자수

    # 시간 정보
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 메모
    memo = Column(Text, nullable=True)


# AI 모델별 가격 정보 (USD per 1M tokens)
# 원고 생성은 Gemini 단일 스택. Claude 항목은 캠페인/카페리뷰/DIA 분석이 계속 쓰므로 남겨둔다.
# 주의: Gemini 2.5 계열의 사고(thinking) 토큰은 출력 단가로 과금된다.
#       ai_rewrite_engine 은 사고 토큰을 output_tokens 에 합산해서 넘긴다.
AI_PRICING = {
    # Gemini (Google) - 원고 생성 기본
    "gemini-2.5-flash": {
        "input": 0.30,
        "output": 2.50,
        "name": "Gemini 2.5 Flash",
    },
    # gemini-2.5-flash-lite 는 신규 사용자에게 차단됨(404). 3.5 계열 lite 로 대체.
    # 아래 두 단가는 서드파티 집계 기준이라 공식 pricing 으로 한 번 확인 필요.
    "gemini-3.5-flash-lite": {
        "input": 0.30,
        "output": 2.50,
        "name": "Gemini 3.5 Flash Lite",
    },
    "gemini-3.5-flash": {
        "input": 0.50,
        "output": 3.00,
        "name": "Gemini 3.5 Flash",
    },
    "gemini-2.5-pro": {
        "input": 1.25,
        "output": 10.00,
        "name": "Gemini 2.5 Pro",
    },

    # Claude (Anthropic) - 캠페인/카페리뷰/DIA 분석
    "claude-opus-5": {
        "input": 15.00,
        "output": 75.00,
        "name": "Claude Opus 5",
    },
    "claude-sonnet-4-5-20250929": {
        "input": 3.00,
        "output": 15.00,
        "name": "Claude Sonnet 4.5",
    },
    "claude-haiku-4-5": {
        "input": 1.00,
        "output": 5.00,
        "name": "Claude Haiku 4.5",
    },
}


# 환율 (USD to KRW)
USD_TO_KRW = 1350


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> dict:
    """
    토큰 사용량으로 비용 계산

    Args:
        model: AI 모델명
        input_tokens: 입력 토큰 수
        output_tokens: 출력 토큰 수

    Returns:
        dict: {
            "input_cost_usd": float,
            "output_cost_usd": float,
            "total_cost_usd": float,
            "total_cost_krw": float,
            "model_name": str
        }
    """
    pricing = AI_PRICING.get(model, {
        "input": 1.0,
        "output": 3.0,
        "name": model
    })

    # 1M 토큰당 가격으로 계산
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    total_usd = input_cost + output_cost
    total_krw = total_usd * USD_TO_KRW

    return {
        "input_cost_usd": round(input_cost, 6),
        "output_cost_usd": round(output_cost, 6),
        "total_cost_usd": round(total_usd, 6),
        "total_cost_krw": round(total_krw, 2),
        "model_name": pricing["name"],
    }


def get_estimated_cost_per_request(model: str, target_length: int = 1800) -> dict:
    """
    원고 1건 생성 시 예상 비용 계산

    Args:
        model: AI 모델명
        target_length: 목표 글자수

    Returns:
        dict: 예상 비용 정보
    """
    # 한국어 기준 예상 토큰 수
    # 입력: 시스템 프롬프트 + 원본 내용
    # 출력: 목표 글자수 * 1.5 (Gemini 토크나이저 기준 한국어는 글자당 약 1.2~1.5 토큰)
    estimated_input_tokens = 3000
    estimated_output_tokens = int(target_length * 1.5)

    # Gemini 2.5 계열은 사고 토큰이 출력 단가로 함께 과금된다.
    # ai_rewrite_engine.THINKING_BUDGET 과 맞춰둔다.
    if model.startswith("gemini-2.5") and not model.endswith("-lite"):
        estimated_output_tokens += 2048

    return calculate_cost(model, estimated_input_tokens, estimated_output_tokens)
