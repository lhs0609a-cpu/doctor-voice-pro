from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from uuid import UUID


class WritingStyle(BaseModel):
    """Writing style configuration"""

    formality: int = Field(default=5, ge=1, le=10)
    friendliness: int = Field(default=5, ge=1, le=10)
    technical_depth: int = Field(default=5, ge=1, le=10)
    storytelling: int = Field(default=5, ge=1, le=10)
    emotion: int = Field(default=5, ge=1, le=10)


class TargetAudience(BaseModel):
    """Target audience configuration"""

    age_range: Optional[str] = None
    gender: Optional[str] = None
    concerns: List[str] = []


class DoctorProfileCreate(BaseModel):
    """Schema for creating doctor profile"""

    writing_style: Optional[WritingStyle] = None
    signature_phrases: List[str] = []
    sample_posts: List[str] = []
    target_audience: Optional[TargetAudience] = None
    preferred_structure: str = "story_problem_solution"


class DoctorProfileUpdate(BaseModel):
    """Schema for updating doctor profile"""

    writing_style: Optional[WritingStyle] = None
    signature_phrases: Optional[List[str]] = None
    sample_posts: Optional[List[str]] = None
    target_audience: Optional[TargetAudience] = None
    preferred_structure: Optional[str] = None


class DoctorProfileResponse(BaseModel):
    """Schema for doctor profile response"""

    id: UUID
    user_id: UUID
    writing_style: Optional[Dict]
    signature_phrases: List[str]
    target_audience: Optional[Dict]
    preferred_structure: str
    learned_at: Optional[datetime]
    profile_version: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
