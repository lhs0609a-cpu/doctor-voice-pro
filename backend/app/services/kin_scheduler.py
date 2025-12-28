"""
네이버 지식인 자동화 스케줄러
주기적 질문 수집, 답변 생성, 답변 등록 작업 관리
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import (
    KnowledgeKeyword, KnowledgeQuestion, KnowledgeAnswer,
    AutoAnswerSetting, KnowledgeStats,
    QuestionStatus, AnswerStatus, AnswerTone
)
from app.services.kin_crawler import kin_crawler

logger = logging.getLogger(__name__)


class JobType(str, Enum):
    COLLECT = "collect"         # 질문 수집
    GENERATE = "generate"       # 답변 생성
    POST = "post"               # 답변 등록
    CHECK_CHOSEN = "check"      # 채택 확인


class KinSchedulerService:
    """지식인 자동화 스케줄러"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._running = False
        self._tasks: Dict[str, asyncio.Task] = {}

    async def start(self, user_id: str):
        """스케줄러 시작"""
        if self._running:
            logger.warning("스케줄러가 이미 실행 중입니다")
            return

        settings = await self._get_settings(user_id)
        if not settings or not settings.is_enabled:
            logger.info("자동화가 비활성화되어 있습니다")
            return

        self._running = True
        logger.info(f"지식인 스케줄러 시작: user_id={user_id}")

        # 백그라운드 태스크 시작
        if settings.auto_collect:
            self._tasks["collect"] = asyncio.create_task(
                self._collection_loop(user_id, settings)
            )

        if settings.auto_generate:
            self._tasks["generate"] = asyncio.create_task(
                self._generation_loop(user_id, settings)
            )

    async def stop(self):
        """스케줄러 중지"""
        self._running = False
        for name, task in self._tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info(f"태스크 중지됨: {name}")
        self._tasks.clear()

    async def _get_settings(self, user_id: str) -> Optional[AutoAnswerSetting]:
        """사용자 설정 조회"""
        result = await self.db.execute(
            select(AutoAnswerSetting).where(AutoAnswerSetting.user_id == user_id)
        )
        return result.scalar_one_or_none()

    def _is_working_hours(self, settings: AutoAnswerSetting) -> bool:
        """업무 시간 체크"""
        if not settings.working_hours:
            return True

        now = datetime.now()
        current_day = now.weekday() + 1  # 1=월요일

        # 요일 체크
        if settings.working_days and current_day not in settings.working_days:
            return False

        # 시간 체크
        start_time = settings.working_hours.get("start", "00:00")
        end_time = settings.working_hours.get("end", "23:59")

        current_time = now.strftime("%H:%M")
        return start_time <= current_time <= end_time

    # ==================== 질문 수집 ====================

    async def _collection_loop(self, user_id: str, settings: AutoAnswerSetting):
        """질문 수집 루프"""
        interval = 30 * 60  # 30분 간격

        while self._running:
            try:
                if self._is_working_hours(settings):
                    await self.run_collection_job(user_id, settings)

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"수집 루프 오류: {e}")
                await asyncio.sleep(60)

    async def run_collection_job(
        self,
        user_id: str,
        settings: Optional[AutoAnswerSetting] = None
    ) -> Dict[str, Any]:
        """질문 수집 작업 실행"""
        if not settings:
            settings = await self._get_settings(user_id)

        logger.info(f"질문 수집 시작: user_id={user_id}")

        # 오늘 수집량 체크
        today_count = await self._get_today_collection_count(user_id)
        daily_limit = settings.daily_collect_limit if settings else 100

        if today_count >= daily_limit:
            return {
                "success": False,
                "message": f"일일 수집 한도 도달 ({today_count}/{daily_limit})"
            }

        # 활성 키워드 조회
        keywords_result = await self.db.execute(
            select(KnowledgeKeyword).where(
                and_(
                    KnowledgeKeyword.user_id == user_id,
                    KnowledgeKeyword.is_active == True
                )
            ).order_by(KnowledgeKeyword.priority.desc())
        )
        keywords = [kw.keyword for kw in keywords_result.scalars().all()]

        if not keywords:
            return {"success": False, "message": "활성 키워드 없음"}

        # 제외 키워드 필터
        exclude_keywords = settings.exclude_keywords if settings else []

        # 크롤링 실행
        remaining_limit = daily_limit - today_count
        collected_questions = await kin_crawler.search_and_collect(
            keywords=keywords,
            total_limit=min(remaining_limit, 20),  # 한 번에 최대 20개
            filter_answerable=True,
            min_reward_points=settings.min_reward_points if settings else 0,
        )

        # 제외 키워드 필터링
        if exclude_keywords:
            collected_questions = [
                q for q in collected_questions
                if not any(ek in q.get("title", "") or ek in q.get("content", "")
                          for ek in exclude_keywords)
            ]

        # DB 저장
        saved_count = 0
        for q_data in collected_questions:
            try:
                # 중복 체크
                existing = await self.db.execute(
                    select(KnowledgeQuestion).where(
                        KnowledgeQuestion.naver_question_id == q_data["naver_question_id"]
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                # 관련성 점수 계산
                relevance_score = self._calculate_relevance(q_data, keywords)

                question = KnowledgeQuestion(
                    user_id=user_id,
                    naver_question_id=q_data["naver_question_id"],
                    title=q_data["title"],
                    content=q_data.get("content", ""),
                    category=q_data.get("category"),
                    url=q_data.get("url"),
                    author_name=q_data.get("author_name"),
                    view_count=q_data.get("view_count", 0),
                    answer_count=q_data.get("answer_count", 0),
                    reward_points=q_data.get("reward_points", 0),
                    matched_keywords=[q_data.get("matched_keyword")] if q_data.get("matched_keyword") else [],
                    relevance_score=relevance_score,
                    collected_at=datetime.utcnow()
                )
                self.db.add(question)
                saved_count += 1

            except Exception as e:
                logger.error(f"질문 저장 오류: {e}")

        await self.db.commit()

        # 통계 업데이트
        await self._update_stats(user_id, questions_collected=saved_count)

        logger.info(f"질문 수집 완료: {saved_count}개")
        return {
            "success": True,
            "collected": saved_count,
            "message": f"{saved_count}개 질문 수집 완료"
        }

    def _calculate_relevance(self, question: Dict, keywords: List[str]) -> float:
        """관련성 점수 계산"""
        title = question.get("title", "").lower()
        content = question.get("content", "").lower()
        full_text = f"{title} {content}"

        matched = sum(1 for kw in keywords if kw.lower() in full_text)
        base_score = min(100, matched * 25 + 25)

        # 내공 보너스
        points = question.get("reward_points", 0)
        if points >= 100:
            base_score += 10
        elif points >= 50:
            base_score += 5

        return min(100, base_score)

    async def _get_today_collection_count(self, user_id: str) -> int:
        """오늘 수집한 질문 수"""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await self.db.execute(
            select(KnowledgeQuestion).where(
                and_(
                    KnowledgeQuestion.user_id == user_id,
                    KnowledgeQuestion.collected_at >= today_start
                )
            )
        )
        return len(result.scalars().all())

    # ==================== 답변 생성 ====================

    async def _generation_loop(self, user_id: str, settings: AutoAnswerSetting):
        """답변 생성 루프"""
        interval = 10 * 60  # 10분 간격

        while self._running:
            try:
                if self._is_working_hours(settings):
                    await self.run_generation_job(user_id, settings)

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"생성 루프 오류: {e}")
                await asyncio.sleep(60)

    async def run_generation_job(
        self,
        user_id: str,
        settings: Optional[AutoAnswerSetting] = None
    ) -> Dict[str, Any]:
        """답변 생성 작업 실행"""
        if not settings:
            settings = await self._get_settings(user_id)

        logger.info(f"답변 생성 시작: user_id={user_id}")

        # 오늘 생성량 체크
        today_count = await self._get_today_answer_count(user_id)
        daily_limit = settings.daily_answer_limit if settings else 20

        if today_count >= daily_limit:
            return {
                "success": False,
                "message": f"일일 답변 생성 한도 도달 ({today_count}/{daily_limit})"
            }

        # 미처리 질문 조회 (관련성 높은 순)
        min_relevance = settings.min_relevance_score if settings else 70
        questions_result = await self.db.execute(
            select(KnowledgeQuestion).where(
                and_(
                    KnowledgeQuestion.user_id == user_id,
                    KnowledgeQuestion.status == QuestionStatus.NEW,
                    KnowledgeQuestion.relevance_score >= min_relevance
                )
            ).order_by(
                KnowledgeQuestion.relevance_score.desc(),
                KnowledgeQuestion.reward_points.desc()
            ).limit(5)
        )
        questions = questions_result.scalars().all()

        if not questions:
            return {"success": True, "generated": 0, "message": "처리할 질문 없음"}

        generated_count = 0

        for question in questions:
            if today_count + generated_count >= daily_limit:
                break

            try:
                # 답변 생성 (knowledge_service 사용)
                from app.services.knowledge_service import KnowledgeService
                knowledge_service = KnowledgeService(self.db)

                answer = await knowledge_service.generate_answer(
                    question_id=question.id,
                    user_id=user_id,
                    tone=settings.default_tone if settings else AnswerTone.PROFESSIONAL,
                    include_promotion=settings.default_include_promotion if settings else True,
                    blog_link=settings.default_blog_link if settings else None,
                    place_link=settings.default_place_link if settings else None,
                )

                if answer:
                    generated_count += 1

                    # 자동 승인 체크
                    if settings and settings.auto_approve:
                        if answer.quality_score and answer.quality_score >= settings.auto_approve_threshold:
                            answer.status = AnswerStatus.APPROVED
                            await self.db.commit()

            except Exception as e:
                logger.error(f"답변 생성 오류: {e}")

        await self.db.commit()

        # 통계 업데이트
        await self._update_stats(user_id, answers_generated=generated_count)

        logger.info(f"답변 생성 완료: {generated_count}개")
        return {
            "success": True,
            "generated": generated_count,
            "message": f"{generated_count}개 답변 생성 완료"
        }

    async def _get_today_answer_count(self, user_id: str) -> int:
        """오늘 생성한 답변 수"""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await self.db.execute(
            select(KnowledgeAnswer).where(
                and_(
                    KnowledgeAnswer.user_id == user_id,
                    KnowledgeAnswer.created_at >= today_start
                )
            )
        )
        return len(result.scalars().all())

    # ==================== 채택 확인 ====================

    async def run_check_chosen_job(self, user_id: str) -> Dict[str, Any]:
        """채택 확인 작업"""
        logger.info(f"채택 확인 시작: user_id={user_id}")

        # 등록된 답변 조회
        result = await self.db.execute(
            select(KnowledgeAnswer).where(
                and_(
                    KnowledgeAnswer.user_id == user_id,
                    KnowledgeAnswer.status == AnswerStatus.POSTED,
                    KnowledgeAnswer.is_chosen == False
                )
            ).limit(20)
        )
        answers = result.scalars().all()

        if not answers:
            return {"success": True, "checked": 0, "chosen": 0}

        chosen_count = 0

        for answer in answers:
            try:
                # 질문 페이지에서 채택 여부 확인
                question_result = await self.db.execute(
                    select(KnowledgeQuestion).where(
                        KnowledgeQuestion.id == answer.question_id
                    )
                )
                question = question_result.scalar_one_or_none()

                if question and question.url:
                    check_result = await kin_crawler.check_answerable(
                        question.naver_question_id,
                        question.url
                    )

                    if not check_result.get("answerable") and "채택" in check_result.get("reason", ""):
                        # 채택됨 (더 정확한 확인은 상세 페이지 파싱 필요)
                        # 여기서는 간단히 처리
                        pass

            except Exception as e:
                logger.error(f"채택 확인 오류: {e}")

        await self.db.commit()

        return {
            "success": True,
            "checked": len(answers),
            "chosen": chosen_count
        }

    # ==================== 통계 ====================

    async def _update_stats(
        self,
        user_id: str,
        questions_collected: int = 0,
        answers_generated: int = 0,
        answers_posted: int = 0,
        answers_chosen: int = 0
    ):
        """일별 통계 업데이트"""
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        result = await self.db.execute(
            select(KnowledgeStats).where(
                and_(
                    KnowledgeStats.user_id == user_id,
                    KnowledgeStats.stat_date == today
                )
            )
        )
        stats = result.scalar_one_or_none()

        if not stats:
            stats = KnowledgeStats(
                user_id=user_id,
                stat_date=today
            )
            self.db.add(stats)

        stats.questions_collected += questions_collected
        stats.answers_generated += answers_generated
        stats.answers_posted += answers_posted
        stats.answers_chosen += answers_chosen

        await self.db.commit()

    async def get_job_status(self, user_id: str) -> Dict[str, Any]:
        """작업 상태 조회"""
        settings = await self._get_settings(user_id)

        today_collected = await self._get_today_collection_count(user_id)
        today_generated = await self._get_today_answer_count(user_id)

        # 대기 중인 질문 수
        pending_result = await self.db.execute(
            select(KnowledgeQuestion).where(
                and_(
                    KnowledgeQuestion.user_id == user_id,
                    KnowledgeQuestion.status == QuestionStatus.NEW
                )
            )
        )
        pending_questions = len(pending_result.scalars().all())

        # 승인 대기 답변 수
        draft_result = await self.db.execute(
            select(KnowledgeAnswer).where(
                and_(
                    KnowledgeAnswer.user_id == user_id,
                    KnowledgeAnswer.status == AnswerStatus.DRAFT
                )
            )
        )
        draft_answers = len(draft_result.scalars().all())

        return {
            "is_running": self._running,
            "is_enabled": settings.is_enabled if settings else False,
            "is_working_hours": self._is_working_hours(settings) if settings else True,
            "today": {
                "collected": today_collected,
                "generated": today_generated,
                "collect_limit": settings.daily_collect_limit if settings else 100,
                "answer_limit": settings.daily_answer_limit if settings else 20,
            },
            "pending": {
                "questions": pending_questions,
                "draft_answers": draft_answers,
            },
            "tasks": list(self._tasks.keys())
        }


# 사용자별 스케줄러 인스턴스 관리
_schedulers: Dict[str, KinSchedulerService] = {}


async def get_scheduler(db: AsyncSession, user_id: str) -> KinSchedulerService:
    """사용자별 스케줄러 인스턴스 반환"""
    if user_id not in _schedulers:
        _schedulers[user_id] = KinSchedulerService(db)
    return _schedulers[user_id]
