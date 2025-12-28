"""
네이버 지식인 답변 자동 등록 서비스
Playwright 기반 브라우저 자동화
"""

import asyncio
import logging
import os
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import (
    KnowledgeQuestion, KnowledgeAnswer,
    QuestionStatus, AnswerStatus
)

logger = logging.getLogger(__name__)

# Playwright는 선택적 의존성
try:
    from playwright.async_api import async_playwright, Browser, Page, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright가 설치되지 않았습니다. pip install playwright && playwright install chromium")


class NaverLoginError(Exception):
    """네이버 로그인 실패"""
    pass


class AnswerPostError(Exception):
    """답변 등록 실패"""
    pass


class KinPosterService:
    """지식인 답변 자동 등록 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._logged_in = False

        # 설정
        self.headless = True  # 프로덕션에서는 True
        self.timeout = 30000  # 30초
        self.user_data_dir = Path("./playwright_data")

    async def initialize(self):
        """브라우저 초기화"""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright가 설치되지 않았습니다")

        if self._browser:
            return

        playwright = await async_playwright().start()

        # 영구 컨텍스트 사용 (쿠키 유지)
        self.user_data_dir.mkdir(exist_ok=True)

        self._browser = await playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ]
        )

        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ko-KR",
        )

        self._page = await self._context.new_page()

        # 자동화 감지 방지
        await self._page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        logger.info("브라우저 초기화 완료")

    async def close(self):
        """브라우저 종료"""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()

        self._browser = None
        self._context = None
        self._page = None
        self._logged_in = False

        logger.info("브라우저 종료됨")

    async def login(self, username: str, password: str) -> bool:
        """
        네이버 로그인

        Args:
            username: 네이버 아이디
            password: 비밀번호

        Returns:
            로그인 성공 여부
        """
        if not self._page:
            await self.initialize()

        try:
            logger.info("네이버 로그인 시도...")

            # 로그인 페이지로 이동
            await self._page.goto("https://nid.naver.com/nidlogin.login", wait_until="networkidle")

            # 이미 로그인되어 있는지 확인
            if await self._check_logged_in():
                logger.info("이미 로그인되어 있습니다")
                self._logged_in = True
                return True

            # 아이디 입력
            await self._page.fill("#id", username)
            await asyncio.sleep(0.5)

            # 비밀번호 입력
            await self._page.fill("#pw", password)
            await asyncio.sleep(0.5)

            # 로그인 버튼 클릭
            await self._page.click("#log\\.login")

            # 로그인 결과 대기
            await asyncio.sleep(3)

            # 캡차 또는 2차 인증 확인
            if await self._page.query_selector("#captcha"):
                raise NaverLoginError("캡차가 필요합니다. 수동으로 로그인하세요.")

            # 2차 인증 확인
            if "2차 인증" in await self._page.content():
                raise NaverLoginError("2차 인증이 필요합니다.")

            # 로그인 성공 확인
            if await self._check_logged_in():
                self._logged_in = True
                logger.info("네이버 로그인 성공")
                return True

            # 로그인 실패 메시지 확인
            error_elem = await self._page.query_selector(".error_message")
            if error_elem:
                error_text = await error_elem.inner_text()
                raise NaverLoginError(f"로그인 실패: {error_text}")

            raise NaverLoginError("로그인 실패: 알 수 없는 오류")

        except NaverLoginError:
            raise
        except Exception as e:
            logger.error(f"로그인 중 오류: {e}")
            raise NaverLoginError(f"로그인 중 오류: {e}")

    async def _check_logged_in(self) -> bool:
        """로그인 상태 확인"""
        try:
            # 네이버 메인으로 이동
            await self._page.goto("https://www.naver.com", wait_until="domcontentloaded")
            await asyncio.sleep(1)

            # 로그인 상태 확인 (로그아웃 버튼 또는 프로필 존재)
            logged_in = await self._page.query_selector(".MyView-module__link_login___HpHMW") is None
            return logged_in

        except:
            return False

    async def post_answer(
        self,
        answer_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        답변 등록

        Args:
            answer_id: 답변 ID
            user_id: 사용자 ID

        Returns:
            등록 결과
        """
        if not self._logged_in:
            raise AnswerPostError("로그인이 필요합니다")

        # 답변 조회
        result = await self.db.execute(
            select(KnowledgeAnswer).where(
                and_(
                    KnowledgeAnswer.id == answer_id,
                    KnowledgeAnswer.user_id == user_id,
                    KnowledgeAnswer.status == AnswerStatus.APPROVED
                )
            )
        )
        answer = result.scalar_one_or_none()

        if not answer:
            raise AnswerPostError("승인된 답변을 찾을 수 없습니다")

        # 질문 조회
        question_result = await self.db.execute(
            select(KnowledgeQuestion).where(
                KnowledgeQuestion.id == answer.question_id
            )
        )
        question = question_result.scalar_one_or_none()

        if not question or not question.url:
            raise AnswerPostError("질문 URL을 찾을 수 없습니다")

        try:
            logger.info(f"답변 등록 시작: question_id={question.naver_question_id}")

            # 질문 페이지로 이동
            await self._page.goto(question.url, wait_until="networkidle")
            await asyncio.sleep(2)

            # 답변 가능 여부 확인
            if await self._page.query_selector(".end_poll"):
                raise AnswerPostError("마감된 질문입니다")

            if await self._page.query_selector(".ico_best"):
                raise AnswerPostError("이미 채택된 질문입니다")

            # 답변 작성 버튼 클릭
            answer_btn = await self._page.query_selector(".btn_answer") or \
                         await self._page.query_selector("[class*='answer_write']")

            if not answer_btn:
                raise AnswerPostError("답변 작성 버튼을 찾을 수 없습니다")

            await answer_btn.click()
            await asyncio.sleep(2)

            # 답변 내용 입력
            content = answer.final_content or answer.content

            # 홍보 문구 추가
            if answer.promotion_text:
                content += f"\n\n{answer.promotion_text}"

            # 에디터에 내용 입력
            editor = await self._page.query_selector(".se-content") or \
                     await self._page.query_selector("[contenteditable='true']") or \
                     await self._page.query_selector("textarea")

            if not editor:
                raise AnswerPostError("답변 입력창을 찾을 수 없습니다")

            # 내용 입력
            await editor.click()
            await asyncio.sleep(0.5)
            await self._page.keyboard.type(content, delay=10)

            await asyncio.sleep(1)

            # 등록 버튼 클릭
            submit_btn = await self._page.query_selector(".btn_register") or \
                         await self._page.query_selector("[class*='submit']") or \
                         await self._page.query_selector("button[type='submit']")

            if not submit_btn:
                raise AnswerPostError("등록 버튼을 찾을 수 없습니다")

            await submit_btn.click()

            # 등록 완료 대기
            await asyncio.sleep(3)

            # 성공 확인
            current_url = self._page.url

            # 답변 상태 업데이트
            answer.status = AnswerStatus.POSTED
            answer.posted_at = datetime.utcnow()
            answer.naver_answer_url = current_url

            # 질문 상태 업데이트
            question.status = QuestionStatus.ANSWERED

            await self.db.commit()

            logger.info(f"답변 등록 성공: {current_url}")

            return {
                "success": True,
                "answer_id": answer_id,
                "question_id": question.naver_question_id,
                "url": current_url,
                "message": "답변이 성공적으로 등록되었습니다"
            }

        except AnswerPostError:
            raise
        except Exception as e:
            logger.error(f"답변 등록 중 오류: {e}")
            raise AnswerPostError(f"답변 등록 중 오류: {e}")

    async def post_multiple_answers(
        self,
        user_id: str,
        limit: int = 5,
        delay_between: int = 30
    ) -> Dict[str, Any]:
        """
        여러 답변 일괄 등록

        Args:
            user_id: 사용자 ID
            limit: 최대 등록 개수
            delay_between: 답변 간 대기 시간 (초)

        Returns:
            등록 결과
        """
        if not self._logged_in:
            raise AnswerPostError("로그인이 필요합니다")

        # 승인된 답변 조회
        result = await self.db.execute(
            select(KnowledgeAnswer).where(
                and_(
                    KnowledgeAnswer.user_id == user_id,
                    KnowledgeAnswer.status == AnswerStatus.APPROVED
                )
            ).limit(limit)
        )
        answers = result.scalars().all()

        if not answers:
            return {
                "success": True,
                "posted": 0,
                "failed": 0,
                "message": "등록할 답변이 없습니다"
            }

        posted_count = 0
        failed_count = 0
        results = []

        for answer in answers:
            try:
                post_result = await self.post_answer(answer.id, user_id)
                results.append(post_result)
                posted_count += 1

                # 다음 답변까지 대기 (스팸 방지)
                if posted_count < len(answers):
                    logger.info(f"{delay_between}초 대기...")
                    await asyncio.sleep(delay_between)

            except Exception as e:
                logger.error(f"답변 등록 실패: {e}")
                failed_count += 1
                results.append({
                    "success": False,
                    "answer_id": answer.id,
                    "error": str(e)
                })

        return {
            "success": True,
            "posted": posted_count,
            "failed": failed_count,
            "results": results,
            "message": f"{posted_count}개 등록 완료, {failed_count}개 실패"
        }

    async def save_cookies(self, filepath: str = "naver_cookies.json"):
        """쿠키 저장"""
        if self._context:
            cookies = await self._context.cookies()
            import json
            with open(filepath, "w") as f:
                json.dump(cookies, f)
            logger.info(f"쿠키 저장됨: {filepath}")

    async def load_cookies(self, filepath: str = "naver_cookies.json"):
        """쿠키 로드"""
        if self._context and os.path.exists(filepath):
            import json
            with open(filepath, "r") as f:
                cookies = json.load(f)
            await self._context.add_cookies(cookies)
            logger.info(f"쿠키 로드됨: {filepath}")

            # 로그인 상태 확인
            if await self._check_logged_in():
                self._logged_in = True
                logger.info("쿠키로 로그인 복원됨")
                return True
        return False


class KinPosterManager:
    """사용자별 포스터 관리"""

    def __init__(self):
        self._posters: Dict[str, KinPosterService] = {}

    async def get_poster(self, db: AsyncSession, user_id: str) -> KinPosterService:
        """사용자별 포스터 인스턴스 반환"""
        if user_id not in self._posters:
            self._posters[user_id] = KinPosterService(db)
        return self._posters[user_id]

    async def close_all(self):
        """모든 포스터 종료"""
        for poster in self._posters.values():
            await poster.close()
        self._posters.clear()


# 전역 관리자
poster_manager = KinPosterManager()
