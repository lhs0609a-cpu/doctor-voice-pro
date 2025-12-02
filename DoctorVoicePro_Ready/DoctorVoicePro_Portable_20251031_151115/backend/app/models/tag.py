"""
Tag Model
사용자 정의 태그 시스템
"""

from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid as uuid_pkg

from app.db.database import Base
from app.models.user import GUID
from app.models.post import post_tags


class Tag(Base):
    __tablename__ = "tags"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)

    name = Column(String(100), nullable=False)
    color = Column(String(20), default="#3B82F6", nullable=False)  # Hex color code

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="tags")
    posts = relationship("Post", secondary=post_tags, back_populates="tags")

    def __repr__(self):
        return f"<Tag {self.name}>"
