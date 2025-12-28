"""
네이버 카페 자동 등록 서비스
Playwright 기반 브라우저 자동화
"""

import asyncio
import logging
import os
import random
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cafe import (
    CafeContent, CafePost, CafeCommunity,
    ContentType, ContentStatus, CafePostStatus
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


class CafePostError(Exception):
    """카페 등록 실패"""
    pass


class CafePosterService:
    """카페 자동 등록 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._logged_in = False

        # 설정
        self.headless = True  # 프로덕션에서는 True
        self.timeout = 30000  # 30초
        self.user_data_dir = Path("./playwright_cafe_data")

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

    async def post_comment(
        self,
        content_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        댓글 등록

        Args:
            content_id: 콘텐츠 ID
            user_id: 사용자 ID

        Returns:
            등록 결과
        """
        if not self._logged_in:
            raise CafePostError("로그인이 필요합니다")

        # 콘텐츠 조회
        result = await self.db.execute(
            select(CafeContent).where(
                and_(
                    CafeContent.id == content_id,
                    CafeContent.user_id == user_id,
                    CafeContent.status == ContentStatus.APPROVED,
                    CafeContent.content_type == ContentType.COMMENT
                )
            )
        )
        content = result.scalar_one_or_none()

        if not content:
            raise CafePostError("승인된 댓글을 찾을 수 없습니다")

        # 대상 게시글 조회
        post_result = await self.db.execute(
            select(CafePost).where(CafePost.id == content.target_post_id)
        )
        post = post_result.scalar_one_or_none()

        if not post or not post.url:
            raise CafePostError("대상 게시글 URL을 찾을 수 없습니다")

        try:
            logger.info(f"댓글 등록 시작: post_url={post.url}")

            # 게시글 페이지로 이동
            await self._page.goto(post.url, wait_until="networkidle")
            await asyncio.sleep(2)

            # 랜덤 스크롤 (인간적인 행동)
            await self._human_scroll()

            # 댓글 입력창 찾기
            comment_input = await self._page.query_selector("textarea.comment_inbox") or \
                           await self._page.query_selector("[placeholder*='댓글']") or \
                           await self._page.query_selector(".CommentWriter textarea") or \
                           await self._page.query_selector(".comment_write textarea")

            if not comment_input:
                # iframe 내부에 있을 수 있음
                frames = self._page.frames
                for frame in frames:
                    comment_input = await frame.query_selector("textarea.comment_inbox") or \
                                   await frame.query_selector("[placeholder*='댓글']")
                    if comment_input:
                        break

            if not comment_input:
                raise CafePostError("댓글 입력창을 찾을 수 없습니다")

            # 입력창 클릭
            await comment_input.click()
            await asyncio.sleep(0.5)

            # 내용 입력 (인간적인 타이핑 속도)
            await self._human_type(content.content)

            await asyncio.sleep(1)

            # 등록 버튼 클릭
            submit_btn = await self._page.query_selector(".btn_register") or \
                        await self._page.query_selector("button[type='submit']") or \
                        await self._page.query_selector(".comment_write .btn") or \
                        await self._page.query_selector("[class*='submit']")

            if not submit_btn:
                raise CafePostError("등록 버튼을 찾을 수 없습니다")

            await submit_btn.click()

            # 등록 완료 대기
            await asyncio.sleep(3)

            # 상태 업데이트
            content.status = ContentStatus.POSTED
            content.posted_at = datetime.utcnow()
            content.posted_url = self._page.url

            # 대상 게시글 상태 업데이트
            post.status = CafePostStatus.COMMENTED

            await self.db.commit()

            logger.info(f"댓글 등록 성공: {post.url}")

            return {
                "success": True,
                "content_id": content_id,
                "post_url": post.url,
                "message": "댓글이 성공적으로 등록되었습니다"
            }

        except CafePostError:
            raise
        except Exception as e:
            logger.error(f"댓글 등록 중 오류: {e}")
            content.status = ContentStatus.FAILED
            content.error_message = str(e)
            await self.db.commit()
            raise CafePostError(f"댓글 등록 중 오류: {e}")

    async def create_post(
        self,
        content_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        새 글 작성

        Args:
            content_id: 콘텐츠 ID
            user_id: 사용자 ID

        Returns:
            등록 결과
        """
        if not self._logged_in:
            raise CafePostError("로그인이 필요합니다")

        # 콘텐츠 조회
        result = await self.db.execute(
            select(CafeContent).where(
                and_(
                    CafeContent.id == content_id,
                    CafeContent.user_id == user_id,
                    CafeContent.status == ContentStatus.APPROVED,
                    CafeContent.content_type == ContentType.POST
                )
            )
        )
        content = result.scalar_one_or_none()

        if not content:
            raise CafePostError("승인된 글을 찾을 수 없습니다")

        # 대상 카페 조회
        cafe_result = await self.db.execute(
            select(CafeCommunity).where(CafeCommunity.id == content.target_cafe_id)
        )
        cafe = cafe_result.scalar_one_or_none()

        if not cafe:
            raise CafePostError("대상 카페를 찾을 수 없습니다")

        try:
            logger.info(f"글 작성 시작: cafe={cafe.cafe_id}")

            # 카페 글쓰기 페이지로 이동
            write_url = f"https://cafe.naver.com/{cafe.cafe_id}?iframe_url=/ArticleWrite.nhn"
            await self._page.goto(write_url, wait_until="networkidle")
            await asyncio.sleep(3)

            # iframe 내부로 전환
            write_frame = None
            for frame in self._page.frames:
                if "ArticleWrite" in frame.url or "write" in frame.url.lower():
                    write_frame = frame
                    break

            if not write_frame:
                write_frame = self._page

            # 제목 입력
            title_input = await write_frame.query_selector("input[name='subject']") or \
                         await write_frame.query_selector(".title_input") or \
                         await write_frame.query_selector("#subject")

            if not title_input:
                raise CafePostError("제목 입력창을 찾을 수 없습니다")

            await title_input.click()
            await self._human_type(content.title or "")

            await asyncio.sleep(1)

            # 본문 입력 (스마트에디터)
            editor = await write_frame.query_selector(".se-content") or \
                    await write_frame.query_selector("[contenteditable='true']") or \
                    await write_frame.query_selector("iframe[title*='에디터']")

            if editor:
                # 에디터 클릭
                await editor.click()
                await asyncio.sleep(0.5)

                # 본문 입력
                await self._human_type(content.content)

            await asyncio.sleep(1)

            # 등록 버튼 클릭
            submit_btn = await write_frame.query_selector(".btn_register") or \
                        await write_frame.query_selector("#writeButton") or \
                        await write_frame.query_selector("button[type='submit']")

            if not submit_btn:
                raise CafePostError("등록 버튼을 찾을 수 없습니다")

            await submit_btn.click()

            # 등록 완료 대기
            await asyncio.sleep(5)

            # 상태 업데이트
            content.status = ContentStatus.POSTED
            content.posted_at = datetime.utcnow()
            content.posted_url = self._page.url

            # 카페 통계 업데이트
            cafe.total_posts += 1
            cafe.last_activity_at = datetime.utcnow()

            await self.db.commit()

            logger.info(f"글 작성 성공: {self._page.url}")

            return {
                "success": True,
                "content_id": content_id,
                "posted_url": self._page.url,
                "message": "글이 성공적으로 등록되었습니다"
            }

        except CafePostError:
            raise
        except Exception as e:
            logger.error(f"글 작성 중 오류: {e}")
            content.status = ContentStatus.FAILED
            content.error_message = str(e)
            await self.db.commit()
            raise CafePostError(f"글 작성 중 오류: {e}")

    async def _human_scroll(self):
        """인간적인 스크롤 동작"""
        scroll_amount = random.randint(100, 300)
        await self._page.mouse.wheel(0, scroll_amount)
        await asyncio.sleep(random.uniform(0.5, 1.5))

    async def _human_type(self, text: str):
        """인간적인 타이핑 속도"""
        for char in text:
            await self._page.keyboard.type(char, delay=random.randint(30, 80))
            if random.random() < 0.1:  # 10% 확률로 짧은 휴식
                await asyncio.sleep(random.uniform(0.1, 0.3))

    async def post_multiple_contents(
        self,
        user_id: str,
        limit: int = 5,
        delay_between: int = 300  # 5분
    ) -> Dict[str, Any]:
        """
        여러 콘텐츠 일괄 등록

        Args:
            user_id: 사용자 ID
            limit: 최대 등록 개수
            delay_between: 콘텐츠 간 대기 시간 (초)

        Returns:
            등록 결과
        """
        if not self._logged_in:
            raise CafePostError("로그인이 필요합니다")

        # 승인된 콘텐츠 조회
        result = await self.db.execute(
            select(CafeContent).where(
                and_(
                    CafeContent.user_id == user_id,
                    CafeContent.status == ContentStatus.APPROVED
                )
            ).limit(limit)
        )
        contents = result.scalars().all()

        if not contents:
            return {
                "success": True,
                "posted": 0,
                "failed": 0,
                "message": "등록할 콘텐츠가 없습니다"
            }

        posted_count = 0
        failed_count = 0
        results = []

        for content in contents:
            try:
                if content.content_type == ContentType.COMMENT:
                    post_result = await self.post_comment(content.id, user_id)
                elif content.content_type == ContentType.POST:
                    post_result = await self.create_post(content.id, user_id)
                else:
                    continue

                results.append(post_result)
                posted_count += 1

                # 다음 등록까지 대기 (스팸 방지)
                if posted_count < len(contents):
                    logger.info(f"{delay_between}초 대기...")
                    await asyncio.sleep(delay_between)

            except Exception as e:
                logger.error(f"콘텐츠 등록 실패: {e}")
                failed_count += 1
                results.append({
                    "success": False,
                    "content_id": content.id,
                    "error": str(e)
                })

        return {
            "success": True,
            "posted": posted_count,
            "failed": failed_count,
            "results": results,
            "message": f"{posted_count}개 등록 완료, {failed_count}개 실패"
        }

    async def save_cookies(self, filepath: str = "naver_cafe_cookies.json"):
        """쿠키 저장"""
        if self._context:
            cookies = await self._context.cookies()
            import json
            with open(filepath, "w") as f:
                json.dump(cookies, f)
            logger.info(f"쿠키 저장됨: {filepath}")

    async def load_cookies(self, filepath: str = "naver_cafe_cookies.json"):
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

    def is_logged_in(self) -> bool:
        """로그인 상태 반환"""
        return self._logged_in


class CafePosterManager:
    """사용자별 포스터 관리"""

    def __init__(self):
        self._posters: Dict[str, CafePosterService] = {}

    async def get_poster(self, db: AsyncSession, user_id: str) -> CafePosterService:
        """사용자별 포스터 인스턴스 반환"""
        if user_id not in self._posters:
            self._posters[user_id] = CafePosterService(db)
        return self._posters[user_id]

    async def close_all(self):
        """모든 포스터 종료"""
        for poster in self._posters.values():
            await poster.close()
        self._posters.clear()


# 전역 관리자
cafe_poster_manager = CafePosterManager()
