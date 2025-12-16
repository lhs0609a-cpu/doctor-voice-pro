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


# AI 모델별 가격 정보 (2024년 11월 기준, USD per 1M tokens)
AI_PRICING = {
    # Claude 모델 (Anthropic)
    "claude-sonnet-4-5-20250929": {
        "input": 3.00,   # $3.00 / 1M input tokens
        "output": 15.00,  # $15.00 / 1M output tokens
        "name": "Claude Sonnet 4.5",
    },
    "claude-3-5-sonnet-20241022": {
        "input": 3.00,
        "output": 15.00,
        "name": "Claude 3.5 Sonnet",
    },
    "claude-3-opus-20240229": {
        "input": 15.00,
        "output": 75.00,
        "name": "Claude 3 Opus",
    },
    "claude-3-haiku-20240307": {
        "input": 0.25,
        "output": 1.25,
        "name": "Claude 3 Haiku",
    },

    # GPT 모델 (OpenAI)
    "gpt-4o-mini": {
        "input": 0.15,
        "output": 0.60,
        "name": "GPT-4o Mini",
    },

    # Gemini 모델 (Google) - 무료 티어 이후 가격
    "gemini-2.5-flash-preview-05-20": {
        "input": 0.15,    # $0.15 / 1M input tokens
        "output": 0.60,   # $0.60 / 1M output tokens (non-thinking)
        "name": "Gemini 2.5 Flash",
    },
    "gemini-2.0-flash": {
        "input": 0.10,    # $0.10 / 1M input tokens
        "output": 0.40,   # $0.40 / 1M output tokens
        "name": "Gemini 2.0 Flash",
    },
    "gemini-2.0-flash-exp": {
        "input": 0.075,   # $0.075 / 1M input tokens (128K 이하)
        "output": 0.30,   # $0.30 / 1M output tokens
        "name": "Gemini 2.0 Flash Exp",
    },
    "gemini-1.5-pro": {
        "input": 1.25,    # $1.25 / 1M input tokens (128K 이하)
        "output": 5.00,   # $5.00 / 1M output tokens
        "name": "Gemini 1.5 Pro",
    },
    "gemini-1.5-flash": {
        "input": 0.075,
        "output": 0.30,
        "name": "Gemini 1.5 Flash",
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
    # 입력: 프롬프트 + 원본 내용 (약 2000-3000 토큰)
    # 출력: 목표 글자수 * 2.5 (한국어는 글자당 약 2-3 토큰)
    estimated_input_tokens = 3000
    estimated_output_tokens = int(target_length * 2.5)

    return calculate_cost(model, estimated_input_tokens, estimated_output_tokens)
