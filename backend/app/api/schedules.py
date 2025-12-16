"""
예약 발행 스케줄 API
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import time, date
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.schedule import (
    ScheduleType, RecurrencePattern, ScheduleStatus,
    PublishSchedule, ScheduleExecution
)
from app.services.schedule_service import schedule_service

router = APIRouter()


# ==================== Schemas ====================

class ScheduleCreateRequest(BaseModel):
    name: Optional[str] = None
    schedule_type: ScheduleType
    scheduled_time: str = Field(..., description="HH:MM 형식")
    scheduled_date: Optional[str] = Field(None, description="YYYY-MM-DD 형식 (1회성용)")
    post_id: Optional[str] = None
    recurrence_pattern: Optional[RecurrencePattern] = None
    days_of_week: Optional[List[int]] = Field(None, description="0-6 (일-토)")
    day_of_month: Optional[int] = Field(None, ge=1, le=31)
    category_no: Optional[str] = None
    open_type: str = "0"
    auto_hashtags: bool = True
    max_executions: Optional[int] = None


class ScheduleUpdateRequest(BaseModel):
    name: Optional[str] = None
    scheduled_time: Optional[str] = None
    scheduled_date: Optional[str] = None
    recurrence_pattern: Optional[RecurrencePattern] = None
    days_of_week: Optional[List[int]] = None
    day_of_month: Optional[int] = None
    category_no: Optional[str] = None
    open_type: Optional[str] = None
    auto_hashtags: Optional[bool] = None
    max_executions: Optional[int] = None


class ScheduleResponse(BaseModel):
    id: str
    name: Optional[str]
    schedule_type: str
    scheduled_time: str
    scheduled_date: Optional[str]
    post_id: Optional[str]
    post_title: Optional[str] = None
    recurrence_pattern: Optional[str]
    days_of_week: Optional[List[int]]
    day_of_month: Optional[int]
    category_no: Optional[str]
    open_type: str
    auto_hashtags: bool
    status: str
    last_executed_at: Optional[str]
    next_execution_at: Optional[str]
    execution_count: int
    max_executions: Optional[int]
    created_at: str

    class Config:
        from_attributes = True


class ExecutionResponse(BaseModel):
    id: str
    schedule_id: str
    post_id: Optional[str]
    status: str
    executed_at: str
    completed_at: Optional[str]
    naver_post_url: Optional[str]
    error_message: Optional[str]

    class Config:
        from_attributes = True


class OptimalTimeResponse(BaseModel):
    day_of_week: int
    day_name: str
    recommended_hour: int
    recommended_minute: int
    engagement_score: float
    confidence_score: float


# ==================== Helper Functions ====================

def parse_time(time_str: str) -> time:
    """HH:MM 문자열을 time 객체로 변환"""
    parts = time_str.split(":")
    return time(int(parts[0]), int(parts[1]))


def parse_date(date_str: Optional[str]) -> Optional[date]:
    """YYYY-MM-DD 문자열을 date 객체로 변환"""
    if not date_str:
        return None
    parts = date_str.split("-")
    return date(int(parts[0]), int(parts[1]), int(parts[2]))


def schedule_to_response(schedule: PublishSchedule) -> dict:
    """PublishSchedule을 응답 딕셔너리로 변환"""
    return {
        "id": str(schedule.id),
        "name": schedule.name,
        "schedule_type": schedule.schedule_type.value,
        "scheduled_time": schedule.scheduled_time.strftime("%H:%M") if schedule.scheduled_time else None,
        "scheduled_date": schedule.scheduled_date.isoformat() if schedule.scheduled_date else None,
        "post_id": str(schedule.post_id) if schedule.post_id else None,
        "post_title": schedule.post.title if schedule.post else None,
        "recurrence_pattern": schedule.recurrence_pattern.value if schedule.recurrence_pattern else None,
        "days_of_week": schedule.days_of_week,
        "day_of_month": schedule.day_of_month,
        "category_no": schedule.category_no,
        "open_type": schedule.open_type,
        "auto_hashtags": schedule.auto_hashtags,
        "status": schedule.status.value,
        "last_executed_at": schedule.last_executed_at.isoformat() if schedule.last_executed_at else None,
        "next_execution_at": schedule.next_execution_at.isoformat() if schedule.next_execution_at else None,
        "execution_count": schedule.execution_count,
        "max_executions": schedule.max_executions,
        "created_at": schedule.created_at.isoformat(),
    }


# ==================== Endpoints ====================

@router.post("/", response_model=ScheduleResponse)
async def create_schedule(
    request: ScheduleCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    새 예약 스케줄 생성
    """
    try:
        scheduled_time = parse_time(request.scheduled_time)
        scheduled_date = parse_date(request.scheduled_date)

        schedule = await schedule_service.create_schedule(
            db=db,
            user_id=str(current_user.id),
            schedule_type=request.schedule_type,
            scheduled_time=scheduled_time,
            scheduled_date=scheduled_date,
            post_id=request.post_id,
            name=request.name,
            recurrence_pattern=request.recurrence_pattern,
            days_of_week=request.days_of_week,
            day_of_month=request.day_of_month,
            category_no=request.category_no,
            open_type=request.open_type,
            auto_hashtags=request.auto_hashtags,
            max_executions=request.max_executions,
        )

        return schedule_to_response(schedule)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[ScheduleResponse])
