"""
평판 모니터링 - 백그라운드 스케줄러
주기적 크롤링, 분석, 스냅샷 생성, 다이제스트 발송
"""
import asyncio
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.models.reputation import (
    MonitorProfile, Mention, ReputationCrawlJob, ReputationSnapshot,
    MentionPlatform, MentionSentiment, RiskLevel, CrawlJobStatus
)

logger = logging.getLogger(__name__)


class ReputationScheduler:
    """평판 모니터링 스케줄러"""

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """스케줄러 시작"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("평판 모니터링 스케줄러 시작")

    async def stop(self):
        """스케줄러 종료"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("평판 모니터링 스케줄러 종료")

    async def _run_loop(self):
        """메인 루프"""
        while self._running:
            try:
                await self._check_scheduled_crawls()
                await self._generate_daily_snapshots()
            except Exception as e:
                logger.error(f"스케줄러 루프 오류: {e}")

            # 5분마다 확인
            await asyncio.sleep(300)

    async def _check_scheduled_crawls(self):
        """예약된 크롤링 작업 확인 및 실행"""
        async with AsyncSessionLocal() as db:
            try:
                # 활성 프로필 조회
                result = await db.execute(
                    select(MonitorProfile).where(MonitorProfile.is_active == True)
                )
                profiles = result.scalars().all()

                for profile in profiles:
                    # 마지막 크롤링 시간 확인
                    last_job = await db.execute(
                        select(ReputationCrawlJob)
                        .where(and_(
                            ReputationCrawlJob.profile_id == profile.id,
                            ReputationCrawlJob.status == CrawlJobStatus.COMPLETED,
                        ))
                        .order_by(ReputationCrawlJob.completed_at.desc())
                        .limit(1)
                    )
                    last = last_job.scalar_one_or_none()

                    # 크롤링 주기 확인
                    interval = timedelta(minutes=profile.crawl_interval_minutes or 60)
                    if last and last.completed_at:
                        next_crawl = last.completed_at + interval
                        if datetime.utcnow() < next_crawl:
                            continue

                    # 크롤링 실행
                    platforms = profile.enabled_platforms or ["naver_place"]
                    for platform_str in platforms:
                        try:
                            platform = MentionPlatform(platform_str)
                            job = ReputationCrawlJob(
                                id=str(uuid.uuid4()),
                                profile_id=profile.id,
                                user_id=profile.user_id,
                                platform=platform,
                                status=CrawlJobStatus.PENDING,
                                trigger_type="scheduled",
                            )
                            db.add(job)
                            await db.commit()

                            from app.services.reputation_crawler import ReputationCrawlerService
                            crawler_service = ReputationCrawlerService(db)
                            await crawler_service.run_crawl_job(job.id, profile)

                        except Exception as e:
                            logger.error(f"스케줄 크롤링 오류 ({platform_str}): {e}")

            except Exception as e:
                logger.error(f"스케줄 크롤링 확인 오류: {e}")

    async def _generate_daily_snapshots(self):
        """일별 평판 스냅샷 생성"""
        async with AsyncSessionLocal() as db:
            try:
                now = datetime.utcnow()
                today = now.replace(hour=0, minute=0, second=0, microsecond=0)

                # 활성 프로필 조회
                result = await db.execute(
                    select(MonitorProfile).where(MonitorProfile.is_active == True)
                )
                profiles = result.scalars().all()

                for profile in profiles:
                    # 오늘 스냅샷이 이미 있는지 확인
                    existing = await db.execute(
                        select(ReputationSnapshot).where(and_(
                            ReputationSnapshot.profile_id == profile.id,
                            ReputationSnapshot.snapshot_date >= today,
                        ))
                    )
                    if existing.scalar_one_or_none():
                        continue

                    # 최근 24시간 멘션 통계
                    since = now - timedelta(hours=24)
                    stats = await db.execute(
                        select(
                            func.count(Mention.id).label("total"),
                            func.count().filter(Mention.sentiment == MentionSentiment.POSITIVE).label("positive"),
                            func.count().filter(Mention.sentiment == MentionSentiment.NEUTRAL).label("neutral"),
                            func.count().filter(Mention.sentiment == MentionSentiment.NEGATIVE).label("negative"),
                            func.count().filter(Mention.sentiment == MentionSentiment.MIXED).label("mixed"),
                            func.avg(Mention.rating).label("avg_rating"),
                        ).where(and_(
                            Mention.profile_id == profile.id,
                            Mention.created_at >= since,
                        ))
                    )
                    row = stats.one()

                    # 평판 점수 계산
                    total = row.total or 0
                    if total > 0:
                        positive_ratio = (row.positive or 0) / total
                        negative_ratio = (row.negative or 0) / total
                        avg_rating_norm = ((row.avg_rating or 3) / 5) * 100

                        reputation_score = (
                            positive_ratio * 40 +
                            (1 - negative_ratio) * 30 +
                            avg_rating_norm * 0.3
                        )
                        reputation_score = min(100, max(0, reputation_score))
                    else:
                        reputation_score = None

                    # 플랫폼별 통계
                    platform_stats_query = await db.execute(
                        select(
                            Mention.platform,
                            func.count(Mention.id),
                            func.avg(Mention.rating),
                        ).where(and_(
                            Mention.profile_id == profile.id,
                            Mention.created_at >= since,
                        ))
                        .group_by(Mention.platform)
                    )
                    platform_stats = {
                        row[0].value: {
                            "count": row[1],
                            "avg_rating": round(float(row[2] or 0), 1),
                        }
                        for row in platform_stats_query.all()
                    }

                    # 스냅샷 생성
                    snapshot = ReputationSnapshot(
                        id=str(uuid.uuid4()),
                        profile_id=profile.id,
                        user_id=profile.user_id,
                        snapshot_date=today,
                        reputation_score=round(reputation_score, 1) if reputation_score else None,
                        avg_rating=round(float(row.avg_rating or 0), 1),
                        positive_count=row.positive or 0,
                        neutral_count=row.neutral or 0,
                        negative_count=row.negative or 0,
                        mixed_count=row.mixed or 0,
                        platform_stats=platform_stats,
                    )
                    db.add(snapshot)
                    await db.commit()

                    logger.info(
                        f"스냅샷 생성: {profile.business_name} | "
                        f"점수: {reputation_score} | 멘션: {total}"
                    )

            except Exception as e:
                logger.error(f"일별 스냅샷 생성 오류: {e}")


# 싱글톤 인스턴스
reputation_scheduler = ReputationScheduler()
