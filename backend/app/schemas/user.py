from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from enum import Enum


class IndustryTypeEnum(str, Enum):
    """업종 타입 Enum"""
    MEDICAL = "medical"
    LEGAL = "legal"
    RESTAURANT = "restaurant"
    BEAUTY = "beauty"
    FITNESS = "fitness"
    EDUCATION = "education"
    REALESTATE = "realestate"
    OTHER = "other"


class UserCreate(BaseModel):
    """Schema for user registration"""

    email: EmailStr
    password: str = Field(..., min_length=8)
    name: Optional[str] = None
    industry_type: Optional[IndustryTypeEnum] = IndustryTypeEnum.MEDICAL
    business_name: Optional[str] = None
    hospital_name: Optional[str] = None  # 레거시 호환
    specialty: Optional[str] = None


class UserLogin(BaseModel):
    """Schema for user login"""

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Schema for user response"""

    id: UUID
    email: str
    name: Optional[str]
    industry_type: IndustryTypeEnum
    business_name: Optional[str]
    hospital_name: Optional[str]  # 레거시 호환
    specialty: Optional[str]
    subscription_tier: str
    is_active: bool
    is_approved: bool
    is_admin: bool
    subscription_start_date: Optional[datetime]
    subscription_end_date: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Schema for authentication token response"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse
