from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserApprovalRequest(BaseModel):
    """사용자 승인 요청 스키마"""
    user_id: str
    is_approved: bool


class UserSubscriptionRequest(BaseModel):
    """사용자 구독 기간 설정 요청 스키마"""
    user_id: str
    subscription_start_date: Optional[datetime] = None
    subscription_end_date: Optional[datetime] = None


class UserListFilter(BaseModel):
    """사용자 목록 필터 스키마"""
    is_approved: Optional[bool] = None
    is_active: Optional[bool] = None
    skip: int = 0
    limit: int = 100
