"""
네이버 블로그 영업 자동화 - 블로그 수집 크롤러
"""
import asyncio
import re
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from urllib.parse import quote, urljoin

import aiohttp
from bs4 import BeautifulSoup

# Playwright는 선택적으로 로드 (서버 환경에서는 설치되지 않을 수 있음)
try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None
    Browser = None
    BrowserContext = None
    Page = None

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blog_outreach import (
    NaverBlog, BlogContact, BlogSearchKeyword, BlogCategory, BlogStatus, ContactSource,
    OutreachSetting
)

logger = logging.getLogger(__name__)


class BlogOutreachCrawler:
    """네이버 블로그 영업용 크롤러"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        # 설정
        self.headless = True
        self.timeout = 30000
        self.max_blogs_per_keyword = 50
        self.request_delay = 2  # 요청 간 딜레이 (초)

        # 네이버 검색 URL
        self.search_url = "https://search.naver.com/search.naver"
        self.blog_base_url = "https://blog.naver.com"

    async def initialize(self):
        """브라우저 초기화"""
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("Playwright가 설치되지 않았습니다. HTTP 기반 크롤링만 사용 가능합니다.")
            return

        if self._browser:
            return

        try:
            playwright = await async_playwright().start()
            self._browser = await playwright.chromium.launch(
                headless=self.headless,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            self._context = await self._browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            self._page = await self._context.new_page()
            logger.info("블로그 아웃리치 크롤러 초기화 완료")
        except Exception as e:
            logger.warning(f"Playwright 브라우저 초기화 실패: {e}. HTTP 기반 크롤링만 사용 가능합니다.")

    async def close(self):
        """브라우저 종료"""
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._context = None
            self._page = None
            logger.info("블로그 아웃리치 크롤러 종료")

    async def search_blogs(
        self,
        keyword: str,
        user_id: str,
        category: Optional[BlogCategory] = None,
        max_results: int = 50
    ) -> Dict[str, Any]:
        """
        키워드로 블로그 검색 및 수집

        Args:
            keyword: 검색 키워드
            user_id: 사용자 ID
            category: 블로그 카테고리
            max_results: 최대 수집 개수

        Returns:
            수집 결과
        """
        # Playwright 초기화 시도
        if not self._page:
            await self.initialize()

        # Playwright 사용 불가능 시 HTTP 기반 크롤링
        if not self._page:
            return await self._search_blogs_http(keyword, user_id, category, max_results)

        collected = 0
        duplicates = 0
        errors = 0
        blogs = []

        try:
            # 네이버 블로그 탭 검색
            search_query = f"{keyword}"
            url = f"{self.search_url}?where=blog&query={quote(search_query)}"

            logger.info(f"블로그 검색 시작: {keyword}")
            await self._page.goto(url, wait_until='domcontentloaded')
            await asyncio.sleep(2)

            page_num = 1
            while collected < max_results:
                # 블로그 목록 추출
                blog_items = await self._extract_blog_list()

                if not blog_items:
                    logger.info(f"더 이상 검색 결과 없음 (page {page_num})")
                    break

                for item in blog_items:
                    if collected >= max_results:
                        break

                    try:
                        # 중복 체크
                        existing = await self.db.execute(
                            select(NaverBlog).where(
                                and_(
                                    NaverBlog.user_id == user_id,
                                    NaverBlog.blog_id == item['blog_id']
                                )
                            )
                        )
                        if existing.scalar_one_or_none():
                            duplicates += 1
                            continue

                        # 블로그 상세 정보 수집
                        blog_info = await self._get_blog_details(item['blog_id'])
                        if not blog_info:
                            errors += 1
                            continue

                        # DB 저장
                        blog = NaverBlog(
                            user_id=user_id,
                            blog_id=item['blog_id'],
                            blog_url=item['blog_url'],
                            blog_name=blog_info.get('blog_name', item.get('blog_name')),
                            owner_nickname=blog_info.get('nickname'),
                            profile_image=blog_info.get('profile_image'),
                            introduction=blog_info.get('introduction'),
                            visitor_daily=blog_info.get('visitor_daily', 0),
                            visitor_total=blog_info.get('visitor_total', 0),
                            neighbor_count=blog_info.get('neighbor_count', 0),
                            post_count=blog_info.get('post_count', 0),
                            last_post_date=blog_info.get('last_post_date'),
                            last_post_title=item.get('post_title'),
                            category=category or BlogCategory.OTHER,
                            keywords=[keyword],
                            status=BlogStatus.NEW
                        )
                        self.db.add(blog)
                        blogs.append(blog)
                        collected += 1

                        # 딜레이
                        await asyncio.sleep(self.request_delay)

                    except Exception as e:
                        logger.error(f"블로그 수집 오류: {e}")
                        errors += 1

                # 다음 페이지
                has_next = await self._go_next_page()
                if not has_next:
                    break
                page_num += 1
                await asyncio.sleep(1)

            await self.db.commit()

            # 검색 키워드 통계 업데이트
            await self._update_keyword_stats(user_id, keyword, collected, category)

            logger.info(f"블로그 수집 완료: {collected}개 수집, {duplicates}개 중복, {errors}개 오류")

            return {
                "success": True,
                "keyword": keyword,
                "collected": collected,
                "duplicates": duplicates,
                "errors": errors,
                "blogs": [{"id": b.id, "blog_id": b.blog_id, "blog_name": b.blog_name} for b in blogs]
            }

        except Exception as e:
            logger.error(f"블로그 검색 오류: {e}")
            return {
                "success": False,
                "error": str(e),
                "collected": collected
            }

    async def _extract_blog_list(self) -> List[Dict[str, Any]]:
        """검색 결과에서 블로그 목록 추출"""
        blogs = []

        try:
            # 블로그 검색 결과 컨테이너 (여러 선택자 시도)
            selectors = ['li.bx', 'div.api_subject_bx', 'div.total_wrap']
            items = []

            for selector in selectors:
                items = await self._page.query_selector_all(selector)
                if items:
                    break

            for item in items:
                try:
                    # 블로그 링크 추출 (여러 선택자 시도)
                    link_selectors = [
                        'a.api_txt_lines.total_tit',
                        'a.title_link',
                        'a[href*="blog.naver.com"]'
                    ]
                    link_elem = None
                    for sel in link_selectors:
                        link_elem = await item.query_selector(sel)
                        if link_elem:
                            break

                    if not link_elem:
                        continue

                    href = await link_elem.get_attribute('href')
                    if not href or 'blog.naver.com' not in href:
                        continue

                    # 블로그 ID 추출
                    blog_id = self._extract_blog_id(href)
                    if not blog_id:
                        continue

                    # 블로그 이름
                    name_selectors = ['.sub_txt.sub_name', '.source_txt', '.blog_name']
                    blog_name = ""
                    for sel in name_selectors:
                        name_elem = await item.query_selector(sel)
                        if name_elem:
                            blog_name = await name_elem.inner_text()
                            break

                    # 포스팅 제목
                    title = await link_elem.inner_text() if link_elem else ""

                    blogs.append({
                        'blog_id': blog_id,
                        'blog_url': f"https://blog.naver.com/{blog_id}",
                        'blog_name': blog_name.strip(),
                        'post_title': title.strip()
                    })

                except Exception as e:
                    logger.debug(f"블로그 항목 추출 오류: {e}")
                    continue

        except Exception as e:
            logger.error(f"블로그 목록 추출 오류: {e}")

        return blogs

    def _extract_blog_id(self, url: str) -> Optional[str]:
        """URL에서 블로그 ID 추출"""
        patterns = [
            r'blog\.naver\.com/([^/?]+)',
            r'blogId=([^&]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                blog_id = match.group(1)
                # 숫자로만 된 경우 (글 번호)는 제외
                if not blog_id.isdigit():
                    return blog_id
        return None

    async def _get_blog_details(self, blog_id: str) -> Optional[Dict[str, Any]]:
        """블로그 상세 정보 수집"""
        try:
            blog_url = f"https://blog.naver.com/{blog_id}"
            await self._page.goto(blog_url, wait_until='domcontentloaded')
            await asyncio.sleep(1)

            info = {
                'blog_id': blog_id,
                'blog_url': blog_url
            }

            # 블로그 이름 (여러 선택자 시도)
            name_selectors = ['.nick', '.blog_name', '#nickNameArea', '.pcol1']
            for sel in name_selectors:
                try:
                    name_elem = await self._page.query_selector(sel)
                    if name_elem:
                        info['blog_name'] = (await name_elem.inner_text()).strip()
                        break
                except:
                    pass

            # 닉네임
            try:
                nick_elem = await self._page.query_selector('.nick, .nickname, .pcol1')
                if nick_elem:
                    info['nickname'] = (await nick_elem.inner_text()).strip()
            except:
                pass

            # 프로필 이미지
            try:
                img_selectors = ['.thumb img', '.profile_img img', '.buddy_profile img']
                for sel in img_selectors:
                    img_elem = await self._page.query_selector(sel)
                    if img_elem:
                        src = await img_elem.get_attribute('src')
                        if src:
                            info['profile_image'] = src
                            break
            except:
                pass

            # 프로필 페이지에서 추가 정보 수집
            try:
                profile_url = f"https://blog.naver.com/profile/intro.naver?blogId={blog_id}"
                await self._page.goto(profile_url, wait_until='domcontentloaded')
                await asyncio.sleep(1)

                # 소개글
                intro_selectors = ['.se_textarea', '.introText', '#introduction', '.intro_text']
                for sel in intro_selectors:
                    intro_elem = await self._page.query_selector(sel)
                    if intro_elem:
                        info['introduction'] = (await intro_elem.inner_text()).strip()
                        break

                # 이웃 수
                neighbor_selectors = ['.neighbor_count', '.buddy_count', '.cnt']
                for sel in neighbor_selectors:
                    neighbor_elem = await self._page.query_selector(sel)
                    if neighbor_elem:
                        text = await neighbor_elem.inner_text()
                        numbers = re.findall(r'[\d,]+', text)
                        if numbers:
                            info['neighbor_count'] = int(numbers[0].replace(',', ''))
                            break

            except Exception as e:
                logger.debug(f"프로필 정보 수집 오류: {e}")

            # 방문자 수 (블로그 메인에서)
            try:
                await self._page.goto(blog_url, wait_until='domcontentloaded')
                await asyncio.sleep(0.5)

                # 오늘 방문자
                today_selectors = ['.today', '.visit_today', '.cnt_today']
                for sel in today_selectors:
                    visitor_elem = await self._page.query_selector(sel)
                    if visitor_elem:
                        text = await visitor_elem.inner_text()
                        numbers = re.findall(r'[\d,]+', text)
                        if numbers:
                            info['visitor_daily'] = int(numbers[0].replace(',', ''))
                            break

                # 전체 방문자
                total_selectors = ['.total', '.visit_total', '.cnt_total']
                for sel in total_selectors:
                    total_elem = await self._page.query_selector(sel)
                    if total_elem:
                        text = await total_elem.inner_text()
                        numbers = re.findall(r'[\d,]+', text)
                        if numbers:
                            info['visitor_total'] = int(numbers[0].replace(',', ''))
                            break

            except Exception as e:
                logger.debug(f"방문자 수 수집 오류: {e}")

            return info

        except Exception as e:
            logger.error(f"블로그 상세 정보 수집 오류 ({blog_id}): {e}")
            return None

    async def _go_next_page(self) -> bool:
        """다음 페이지로 이동"""
        try:
            next_selectors = ['a.btn_next', '.next', 'a[aria-label="다음"]']
            for sel in next_selectors:
                next_btn = await self._page.query_selector(sel)
                if next_btn:
                    is_disabled = await next_btn.get_attribute('aria-disabled')
                    if is_disabled != 'true':
                        await next_btn.click()
                        await asyncio.sleep(2)
                        return True
            return False
        except:
            return False

    async def _update_keyword_stats(
        self,
        user_id: str,
        keyword: str,
        collected: int,
        category: Optional[BlogCategory] = None
    ):
        """키워드 통계 업데이트"""
        try:
            result = await self.db.execute(
                select(BlogSearchKeyword).where(
                    and_(
                        BlogSearchKeyword.user_id == user_id,
                        BlogSearchKeyword.keyword == keyword
                    )
                )
            )
            kw = result.scalar_one_or_none()

            if kw:
                kw.total_collected = (kw.total_collected or 0) + collected
                kw.last_collected_at = datetime.utcnow()
            else:
                kw = BlogSearchKeyword(
                    user_id=user_id,
                    keyword=keyword,
                    category=category,
                    total_collected=collected,
                    last_collected_at=datetime.utcnow()
                )
                self.db.add(kw)

            await self.db.commit()
        except Exception as e:
            logger.error(f"키워드 통계 업데이트 오류: {e}")

    async def collect_by_category(
        self,
        user_id: str,
        category: BlogCategory,
        keywords: Optional[List[str]] = None,
        max_per_keyword: int = 30
    ) -> Dict[str, Any]:
        """
        카테고리별 블로그 수집

        Args:
            user_id: 사용자 ID
            category: 블로그 카테고리
            keywords: 검색 키워드 목록 (없으면 기본 키워드 사용)
            max_per_keyword: 키워드당 최대 수집 수

        Returns:
            수집 결과
        """
        # 카테고리별 기본 키워드
        default_keywords = {
            BlogCategory.BEAUTY: ["뷰티 블로거", "화장품 리뷰", "코스메틱 추천"],
            BlogCategory.FOOD: ["맛집 블로거", "음식 리뷰", "카페 추천"],
            BlogCategory.TRAVEL: ["여행 블로거", "여행 후기", "국내여행 추천"],
            BlogCategory.PARENTING: ["육아 블로거", "맘블로거", "아이 교육"],
            BlogCategory.LIVING: ["인테리어 블로거", "리빙 추천", "홈스타일링"],
            BlogCategory.HEALTH: ["건강 블로거", "운동 후기", "다이어트 정보"],
            BlogCategory.IT: ["IT 블로거", "테크 리뷰", "가젯 추천"],
            BlogCategory.FINANCE: ["재테크 블로거", "투자 정보", "금융 팁"],
            BlogCategory.LIFESTYLE: ["일상 블로거", "라이프스타일", "취미 생활"],
        }

        if not keywords:
            keywords = default_keywords.get(category, [f"{category.value} 블로거"])

        total_collected = 0
        results = []

        for keyword in keywords:
            result = await self.search_blogs(
                keyword=keyword,
                user_id=user_id,
                category=category,
                max_results=max_per_keyword
            )
            results.append(result)
            total_collected += result.get('collected', 0)

            # 키워드 간 딜레이
            await asyncio.sleep(3)

        return {
            "success": True,
            "category": category.value,
            "total_collected": total_collected,
            "keyword_results": results
        }

    async def collect_influencers(
        self,
        user_id: str,
        category: Optional[BlogCategory] = None,
        min_visitors: int = 1000,
        min_neighbors: int = 500
    ) -> Dict[str, Any]:
        """
        인플루언서 블로그 수집

        Args:
            user_id: 사용자 ID
            category: 카테고리 필터
            min_visitors: 최소 일일 방문자
            min_neighbors: 최소 이웃 수

        Returns:
            수집 결과
        """
        # 인플루언서 검색 키워드
        influencer_keywords = [
            "인플루언서 협찬", "체험단 블로거", "파워블로거",
            "블로그 협업", "블로거 섭외", "협찬 문의"
        ]

        if category:
            category_keywords = {
                BlogCategory.BEAUTY: ["뷰티 인플루언서", "화장품 체험단"],
                BlogCategory.FOOD: ["맛집 인플루언서", "푸드 블로거 협찬"],
                BlogCategory.TRAVEL: ["여행 인플루언서", "여행 블로거 협업"],
                BlogCategory.PARENTING: ["육아 인플루언서", "맘블로거 체험단"],
                BlogCategory.LIVING: ["인테리어 인플루언서", "리빙 블로거"],
            }
            influencer_keywords.extend(category_keywords.get(category, []))

        results = []
        for keyword in influencer_keywords:
            result = await self.search_blogs(
                keyword=keyword,
                user_id=user_id,
                category=category,
                max_results=20
            )
            results.append(result)
            await asyncio.sleep(3)

        # 인플루언서 마킹
        influencer_count = 0
        query = select(NaverBlog).where(NaverBlog.user_id == user_id)
        if min_visitors > 0:
            query = query.where(NaverBlog.visitor_daily >= min_visitors)

        blogs_result = await self.db.execute(query)
        for blog in blogs_result.scalars():
            if blog.neighbor_count >= min_neighbors or blog.visitor_daily >= min_visitors:
                blog.is_influencer = True
                influencer_count += 1

        await self.db.commit()

        total_collected = sum(r.get('collected', 0) for r in results)

        return {
            "success": True,
            "total_collected": total_collected,
            "influencers_marked": influencer_count,
            "results": results
        }

    async def _search_blogs_http(
        self,
        keyword: str,
        user_id: str,
        category: Optional[BlogCategory] = None,
        max_results: int = 50
    ) -> Dict[str, Any]:
        """HTTP 기반 블로그 검색 (Playwright 없을 때 사용)"""
        # 먼저 Naver API가 설정되어 있는지 확인
        naver_api_result = await self._search_blogs_naver_api(keyword, user_id, category, max_results)
        if naver_api_result.get("success"):
            return naver_api_result

        # Naver API가 없으면 HTTP 스크래핑 시도 (네이버에서 차단될 가능성 높음)
        collected = 0
        duplicates = 0
        errors = 0
        blogs = []

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        }

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                # 네이버 블로그 검색 페이지 스크래핑
                for start in range(1, max_results + 1, 10):
                    if collected >= max_results:
                        break

                    search_url = f"https://search.naver.com/search.naver?where=blog&query={quote(keyword)}&start={start}"

                    try:
                        async with session.get(search_url) as response:
                            if response.status != 200:
                                logger.warning(f"검색 요청 실패: {response.status}")
                                continue

                            html = await response.text()
                            soup = BeautifulSoup(html, 'html.parser')

                            # 블로그 검색 결과 파싱
                            blog_items = soup.select('li.bx') or soup.select('div.api_subject_bx') or soup.select('div.total_wrap')

                            if not blog_items:
                                logger.info(f"검색 결과 없음 (start={start})")
                                break

                            for item in blog_items:
                                if collected >= max_results:
                                    break

                                try:
                                    # 블로그 링크 추출
                                    link_elem = (
                                        item.select_one('a.api_txt_lines.total_tit') or
                                        item.select_one('a.title_link') or
                                        item.select_one('a[href*="blog.naver.com"]')
                                    )

                                    if not link_elem:
                                        continue

                                    href = link_elem.get('href', '')
                                    if 'blog.naver.com' not in href:
                                        continue

                                    blog_id = self._extract_blog_id(href)
                                    if not blog_id:
                                        continue

                                    # 중복 체크
                                    existing = await self.db.execute(
                                        select(NaverBlog).where(
                                            and_(
                                                NaverBlog.user_id == user_id,
                                                NaverBlog.blog_id == blog_id
                                            )
                                        )
                                    )
                                    if existing.scalar_one_or_none():
                                        duplicates += 1
                                        continue

                                    # 블로그 이름
                                    name_elem = (
                                        item.select_one('.sub_txt.sub_name') or
                                        item.select_one('.source_txt') or
                                        item.select_one('.blog_name')
                                    )
                                    blog_name = name_elem.get_text(strip=True) if name_elem else ""

                                    # 포스팅 제목
                                    title = link_elem.get_text(strip=True)

                                    # DB 저장
                                    blog = NaverBlog(
                                        user_id=user_id,
                                        blog_id=blog_id,
                                        blog_url=f"https://blog.naver.com/{blog_id}",
                                        blog_name=blog_name,
                                        last_post_title=title,
                                        category=category or BlogCategory.OTHER,
                                        keywords=[keyword],
                                        status=BlogStatus.NEW
                                    )
                                    self.db.add(blog)
                                    blogs.append(blog)
                                    collected += 1

                                except Exception as e:
                                    logger.debug(f"블로그 항목 처리 오류: {e}")
                                    errors += 1

                        # 요청 간 딜레이
                        await asyncio.sleep(self.request_delay)

                    except Exception as e:
                        logger.error(f"검색 페이지 요청 오류: {e}")
                        errors += 1

                await self.db.commit()

                # 검색 키워드 통계 업데이트
                await self._update_keyword_stats(user_id, keyword, collected, category)

                logger.info(f"HTTP 기반 블로그 수집 완료: {collected}개 수집, {duplicates}개 중복, {errors}개 오류")

                return {
                    "success": True,
                    "keyword": keyword,
                    "collected": collected,
                    "duplicates": duplicates,
                    "errors": errors,
                    "blogs": [{"id": b.id, "blog_id": b.blog_id, "blog_name": b.blog_name} for b in blogs],
                    "method": "http"
                }

        except Exception as e:
            logger.error(f"HTTP 기반 블로그 검색 오류: {e}")
            return {
                "success": False,
                "error": str(e),
                "collected": collected,
                "method": "http"
            }

    async def _search_blogs_naver_api(
        self,
        keyword: str,
        user_id: str,
        category: Optional[BlogCategory] = None,
        max_results: int = 50
    ) -> Dict[str, Any]:
        """네이버 검색 API를 사용한 블로그 검색"""
        # 사용자의 네이버 API 설정 조회
        try:
            result = await self.db.execute(
                select(OutreachSetting).where(OutreachSetting.user_id == user_id)
            )
            settings = result.scalar_one_or_none()

            if not settings or not settings.naver_client_id or not settings.naver_client_secret_encrypted:
                logger.info("네이버 API 설정이 없습니다. HTTP 스크래핑으로 대체합니다.")
                return {
                    "success": False,
                    "error": "naver_api_not_configured",
                    "error_code": "NAVER_API_NOT_CONFIGURED",
                    "user_message": "네이버 검색 API가 설정되지 않았습니다.",
                    "action_required": "설정 > 네이버 검색 API에서 Client ID와 Secret을 입력해주세요.",
                    "help_url": "/dashboard/outreach/settings"
                }

            # 암호화된 비밀번호 복호화
            from app.services.email_sender_service import EmailSenderService
            email_service = EmailSenderService(self.db)
            naver_client_secret = email_service.decrypt_password(settings.naver_client_secret_encrypted)

            if not naver_client_secret:
                logger.error("네이버 API Secret 복호화 실패")
                return {
                    "success": False,
                    "error": "naver_secret_decrypt_failed",
                    "error_code": "NAVER_SECRET_DECRYPT_FAILED",
                    "user_message": "네이버 API Secret 복호화에 실패했습니다.",
                    "action_required": "설정에서 네이버 API Secret을 다시 입력해주세요.",
                    "help_url": "/dashboard/outreach/settings"
                }

        except Exception as e:
            logger.error(f"네이버 API 설정 조회 오류: {e}")
            return {"success": False, "error": str(e)}

        collected = 0
        duplicates = 0
        errors = 0
        blogs = []

        headers = {
            'X-Naver-Client-Id': settings.naver_client_id,
            'X-Naver-Client-Secret': naver_client_secret,
        }

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                # 네이버 블로그 검색 API (최대 100개씩, 총 1000개까지)
                for start in range(1, min(max_results, 1000) + 1, 100):
                    if collected >= max_results:
                        break

                    display = min(100, max_results - collected)
                    api_url = f"https://openapi.naver.com/v1/search/blog.json?query={quote(keyword)}&display={display}&start={start}&sort=sim"

                    try:
                        async with session.get(api_url) as response:
                            if response.status != 200:
                                error_text = await response.text()
                                logger.error(f"네이버 API 오류: {response.status} - {error_text}")
                                if response.status == 429:
                                    logger.warning("API 호출 한도 초과. 잠시 후 다시 시도하세요.")
                                    break
                                continue

                            data = await response.json()
                            items = data.get('items', [])

                            if not items:
                                logger.info(f"검색 결과 없음 (start={start})")
                                break

                            for item in items:
                                if collected >= max_results:
                                    break

                                try:
                                    # 블로그 링크에서 ID 추출
                                    blog_link = item.get('bloggerlink', '') or item.get('link', '')

                                    # blog.naver.com 링크가 아닌 경우 스킵
                                    if 'blog.naver.com' not in blog_link:
                                        continue

                                    blog_id = self._extract_blog_id(blog_link)
                                    if not blog_id:
                                        # 포스트 링크에서 추출 시도
                                        post_link = item.get('link', '')
                                        blog_id = self._extract_blog_id(post_link)

                                    if not blog_id:
                                        continue

                                    # 중복 체크
                                    existing = await self.db.execute(
                                        select(NaverBlog).where(
                                            and_(
                                                NaverBlog.user_id == user_id,
                                                NaverBlog.blog_id == blog_id
                                            )
                                        )
                                    )
                                    if existing.scalar_one_or_none():
                                        duplicates += 1
                                        continue

                                    # HTML 태그 제거
                                    import html
                                    title = re.sub(r'<[^>]+>', '', item.get('title', ''))
                                    title = html.unescape(title)
                                    description = re.sub(r'<[^>]+>', '', item.get('description', ''))
                                    description = html.unescape(description)
                                    blogger_name = item.get('bloggername', '')

                                    # DB 저장
                                    blog = NaverBlog(
                                        user_id=user_id,
                                        blog_id=blog_id,
                                        blog_url=f"https://blog.naver.com/{blog_id}",
                                        blog_name=blogger_name,
                                        last_post_title=title,
                                        introduction=description[:500] if description else None,
                                        category=category or BlogCategory.OTHER,
                                        keywords=[keyword],
                                        status=BlogStatus.NEW
                                    )
                                    self.db.add(blog)
                                    blogs.append(blog)
                                    collected += 1

                                except Exception as e:
                                    logger.debug(f"블로그 항목 처리 오류: {e}")
                                    errors += 1

                            # 다음 페이지가 없으면 종료
                            total = data.get('total', 0)
                            if start + display > total:
                                break

                        # API 호출 간 딜레이 (초당 10회 제한 고려)
                        await asyncio.sleep(0.2)

                    except Exception as e:
                        logger.error(f"네이버 API 요청 오류: {e}")
                        errors += 1

                await self.db.commit()

                # 검색 키워드 통계 업데이트
                await self._update_keyword_stats(user_id, keyword, collected, category)

                logger.info(f"네이버 API 블로그 수집 완료: {collected}개 수집, {duplicates}개 중복, {errors}개 오류")

                return {
                    "success": True,
                    "keyword": keyword,
                    "collected": collected,
                    "duplicates": duplicates,
                    "errors": errors,
                    "blogs": [{"id": b.id, "blog_id": b.blog_id, "blog_name": b.blog_name} for b in blogs],
                    "method": "naver_api"
                }

        except Exception as e:
            logger.error(f"네이버 API 블로그 검색 오류: {e}")
            return {
                "success": False,
                "error": str(e),
                "collected": collected,
                "method": "naver_api"
            }

    async def refresh_blog_info(self, blog_id: str) -> Dict[str, Any]:
        """블로그 정보 갱신"""
        try:
            result = await self.db.execute(
                select(NaverBlog).where(NaverBlog.id == blog_id)
            )
            blog = result.scalar_one_or_none()

            if not blog:
                return {"success": False, "error": "블로그를 찾을 수 없습니다"}

            if not self._page:
                await self.initialize()

            info = await self._get_blog_details(blog.blog_id)
            if info:
                blog.blog_name = info.get('blog_name', blog.blog_name)
                blog.owner_nickname = info.get('nickname', blog.owner_nickname)
                blog.visitor_daily = info.get('visitor_daily', blog.visitor_daily)
                blog.visitor_total = info.get('visitor_total', blog.visitor_total)
                blog.neighbor_count = info.get('neighbor_count', blog.neighbor_count)
                blog.introduction = info.get('introduction', blog.introduction)
                blog.updated_at = datetime.utcnow()

                await self.db.commit()
                return {"success": True, "message": "블로그 정보가 갱신되었습니다"}

            return {"success": False, "error": "블로그 정보를 가져올 수 없습니다"}

        except Exception as e:
            logger.error(f"블로그 정보 갱신 오류: {e}")
            return {"success": False, "error": str(e)}


# 싱글톤 인스턴스 관리 (P2: 메모리 관리 개선)
_crawler_instances: Dict[str, Dict[str, Any]] = {}
_MAX_INSTANCES = 10  # 최대 인스턴스 수
_INSTANCE_TTL_SECONDS = 1800  # 30분 미사용 시 정리
_BROWSER_IDLE_SECONDS = 600  # 10분 미사용 시 브라우저 종료


async def get_blog_outreach_crawler(db: AsyncSession, user_id: str) -> BlogOutreachCrawler:
    """사용자별 크롤러 인스턴스 반환 (메모리 관리 포함)"""
    now = datetime.utcnow()

    # 주기적 정리 (매 호출 시 체크)
    await _cleanup_idle_instances()

    if user_id in _crawler_instances:
        instance_data = _crawler_instances[user_id]
        instance_data["last_access"] = now
        instance_data["crawler"].db = db
        return instance_data["crawler"]

    # 최대 인스턴스 수 초과 시 가장 오래된 인스턴스 제거
    if len(_crawler_instances) >= _MAX_INSTANCES:
        await _evict_oldest_instance()

    # 새 인스턴스 생성
    crawler = BlogOutreachCrawler(db)
    _crawler_instances[user_id] = {
        "crawler": crawler,
        "created_at": now,
        "last_access": now,
        "browser_last_used": None
    }

    return crawler


async def _cleanup_idle_instances():
    """유휴 인스턴스 정리"""
    now = datetime.utcnow()
    to_remove = []

    for user_id, data in _crawler_instances.items():
        idle_seconds = (now - data["last_access"]).total_seconds()

        # TTL 초과한 인스턴스 제거 대상
        if idle_seconds > _INSTANCE_TTL_SECONDS:
            to_remove.append(user_id)
        # 브라우저만 종료 (인스턴스는 유지)
        elif idle_seconds > _BROWSER_IDLE_SECONDS:
            crawler = data["crawler"]
            if crawler._browser:
                try:
                    await crawler.close()
                    logger.info(f"유휴 브라우저 종료: user_id={user_id}")
                except Exception as e:
                    logger.warning(f"브라우저 종료 실패: {e}")

    # 오래된 인스턴스 제거
    for user_id in to_remove:
        await _remove_instance(user_id)


async def _evict_oldest_instance():
    """가장 오래된 인스턴스 제거 (LRU)"""
    if not _crawler_instances:
        return

    oldest_user_id = min(
        _crawler_instances.keys(),
        key=lambda uid: _crawler_instances[uid]["last_access"]
    )
    await _remove_instance(oldest_user_id)
    logger.info(f"LRU 인스턴스 제거: user_id={oldest_user_id}")


async def _remove_instance(user_id: str):
    """인스턴스 안전하게 제거"""
    if user_id not in _crawler_instances:
        return

    try:
        crawler = _crawler_instances[user_id]["crawler"]
        await crawler.close()
    except Exception as e:
        logger.warning(f"인스턴스 종료 중 오류: {e}")
    finally:
        del _crawler_instances[user_id]


async def cleanup_all_crawler_instances():
    """모든 크롤러 인스턴스 정리 (앱 종료 시 호출)"""
    user_ids = list(_crawler_instances.keys())
    for user_id in user_ids:
        await _remove_instance(user_id)
    logger.info(f"모든 크롤러 인스턴스 정리 완료 ({len(user_ids)}개)")
