"""
예약 발행 스케줄 관리 서비스
"""

import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta, time, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from app.models.schedule import (
    PublishSchedule, ScheduleExecution, OptimalTimeRecommendation,
    ScheduleType, RecurrencePattern, ScheduleStatus, ExecutionStatus
)
from app.models.post import Post, PostStatus
from app.services.naver_blog_service import NaverBlogService

logger = logging.getLogger(__name__)


class ScheduleService:
    """예약 발행 스케줄 관리 서비스"""

    def __init__(self):
        self.naver_service = NaverBlogService()

    async def create_schedule(
        self,
        db: AsyncSession,
        user_id: str,
        schedule_type: ScheduleType,
        scheduled_time: time,
        scheduled_date: Optional[date] = None,
        post_id: Optional[str] = None,
        name: Optional[str] = None,
        recurrence_pattern: Optional[RecurrencePattern] = None,
        days_of_week: Optional[List[int]] = None,
        day_of_month: Optional[int] = None,
        category_no: Optional[str] = None,
        open_type: str = "0",
        auto_hashtags: bool = True,
        max_executions: Optional[int] = None,
    ) -> PublishSchedule:
        """
        새 예약 스케줄 생성

        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            schedule_type: 예약 타입 (one_time, recurring)
            scheduled_time: 발행 시각
            scheduled_date: 1회성 예약 날짜
            post_id: 발행할 포스트 ID
            name: 스케줄 이름
            recurrence_pattern: 반복 패턴 (daily, weekly, monthly)
            days_of_week: 주간 반복 요일 [0-6]
            day_of_month: 월간 반복 일자 (1-31)
            category_no: 네이버 카테고리 번호
            open_type: 공개 설정
            auto_hashtags: 자동 해시태그 추가
            max_executions: 최대 실행 횟수

        Returns:
            생성된 PublishSchedule
        """
        schedule = PublishSchedule(
            user_id=user_id,
            post_id=post_id,
            name=name,
            schedule_type=schedule_type,
            scheduled_time=scheduled_time,
            scheduled_date=scheduled_date,
            recurrence_pattern=recurrence_pattern,
            days_of_week=days_of_week,
            day_of_month=day_of_month,
            category_no=category_no,
            open_type=open_type,
            auto_hashtags=auto_hashtags,
            max_executions=max_executions,
            status=ScheduleStatus.ACTIVE,
        )

        # 다음 실행 시간 계산
        schedule.next_execution_at = self._calculate_next_execution(
            schedule_type=schedule_type,
            scheduled_time=scheduled_time,
            scheduled_date=scheduled_date,
            recurrence_pattern=recurrence_pattern,
            days_of_week=days_of_week,
            day_of_month=day_of_month,
        )

        db.add(schedule)
        await db.commit()
        await db.refresh(schedule)

        logger.info(f"Created schedule {schedule.id} for user {user_id}")
        return schedule

    def _calculate_next_execution(
        self,
        schedule_type: ScheduleType,
        scheduled_time: time,
        scheduled_date: Optional[date] = None,
        recurrence_pattern: Optional[RecurrencePattern] = None,
        days_of_week: Optional[List[int]] = None,
        day_of_month: Optional[int] = None,
        from_datetime: Optional[datetime] = None,
    ) -> Optional[datetime]:
        """
        다음 실행 시간 계산

        Args:
            schedule_type: 예약 타입
            scheduled_time: 발행 시각
            scheduled_date: 1회성 날짜
            recurrence_pattern: 반복 패턴
            days_of_week: 주간 반복 요일
            day_of_month: 월간 반복 일자
            from_datetime: 기준 시간 (None이면 현재 시간)

        Returns:
            다음 실행 datetime
        """
        now = from_datetime or datetime.utcnow()

        if schedule_type == ScheduleType.ONE_TIME:
            if scheduled_date:
                next_dt = datetime.combine(scheduled_date, scheduled_time)
                return next_dt if next_dt > now else None
            return None

        # 반복 스케줄
        if recurrence_pattern == RecurrencePattern.DAILY:
            # 매일 같은 시간
            today_execution = datetime.combine(now.date(), scheduled_time)
            if today_execution > now:
                return today_execution
            return today_execution + timedelta(days=1)

        elif recurrence_pattern == RecurrencePattern.WEEKLY:
            if not days_of_week:
                return None

            # 오늘부터 7일 내에서 가장 빠른 실행 시간 찾기
            for i in range(8):
                check_date = now.date() + timedelta(days=i)
                if check_date.weekday() in days_of_week:
                    next_dt = datetime.combine(check_date, scheduled_time)
                    if next_dt > now:
                        return next_dt
            return None

        elif recurrence_pattern == RecurrencePattern.MONTHLY:
            if not day_of_month:
                return None

            # 이번 달 실행
            try:
                this_month = now.replace(day=day_of_month, hour=scheduled_time.hour,
                                         minute=scheduled_time.minute, second=0, microsecond=0)
                if this_month > now:
                    return this_month
            except ValueError:
                pass  # 해당 월에 그 날짜가 없음 (예: 2월 30일)

            # 다음 달 실행
            next_month = now.replace(day=1) + timedelta(days=32)
            next_month = next_month.replace(day=1)
            try:
                return next_month.replace(day=day_of_month, hour=scheduled_time.hour,
                                          minute=scheduled_time.minute, second=0, microsecond=0)
            except ValueError:
                return None

        return None

    async def get_schedules(
        self,
        db: AsyncSession,
        user_id: str,
        status: Optional[ScheduleStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[PublishSchedule]:
        """
        사용자의 예약 목록 조회
        """
        query = select(PublishSchedule).where(
            PublishSchedule.user_id == user_id
        ).options(
            selectinload(PublishSchedule.post)
        ).order_by(PublishSchedule.next_execution_at.asc())

        if status:
            query = query.where(PublishSchedule.status == status)

        query = query.offset(offset).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    async def get_schedule(
        self,
        db: AsyncSession,
        schedule_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[PublishSchedule]:
        """
        예약 상세 조회
        """
        query = select(PublishSchedule).where(
            PublishSchedule.id == schedule_id
        ).options(
            selectinload(PublishSchedule.post),
            selectinload(PublishSchedule.executions)
        )

        if user_id:
            query = query.where(PublishSchedule.user_id == user_id)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def update_schedule(
        self,
        db: AsyncSession,
        schedule_id: str,
        user_id: str,
        **kwargs
    ) -> Optional[PublishSchedule]:
        """
        예약 수정
        """
        schedule = await self.get_schedule(db, schedule_id, user_id)
        if not schedule:
            return None

        # 허용된 필드만 업데이트
        allowed_fields = [
            'name', 'scheduled_time', 'scheduled_date', 'recurrence_pattern',
            'days_of_week', 'day_of_month', 'category_no', 'open_type',
            'auto_hashtags', 'max_executions', 'status'
        ]

        for key, value in kwargs.items():
            if key in allowed_fields and value is not None:
                setattr(schedule, key, value)

        # 다음 실행 시간 재계산
        schedule.next_execution_at = self._calculate_next_execution(
            schedule_type=schedule.schedule_type,
            scheduled_time=schedule.scheduled_time,
            scheduled_date=schedule.scheduled_date,
            recurrence_pattern=schedule.recurrence_pattern,
            days_of_week=schedule.days_of_week,
            day_of_month=schedule.day_of_month,
        )

        await db.commit()
        await db.refresh(schedule)
        return schedule

    async def delete_schedule(
        self,
        db: AsyncSession,
        schedule_id: str,
        user_id: str,
    ) -> bool:
        """
        예약 삭제
        """
        schedule = await self.get_schedule(db, schedule_id, user_id)
        if not schedule:
            return False

        await db.delete(schedule)
        await db.commit()
        return True

    async def toggle_schedule(
        self,
        db: AsyncSession,
        schedule_id: str,
        user_id: str,
    ) -> Optional[PublishSchedule]:
        """
        예약 활성화/비활성화 토글
        """
        schedule = await self.get_schedule(db, schedule_id, user_id)
        if not schedule:
            return None

        if schedule.status == ScheduleStatus.ACTIVE:
            schedule.status = ScheduleStatus.PAUSED
        elif schedule.status == ScheduleStatus.PAUSED:
            schedule.status = ScheduleStatus.ACTIVE
            # 다음 실행 시간 재계산
            schedule.next_execution_at = self._calculate_next_execution(
                schedule_type=schedule.schedule_type,
                scheduled_time=schedule.scheduled_time,
                scheduled_date=schedule.scheduled_date,
                recurrence_pattern=schedule.recurrence_pattern,
                days_of_week=schedule.days_of_week,
                day_of_month=schedule.day_of_month,
            )

        await db.commit()
        await db.refresh(schedule)
        return schedule

    async def get_pending_schedules(
        self,
        db: AsyncSession,
        before: Optional[datetime] = None,
    ) -> List[PublishSchedule]:
        """
        실행 대기 중인 스케줄 조회 (스케줄러용)
        """
        now = before or datetime.utcnow()

        query = select(PublishSchedule).where(
            and_(
                PublishSchedule.status == ScheduleStatus.ACTIVE,
                PublishSchedule.next_execution_at <= now,
                PublishSchedule.next_execution_at.isnot(None)
            )
        ).options(
            selectinload(PublishSchedule.post),
            selectinload(PublishSchedule.user)
        )

        result = await db.execute(query)
        return result.scalars().all()

    async def execute_schedule(
        self,
        db: AsyncSession,
        schedule_id: str,
        naver_access_token: str,
    ) -> ScheduleExecution:
        """
        예약된 포스트 발행 실행
        """
        schedule = await self.get_schedule(db, schedule_id)
        if not schedule:
            raise ValueError(f"Schedule {schedule_id} not found")

        # 실행 로그 생성
        execution = ScheduleExecution(
            schedule_id=schedule_id,
            post_id=schedule.post_id,
            status=ExecutionStatus.PENDING,
        )
        db.add(execution)

        try:
            # 포스트 조회
            if not schedule.post_id:
                raise ValueError("No post associated with this schedule")

            post_result = await db.execute(
                select(Post).where(Post.id == schedule.post_id)
            )
            post = post_result.scalar_one_or_none()

            if not post:
                raise ValueError(f"Post {schedule.post_id} not found")

            # 네이버 블로그 발행
            result = await self.naver_service.create_blog_post(
                access_token=naver_access_token,
                title=post.title,
                contents=post.generated_content or post.original_content,
                category_no=schedule.category_no,
                open_type=schedule.open_type,
            )

            if result and result.get("success"):
                execution.status = ExecutionStatus.SUCCESS
                execution.naver_post_url = result.get("post_url")
                execution.naver_post_id = result.get("post_id")

                # 포스트 상태 업데이트
                post.status = PostStatus.PUBLISHED
                post.published_at = datetime.utcnow()
                post.naver_blog_url = result.get("post_url")
            else:
                execution.status = ExecutionStatus.FAILED
                execution.error_message = result.get("error", "Unknown error")

        except Exception as e:
            logger.error(f"Failed to execute schedule {schedule_id}: {e}")
            execution.status = ExecutionStatus.FAILED
            execution.error_message = str(e)

        execution.completed_at = datetime.utcnow()

        # 스케줄 업데이트
        schedule.last_executed_at = datetime.utcnow()
        schedule.execution_count += 1

        # 1회성이거나 최대 실행 횟수 도달 시 완료 처리
        if schedule.schedule_type == ScheduleType.ONE_TIME:
            schedule.status = ScheduleStatus.COMPLETED
            schedule.next_execution_at = None
        elif schedule.max_executions and schedule.execution_count >= schedule.max_executions:
            schedule.status = ScheduleStatus.COMPLETED
            schedule.next_execution_at = None
        else:
            # 다음 실행 시간 계산
            schedule.next_execution_at = self._calculate_next_execution(
                schedule_type=schedule.schedule_type,
                scheduled_time=schedule.scheduled_time,
                scheduled_date=schedule.scheduled_date,
                recurrence_pattern=schedule.recurrence_pattern,
                days_of_week=schedule.days_of_week,
                day_of_month=schedule.day_of_month,
            )

        await db.commit()
        await db.refresh(execution)
        return execution

    async def get_executions(
        self,
        db: AsyncSession,
        schedule_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> List[ScheduleExecution]:
        """
        예약 실행 이력 조회
        """
        query = select(ScheduleExecution).where(
            ScheduleExecution.schedule_id == schedule_id
        ).order_by(
            ScheduleExecution.executed_at.desc()
        ).offset(offset).limit(limit)

        result = await db.execute(query)
        return result.scalars().all()

    async def get_upcoming_posts(
        self,
        db: AsyncSession,
        user_id: str,
        days: int = 7,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        예정된 발행 목록 조회
        """
        end_date = datetime.utcnow() + timedelta(days=days)

        query = select(PublishSchedule).where(
            and_(
                PublishSchedule.user_id == user_id,
                PublishSchedule.status == ScheduleStatus.ACTIVE,
                PublishSchedule.next_execution_at.isnot(None),
                PublishSchedule.next_execution_at <= end_date,
            )
        ).options(
            selectinload(PublishSchedule.post)
        ).order_by(
            PublishSchedule.next_execution_at.asc()
        ).limit(limit)

        result = await db.execute(query)
        schedules = result.scalars().all()

        upcoming = []
        for schedule in schedules:
            upcoming.append({
                "schedule_id": str(schedule.id),
                "schedule_name": schedule.name,
                "next_execution_at": schedule.next_execution_at,
                "post_id": str(schedule.post_id) if schedule.post_id else None,
                "post_title": schedule.post.title if schedule.post else None,
                "schedule_type": schedule.schedule_type.value,
                "recurrence_pattern": schedule.recurrence_pattern.value if schedule.recurrence_pattern else None,
            })

        return upcoming

    async def get_optimal_times(
        self,
        db: AsyncSession,
        user_id: str,
        category: Optional[str] = None,
    ) -> List[OptimalTimeRecommendation]:
        """
        최적 발행 시간 추천 조회
        """
        query = select(OptimalTimeRecommendation).where(
            OptimalTimeRecommendation.user_id == user_id
        )

        if category:
            query = query.where(OptimalTimeRecommendation.category == category)

        query = query.order_by(
            OptimalTimeRecommendation.engagement_score.desc()
        )

        result = await db.execute(query)
        return result.scalars().all()

    async def calculate_optimal_times(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> List[OptimalTimeRecommendation]:
        """
        사용자 데이터 기반 최적 시간 계산 (향후 구현)

        실제 구현에서는:
        1. 사용자의 발행된 포스트 성과 데이터 분석
        2. 요일별, 시간별 참여율 계산
        3. 상위 시간대 추출
        """
        # 기본 추천 시간 (의료 블로그 기준)
        default_times = [
            {"day": 1, "hour": 10, "score": 85.0},  # 화요일 10시
            {"day": 3, "hour": 10, "score": 82.0},  # 목요일 10시
            {"day": 0, "hour": 9, "score": 80.0},   # 월요일 9시
            {"day": 2, "hour": 14, "score": 78.0},  # 수요일 14시
            {"day": 4, "hour": 11, "score": 75.0},  # 금요일 11시
        ]

        recommendations = []
        for rec in default_times:
            recommendation = OptimalTimeRecommendation(
                user_id=user_id,
                day_of_week=rec["day"],
                recommended_hour=rec["hour"],
                recommended_minute=0,
                engagement_score=rec["score"],
                confidence_score=0.7,  # 기본 추천이므로 낮은 신뢰도
                sample_count=0,
            )
            db.add(recommendation)
            recommendations.append(recommendation)

        await db.commit()
        return recommendations


# Singleton instance
schedule_service = ScheduleService()
