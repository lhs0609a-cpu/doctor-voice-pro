"""
성과 추적 서비스
- 이벤트 기록
- 일별 통계
- 성과 분석
"""

import uuid
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.viral_common import (
    PerformanceEvent, PerformanceDaily,
    PerformanceEventType
)


class PerformanceTrackerService:
    """성과 추적 서비스"""

    async def record_event(
        self,
        db: AsyncSession,
        user_id: str,
        event_type: PerformanceEventType,
        platform: str,  # knowledge / cafe
        account_id: Optional[str] = None,
        target_id: Optional[str] = None,
        target_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PerformanceEvent:
        """이벤트 기록"""
        event = PerformanceEvent(
            id=str(uuid.uuid4()),
            user_id=user_id,
            account_id=account_id,
            event_type=event_type.value,
            platform=platform,
            target_id=target_id,
            target_url=target_url,
            metadata=metadata,
            event_at=datetime.utcnow()
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)

        # 일별 통계 업데이트
        await self._update_daily_stats(db, user_id, platform, event_type)

        return event

    async def _update_daily_stats(
        self,
        db: AsyncSession,
        user_id: str,
        platform: str,
        event_type: PerformanceEventType
    ):
        """일별 통계 업데이트"""
        today = date.today()

        # 기존 레코드 조회
        result = await db.execute(
            select(PerformanceDaily).where(
                and_(
                    PerformanceDaily.user_id == user_id,
                    PerformanceDaily.platform == platform,
                    PerformanceDaily.date == today
                )
            )
        )
        daily = result.scalar_one_or_none()

        if not daily:
            daily = PerformanceDaily(
                id=str(uuid.uuid4()),
                user_id=user_id,
                platform=platform,
                date=today
            )
            db.add(daily)

        # 이벤트 유형별 카운터 증가
        if event_type == PerformanceEventType.ANSWER_POSTED:
            daily.answers_posted += 1
        elif event_type == PerformanceEventType.ANSWER_ADOPTED:
            daily.answers_adopted += 1
        elif event_type == PerformanceEventType.COMMENT_POSTED:
            daily.comments_posted += 1
        elif event_type == PerformanceEventType.POST_CREATED:
            daily.posts_created += 1
        elif event_type == PerformanceEventType.LIKE_RECEIVED:
            daily.likes_received += 1
        elif event_type == PerformanceEventType.REPLY_RECEIVED:
            daily.replies_received += 1
        elif event_type == PerformanceEventType.CLICK_BLOG:
            daily.blog_clicks += 1
        elif event_type == PerformanceEventType.CLICK_PLACE:
            daily.place_clicks += 1

        await db.commit()

    async def get_daily_stats(
        self,
        db: AsyncSession,
        user_id: str,
        platform: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[PerformanceDaily]:
        """일별 통계 조회"""
        query = select(PerformanceDaily).where(
            PerformanceDaily.user_id == user_id
        )

        if platform:
            query = query.where(PerformanceDaily.platform == platform)

        if start_date:
            query = query.where(PerformanceDaily.date >= start_date)

        if end_date:
            query = query.where(PerformanceDaily.date <= end_date)

        query = query.order_by(PerformanceDaily.date.desc())

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_events(
        self,
        db: AsyncSession,
        user_id: str,
        platform: Optional[str] = None,
        event_type: Optional[PerformanceEventType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[PerformanceEvent]:
        """이벤트 목록 조회"""
        query = select(PerformanceEvent).where(
            PerformanceEvent.user_id == user_id
        )

        if platform:
            query = query.where(PerformanceEvent.platform == platform)

        if event_type:
            query = query.where(PerformanceEvent.event_type == event_type.value)

        if start_date:
            query = query.where(PerformanceEvent.event_at >= start_date)

        if end_date:
            query = query.where(PerformanceEvent.event_at <= end_date)

        query = query.order_by(PerformanceEvent.event_at.desc()).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_summary(
        self,
        db: AsyncSession,
        user_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """성과 요약"""
        start_date = date.today() - timedelta(days=days)

        # 일별 통계 조회
        daily_stats = await self.get_daily_stats(
            db, user_id, start_date=start_date
        )

        # 플랫폼별 집계
        knowledge_stats = {
            "answers_posted": 0,
            "answers_adopted": 0,
            "adoption_rate": 0,
            "likes_received": 0,
            "blog_clicks": 0,
            "place_clicks": 0
        }

        cafe_stats = {
            "comments_posted": 0,
            "posts_created": 0,
            "likes_received": 0,
            "replies_received": 0,
            "blog_clicks": 0,
            "place_clicks": 0
        }

        for stat in daily_stats:
            if stat.platform == "knowledge":
                knowledge_stats["answers_posted"] += stat.answers_posted
                knowledge_stats["answers_adopted"] += stat.answers_adopted
                knowledge_stats["likes_received"] += stat.likes_received
                knowledge_stats["blog_clicks"] += stat.blog_clicks
                knowledge_stats["place_clicks"] += stat.place_clicks
            elif stat.platform == "cafe":
                cafe_stats["comments_posted"] += stat.comments_posted
                cafe_stats["posts_created"] += stat.posts_created
                cafe_stats["likes_received"] += stat.likes_received
                cafe_stats["replies_received"] += stat.replies_received
                cafe_stats["blog_clicks"] += stat.blog_clicks
                cafe_stats["place_clicks"] += stat.place_clicks

        # 채택률 계산
        if knowledge_stats["answers_posted"] > 0:
            knowledge_stats["adoption_rate"] = (
                knowledge_stats["answers_adopted"] / knowledge_stats["answers_posted"]
            )

        # 일별 트렌드
        daily_trend = []
        for stat in sorted(daily_stats, key=lambda x: x.date):
            daily_trend.append({
                "date": stat.date.isoformat(),
                "platform": stat.platform,
                "activity": (
                    stat.answers_posted + stat.comments_posted +
                    stat.posts_created
                ),
                "engagement": stat.likes_received + stat.replies_received,
                "clicks": stat.blog_clicks + stat.place_clicks
            })

        return {
            "period_days": days,
            "knowledge": knowledge_stats,
            "cafe": cafe_stats,
            "daily_trend": daily_trend,
            "total_activity": (
                knowledge_stats["answers_posted"] +
                cafe_stats["comments_posted"] +
                cafe_stats["posts_created"]
            ),
            "total_engagement": (
                knowledge_stats["likes_received"] +
                cafe_stats["likes_received"] +
                cafe_stats["replies_received"]
            ),
            "total_clicks": (
                knowledge_stats["blog_clicks"] +
                knowledge_stats["place_clicks"] +
                cafe_stats["blog_clicks"] +
                cafe_stats["place_clicks"]
            )
        }

    async def get_account_performance(
        self,
        db: AsyncSession,
        user_id: str,
        account_id: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """계정별 성과"""
        start_date = datetime.utcnow() - timedelta(days=days)

        result = await db.execute(
            select(
                PerformanceEvent.event_type,
                func.count(PerformanceEvent.id).label("count")
            ).where(
                and_(
                    PerformanceEvent.user_id == user_id,
                    PerformanceEvent.account_id == account_id,
                    PerformanceEvent.event_at >= start_date
                )
            ).group_by(PerformanceEvent.event_type)
        )

        stats = {row.event_type: row.count for row in result.all()}

        return {
            "account_id": account_id,
            "period_days": days,
            "answers_posted": stats.get(PerformanceEventType.ANSWER_POSTED.value, 0),
            "answers_adopted": stats.get(PerformanceEventType.ANSWER_ADOPTED.value, 0),
            "comments_posted": stats.get(PerformanceEventType.COMMENT_POSTED.value, 0),
            "posts_created": stats.get(PerformanceEventType.POST_CREATED.value, 0),
            "likes_received": stats.get(PerformanceEventType.LIKE_RECEIVED.value, 0),
            "replies_received": stats.get(PerformanceEventType.REPLY_RECEIVED.value, 0)
        }

    async def get_top_performing_content(
        self,
        db: AsyncSession,
        user_id: str,
        platform: str,
        metric: str = "clicks",  # clicks / likes / replies
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """최고 성과 콘텐츠"""
        # 클릭 이벤트 기준 집계
        if metric == "clicks":
            event_types = [
                PerformanceEventType.CLICK_BLOG.value,
                PerformanceEventType.CLICK_PLACE.value
            ]
        elif metric == "likes":
            event_types = [PerformanceEventType.LIKE_RECEIVED.value]
        elif metric == "replies":
            event_types = [PerformanceEventType.REPLY_RECEIVED.value]
        else:
            event_types = []

        result = await db.execute(
            select(
                PerformanceEvent.target_id,
                PerformanceEvent.target_url,
                func.count(PerformanceEvent.id).label("count")
            ).where(
                and_(
                    PerformanceEvent.user_id == user_id,
                    PerformanceEvent.platform == platform,
                    PerformanceEvent.event_type.in_(event_types),
                    PerformanceEvent.target_id.isnot(None)
                )
            ).group_by(
                PerformanceEvent.target_id,
                PerformanceEvent.target_url
            ).order_by(
                func.count(PerformanceEvent.id).desc()
            ).limit(limit)
        )

        return [
            {
                "target_id": row.target_id,
                "target_url": row.target_url,
                "count": row.count
            }
            for row in result.all()
        ]

    async def compare_periods(
        self,
        db: AsyncSession,
        user_id: str,
        current_start: date,
        current_end: date,
        previous_start: date,
        previous_end: date
    ) -> Dict[str, Any]:
        """기간 비교"""
        current_stats = await self.get_daily_stats(
            db, user_id, start_date=current_start, end_date=current_end
        )
        previous_stats = await self.get_daily_stats(
            db, user_id, start_date=previous_start, end_date=previous_end
        )

        def sum_stats(stats_list):
            return {
                "activity": sum(
                    s.answers_posted + s.comments_posted + s.posts_created
                    for s in stats_list
                ),
                "engagement": sum(
                    s.likes_received + s.replies_received
                    for s in stats_list
                ),
                "clicks": sum(
                    s.blog_clicks + s.place_clicks
                    for s in stats_list
                )
            }

        current = sum_stats(current_stats)
        previous = sum_stats(previous_stats)

        def calc_change(curr, prev):
            if prev == 0:
                return 100 if curr > 0 else 0
            return ((curr - prev) / prev) * 100

        return {
            "current_period": {
                "start": current_start.isoformat(),
                "end": current_end.isoformat(),
                **current
            },
            "previous_period": {
                "start": previous_start.isoformat(),
                "end": previous_end.isoformat(),
                **previous
            },
            "changes": {
                "activity": calc_change(current["activity"], previous["activity"]),
                "engagement": calc_change(current["engagement"], previous["engagement"]),
                "clicks": calc_change(current["clicks"], previous["clicks"])
            }
        }


# 싱글톤 인스턴스
performance_tracker = PerformanceTrackerService()
