"""
네이버 블로그 연동 스키마
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class NaverAuthCallbackRequest(BaseModel):
    """네이버 OAuth 콜백 요청"""

    code: str
    state: str


class NaverConnectionResponse(BaseModel):
    """네이버 연동 정보 응답"""

    id: UUID
    user_id: UUID
    naver_user_id: Optional[str]
    naver_email: Optional[str]
    naver_name: Optional[str]
    blog_id: Optional[str]
    blog_name: Optional[str]
    blog_url: Optional[str]
    default_category_no: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NaverCategoryResponse(BaseModel):
    """네이버 블로그 카테고리 응답"""

    category_no: str
    category_name: str
    post_count: int


class NaverPublishRequest(BaseModel):
    """네이버 블로그 발행 요청"""

    post_id: UUID
    category_no: Optional[str] = None
    open_type: str = "0"  # 0: 전체공개, 1: 이웃공개, 2: 비공개
    tags: Optional[List[str]] = None


class NaverPublishResponse(BaseModel):
    """네이버 블로그 발행 응답"""

    success: bool
    naver_post_id: Optional[str] = None
    naver_post_url: Optional[str] = None
    message: str
