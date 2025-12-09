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

    # Writing style stored as JSON
    writing_style = Column(JSON, nullable=True)
    # {
    #   "formality": 7,
    #   "friendliness": 8,
    #   "technical_depth": 6,
    #   "storytelling": 9,
    #   "emotion": 7
    # }

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
