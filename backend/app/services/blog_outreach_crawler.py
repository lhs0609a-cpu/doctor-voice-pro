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
    NaverBlog, BlogContact, BlogSearchKeyword, BlogCategory, BlogStatus, ContactSource
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
        if not self._page:
            await self.initialize()

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


# 싱글톤 인스턴스 관리
_crawler_instances: Dict[str, BlogOutreachCrawler] = {}


async def get_blog_outreach_crawler(db: AsyncSession, user_id: str) -> BlogOutreachCrawler:
    """사용자별 크롤러 인스턴스 반환"""
    if user_id not in _crawler_instances:
        _crawler_instances[user_id] = BlogOutreachCrawler(db)
    else:
        _crawler_instances[user_id].db = db
    return _crawler_instances[user_id]
