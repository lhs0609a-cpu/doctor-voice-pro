"""
네이버 블로그 연동 정보 모델
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid as uuid_pkg

from app.db.database import Base
from app.models.user import GUID


class NaverConnection(Base):
    """네이버 블로그 연동 정보"""

    __tablename__ = "naver_connections"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, unique=True)

    # OAuth 토큰
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    token_expires_at = Column(DateTime, nullable=False)

    # 네이버 사용자 정보
    naver_user_id = Column(String(100), nullable=True)
    naver_email = Column(String(255), nullable=True)
    naver_name = Column(String(100), nullable=True)

    # 블로그 정보
    blog_id = Column(String(100), nullable=True)
    blog_name = Column(String(200), nullable=True)
    blog_url = Column(String(500), nullable=True)

    # 기본 카테고리 설정
    default_category_no = Column(String(50), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="naver_connection")
