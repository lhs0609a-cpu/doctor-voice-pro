from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from uuid import UUID


class PostCreate(BaseModel):
    """Schema for creating a new post"""

    original_content: str = Field(..., min_length=50)
    persuasion_level: int = Field(default=3, ge=1, le=5)
    framework: str = Field(default="AIDA")  # AIDA, PAS, STORY, QA
    target_length: int = Field(default=1500, ge=500, le=5000)


class RewriteRequest(BaseModel):
    """Schema for rewriting an existing post"""

    persuasion_level: Optional[int] = Field(default=None, ge=1, le=5)
    framework: Optional[str] = None
    target_length: Optional[int] = Field(default=None, ge=500, le=5000)


class PostUpdate(BaseModel):
    """Schema for updating a post"""

    title: Optional[str] = None
    generated_content: Optional[str] = None
    status: Optional[str] = None


class MedicalLawCheck(BaseModel):
    """Medical law compliance check result"""

    is_compliant: bool
    violations: List[Dict] = []
    warnings: List[Dict] = []


class PersuasionScores(BaseModel):
    """Breakdown of persuasion scores"""

    storytelling: float
    data_evidence: float
    emotion: float
    authority: float
    social_proof: float
    cta_clarity: float
    total: float


class PostResponse(BaseModel):
    """Schema for post response"""

    id: UUID
    user_id: UUID
    title: Optional[str]
    original_content: str
    generated_content: Optional[str]
    persuasion_score: float
    medical_law_check: Optional[Dict]
    seo_keywords: List[str]
    hashtags: List[str]
    meta_description: Optional[str]
    status: str
    published_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PostListResponse(BaseModel):
    """Schema for paginated post list"""

    posts: List[PostResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
