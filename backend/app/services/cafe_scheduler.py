"""
카페 바이럴 자동화 스케줄러
주기적으로 게시글 수집, 콘텐츠 생성, 자동 등록 실행
"""

import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cafe import (
    CafeCommunity, CafeKeyword, CafePost, CafeContent,
    CafeAutoSetting, CafeStats, CafePostStatus, ContentStatus, ContentType, CafeTone
)
from app.services.cafe_crawler import cafe_crawler
from app.services.cafe_content_generator import cafe_content_generator
from app.services.cafe_poster import CafePosterService

logger = logging.getLogger(__name__)


class CafeSchedulerService:
    """카페 바이럴 자동화 스케줄러"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._is_running = False
        self._posting_running = False
        self._collection_task: Optional[asyncio.Task] = None
        self._generation_task: Optional[asyncio.Task] = None
        self._posting_task: Optional[asyncio.Task] = None
        self._user_id: Optional[str] = None

        # 기본 주기 설정 (초)
        self.collection_interval = 30 * 60  # 30분
        self.generation_interval = 10 * 60  # 10분
        self.posting_interval = 15 * 60  # 15분

    async def start(self, user_id: str, include_posting: bool = False):
        """
        스케줄러 시작

        Args:
            user_id: 사용자 ID
            include_posting: 자동 게시 포함 여부
        """
        if self._is_running:
            logger.warning("스케줄러가 이미 실행 중입니다")
            return

        self._user_id = user_id
        self._is_running = True

        # 설정 로드
        settings = await self._get_settings(user_id)
        if settings:
            self.collection_interval = settings.collect_interval_minutes * 60

        # 수집 루프 시작
        self._collection_task = asyncio.create_task(
            self._collection_loop(user_id, settings)
        )

        # 생성 루프 시작
        self._generation_task = asyncio.create_task(
            self._generation_loop(user_id, settings)
        )

        # 게시 루프 시작 (옵션)
        if include_posting:
            await self.start_posting(user_id)

        logger.info(f"카페 스케줄러 시작: user_id={user_id}, include_posting={include_posting}")

    async def stop(self):
        """스케줄러 중지"""
        self._is_running = False
        self._posting_running = False

        if self._collection_task:
            self._collection_task.cancel()
            try:
                await self._collection_task
            except asyncio.CancelledError:
                pass

        if self._generation_task:
            self._generation_task.cancel()
            try:
                await self._generation_task
            except asyncio.CancelledError:
                pass

        if self._posting_task:
            self._posting_task.cancel()
            try:
                await self._posting_task
            except asyncio.CancelledError:
                pass

        logger.info("카페 스케줄러 중지")

    async def start_posting(self, user_id: str):
        """자동 게시만 시작"""
        if self._posting_running:
            logger.warning("게시 스케줄러가 이미 실행 중입니다")
            return

        self._user_id = user_id
        self._posting_running = True

        settings = await self._get_settings(user_id)

        self._posting_task = asyncio.create_task(
            self._posting_loop(user_id, settings)
        )

        logger.info(f"카페 게시 스케줄러 시작: user_id={user_id}")

    async def stop_posting(self):
        """자동 게시만 중지"""
        self._posting_running = False

        if self._posting_task:
            self._posting_task.cancel()
            try:
                await self._posting_task
            except asyncio.CancelledError:
                pass

        logger.info("카페 게시 스케줄러 중지")

    async def start_full_automation(self, user_id: str):
        """풀 자동화 시작 (수집 + 생성 + 게시)"""
        await self.start(user_id, include_posting=True)

    async def _get_settings(self, user_id: str) -> Optional[CafeAutoSetting]:
        """사용자 설정 조회"""
        result = await self.db.execute(
            select(CafeAutoSetting).where(CafeAutoSetting.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def _collection_loop(self, user_id: str, settings: Optional[CafeAutoSetting]):
        """게시글 수집 루프"""
        while self._is_running:
            try:
                # 업무 시간 확인
                if not await self._is_working_hours(settings):
                    logger.debug("업무 시간 외 - 수집 건너뜀")
                    await asyncio.sleep(60)
                    continue

                # 일일 한도 확인
                today_stats = await self._get_today_stats(user_id)
                daily_limit = settings.posts_per_collect * 10 if settings else 200

                if today_stats and today_stats.posts_collected >= daily_limit:
                    logger.info("일일 수집 한도 도달")
                    await asyncio.sleep(60 * 60)  # 1시간 대기
                    continue

                # 수집 실행
                await self.run_collection_job(user_id, settings)

                # 다음 수집까지 대기
                await asyncio.sleep(self.collection_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"수집 루프 오류: {e}")
                await asyncio.sleep(60)

    async def _generation_loop(self, user_id: str, settings: Optional[CafeAutoSetting]):
        """콘텐츠 생성 루프"""
        while self._is_running:
            try:
                # 업무 시간 확인
                if not await self._is_working_hours(settings):
                    await asyncio.sleep(60)
                    continue

                # 일일 한도 확인
                today_stats = await self._get_today_stats(user_id)
                daily_limit = settings.daily_comment_limit if settings else 30

                if today_stats and today_stats.contents_generated >= daily_limit:
                    logger.info("일일 생성 한도 도달")
                    await asyncio.sleep(60 * 60)
                    continue

                # 생성 실행
                await self.run_generation_job(user_id, settings)

                # 다음 생성까지 대기
                await asyncio.sleep(self.generation_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"생성 루프 오류: {e}")
                await asyncio.sleep(60)

    async def _posting_loop(self, user_id: str, settings: Optional[CafeAutoSetting]):
        """
        자동 게시 루프 (15분 간격)

        승인된 콘텐츠를 다중 계정 로테이션으로 자동 게시
        """
        import random

        while self._posting_running:
            try:
                # 업무 시간 확인
                if not await self._is_working_hours(settings):
                    logger.debug("업무 시간 외 - 게시 건너뜀")
                    await asyncio.sleep(60)
                    continue

                # 일일 한도 확인
                today_stats = await self._get_today_stats(user_id)
                daily_limit = settings.daily_comment_limit if settings else 30

                total_posted = (today_stats.comments_published + today_stats.posts_published) if today_stats else 0
                if total_posted >= daily_limit:
                    logger.info("일일 게시 한도 도달")
                    await asyncio.sleep(60 * 60)  # 1시간 대기
                    continue

                # 게시 실행
                result = await self.run_posting_job(user_id, settings)

                if result.get("posted", 0) > 0:
                    # 랜덤 딜레이 추가 (10~20분)
                    delay = random.randint(600, 1200)
                    logger.info(f"다음 게시까지 {delay}초 대기")
                    await asyncio.sleep(delay)
                else:
                    # 게시할 콘텐츠 없으면 15분 대기
                    await asyncio.sleep(self.posting_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"게시 루프 오류: {e}")
                await asyncio.sleep(60)

    async def run_posting_job(
        self,
        user_id: str,
        settings: Optional[CafeAutoSetting] = None
    ) -> Dict[str, Any]:
        """
        게시 작업 실행 (다중 계정 로테이션)

        Args:
            user_id: 사용자 ID
            settings: 자동화 설정

        Returns:
            게시 결과
        """
        import random

        try:
            if not settings:
                settings = await self._get_settings(user_id)

            # 승인된 콘텐츠 조회
            contents_result = await self.db.execute(
                select(CafeContent).where(
                    and_(
                        CafeContent.user_id == user_id,
                        CafeContent.status == ContentStatus.APPROVED
                    )
                ).order_by(CafeContent.created_at.asc()).limit(5)
            )
            contents = contents_result.scalars().all()

            if not contents:
                return {"posted": 0, "failed": 0, "message": "게시할 콘텐츠가 없습니다"}

            # 포스터 서비스 초기화
            poster = CafePosterService(self.db)
            await poster.initialize()

            posted_count = 0
            failed_count = 0
            results = []

            try:
                for content in contents:
                    try:
                        if content.content_type == ContentType.COMMENT:
                            result = await poster.post_comment_rotated(content.id, user_id)
                        elif content.content_type == ContentType.POST:
                            result = await poster.create_post_rotated(content.id, user_id)
                        else:
                            continue

                        results.append(result)

                        if result.get("success"):
                            posted_count += 1
                        else:
                            failed_count += 1

                        # 랜덤 딜레이 (30~120초)
                        delay = random.randint(30, 120)
                        logger.info(f"다음 콘텐츠까지 {delay}초 대기")
                        await asyncio.sleep(delay)

                    except Exception as e:
                        logger.error(f"콘텐츠 게시 실패: {e}")
                        failed_count += 1

            finally:
                await poster.close()

            # 통계 업데이트
            stats = await self._ensure_today_stats(user_id)
            stats.comments_published += posted_count
            await self.db.commit()

            logger.info(f"게시 완료: {posted_count}개 성공, {failed_count}개 실패")
            return {
                "posted": posted_count,
                "failed": failed_count,
                "results": results,
                "message": f"{posted_count}개 게시 완료"
            }

        except Exception as e:
            logger.error(f"게시 작업 오류: {e}")
            return {"posted": 0, "failed": 0, "error": str(e)}

    async def _is_working_hours(self, settings: Optional[CafeAutoSetting]) -> bool:
        """업무 시간 확인"""
        if not settings or not settings.working_hours:
            return True

        now = datetime.now()
        current_day = now.isoweekday()  # 1=월요일, 7=일요일

        # 요일 확인
        working_days = settings.working_days or [1, 2, 3, 4, 5, 6, 7]
        if current_day not in working_days:
            return False

        # 시간 확인
        working_hours = settings.working_hours
        start_time = datetime.strptime(working_hours.get("start", "09:00"), "%H:%M").time()
        end_time = datetime.strptime(working_hours.get("end", "22:00"), "%H:%M").time()

        current_time = now.time()
        return start_time <= current_time <= end_time

    async def _get_today_stats(self, user_id: str) -> Optional[CafeStats]:
        """오늘 통계 조회"""
        today = date.today()
        result = await self.db.execute(
            select(CafeStats).where(
                and_(
                    CafeStats.user_id == user_id,
                    func.date(CafeStats.stat_date) == today
                )
            )
        )
        return result.scalar_one_or_none()

    async def _ensure_today_stats(self, user_id: str) -> CafeStats:
        """오늘 통계 생성 또는 조회"""
        stats = await self._get_today_stats(user_id)
        if not stats:
            stats = CafeStats(
                user_id=user_id,
                stat_date=datetime.now(),
                posts_collected=0,
                contents_generated=0,
                comments_published=0,
                posts_published=0,
            )
            self.db.add(stats)
            await self.db.commit()
            await self.db.refresh(stats)
        return stats

    async def run_collection_job(
        self,
        user_id: str,
        settings: Optional[CafeAutoSetting] = None
    ) -> Dict[str, Any]:
        """
        게시글 수집 작업

        Args:
            user_id: 사용자 ID
            settings: 자동화 설정

        Returns:
            수집 결과
        """
        try:
            if not settings:
                settings = await self._get_settings(user_id)

            # 활성 카페 조회
            cafes_result = await self.db.execute(
                select(CafeCommunity).where(
                    and_(
                        CafeCommunity.user_id == user_id,
                        CafeCommunity.is_active == True
                    )
                )
            )
            cafes = cafes_result.scalars().all()

            if not cafes:
                return {"collected": 0, "message": "활성화된 카페가 없습니다"}

            # 활성 키워드 조회
            keywords_result = await self.db.execute(
                select(CafeKeyword).where(
                    and_(
                        CafeKeyword.user_id == user_id,
                        CafeKeyword.is_active == True
                    )
                ).order_by(CafeKeyword.priority.desc())
            )
            keywords = keywords_result.scalars().all()

            if not keywords:
                return {"collected": 0, "message": "활성화된 키워드가 없습니다"}

            collected_count = 0
            limit_per_cafe = settings.posts_per_collect if settings else 20

            for cafe in cafes:
                for keyword in keywords:
                    try:
                        # 카페별/키워드별 검색
                        posts = await cafe_crawler.search_cafe_posts(
                            cafe_id=cafe.cafe_id,
                            keyword=keyword.keyword,
                            limit=limit_per_cafe
                        )

                        for post_data in posts:
                            # 중복 체크
                            existing = await self.db.execute(
                                select(CafePost).where(
                                    CafePost.naver_post_id == post_data.get("naver_post_id")
                                )
                            )
                            if existing.scalar_one_or_none():
                                continue

                            # 게시글 저장
                            new_post = CafePost(
                                user_id=user_id,
                                cafe_id=cafe.id,
                                naver_post_id=post_data.get("naver_post_id"),
                                article_id=post_data.get("article_id"),
                                title=post_data.get("title"),
                                content=post_data.get("content_preview", ""),
                                url=post_data.get("url"),
                                author_name=post_data.get("author_name"),
                                board_name=post_data.get("board_name"),
                                view_count=post_data.get("view_count", 0),
                                comment_count=post_data.get("comment_count", 0),
                                like_count=post_data.get("like_count", 0),
                                posted_at=post_data.get("posted_at"),
                                matched_keywords=[keyword.keyword],
                                status=CafePostStatus.NEW,
                            )
                            self.db.add(new_post)
                            collected_count += 1

                            # 키워드 통계 업데이트
                            keyword.matched_count += 1

                        await asyncio.sleep(2)  # 요청 간 딜레이

                    except Exception as e:
                        logger.error(f"카페 수집 오류: cafe={cafe.cafe_id}, keyword={keyword.keyword}, error={e}")
                        continue

            await self.db.commit()

            # 통계 업데이트
            stats = await self._ensure_today_stats(user_id)
            stats.posts_collected += collected_count
            await self.db.commit()

            logger.info(f"수집 완료: {collected_count}개 게시글")
            return {"collected": collected_count, "message": f"{collected_count}개 게시글 수집 완료"}

        except Exception as e:
            logger.error(f"수집 작업 오류: {e}")
            return {"collected": 0, "error": str(e)}

    async def run_generation_job(
        self,
        user_id: str,
        settings: Optional[CafeAutoSetting] = None
    ) -> Dict[str, Any]:
        """
        콘텐츠 생성 작업

        Args:
            user_id: 사용자 ID
            settings: 자동화 설정

        Returns:
            생성 결과
        """
        try:
            if not settings:
                settings = await self._get_settings(user_id)

            # 분석되지 않은 게시글 조회
            posts_result = await self.db.execute(
                select(CafePost).where(
                    and_(
                        CafePost.user_id == user_id,
                        CafePost.status == CafePostStatus.NEW
                    )
                ).order_by(CafePost.collected_at.desc()).limit(10)
            )
            posts = posts_result.scalars().all()

            if not posts:
                return {"generated": 0, "message": "생성할 게시글이 없습니다"}

            generated_count = 0
            min_relevance = settings.min_relevance_score if settings else 60
            auto_approve_threshold = settings.auto_approve_threshold if settings else 85
            default_tone = settings.default_tone if settings else CafeTone.FRIENDLY
            include_emoji = settings.include_emoji if settings else True

            for post in posts:
                try:
                    # 카페 정보 조회
                    cafe_result = await self.db.execute(
                        select(CafeCommunity).where(CafeCommunity.id == post.cafe_id)
                    )
                    cafe = cafe_result.scalar_one_or_none()

                    if not cafe or not cafe.commenting_enabled:
                        continue

                    # 게시글 분석
                    analysis = await cafe_content_generator.analyze_post(
                        title=post.title,
                        content=post.content or "",
                        keywords=post.matched_keywords or []
                    )

                    # 관련성 점수 업데이트
                    post.relevance_score = analysis.get("relevance_score", 50)
                    post.sentiment = analysis.get("sentiment", "neutral")
                    post.topic_tags = analysis.get("topic_tags", [])
                    post.status = CafePostStatus.ANALYZED

                    # 관련성 점수 체크
                    if post.relevance_score < min_relevance:
                        post.status = CafePostStatus.SKIPPED
                        post.skip_reason = f"관련성 점수 미달 ({post.relevance_score})"
                        continue

                    # 댓글 추천 여부 체크
                    if not analysis.get("should_comment", False):
                        post.status = CafePostStatus.SKIPPED
                        post.skip_reason = "댓글 부적합"
                        continue

                    # 홍보 포함 여부 결정
                    include_promotion = False
                    promotion_info = None

                    if settings and settings.promotion_frequency > 0:
                        import random
                        if random.random() < settings.promotion_frequency:
                            include_promotion = True
                            promotion_info = {
                                "blog_link": settings.default_blog_link,
                                "place_link": settings.default_place_link,
                                "text": ""
                            }

                    # 댓글 생성
                    comment_result = await cafe_content_generator.generate_comment(
                        post_title=post.title,
                        post_content=post.content or "",
                        cafe_category=cafe.category,
                        tone=default_tone,
                        include_promotion=include_promotion,
                        promotion_info=promotion_info,
                        max_length=settings.max_content_length if settings else 200,
                        include_emoji=include_emoji
                    )

                    # 콘텐츠 저장
                    new_content = CafeContent(
                        user_id=user_id,
                        target_post_id=post.id,
                        content_type=ContentType.COMMENT,
                        content=comment_result.get("content"),
                        tone=default_tone,
                        quality_score=comment_result.get("quality_score"),
                        naturalness_score=comment_result.get("naturalness_score"),
                        relevance_score=comment_result.get("relevance_score"),
                        include_promotion=include_promotion,
                        promotion_text=comment_result.get("promotion_text"),
                        blog_link=comment_result.get("blog_link"),
                        place_link=comment_result.get("place_link"),
                        status=ContentStatus.DRAFT,
                    )

                    # 자동 승인 체크
                    if new_content.quality_score and new_content.quality_score >= auto_approve_threshold:
                        new_content.status = ContentStatus.APPROVED

                    self.db.add(new_content)
                    generated_count += 1

                    await asyncio.sleep(1)  # API 호출 간 딜레이

                except Exception as e:
                    logger.error(f"콘텐츠 생성 오류: post_id={post.id}, error={e}")
                    continue

            await self.db.commit()

            # 통계 업데이트
            stats = await self._ensure_today_stats(user_id)
            stats.contents_generated += generated_count
            await self.db.commit()

            logger.info(f"생성 완료: {generated_count}개 콘텐츠")
            return {"generated": generated_count, "message": f"{generated_count}개 콘텐츠 생성 완료"}

        except Exception as e:
            logger.error(f"생성 작업 오류: {e}")
            return {"generated": 0, "error": str(e)}

    async def get_status(self, user_id: str) -> Dict[str, Any]:
        """스케줄러 상태 조회"""
        settings = await self._get_settings(user_id)
        today_stats = await self._get_today_stats(user_id)

        # 대기 중인 콘텐츠 수
        pending_result = await self.db.execute(
            select(func.count(CafeContent.id)).where(
                and_(
                    CafeContent.user_id == user_id,
                    CafeContent.status.in_([ContentStatus.DRAFT, ContentStatus.APPROVED])
                )
            )
        )
        pending_count = pending_result.scalar() or 0

        # 새 게시글 수
        new_posts_result = await self.db.execute(
            select(func.count(CafePost.id)).where(
                and_(
                    CafePost.user_id == user_id,
                    CafePost.status == CafePostStatus.NEW
                )
            )
        )
        new_posts_count = new_posts_result.scalar() or 0

        # 승인된 콘텐츠 수 (게시 대기)
        approved_result = await self.db.execute(
            select(func.count(CafeContent.id)).where(
                and_(
                    CafeContent.user_id == user_id,
                    CafeContent.status == ContentStatus.APPROVED
                )
            )
        )
        approved_count = approved_result.scalar() or 0

        return {
            "is_running": self._is_running and self._user_id == user_id,
            "is_posting_running": self._posting_running and self._user_id == user_id,
            "is_enabled": settings.is_enabled if settings else False,
            "is_working_hours": await self._is_working_hours(settings),
            "today": {
                "collected": today_stats.posts_collected if today_stats else 0,
                "generated": today_stats.contents_generated if today_stats else 0,
                "posted": (today_stats.comments_published + today_stats.posts_published) if today_stats else 0,
                "collect_limit": settings.posts_per_collect * 10 if settings else 200,
                "comment_limit": settings.daily_comment_limit if settings else 30,
            },
            "pending": {
                "new_posts": new_posts_count,
                "contents": pending_count,
                "approved": approved_count,
            }
        }


# 전역 스케줄러 인스턴스 관리
_schedulers: Dict[str, CafeSchedulerService] = {}


async def get_cafe_scheduler(db: AsyncSession, user_id: str) -> CafeSchedulerService:
    """사용자별 스케줄러 인스턴스 반환"""
    if user_id not in _schedulers:
        _schedulers[user_id] = CafeSchedulerService(db)
    return _schedulers[user_id]
