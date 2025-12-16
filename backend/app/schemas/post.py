from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from uuid import UUID


class WritingStyleCreate(BaseModel):
    """Schema for writing style settings"""
    formality: int = Field(default=5, ge=1, le=10)
    friendliness: int = Field(default=7, ge=1, le=10)
    technical_depth: int = Field(default=5, ge=1, le=10)
    storytelling: int = Field(default=6, ge=1, le=10)
    emotion: int = Field(default=6, ge=1, le=10)
    humor: int = Field(default=5, ge=1, le=10)
    question_usage: int = Field(default=6, ge=1, le=10)
    metaphor_usage: int = Field(default=5, ge=1, le=10)
    sentence_length: int = Field(default=5, ge=1, le=10)


class RequestRequirementsCreate(BaseModel):
    """Schema for request requirements"""
    common: List[str] = Field(default_factory=list)
    individual: str = Field(default="")


class SEOOptimization(BaseModel):
    """Schema for SEO optimization settings (DIA/CRANK)"""
    enabled: bool = Field(default=False)
    experience_focus: bool = Field(default=True)      # 실제 경험 중심 작성 (DIA: 경험 정보)
    expertise: bool = Field(default=True)              # 전문성과 깊이 강화 (C-Rank: Content 품질)
    originality: bool = Field(default=True)            # 독창성 강조 (DIA: 독창성)
    timeliness: bool = Field(default=True)             # 적시성 반영 (DIA: 적시성)
    topic_concentration: bool = Field(default=True)    # 주제 집중도 향상 (C-Rank: Context)


class TopPostRules(BaseModel):
    """Schema for top post analysis rules - 상위글 분석 기반 글쓰기 규칙"""
    title: Optional[Dict] = None  # {"length": {"optimal": 30, "min": 20, "max": 45}, "keyword_placement": {...}}
    content: Optional[Dict] = None  # {"length": {"optimal": 2000, ...}, "structure": {...}}
    media: Optional[Dict] = None  # {"images": {"optimal": 10, ...}, "videos": {...}}


class PostCreate(BaseModel):
    """Schema for creating a new post"""

    original_content: str = Field(..., min_length=10)
    persuasion_level: int = Field(default=3, ge=1, le=5)
    framework: str = Field(default="AIDA")  # AIDA, PAS, STORY, QA
    target_length: int = Field(default=1500, ge=300, le=5000)
    writing_perspective: Optional[str] = Field(default="1인칭")  # 1인칭, 3인칭, 대화형
    writing_style: Optional[WritingStyleCreate] = None
    requirements: Optional[RequestRequirementsCreate] = None
    # AI 제공자 및 모델 선택
    ai_provider: str = Field(default="gpt")  # "claude" or "gpt"
    ai_model: Optional[str] = Field(default="gpt-4o")  # GPT: gpt-4o, gpt-4-turbo, gpt-4o-mini, gpt-3.5-turbo / Claude: claude-sonnet-4-5-20250929, claude-3-5-sonnet-20241022
    # SEO 최적화 (DIA/CRANK)
    seo_optimization: Optional[SEOOptimization] = None
    # 상위글 분석 기반 규칙
    top_post_rules: Optional[TopPostRules] = None


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
    user_id: Optional[UUID]  # Allow None for anonymous users
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
    suggested_titles: Optional[List[str]] = None
    suggested_subtitles: Optional[List[str]] = None
    content_analysis: Optional[Dict] = None
    forbidden_words_check: Optional[Dict] = None
    dia_crank_analysis: Optional[Dict] = None

    class Config:
        from_attributes = True


class PostListResponse(BaseModel):
    """Schema for paginated post list"""

    posts: List[PostResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
