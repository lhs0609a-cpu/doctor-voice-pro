"""
경쟁 병원 분석 서비스
"""

import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from sqlalchemy.orm import selectinload
import uuid

from app.models.competitor import (
    Competitor, CompetitorSnapshot, CompetitorAlert, CompetitorComparison, WeeklyCompetitorReport
)
from app.models.naver_place import NaverPlace

logger = logging.getLogger(__name__)


class CompetitorService:
    """경쟁 병원 분석 서비스"""

    async def add_competitor(
        self,
        db: AsyncSession,
        user_id: str,
        place_id: str,
        place_name: str,
        **kwargs,
    ) -> Competitor:
        """경쟁사 추가"""
        # 중복 체크
        query = select(Competitor).where(
            and_(
                Competitor.user_id == user_id,
                Competitor.place_id == place_id,
            )
        )
        result = await db.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            existing.is_active = True
            for key, value in kwargs.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            await db.commit()
            await db.refresh(existing)
            return existing

        competitor = Competitor(
            user_id=user_id,
            place_id=place_id,
            place_name=place_name,
            is_active=True,
            **kwargs,
        )

        db.add(competitor)
        await db.commit()
        await db.refresh(competitor)

        logger.info(f"Added competitor {place_id} for user {user_id}")
        return competitor

    async def get_competitors(
        self,
        db: AsyncSession,
        user_id: str,
        is_active: Optional[bool] = True,
    ) -> List[Competitor]:
        """경쟁사 목록 조회"""
        query = select(Competitor).where(Competitor.user_id == user_id)

        if is_active is not None:
            query = query.where(Competitor.is_active == is_active)

        query = query.order_by(desc(Competitor.priority), desc(Competitor.created_at))

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_competitor(
        self,
        db: AsyncSession,
        competitor_id: str,
    ) -> Optional[Competitor]:
        """경쟁사 상세 조회"""
        query = select(Competitor).where(Competitor.id == competitor_id).options(
            selectinload(Competitor.snapshots),
            selectinload(Competitor.alerts),
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def remove_competitor(
        self,
        db: AsyncSession,
        competitor_id: str,
    ) -> bool:
        """경쟁사 제거"""
        query = select(Competitor).where(Competitor.id == competitor_id)
        result = await db.execute(query)
        competitor = result.scalar_one_or_none()

        if competitor:
            competitor.is_active = False
            await db.commit()
            return True

        return False

    async def auto_detect_competitors(
        self,
        db: AsyncSession,
        user_id: str,
        place_db_id: str,
        radius_km: float = 3.0,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """경쟁사 자동 탐지"""
        # 내 플레이스 정보 조회
        place_query = select(NaverPlace).where(NaverPlace.id == place_db_id)
        place_result = await db.execute(place_query)
        my_place = place_result.scalar_one_or_none()

        if not my_place:
            return []

        # 실제로는 네이버 API 또는 크롤링으로 주변 경쟁사를 탐지
        # 여기서는 시뮬레이션 데이터 반환
        detected = []

        # 기존 경쟁사 ID 목록
        existing_query = select(Competitor.place_id).where(
            Competitor.user_id == user_id
        )
        existing_result = await db.execute(existing_query)
        existing_ids = set(row[0] for row in existing_result.all())

        # 시뮬레이션: 같은 카테고리의 주변 병원 탐지
        simulation_competitors = [
            {
                "place_id": f"sim_{i}",
                "place_name": f"주변병원{i}",
                "category": my_place.category,
                "address": f"주변 지역 {i}번지",
                "distance_km": round(0.5 + i * 0.3, 1),
                "review_count": 50 + i * 20,
                "avg_rating": round(4.0 + (i % 5) * 0.1, 1),
                "detection_reason": "동일 카테고리, 반경 3km 이내",
                "similarity_score": round(0.9 - i * 0.05, 2),
            }
            for i in range(1, limit + 1)
        ]

        for comp in simulation_competitors:
            if comp["place_id"] not in existing_ids and comp["distance_km"] <= radius_km:
                detected.append(comp)

        return detected[:limit]

    async def create_snapshot(
        self,
        db: AsyncSession,
        competitor_id: str,
        **kwargs,
    ) -> CompetitorSnapshot:
        """경쟁사 스냅샷 생성"""
        # 이전 스냅샷 조회 (변동 계산용)
        prev_query = select(CompetitorSnapshot).where(
            CompetitorSnapshot.competitor_id == competitor_id
        ).order_by(desc(CompetitorSnapshot.snapshot_date)).limit(1)

        prev_result = await db.execute(prev_query)
        prev_snapshot = prev_result.scalar_one_or_none()

        review_count = kwargs.get("review_count", 0)
        avg_rating = kwargs.get("avg_rating", 0)

        review_count_change = 0
        rating_change = 0.0

        if prev_snapshot:
            review_count_change = review_count - prev_snapshot.review_count
            rating_change = avg_rating - prev_snapshot.avg_rating

        snapshot = CompetitorSnapshot(
            competitor_id=competitor_id,
            review_count=review_count,
            avg_rating=avg_rating,
            review_count_change=review_count_change,
            rating_change=round(rating_change, 2),
            snapshot_date=date.today(),
            **{k: v for k, v in kwargs.items() if k not in ["review_count", "avg_rating"]},
        )

        db.add(snapshot)
        await db.commit()
        await db.refresh(snapshot)

        # 주요 변동 시 알림 생성
        if abs(review_count_change) >= 5:
            await self._create_alert(
                db, competitor_id,
                "review_surge",
                f"리뷰 수 {'증가' if review_count_change > 0 else '감소'} ({review_count_change:+d})",
                {"change": review_count_change},
            )

        if abs(rating_change) >= 0.2:
            await self._create_alert(
                db, competitor_id,
                "rating_change",
                f"평점 변동 ({rating_change:+.1f})",
                {"change": rating_change},
            )

        return snapshot

    async def _create_alert(
        self,
        db: AsyncSession,
        competitor_id: str,
        alert_type: str,
        message: str,
        data: Dict[str, Any],
        severity: str = "info",
    ) -> CompetitorAlert:
        """경쟁사 알림 생성"""
        # 경쟁사 정보 조회
        comp_query = select(Competitor).where(Competitor.id == competitor_id)
        comp_result = await db.execute(comp_query)
        competitor = comp_result.scalar_one_or_none()

        title = f"[{competitor.place_name if competitor else '경쟁사'}] {message}"

        alert = CompetitorAlert(
            competitor_id=competitor_id,
            alert_type=alert_type,
            title=title,
            message=message,
            data=data,
            severity=severity,
        )

        db.add(alert)
        await db.commit()
        await db.refresh(alert)

        return alert

    async def get_comparison(
        self,
        db: AsyncSession,
        user_id: str,
        my_place_db_id: str,
        competitor_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """경쟁사 비교 분석"""
        # 내 플레이스 정보
        my_query = select(NaverPlace).where(NaverPlace.id == my_place_db_id)
        my_result = await db.execute(my_query)
        my_place = my_result.scalar_one_or_none()

        if not my_place:
            return {"error": "Place not found"}

        # 경쟁사 목록
        comp_query = select(Competitor).where(
            and_(
                Competitor.user_id == user_id,
                Competitor.is_active == True,
            )
        )
        if competitor_ids:
            comp_query = comp_query.where(Competitor.id.in_(competitor_ids))

        comp_result = await db.execute(comp_query)
        competitors = list(comp_result.scalars().all())

        # 비교 데이터 구성
        my_stats = {
            "place_name": my_place.place_name,
            "review_count": my_place.review_count or 0,
            "avg_rating": my_place.avg_rating or 0,
            "visitor_review_count": my_place.visitor_review_count or 0,
            "blog_review_count": my_place.blog_review_count or 0,
            "save_count": my_place.save_count or 0,
            "optimization_score": my_place.optimization_score or 0,
        }

        competitor_stats = []
        for comp in competitors:
            competitor_stats.append({
                "id": str(comp.id),
                "place_name": comp.place_name,
                "review_count": comp.review_count or 0,
                "avg_rating": comp.avg_rating or 0,
                "visitor_review_count": comp.visitor_review_count or 0,
                "blog_review_count": comp.blog_review_count or 0,
                "save_count": comp.save_count or 0,
                "distance_km": comp.distance_km or 0,
            })

        # 순위 계산
        all_ratings = [my_stats["avg_rating"]] + [c["avg_rating"] for c in competitor_stats]
        all_reviews = [my_stats["review_count"]] + [c["review_count"] for c in competitor_stats]

        rating_rank = sorted(all_ratings, reverse=True).index(my_stats["avg_rating"]) + 1
        review_rank = sorted(all_reviews, reverse=True).index(my_stats["review_count"]) + 1

        # 평균 계산
        if competitor_stats:
            avg_competitor_rating = sum(c["avg_rating"] for c in competitor_stats) / len(competitor_stats)
            avg_competitor_reviews = sum(c["review_count"] for c in competitor_stats) / len(competitor_stats)
        else:
            avg_competitor_rating = 0
            avg_competitor_reviews = 0

        return {
            "my_stats": my_stats,
            "competitor_stats": competitor_stats,
            "ranking": {
                "total_compared": len(competitors) + 1,
                "rating_rank": rating_rank,
                "review_rank": review_rank,
            },
            "comparison": {
                "rating_vs_avg": round(my_stats["avg_rating"] - avg_competitor_rating, 2),
                "reviews_vs_avg": round(my_stats["review_count"] - avg_competitor_reviews),
            },
            "analysis_date": datetime.utcnow().isoformat(),
        }

    async def get_competitor_reviews_analysis(
        self,
        db: AsyncSession,
        competitor_id: str,
    ) -> Dict[str, Any]:
        """경쟁사 리뷰 분석"""
        # 최근 스냅샷 조회
        query = select(CompetitorSnapshot).where(
            CompetitorSnapshot.competitor_id == competitor_id
        ).order_by(desc(CompetitorSnapshot.snapshot_date)).limit(30)

        result = await db.execute(query)
        snapshots = list(result.scalars().all())

        if not snapshots:
            return {"message": "No snapshot data"}

        latest = snapshots[0]

        # 트렌드 분석
        trends = []
        for s in reversed(snapshots):
            trends.append({
                "date": s.snapshot_date.isoformat(),
                "review_count": s.review_count,
                "avg_rating": s.avg_rating,
            })

        return {
            "latest": {
                "review_count": latest.review_count,
                "avg_rating": latest.avg_rating,
                "visitor_review_count": latest.visitor_review_count,
                "blog_review_count": latest.blog_review_count,
            },
            "recent_keywords": {
                "positive": latest.recent_positive_keywords or [],
                "negative": latest.recent_negative_keywords or [],
            },
            "trends": trends,
        }

    async def get_weekly_report(
        self,
        db: AsyncSession,
        user_id: str,
        week_start: Optional[date] = None,
    ) -> Optional[WeeklyCompetitorReport]:
        """주간 경쟁 리포트 조회"""
        if not week_start:
            # 이번 주 월요일
            today = date.today()
            week_start = today - timedelta(days=today.weekday())

        query = select(WeeklyCompetitorReport).where(
            and_(
                WeeklyCompetitorReport.user_id == user_id,
                WeeklyCompetitorReport.week_start == week_start,
            )
        )

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def generate_weekly_report(
        self,
        db: AsyncSession,
        user_id: str,
        place_db_id: str,
    ) -> WeeklyCompetitorReport:
        """주간 경쟁 리포트 생성"""
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        year, week_number, _ = today.isocalendar()

        # 비교 분석 데이터 조회
        comparison = await self.get_comparison(db, user_id, place_db_id)

        # 경쟁사 변동사항 조회
        alert_query = select(CompetitorAlert).join(Competitor).where(
            and_(
                Competitor.user_id == user_id,
                CompetitorAlert.created_at >= datetime.combine(week_start, datetime.min.time()),
                CompetitorAlert.created_at <= datetime.combine(week_end, datetime.max.time()),
            )
        ).order_by(desc(CompetitorAlert.created_at))

        alert_result = await db.execute(alert_query)
        alerts = list(alert_result.scalars().all())

        significant_changes = [
            {
                "type": alert.alert_type,
                "title": alert.title,
                "message": alert.message,
                "data": alert.data,
            }
            for alert in alerts[:10]
        ]

        # 리포트 생성 또는 업데이트
        report_query = select(WeeklyCompetitorReport).where(
            and_(
                WeeklyCompetitorReport.user_id == user_id,
                WeeklyCompetitorReport.week_start == week_start,
            )
        )
        report_result = await db.execute(report_query)
        report = report_result.scalar_one_or_none()

        if not report:
            report = WeeklyCompetitorReport(
                user_id=user_id,
                week_start=week_start,
                week_end=week_end,
                year=year,
                week_number=week_number,
            )
            db.add(report)

        report.my_stats = comparison.get("my_stats", {})
        report.competitor_stats = comparison.get("competitor_stats", {})
        report.significant_changes = significant_changes
        report.generated_at = datetime.utcnow()

        # 요약 생성
        my_rating = comparison.get("my_stats", {}).get("avg_rating", 0)
        rating_vs_avg = comparison.get("comparison", {}).get("rating_vs_avg", 0)

        if rating_vs_avg > 0.3:
            summary = f"이번 주 평점이 경쟁사 평균보다 {rating_vs_avg:.1f}점 높습니다. 좋은 성과입니다!"
        elif rating_vs_avg < -0.3:
            summary = f"이번 주 평점이 경쟁사 평균보다 {abs(rating_vs_avg):.1f}점 낮습니다. 리뷰 관리에 신경 써주세요."
        else:
            summary = "경쟁사와 비슷한 수준을 유지하고 있습니다."

        report.summary = summary

        await db.commit()
        await db.refresh(report)

        return report

    async def get_alerts(
        self,
        db: AsyncSession,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
    ) -> List[CompetitorAlert]:
        """경쟁사 알림 조회"""
        query = select(CompetitorAlert).join(Competitor).where(
            Competitor.user_id == user_id
        )

        if unread_only:
            query = query.where(CompetitorAlert.is_read == False)

        query = query.order_by(desc(CompetitorAlert.created_at)).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def mark_alert_read(
        self,
        db: AsyncSession,
        alert_id: str,
    ) -> bool:
        """알림 읽음 처리"""
        query = select(CompetitorAlert).where(CompetitorAlert.id == alert_id)
        result = await db.execute(query)
        alert = result.scalar_one_or_none()

        if alert:
            alert.is_read = True
            alert.read_at = datetime.utcnow()
            await db.commit()
            return True

        return False
