"""
API 키 저장 모델
AI API 키를 DB에 저장하여 서버 재시작해도 유지
"""
from sqlalchemy import Column, String, DateTime, Boolean, Text
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


class APIKey(Base):
    """AI API 키 저장 테이블"""
    __tablename__ = "api_keys"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)

    # API 제공자 (claude, gpt, gemini)
    provider = Column(String(50), nullable=False, unique=True)

    # API 키 (암호화 저장 권장, 여기서는 간단히 저장)
    api_key = Column(Text, nullable=False)

    # 키 이름/설명 (선택)
    name = Column(String(200), nullable=True)

    # 활성화 여부
    is_active = Column(Boolean, default=True)

    # 마지막 연결 확인 시간
    last_checked_at = Column(DateTime, nullable=True)

    # 마지막 연결 상태
    last_status = Column(String(50), default="unknown")  # connected, failed, unknown

    # 마지막 에러 메시지
    last_error = Column(Text, nullable=True)

    # 생성/수정 시간
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
