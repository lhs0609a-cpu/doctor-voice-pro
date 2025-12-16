"""
글 작성 요청사항 모델
"""

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    ForeignKey,
    Text,
    Boolean,
)
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid as uuid_pkg

from app.db.database import Base
from app.models.user import GUID


class WritingRequest(Base):
    """
    글 작성 요청사항 (공통 + 개별)
    """

    __tablename__ = "writing_requests"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=True)

    # 요청 내용
    request_text = Column(Text, nullable=False)  # 요청사항 내용
    is_common = Column(Boolean, default=False, nullable=False)  # True: 공통, False: 개별

    # 사용 횟수 (재사용 추적)
    usage_count = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="writing_requests")
