from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid as uuid_pkg

from app.db.database import Base
from app.models.user import GUID


class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"

    id = Column(GUID(), primary_key=True, default=uuid_pkg.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)

    # Writing style stored as JSON (더 다양한 옵션 추가)
    writing_style = Column(JSON, nullable=True)
    # {
    #   "formality": 7,         # 격식체 정도 (1-10)
    #   "friendliness": 8,      # 친근함 (1-10)
    #   "technical_depth": 6,   # 전문성 (1-10)
    #   "storytelling": 9,      # 스토리텔링 (1-10)
    #   "emotion": 7,           # 감성적 표현 (1-10)
    #   "humor": 5,             # 유머 사용 (1-10)
    #   "question_usage": 6,    # 질문형 문장 사용 (1-10)
    #   "metaphor_usage": 5,    # 비유·은유 사용 (1-10)
    #   "sentence_length": 5,   # 문장 길이 (1:짧게, 10:길게)
    # }

    # 말투 프리셋 (빠른 선택용)
    tone_preset = Column(String(50), nullable=True)
    # Options: "professional"(전문적), "friendly"(친근한),
    #          "warm"(따뜻한), "confident"(자신감있는),
    #          "caring"(배려하는), "energetic"(활기찬)

    # Signature phrases
    signature_phrases = Column(JSON, nullable=True)

    # Sample posts for learning
    sample_posts = Column(JSON, nullable=True)

    # Target audience
    target_audience = Column(JSON, nullable=True)
    # {
    #   "age_range": "50-70",
    #   "gender": "female",
    #   "concerns": ["무릎 통증", "관절염"]
    # }

    # Preferred writing structure
    preferred_structure = Column(
        String(50), default="story_problem_solution"
    )  # AIDA, PAS, STORY, QA

    # Learning metadata
    learned_at = Column(DateTime, nullable=True)
    profile_version = Column(Integer, default=1)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="profile")
