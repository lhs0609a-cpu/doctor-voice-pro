"""
블로그 영업 자동화 스케줄러
주기적으로 블로그 수집, 연락처 추출, 스코어링, 이메일 발송 실행
"""

import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List

from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from app.models.blog_outreach import (
    NaverBlog, BlogContact, BlogSearchKeyword, EmailCampaign, EmailLog,
    OutreachSetting, OutreachStats, BlogStatus, CampaignStatus, EmailStatus, LeadGrade
)
from app.services.blog_outreach_crawler import BlogOutreachCrawler
from app.services.contact_extractor import ContactExtractorService
from app.services.lead_scoring_service import LeadScoringService
from app.services.email_sender_service import EmailSenderService

logger = logging.getLogger(__name__)


class OutreachSchedulerService:
    """블로그 영업 자동화 스케줄러"""

    def __init__(self, db: Session):
        self.db = db
        self._is_running = False
        self._collection_task: Optional[asyncio.Task] = None
        self._extraction_task: Optional[asyncio.Task] = None
        self._scoring_task: Optional[asyncio.Task] = None
        self._campaign_task: Optional[asyncio.Task] = None
        self._stats_task: Optional[asyncio.Task] = None
        self._user_id: Optional[str] = None

        # 통계 추적
        self._started_at: Optional[datetime] = None
        self._blogs_collected: int = 0
        self._contacts_extracted: int = 0
        self._emails_sent: int = 0
        self._last_collection: Optional[datetime] = None
        self._last_campaign_run: Optional[datetime] = None

        # 기본 주기 설정 (초)
        self.collection_interval = 60 * 60  # 1시간
        self.extraction_interval = 30 * 60  # 30분
        self.scoring_interval = 60 * 60  # 1시간
        self.campaign_interval = 5 * 60  # 5분
        self.stats_interval = 60 * 60  # 1시간

    async def start(self, user_id: str):
        """
        스케줄러 시작

        Args:
            user_id: 사용자 ID
        """
        if self._is_running:
            logger.warning("아웃리치 스케줄러가 이미 실행 중입니다")
            return {"success": False, "message": "스케줄러가 이미 실행 중입니다"}

        self._user_id = user_id
        self._is_running = True
        self._started_at = datetime.utcnow()
        self._blogs_collected = 0
        self._contacts_extracted = 0
        self._emails_sent = 0

        # 설정 로드
        settings = self._get_settings(user_id)

        # 자동 수집 루프
        if settings and settings.auto_collect:
            self._collection_task = asyncio.create_task(
                self._collection_loop(user_id, settings)
            )

        # 자동 연락처 추출 루프
        if settings and settings.auto_extract_contact:
            self._extraction_task = asyncio.create_task(
                self._extraction_loop(user_id, settings)
            )

        # 자동 스코어링 루프
        if settings and settings.auto_score:
            self._scoring_task = asyncio.create_task(
                self._scoring_loop(user_id, settings)
            )

        # 캠페인 발송 루프
        self._campaign_task = asyncio.create_task(
            self._campaign_loop(user_id, settings)
        )

        # 통계 집계 루프
        self._stats_task = asyncio.create_task(
            self._stats_loop(user_id)
        )

        logger.info(f"아웃리치 스케줄러 시작: user_id={user_id}")
        return {"success": True, "message": "스케줄러가 시작되었습니다"}

    async def stop(self):
        """스케줄러 중지"""
        self._is_running = False

        tasks = [
            self._collection_task,
            self._extraction_task,
            self._scoring_task,
            self._campaign_task,
            self._stats_task
        ]

        for task in tasks:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        logger.info("아웃리치 스케줄러 중지")
        return {"success": True, "message": "스케줄러가 중지되었습니다"}

    def get_status(self) -> Dict[str, Any]:
        """스케줄러 상태 조회"""
        return {
            "is_running": self._is_running,
            "user_id": self._user_id,
            "tasks": {
                "collection": self._collection_task is not None and not self._collection_task.done(),
                "extraction": self._extraction_task is not None and not self._extraction_task.done(),
                "scoring": self._scoring_task is not None and not self._scoring_task.done(),
                "campaign": self._campaign_task is not None and not self._campaign_task.done(),
                "stats": self._stats_task is not None and not self._stats_task.done()
            },
            "blogs_collected": self._blogs_collected,
            "contacts_extracted": self._contacts_extracted,
            "emails_sent": self._emails_sent,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "last_collection": self._last_collection.isoformat() if self._last_collection else None,
            "last_campaign_run": self._last_campaign_run.isoformat() if self._last_campaign_run else None
        }

    def _get_settings(self, user_id: str) -> Optional[OutreachSetting]:
        """사용자 설정 조회"""
        return self.db.query(OutreachSetting).filter(
            OutreachSetting.user_id == user_id
        ).first()

    def _is_working_hours(self, settings: Optional[OutreachSetting]) -> bool:
        """영업 시간 확인"""
        now = datetime.now()
        start_hour = 9  # 기본 시작 시간
        end_hour = 18  # 기본 종료 시간

        return start_hour <= now.hour < end_hour

    async def _collection_loop(self, user_id: str, settings: Optional[OutreachSetting]):
        """블로그 수집 루프"""
        while self._is_running:
            try:
                if self._is_working_hours(settings):
                    await self._run_collection(user_id)
            except Exception as e:
                logger.error(f"수집 루프 오류: {e}")

            await asyncio.sleep(self.collection_interval)

    async def _run_collection(self, user_id: str):
        """블로그 수집 실행"""
        try:
            # 활성 키워드 조회
            keywords = self.db.query(BlogSearchKeyword).filter(
                BlogSearchKeyword.user_id == user_id,
                BlogSearchKeyword.is_active == True
            ).order_by(BlogSearchKeyword.priority.desc()).limit(5).all()

            if not keywords:
                logger.info("수집할 키워드가 없습니다")
                return

            crawler = BlogOutreachCrawler(self.db)
            total_collected = 0

            for keyword in keywords:
                try:
                    result = await crawler.search_blogs(
                        keyword=keyword.keyword,
                        user_id=user_id,
                        category=keyword.category,
                        max_results=20
                    )
                    collected = result.get('collected', 0)
                    total_collected += collected
                    logger.info(f"키워드 '{keyword.keyword}' 수집 완료: {collected}개")

                    # 키워드 간 딜레이
                    await asyncio.sleep(60)

                except Exception as e:
                    logger.error(f"키워드 '{keyword.keyword}' 수집 오류: {e}")

            await crawler.close()

            # 통계 업데이트
            self._blogs_collected += total_collected
            self._last_collection = datetime.utcnow()

        except Exception as e:
            logger.error(f"수집 실행 오류: {e}")

    async def _extraction_loop(self, user_id: str, settings: Optional[OutreachSetting]):
        """연락처 추출 루프"""
        while self._is_running:
            try:
                if self._is_working_hours(settings):
                    await self._run_extraction(user_id)
            except Exception as e:
                logger.error(f"추출 루프 오류: {e}")

            await asyncio.sleep(self.extraction_interval)

    async def _run_extraction(self, user_id: str):
        """연락처 추출 실행"""
        try:
            extractor = ContactExtractorService(self.db)
            result = await extractor.extract_contacts_batch(
                user_id=user_id,
                limit=10
            )
            contacts_found = result.get('contacts_found', 0)
            self._contacts_extracted += contacts_found
            logger.info(f"연락처 추출 완료: {contacts_found}개 발견")
            await extractor.close()

        except Exception as e:
            logger.error(f"추출 실행 오류: {e}")

    async def _scoring_loop(self, user_id: str, settings: Optional[OutreachSetting]):
        """스코어링 루프"""
        while self._is_running:
            try:
                await self._run_scoring(user_id)
            except Exception as e:
                logger.error(f"스코어링 루프 오류: {e}")

            await asyncio.sleep(self.scoring_interval)

    async def _run_scoring(self, user_id: str):
        """스코어링 실행"""
        try:
            scorer = LeadScoringService(self.db)
            result = await scorer.score_blogs_batch(
                user_id=user_id,
                limit=50
            )
            logger.info(f"스코어링 완료: {result.get('results', {}).get('scored', 0)}개")

        except Exception as e:
            logger.error(f"스코어링 실행 오류: {e}")

    async def _campaign_loop(self, user_id: str, settings: Optional[OutreachSetting]):
        """캠페인 발송 루프"""
        while self._is_running:
            try:
                if self._is_working_hours(settings):
                    await self._run_campaigns(user_id)
            except Exception as e:
                logger.error(f"캠페인 루프 오류: {e}")

            await asyncio.sleep(self.campaign_interval)

    async def _run_campaigns(self, user_id: str):
        """활성 캠페인 발송 실행"""
        try:
            # 활성 캠페인 조회
            active_campaigns = self.db.query(EmailCampaign).filter(
                EmailCampaign.user_id == user_id,
                EmailCampaign.status == CampaignStatus.ACTIVE
            ).all()

            if not active_campaigns:
                return

            settings = self._get_settings(user_id)
            sender = EmailSenderService(self.db)
            total_sent = 0

            for campaign in active_campaigns:
                try:
                    # 발송 시간 확인
                    now = datetime.now()
                    if campaign.sending_hours_start and campaign.sending_hours_end:
                        if not (campaign.sending_hours_start <= now.hour < campaign.sending_hours_end):
                            continue

                    # 발송 요일 확인
                    if campaign.sending_days:
                        if now.isoweekday() not in campaign.sending_days:
                            continue

                    # 배치 발송
                    result = await sender.send_campaign_batch(
                        user_id=user_id,
                        campaign_id=campaign.id,
                        batch_size=5
                    )

                    if result.get("success"):
                        sent = result.get("results", {}).get("sent", 0)
                        total_sent += sent
                        if sent > 0:
                            logger.info(f"캠페인 '{campaign.name}' 발송: {sent}건")

                except Exception as e:
                    logger.error(f"캠페인 '{campaign.name}' 발송 오류: {e}")

            # 팔로업 이메일 발송
            followup_sent = await self._run_followups(user_id, sender)
            total_sent += followup_sent

            # 통계 업데이트
            self._emails_sent += total_sent
            self._last_campaign_run = datetime.utcnow()

        except Exception as e:
            logger.error(f"캠페인 실행 오류: {e}")

    async def _run_followups(self, user_id: str, sender: EmailSenderService) -> int:
        """팔로업 이메일 발송"""
        sent_count = 0
        try:
            # 활성 캠페인에서 팔로업 필요한 이메일 조회
            campaigns = self.db.query(EmailCampaign).filter(
                EmailCampaign.user_id == user_id,
                EmailCampaign.status == CampaignStatus.ACTIVE
            ).all()

            for campaign in campaigns:
                templates = campaign.templates or []
                if len(templates) <= 1:
                    continue

                # 이전 이메일 발송 후 팔로업 대기 중인 블로그 조회
                for i, template_info in enumerate(templates[1:], start=2):
                    delay_days = template_info.get("delay_days", 3)
                    template_id = template_info.get("template_id")

                    if not template_id:
                        continue

                    # 팔로업 대상 조회
                    cutoff_date = datetime.utcnow() - timedelta(days=delay_days)

                    # 이전 시퀀스 이메일이 발송되었고 회신 없는 블로그
                    prev_logs = self.db.query(EmailLog).filter(
                        EmailLog.campaign_id == campaign.id,
                        EmailLog.sequence_number == i - 1,
                        EmailLog.status.in_([EmailStatus.SENT, EmailStatus.OPENED, EmailStatus.CLICKED]),
                        EmailLog.sent_at <= cutoff_date
                    ).all()

                    for prev_log in prev_logs:
                        # 이미 이 시퀀스 발송했는지 확인
                        existing = self.db.query(EmailLog).filter(
                            EmailLog.campaign_id == campaign.id,
                            EmailLog.blog_id == prev_log.blog_id,
                            EmailLog.sequence_number == i
                        ).first()

                        if existing:
                            continue

                        # 팔로업 발송
                        try:
                            result = await sender.send_with_template(
                                user_id=user_id,
                                blog_id=prev_log.blog_id,
                                template_id=template_id,
                                campaign_id=campaign.id
                            )

                            if result.get("success"):
                                sent_count += 1
                                # 시퀀스 번호 업데이트
                                log = self.db.query(EmailLog).filter(
                                    EmailLog.id == result.get("email_log_id")
                                ).first()
                                if log:
                                    log.sequence_number = i
                                    self.db.commit()

                                logger.info(f"팔로업 발송 완료: blog_id={prev_log.blog_id}, sequence={i}")

                        except Exception as e:
                            logger.error(f"팔로업 발송 오류: {e}")

        except Exception as e:
            logger.error(f"팔로업 실행 오류: {e}")

        return sent_count

    async def _stats_loop(self, user_id: str):
        """통계 집계 루프"""
        while self._is_running:
            try:
                await self._run_stats(user_id)
            except Exception as e:
                logger.error(f"통계 루프 오류: {e}")

            await asyncio.sleep(self.stats_interval)

    async def _run_stats(self, user_id: str):
        """일일 통계 집계"""
        try:
            today = date.today()
            today_start = datetime.combine(today, datetime.min.time())

            # 기존 통계 확인
            existing = self.db.query(OutreachStats).filter(
                OutreachStats.user_id == user_id,
                OutreachStats.stat_date >= today_start,
                OutreachStats.stat_date < today_start + timedelta(days=1)
            ).first()

            if existing:
                stats = existing
            else:
                stats = OutreachStats(
                    user_id=user_id,
                    stat_date=today_start
                )
                self.db.add(stats)

            # 수집 통계
            stats.blogs_collected = self.db.query(NaverBlog).filter(
                NaverBlog.user_id == user_id,
                NaverBlog.collected_at >= today_start
            ).count()

            stats.contacts_extracted = self.db.query(BlogContact).filter(
                BlogContact.extracted_at >= today_start
            ).count()

            # 이메일 통계
            today_logs = self.db.query(EmailLog).filter(
                EmailLog.user_id == user_id,
                EmailLog.created_at >= today_start
            ).all()

            stats.emails_sent = sum(1 for l in today_logs if l.status not in [EmailStatus.PENDING, EmailStatus.BOUNCED])
            stats.emails_opened = sum(1 for l in today_logs if l.status in [EmailStatus.OPENED, EmailStatus.CLICKED, EmailStatus.REPLIED])
            stats.emails_clicked = sum(1 for l in today_logs if l.status in [EmailStatus.CLICKED, EmailStatus.REPLIED])
            stats.emails_replied = sum(1 for l in today_logs if l.status == EmailStatus.REPLIED)
            stats.emails_bounced = sum(1 for l in today_logs if l.status == EmailStatus.BOUNCED)

            # 비율 계산
            if stats.emails_sent > 0:
                stats.open_rate = round(stats.emails_opened / stats.emails_sent * 100, 1)
                stats.click_rate = round(stats.emails_clicked / stats.emails_sent * 100, 1)
                stats.reply_rate = round(stats.emails_replied / stats.emails_sent * 100, 1)

            # 등급별 분포
            grade_breakdown = {}
            for grade in LeadGrade:
                count = self.db.query(NaverBlog).filter(
                    NaverBlog.user_id == user_id,
                    NaverBlog.lead_grade == grade
                ).count()
                grade_breakdown[grade.value] = count
            stats.grade_breakdown = grade_breakdown

            self.db.commit()
            logger.debug("일일 통계 집계 완료")

        except Exception as e:
            logger.error(f"통계 집계 오류: {e}")
            self.db.rollback()


# 싱글톤 인스턴스 관리
_scheduler_instances: Dict[str, OutreachSchedulerService] = {}


def get_outreach_scheduler(db: Session, user_id: str) -> OutreachSchedulerService:
    """사용자별 스케줄러 인스턴스 반환"""
    if user_id not in _scheduler_instances:
        _scheduler_instances[user_id] = OutreachSchedulerService(db)
    else:
        _scheduler_instances[user_id].db = db
    return _scheduler_instances[user_id]
