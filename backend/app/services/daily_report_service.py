"""
일일 리포트 서비스
- 자동 리포트 생성
- 알림 발송
- 리포트 조회
"""

import uuid
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.viral_common import DailyReport, PerformanceDaily, NotificationType
from app.models.knowledge import KnowledgeAnswer, KnowledgeStats
from app.models.cafe import CafeContent, CafeStats


class DailyReportService:
    """일일 리포트 서비스"""

    async def generate_report(
        self,
        db: AsyncSession,
        user_id: str,
        report_date: Optional[date] = None
    ) -> DailyReport:
        """일일 리포트 생성"""
        target_date = report_date or date.today()

        # 기존 리포트 확인
        existing = await self.get_report(db, user_id, target_date)
        if existing:
            # 업데이트
            report = existing
        else:
            report = DailyReport(
                id=str(uuid.uuid4()),
                user_id=user_id,
                date=target_date
            )
            db.add(report)

        # 성과 데이터 수집
        performance_data = await self._collect_performance_data(db, user_id, target_date)

        # 지식인 데이터
        report.knowledge_answers = performance_data.get("knowledge_answers", 0)
        report.knowledge_adoptions = performance_data.get("knowledge_adoptions", 0)
        report.knowledge_likes = performance_data.get("knowledge_likes", 0)

        # 카페 데이터
        report.cafe_comments = performance_data.get("cafe_comments", 0)
        report.cafe_posts = performance_data.get("cafe_posts", 0)
        report.cafe_likes = performance_data.get("cafe_likes", 0)
        report.cafe_replies = performance_data.get("cafe_replies", 0)

        # 클릭 데이터
        report.blog_clicks = performance_data.get("blog_clicks", 0)
        report.place_clicks = performance_data.get("place_clicks", 0)

        # 하이라이트 생성
        report.highlights = await self._generate_highlights(performance_data)

        # 전일 대비 변화율
        previous_date = target_date - timedelta(days=1)
        previous_data = await self._collect_performance_data(db, user_id, previous_date)
        report.comparison = self._calculate_comparison(performance_data, previous_data)

        # 추천사항 생성
        report.recommendations = await self._generate_recommendations(
            db, user_id, performance_data
        )

        await db.commit()
        await db.refresh(report)

        return report

    async def _collect_performance_data(
        self,
        db: AsyncSession,
        user_id: str,
        target_date: date
    ) -> Dict[str, Any]:
        """성과 데이터 수집"""
        data = {
            "knowledge_answers": 0,
            "knowledge_adoptions": 0,
            "knowledge_likes": 0,
            "cafe_comments": 0,
            "cafe_posts": 0,
            "cafe_likes": 0,
            "cafe_replies": 0,
            "blog_clicks": 0,
            "place_clicks": 0
        }

        # PerformanceDaily에서 데이터 조회
        result = await db.execute(
            select(PerformanceDaily).where(
                and_(
                    PerformanceDaily.user_id == user_id,
                    PerformanceDaily.date == target_date
                )
            )
        )
        daily_stats = list(result.scalars().all())

        for stat in daily_stats:
            if stat.platform == "knowledge":
                data["knowledge_answers"] += stat.answers_posted
                data["knowledge_adoptions"] += stat.answers_adopted
                data["knowledge_likes"] += stat.likes_received
                data["blog_clicks"] += stat.blog_clicks
                data["place_clicks"] += stat.place_clicks
            elif stat.platform == "cafe":
                data["cafe_comments"] += stat.comments_posted
                data["cafe_posts"] += stat.posts_created
                data["cafe_likes"] += stat.likes_received
                data["cafe_replies"] += stat.replies_received
                data["blog_clicks"] += stat.blog_clicks
                data["place_clicks"] += stat.place_clicks

        return data

    async def _generate_highlights(
        self,
        data: Dict[str, Any]
    ) -> List[str]:
        """하이라이트 생성"""
        highlights = []

        total_activity = (
            data.get("knowledge_answers", 0) +
            data.get("cafe_comments", 0) +
            data.get("cafe_posts", 0)
        )

        if total_activity > 0:
            highlights.append(f"총 {total_activity}건의 콘텐츠 발행")

        adoptions = data.get("knowledge_adoptions", 0)
        if adoptions > 0:
            highlights.append(f"답변 {adoptions}건 채택")

        total_likes = (
            data.get("knowledge_likes", 0) +
            data.get("cafe_likes", 0)
        )
        if total_likes > 0:
            highlights.append(f"좋아요 {total_likes}개 획득")

        replies = data.get("cafe_replies", 0)
        if replies > 0:
            highlights.append(f"댓글 {replies}개 수신")

        total_clicks = (
            data.get("blog_clicks", 0) +
            data.get("place_clicks", 0)
        )
        if total_clicks > 0:
            highlights.append(f"링크 클릭 {total_clicks}회")

        if not highlights:
            highlights.append("오늘은 활동이 없었습니다")

        return highlights

    def _calculate_comparison(
        self,
        current: Dict[str, Any],
        previous: Dict[str, Any]
    ) -> Dict[str, Any]:
        """전일 대비 비교"""

        def calc_change(curr, prev):
            if prev == 0:
                return 100 if curr > 0 else 0
            return round(((curr - prev) / prev) * 100, 1)

        return {
            "answers_change": calc_change(
                current.get("knowledge_answers", 0),
                previous.get("knowledge_answers", 0)
            ),
            "comments_change": calc_change(
                current.get("cafe_comments", 0),
                previous.get("cafe_comments", 0)
            ),
            "likes_change": calc_change(
                current.get("knowledge_likes", 0) + current.get("cafe_likes", 0),
                previous.get("knowledge_likes", 0) + previous.get("cafe_likes", 0)
            ),
            "clicks_change": calc_change(
                current.get("blog_clicks", 0) + current.get("place_clicks", 0),
                previous.get("blog_clicks", 0) + previous.get("place_clicks", 0)
            )
        }

    async def _generate_recommendations(
        self,
        db: AsyncSession,
        user_id: str,
        data: Dict[str, Any]
    ) -> List[str]:
        """추천사항 생성"""
        recommendations = []

        # 활동량 분석
        total_activity = (
            data.get("knowledge_answers", 0) +
            data.get("cafe_comments", 0)
        )

        if total_activity == 0:
            recommendations.append("오늘 활동이 없습니다. 자동화 설정을 확인해주세요.")
        elif total_activity < 5:
            recommendations.append("활동량을 늘리면 더 많은 노출을 얻을 수 있습니다.")

        # 채택률 분석
        answers = data.get("knowledge_answers", 0)
        adoptions = data.get("knowledge_adoptions", 0)
        if answers > 0:
            adoption_rate = adoptions / answers
            if adoption_rate < 0.1:
                recommendations.append("채택률이 낮습니다. 답변 품질 개선을 고려해보세요.")
            elif adoption_rate > 0.3:
                recommendations.append("채택률이 매우 좋습니다! 현재 전략을 유지하세요.")

        # 클릭률 분석
        clicks = data.get("blog_clicks", 0) + data.get("place_clicks", 0)
        if total_activity > 0 and clicks == 0:
            recommendations.append("링크 클릭이 없습니다. 홍보 문구를 개선해보세요.")

        # 반응 분석
        likes = data.get("knowledge_likes", 0) + data.get("cafe_likes", 0)
        if total_activity > 5 and likes == 0:
            recommendations.append("좋아요가 적습니다. 더 공감가는 콘텐츠를 작성해보세요.")

        if not recommendations:
            recommendations.append("전반적으로 좋은 성과를 보이고 있습니다!")

        return recommendations

    async def get_report(
        self,
        db: AsyncSession,
        user_id: str,
        report_date: date
    ) -> Optional[DailyReport]:
        """리포트 조회"""
        result = await db.execute(
            select(DailyReport).where(
                and_(
                    DailyReport.user_id == user_id,
                    DailyReport.date == report_date
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_reports(
        self,
        db: AsyncSession,
        user_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 30
    ) -> List[DailyReport]:
        """리포트 목록 조회"""
        query = select(DailyReport).where(DailyReport.user_id == user_id)

        if start_date:
            query = query.where(DailyReport.date >= start_date)

        if end_date:
            query = query.where(DailyReport.date <= end_date)

        query = query.order_by(DailyReport.date.desc()).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def send_daily_report(
        self,
        db: AsyncSession,
        user_id: str,
        report_date: Optional[date] = None
    ) -> DailyReport:
        """일일 리포트 발송"""
        from app.services.notification_service import notification_service

        # 리포트 생성 (없으면)
        report = await self.generate_report(db, user_id, report_date)

        # 알림 발송
        report_data = {
            "지식인 답변": report.knowledge_answers,
            "채택": report.knowledge_adoptions,
            "카페 댓글": report.cafe_comments,
            "카페 게시글": report.cafe_posts,
            "좋아요": report.knowledge_likes + report.cafe_likes,
            "링크 클릭": report.blog_clicks + report.place_clicks
        }

        await notification_service.notify_daily_report(
            db, user_id, report_data
        )

        # 발송 상태 업데이트
        report.is_sent = True
        report.sent_at = datetime.utcnow()
        await db.commit()

        return report

    async def get_weekly_summary(
        self,
        db: AsyncSession,
        user_id: str,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """주간 요약"""
        end = end_date or date.today()
        start = end - timedelta(days=6)

        reports = await self.get_reports(
            db, user_id, start_date=start, end_date=end, limit=7
        )

        summary = {
            "period": {
                "start": start.isoformat(),
                "end": end.isoformat()
            },
            "totals": {
                "knowledge_answers": sum(r.knowledge_answers for r in reports),
                "knowledge_adoptions": sum(r.knowledge_adoptions for r in reports),
                "cafe_comments": sum(r.cafe_comments for r in reports),
                "cafe_posts": sum(r.cafe_posts for r in reports),
                "likes": sum(r.knowledge_likes + r.cafe_likes for r in reports),
                "clicks": sum(r.blog_clicks + r.place_clicks for r in reports)
            },
            "averages": {},
            "best_day": None,
            "daily": []
        }

        # 평균 계산
        count = len(reports) or 1
        summary["averages"] = {
            k: round(v / count, 1)
            for k, v in summary["totals"].items()
        }

        # 일별 데이터
        best_score = -1
        for report in sorted(reports, key=lambda x: x.date):
            day_data = {
                "date": report.date.isoformat(),
                "answers": report.knowledge_answers,
                "adoptions": report.knowledge_adoptions,
                "comments": report.cafe_comments,
                "posts": report.cafe_posts,
                "likes": report.knowledge_likes + report.cafe_likes,
                "clicks": report.blog_clicks + report.place_clicks
            }
            summary["daily"].append(day_data)

            # 최고 성과일 찾기
            score = (
                report.knowledge_answers +
                report.knowledge_adoptions * 3 +
                report.cafe_comments +
                report.cafe_posts * 2 +
                report.blog_clicks + report.place_clicks
            )
            if score > best_score:
                best_score = score
                summary["best_day"] = report.date.isoformat()

        # 채택률
        total_answers = summary["totals"]["knowledge_answers"]
        total_adoptions = summary["totals"]["knowledge_adoptions"]
        summary["adoption_rate"] = round(
            total_adoptions / total_answers * 100, 1
        ) if total_answers > 0 else 0

        return summary

    async def get_monthly_summary(
        self,
        db: AsyncSession,
        user_id: str,
        year: int,
        month: int
    ) -> Dict[str, Any]:
        """월간 요약"""
        from calendar import monthrange

        start = date(year, month, 1)
        _, last_day = monthrange(year, month)
        end = date(year, month, last_day)

        reports = await self.get_reports(
            db, user_id, start_date=start, end_date=end, limit=31
        )

        # 주차별 집계
        weeks = {}
        for report in reports:
            week_num = report.date.isocalendar()[1]
            if week_num not in weeks:
                weeks[week_num] = {
                    "answers": 0,
                    "adoptions": 0,
                    "comments": 0,
                    "posts": 0,
                    "likes": 0,
                    "clicks": 0
                }

            weeks[week_num]["answers"] += report.knowledge_answers
            weeks[week_num]["adoptions"] += report.knowledge_adoptions
            weeks[week_num]["comments"] += report.cafe_comments
            weeks[week_num]["posts"] += report.cafe_posts
            weeks[week_num]["likes"] += report.knowledge_likes + report.cafe_likes
            weeks[week_num]["clicks"] += report.blog_clicks + report.place_clicks

        return {
            "period": {
                "year": year,
                "month": month,
                "start": start.isoformat(),
                "end": end.isoformat()
            },
            "totals": {
                "knowledge_answers": sum(r.knowledge_answers for r in reports),
                "knowledge_adoptions": sum(r.knowledge_adoptions for r in reports),
                "cafe_comments": sum(r.cafe_comments for r in reports),
                "cafe_posts": sum(r.cafe_posts for r in reports),
                "likes": sum(r.knowledge_likes + r.cafe_likes for r in reports),
                "clicks": sum(r.blog_clicks + r.place_clicks for r in reports)
            },
            "weeks": weeks,
            "days_active": len(reports)
        }


# 싱글톤 인스턴스
daily_report_service = DailyReportService()
