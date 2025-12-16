"""
ROI 트래커 서비스 - 전환 추적 및 ROI 분석
"""

import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, date, timedelta
from calendar import monthrange
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from sqlalchemy.orm import selectinload
import uuid

from app.models.roi_tracker import (
    ConversionEvent, ROISummary, KeywordROI, FunnelStage, MarketingCost,
    EventType
)

logger = logging.getLogger(__name__)


class ROIService:
    """ROI 트래커 서비스"""

    async def create_event(
        self,
        db: AsyncSession,
        user_id: str,
        event_type: EventType,
        event_date: date,
        keyword: Optional[str] = None,
        post_id: Optional[str] = None,
        source: Optional[str] = None,
        channel: Optional[str] = None,
        revenue: Optional[int] = None,
        cost: Optional[int] = None,
        customer_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> ConversionEvent:
        """전환 이벤트 기록"""
        event = ConversionEvent(
            user_id=user_id,
            post_id=post_id,
            keyword=keyword,
            event_type=event_type,
            source=source,
            channel=channel,
            revenue=revenue,
            cost=cost,
            customer_id=customer_id,
            notes=notes,
            event_date=event_date,
        )

        db.add(event)
        await db.commit()
        await db.refresh(event)

        logger.info(f"Created conversion event {event.id} for user {user_id}")
        return event

    async def create_bulk_events(
        self,
        db: AsyncSession,
        user_id: str,
        events: List[Dict[str, Any]],
    ) -> List[ConversionEvent]:
        """여러 전환 이벤트 일괄 기록"""
        created_events = []
        for event_data in events:
            event = ConversionEvent(
                user_id=user_id,
                **event_data
            )
            db.add(event)
            created_events.append(event)

        await db.commit()
        for event in created_events:
            await db.refresh(event)

        logger.info(f"Created {len(created_events)} conversion events for user {user_id}")
        return created_events

    async def get_events(
        self,
        db: AsyncSession,
        user_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        event_type: Optional[EventType] = None,
        source: Optional[str] = None,
        channel: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ConversionEvent]:
        """전환 이벤트 조회"""
        query = select(ConversionEvent).where(
            ConversionEvent.user_id == user_id
        )

        if start_date:
            query = query.where(ConversionEvent.event_date >= start_date)
        if end_date:
            query = query.where(ConversionEvent.event_date <= end_date)
        if event_type:
            query = query.where(ConversionEvent.event_type == event_type)
        if source:
            query = query.where(ConversionEvent.source == source)
        if channel:
            query = query.where(ConversionEvent.channel == channel)
        if keyword:
            query = query.where(ConversionEvent.keyword.ilike(f"%{keyword}%"))

        query = query.order_by(desc(ConversionEvent.event_date)).offset(offset).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_dashboard(
        self,
        db: AsyncSession,
        user_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """ROI 대시보드 데이터 조회"""
        if not start_date:
            start_date = date.today().replace(day=1)
        if not end_date:
            end_date = date.today()

        # 기본 통계
        stats = await self._get_event_stats(db, user_id, start_date, end_date)

        # 채널별 분석
        channel_breakdown = await self._get_channel_breakdown(db, user_id, start_date, end_date)

        # 소스별 분석
        source_breakdown = await self._get_source_breakdown(db, user_id, start_date, end_date)

        # 일별 트렌드
        daily_trend = await self._get_daily_trend(db, user_id, start_date, end_date)

        # 전환 퍼널
        funnel = await self._calculate_funnel(db, user_id, start_date, end_date)

        # 상위 키워드
        top_keywords = await self._get_top_keywords(db, user_id, start_date, end_date, limit=10)

        # ROI 계산
        roi = self._calculate_roi(stats["total_revenue"], stats["total_cost"])

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "stats": stats,
            "channel_breakdown": channel_breakdown,
            "source_breakdown": source_breakdown,
            "daily_trend": daily_trend,
            "funnel": funnel,
            "top_keywords": top_keywords,
            "roi_percentage": roi,
        }

    async def _get_event_stats(
        self,
        db: AsyncSession,
        user_id: str,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """기본 이벤트 통계"""
        # 이벤트 타입별 카운트
        query = select(
            ConversionEvent.event_type,
            func.count(ConversionEvent.id).label("count"),
            func.sum(ConversionEvent.revenue).label("revenue"),
        ).where(
            and_(
                ConversionEvent.user_id == user_id,
                ConversionEvent.event_date >= start_date,
                ConversionEvent.event_date <= end_date,
            )
        ).group_by(ConversionEvent.event_type)

        result = await db.execute(query)
        rows = result.all()

        stats = {
            "total_views": 0,
            "total_inquiries": 0,
            "total_visits": 0,
            "total_reservations": 0,
            "total_revenue": 0,
            "total_cost": 0,
        }

        for row in rows:
            event_type, count, revenue = row
            if event_type == EventType.VIEW:
                stats["total_views"] = count
            elif event_type == EventType.INQUIRY:
                stats["total_inquiries"] = count
            elif event_type == EventType.VISIT:
                stats["total_visits"] = count
            elif event_type == EventType.RESERVATION:
                stats["total_reservations"] = count
            if revenue:
                stats["total_revenue"] += revenue

        # 마케팅 비용 합계
        cost_query = select(func.sum(MarketingCost.cost)).where(
            and_(
                MarketingCost.user_id == user_id,
                MarketingCost.date >= start_date,
                MarketingCost.date <= end_date,
            )
        )
        cost_result = await db.execute(cost_query)
        total_cost = cost_result.scalar()
        stats["total_cost"] = total_cost or 0

        return stats

    async def _get_channel_breakdown(
        self,
        db: AsyncSession,
        user_id: str,
        start_date: date,
        end_date: date,
    ) -> List[Dict[str, Any]]:
        """채널별 분석"""
        query = select(
            ConversionEvent.channel,
            ConversionEvent.event_type,
            func.count(ConversionEvent.id).label("count"),
            func.sum(ConversionEvent.revenue).label("revenue"),
        ).where(
            and_(
                ConversionEvent.user_id == user_id,
                ConversionEvent.event_date >= start_date,
                ConversionEvent.event_date <= end_date,
                ConversionEvent.channel.isnot(None),
            )
        ).group_by(ConversionEvent.channel, ConversionEvent.event_type)

        result = await db.execute(query)
        rows = result.all()

        channel_data = {}
        for row in rows:
            channel, event_type, count, revenue = row
            if channel not in channel_data:
                channel_data[channel] = {
                    "channel": channel,
                    "views": 0, "inquiries": 0, "visits": 0, "reservations": 0,
                    "revenue": 0
                }
            if event_type == EventType.VIEW:
                channel_data[channel]["views"] = count
            elif event_type == EventType.INQUIRY:
                channel_data[channel]["inquiries"] = count
            elif event_type == EventType.VISIT:
                channel_data[channel]["visits"] = count
            elif event_type == EventType.RESERVATION:
                channel_data[channel]["reservations"] = count
            if revenue:
                channel_data[channel]["revenue"] += revenue

        return list(channel_data.values())

    async def _get_source_breakdown(
        self,
        db: AsyncSession,
        user_id: str,
        start_date: date,
        end_date: date,
    ) -> List[Dict[str, Any]]:
        """소스별 분석"""
        query = select(
            ConversionEvent.source,
            func.count(ConversionEvent.id).label("count"),
            func.sum(ConversionEvent.revenue).label("revenue"),
        ).where(
            and_(
                ConversionEvent.user_id == user_id,
                ConversionEvent.event_date >= start_date,
                ConversionEvent.event_date <= end_date,
                ConversionEvent.source.isnot(None),
            )
        ).group_by(ConversionEvent.source)

        result = await db.execute(query)
        rows = result.all()

        return [
            {"source": row[0], "count": row[1], "revenue": row[2] or 0}
            for row in rows
        ]

    async def _get_daily_trend(
        self,
        db: AsyncSession,
        user_id: str,
        start_date: date,
        end_date: date,
    ) -> List[Dict[str, Any]]:
        """일별 트렌드"""
        query = select(
            ConversionEvent.event_date,
            ConversionEvent.event_type,
            func.count(ConversionEvent.id).label("count"),
        ).where(
            and_(
                ConversionEvent.user_id == user_id,
                ConversionEvent.event_date >= start_date,
                ConversionEvent.event_date <= end_date,
            )
        ).group_by(ConversionEvent.event_date, ConversionEvent.event_type).order_by(ConversionEvent.event_date)

        result = await db.execute(query)
        rows = result.all()

        daily_data = {}
        for row in rows:
            event_date, event_type, count = row
            date_str = event_date.isoformat()
            if date_str not in daily_data:
                daily_data[date_str] = {
                    "date": date_str,
                    "views": 0, "inquiries": 0, "visits": 0, "reservations": 0
                }
            if event_type == EventType.VIEW:
                daily_data[date_str]["views"] = count
            elif event_type == EventType.INQUIRY:
                daily_data[date_str]["inquiries"] = count
            elif event_type == EventType.VISIT:
                daily_data[date_str]["visits"] = count
            elif event_type == EventType.RESERVATION:
                daily_data[date_str]["reservations"] = count

        return list(daily_data.values())

    async def _calculate_funnel(
        self,
        db: AsyncSession,
        user_id: str,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """전환 퍼널 계산"""
        stats = await self._get_event_stats(db, user_id, start_date, end_date)

        views = stats["total_views"]
        inquiries = stats["total_inquiries"]
        visits = stats["total_visits"]
        reservations = stats["total_reservations"]

        return {
            "stages": [
                {"name": "조회", "count": views, "rate": 100},
                {"name": "상담문의", "count": inquiries, "rate": round(inquiries / views * 100, 1) if views > 0 else 0},
                {"name": "내원", "count": visits, "rate": round(visits / views * 100, 1) if views > 0 else 0},
                {"name": "예약/결제", "count": reservations, "rate": round(reservations / views * 100, 1) if views > 0 else 0},
            ],
            "conversion_rates": {
                "view_to_inquiry": round(inquiries / views * 100, 1) if views > 0 else 0,
                "inquiry_to_visit": round(visits / inquiries * 100, 1) if inquiries > 0 else 0,
                "visit_to_reservation": round(reservations / visits * 100, 1) if visits > 0 else 0,
                "overall": round(reservations / views * 100, 1) if views > 0 else 0,
            }
        }

    async def _get_top_keywords(
        self,
        db: AsyncSession,
        user_id: str,
        start_date: date,
        end_date: date,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """상위 키워드 분석"""
        query = select(
            ConversionEvent.keyword,
            func.count(ConversionEvent.id).label("total_count"),
            func.sum(func.cast(ConversionEvent.event_type == EventType.RESERVATION, Integer)).label("conversions"),
            func.sum(ConversionEvent.revenue).label("revenue"),
        ).where(
            and_(
                ConversionEvent.user_id == user_id,
                ConversionEvent.event_date >= start_date,
                ConversionEvent.event_date <= end_date,
                ConversionEvent.keyword.isnot(None),
            )
        ).group_by(ConversionEvent.keyword).order_by(desc("conversions")).limit(limit)

        result = await db.execute(query)
        rows = result.all()

        return [
            {
                "keyword": row[0],
                "total_events": row[1],
                "conversions": row[2] or 0,
                "revenue": row[3] or 0,
            }
            for row in rows
        ]

    def _calculate_roi(self, revenue: int, cost: int) -> float:
        """ROI 계산"""
        if cost == 0:
            return 0.0
        return round((revenue - cost) / cost * 100, 1)

    async def get_keyword_roi(
        self,
        db: AsyncSession,
        user_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """키워드별 ROI 분석"""
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()

        # 키워드별 이벤트 집계
        query = select(
            ConversionEvent.keyword,
            ConversionEvent.event_type,
            func.count(ConversionEvent.id).label("count"),
            func.sum(ConversionEvent.revenue).label("revenue"),
            func.sum(ConversionEvent.cost).label("cost"),
        ).where(
            and_(
                ConversionEvent.user_id == user_id,
                ConversionEvent.event_date >= start_date,
                ConversionEvent.event_date <= end_date,
                ConversionEvent.keyword.isnot(None),
            )
        ).group_by(ConversionEvent.keyword, ConversionEvent.event_type)

        result = await db.execute(query)
        rows = result.all()

        keyword_data = {}
        for row in rows:
            keyword, event_type, count, revenue, cost = row
            if keyword not in keyword_data:
                keyword_data[keyword] = {
                    "keyword": keyword,
                    "views": 0, "inquiries": 0, "visits": 0, "reservations": 0,
                    "revenue": 0, "cost": 0,
                }
            if event_type == EventType.VIEW:
                keyword_data[keyword]["views"] = count
            elif event_type == EventType.INQUIRY:
                keyword_data[keyword]["inquiries"] = count
            elif event_type == EventType.VISIT:
                keyword_data[keyword]["visits"] = count
            elif event_type == EventType.RESERVATION:
                keyword_data[keyword]["reservations"] = count
            if revenue:
                keyword_data[keyword]["revenue"] += revenue
            if cost:
                keyword_data[keyword]["cost"] += cost

        # ROI 계산 및 정렬
        keywords = []
        for k, data in keyword_data.items():
            roi = self._calculate_roi(data["revenue"], data["cost"])
            conversion_rate = round(data["reservations"] / data["views"] * 100, 1) if data["views"] > 0 else 0
            keywords.append({
                **data,
                "roi_percentage": roi,
                "conversion_rate": conversion_rate,
            })

        # ROI 기준 정렬
        keywords.sort(key=lambda x: x["roi_percentage"], reverse=True)
        return keywords[:limit]

    async def add_marketing_cost(
        self,
        db: AsyncSession,
        user_id: str,
        cost_date: date,
        channel: str,
        cost: int,
        description: Optional[str] = None,
        cost_type: Optional[str] = None,
        campaign_name: Optional[str] = None,
    ) -> MarketingCost:
        """마케팅 비용 기록"""
        marketing_cost = MarketingCost(
            user_id=user_id,
            date=cost_date,
            channel=channel,
            cost=cost,
            description=description,
            cost_type=cost_type,
            campaign_name=campaign_name,
        )

        db.add(marketing_cost)
        await db.commit()
        await db.refresh(marketing_cost)

        return marketing_cost

    async def get_marketing_costs(
        self,
        db: AsyncSession,
        user_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[MarketingCost]:
        """마케팅 비용 조회"""
        query = select(MarketingCost).where(MarketingCost.user_id == user_id)

        if start_date:
            query = query.where(MarketingCost.date >= start_date)
        if end_date:
            query = query.where(MarketingCost.date <= end_date)

        query = query.order_by(desc(MarketingCost.date))

        result = await db.execute(query)
        return list(result.scalars().all())

    async def calculate_monthly_summary(
        self,
        db: AsyncSession,
        user_id: str,
        year: int,
        month: int,
    ) -> ROISummary:
        """월별 ROI 요약 계산 및 저장"""
        # 기간 설정
        start_date = date(year, month, 1)
        _, last_day = monthrange(year, month)
        end_date = date(year, month, last_day)

        # 대시보드 데이터 조회
        dashboard = await self.get_dashboard(db, user_id, start_date, end_date)

        # 기존 요약 조회 또는 생성
        query = select(ROISummary).where(
            and_(
                ROISummary.user_id == user_id,
                ROISummary.year == year,
                ROISummary.month == month,
            )
        )
        result = await db.execute(query)
        summary = result.scalar_one_or_none()

        if not summary:
            summary = ROISummary(user_id=user_id, year=year, month=month)
            db.add(summary)

        # 데이터 업데이트
        stats = dashboard["stats"]
        funnel = dashboard["funnel"]

        summary.total_views = stats["total_views"]
        summary.total_inquiries = stats["total_inquiries"]
        summary.total_visits = stats["total_visits"]
        summary.total_reservations = stats["total_reservations"]
        summary.total_revenue = stats["total_revenue"]
        summary.total_cost = stats["total_cost"]

        summary.conversion_rate_view_to_inquiry = funnel["conversion_rates"]["view_to_inquiry"]
        summary.conversion_rate_inquiry_to_visit = funnel["conversion_rates"]["inquiry_to_visit"]
        summary.conversion_rate_visit_to_reservation = funnel["conversion_rates"]["visit_to_reservation"]
        summary.overall_conversion_rate = funnel["conversion_rates"]["overall"]

        summary.roi_percentage = dashboard["roi_percentage"]

        summary.top_keywords = dashboard["top_keywords"]
        summary.channel_breakdown = dashboard["channel_breakdown"]
        summary.source_breakdown = dashboard["source_breakdown"]
        summary.daily_breakdown = dashboard["daily_trend"]

        summary.calculated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(summary)

        return summary

    async def get_trends(
        self,
        db: AsyncSession,
        user_id: str,
        months: int = 6,
    ) -> List[Dict[str, Any]]:
        """월별 트렌드 분석"""
        query = select(ROISummary).where(
            ROISummary.user_id == user_id
        ).order_by(desc(ROISummary.year), desc(ROISummary.month)).limit(months)

        result = await db.execute(query)
        summaries = list(result.scalars().all())

        return [
            {
                "year": s.year,
                "month": s.month,
                "views": s.total_views,
                "inquiries": s.total_inquiries,
                "visits": s.total_visits,
                "reservations": s.total_reservations,
                "revenue": s.total_revenue,
                "cost": s.total_cost,
                "roi_percentage": s.roi_percentage,
                "overall_conversion_rate": s.overall_conversion_rate,
            }
            for s in reversed(summaries)
        ]


# Integer 임포트 추가
from sqlalchemy import Integer