async def get_schedules(
    status: Optional[ScheduleStatus] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    예약 목록 조회
    """
    schedules = await schedule_service.get_schedules(
        db=db,
        user_id=str(current_user.id),
        status=status,
        limit=limit,
        offset=offset,
    )

    return [schedule_to_response(s) for s in schedules]


@router.get("/upcoming")
async def get_upcoming_posts(
    days: int = Query(7, ge=1, le=30),
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    예정된 발행 목록 조회
    """
    upcoming = await schedule_service.get_upcoming_posts(
        db=db,
        user_id=str(current_user.id),
        days=days,
        limit=limit,
    )

    return upcoming


@router.get("/optimal-times", response_model=List[OptimalTimeResponse])
async def get_optimal_times(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    최적 발행 시간 추천 조회
    """
    day_names = ["일", "월", "화", "수", "목", "금", "토"]

    recommendations = await schedule_service.get_optimal_times(
        db=db,
        user_id=str(current_user.id),
        category=category,
    )

    # 추천이 없으면 기본 추천 생성
    if not recommendations:
        recommendations = await schedule_service.calculate_optimal_times(
            db=db,
            user_id=str(current_user.id),
        )

    return [
        {
            "day_of_week": r.day_of_week,
            "day_name": day_names[r.day_of_week],
            "recommended_hour": r.recommended_hour,
            "recommended_minute": r.recommended_minute,
            "engagement_score": r.engagement_score,
            "confidence_score": r.confidence_score,
        }
        for r in recommendations
    ]


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    예약 상세 조회
    """
    schedule = await schedule_service.get_schedule(
        db=db,
        schedule_id=schedule_id,
        user_id=str(current_user.id),
    )

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    return schedule_to_response(schedule)


@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: str,
    request: ScheduleUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    예약 수정
    """
    update_data = {}

    if request.name is not None:
        update_data["name"] = request.name
    if request.scheduled_time is not None:
        update_data["scheduled_time"] = parse_time(request.scheduled_time)
    if request.scheduled_date is not None:
        update_data["scheduled_date"] = parse_date(request.scheduled_date)
    if request.recurrence_pattern is not None:
        update_data["recurrence_pattern"] = request.recurrence_pattern
    if request.days_of_week is not None:
        update_data["days_of_week"] = request.days_of_week
    if request.day_of_month is not None:
        update_data["day_of_month"] = request.day_of_month
    if request.category_no is not None:
        update_data["category_no"] = request.category_no
    if request.open_type is not None:
        update_data["open_type"] = request.open_type
    if request.auto_hashtags is not None:
        update_data["auto_hashtags"] = request.auto_hashtags
    if request.max_executions is not None:
        update_data["max_executions"] = request.max_executions

    schedule = await schedule_service.update_schedule(
        db=db,
        schedule_id=schedule_id,
        user_id=str(current_user.id),
        **update_data,
    )

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    return schedule_to_response(schedule)


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    예약 삭제
    """
    success = await schedule_service.delete_schedule(
        db=db,
        schedule_id=schedule_id,
        user_id=str(current_user.id),
    )

    if not success:
        raise HTTPException(status_code=404, detail="Schedule not found")

    return {"message": "Schedule deleted successfully"}


@router.post("/{schedule_id}/toggle", response_model=ScheduleResponse)
async def toggle_schedule(
    schedule_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    예약 활성화/비활성화 토글
    """
    schedule = await schedule_service.toggle_schedule(
        db=db,
        schedule_id=schedule_id,
        user_id=str(current_user.id),
    )

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    return schedule_to_response(schedule)


@router.get("/{schedule_id}/executions", response_model=List[ExecutionResponse])
async def get_executions(
    schedule_id: str,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    예약 실행 이력 조회
    """
    # 권한 확인
    schedule = await schedule_service.get_schedule(
        db=db,
        schedule_id=schedule_id,
        user_id=str(current_user.id),
    )

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    executions = await schedule_service.get_executions(
        db=db,
        schedule_id=schedule_id,
        limit=limit,
        offset=offset,
    )

    return [
        {
            "id": str(e.id),
            "schedule_id": str(e.schedule_id),
            "post_id": str(e.post_id) if e.post_id else None,
            "status": e.status.value,
            "executed_at": e.executed_at.isoformat(),
            "completed_at": e.completed_at.isoformat() if e.completed_at else None,
            "naver_post_url": e.naver_post_url,
            "error_message": e.error_message,
        }
        for e in executions
    ]
