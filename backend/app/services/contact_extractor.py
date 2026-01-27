"""
블로그 연락처 추출 서비스
이메일, 전화번호, SNS 링크 등을 블로그에서 자동 추출
"""
import asyncio
import re
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse

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

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blog_outreach import (
    NaverBlog, BlogContact, BlogStatus, ContactSource
)

logger = logging.getLogger(__name__)


class ContactExtractorService:
    """블로그 연락처 추출 서비스"""

    # 이메일 패턴
    EMAIL_PATTERNS = [
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        r'[a-zA-Z0-9._%+-]+\s*@\s*[a-zA-Z0-9.-]+\.\s*[a-zA-Z]{2,}',
        r'[a-zA-Z0-9._%+-]+\s*\(\s*@\s*\)\s*[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        r'[a-zA-Z0-9._%+-]+\s*\[at\]\s*[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        r'[a-zA-Z0-9._%+-]+\s*\(at\)\s*[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    ]

    # 전화번호 패턴
    PHONE_PATTERNS = [
        r'01[0-9]-?\d{3,4}-?\d{4}',  # 휴대폰
        r'0\d{1,2}-?\d{3,4}-?\d{4}',  # 일반전화
        r'\d{3,4}-\d{4}',  # 지역번호 없는 전화
    ]

    # 인스타그램 패턴
    INSTAGRAM_PATTERNS = [
        r'instagram\.com/([a-zA-Z0-9_.]+)',
        r'@([a-zA-Z0-9_.]+)\s*\(?인스타',
        r'인스타\s*:?\s*@?([a-zA-Z0-9_.]+)',
        r'ig\s*:?\s*@?([a-zA-Z0-9_.]+)',
    ]

    # 유튜브 패턴
    YOUTUBE_PATTERNS = [
        r'youtube\.com/(?:channel/|c/|user/|@)([a-zA-Z0-9_-]+)',
        r'youtu\.be/([a-zA-Z0-9_-]+)',
    ]

    # 카카오 채널 패턴
    KAKAO_PATTERNS = [
        r'pf\.kakao\.com/([a-zA-Z0-9_]+)',
        r'open\.kakao\.com/o/([a-zA-Z0-9_]+)',
        r'카카오.*:?\s*([a-zA-Z0-9_]+)',
    ]

    # 연락처 관련 키워드
    CONTACT_KEYWORDS = [
        "협찬문의", "제휴문의", "비즈니스", "업무문의", "광고문의",
        "섭외", "contact", "business", "문의", "연락처", "이메일",
        "협업", "제휴", "광고", "협찬", "리뷰문의"
    ]

    def __init__(self, db: AsyncSession):
        self.db = db
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self.headless = True

    async def initialize(self):
        """브라우저 초기화"""
        if self._browser:
            return

        playwright = await async_playwright().start()
        self._browser = await playwright.chromium.launch(
            headless=self.headless,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        self._context = await self._browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        self._page = await self._context.new_page()
        logger.info("연락처 추출기 초기화 완료")

    async def close(self):
        """브라우저 종료"""
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._context = None
            self._page = None

    async def extract_contacts(
        self,
        blog_id: str,
        user_id: str,
        auto_generate_naver_email: bool = True
    ) -> Dict[str, Any]:
        """
        블로그에서 연락처 추출

        Args:
            blog_id: 블로그 DB ID
            user_id: 사용자 ID
            auto_generate_naver_email: 블로그 ID 기반 네이버 이메일 자동 생성 여부

        Returns:
            추출 결과
        """
        try:
            # 블로그 조회
            result = await self.db.execute(
                select(NaverBlog).where(
                    and_(
                        NaverBlog.id == blog_id,
                        NaverBlog.user_id == user_id
                    )
                )
            )
            blog = result.scalar_one_or_none()

            if not blog:
                return {"success": False, "error": "블로그를 찾을 수 없습니다"}

            contacts_found = []

            # 0. 블로그 ID 기반 네이버 이메일 자동 생성 (가장 우선)
            if auto_generate_naver_email and blog.blog_id:
                naver_email = self._generate_naver_email(blog.blog_id)
                contacts_found.append({
                    'email': naver_email,
                    'source': ContactSource.PROFILE,
                    'source_url': blog.blog_url,
                    'is_naver_id_email': True  # 블로그 ID 기반 이메일 표시
                })
                logger.info(f"블로그 ID 기반 네이버 이메일 생성: {naver_email}")

            # Playwright 초기화 (선택적 - 추가 연락처 추출용)
            try:
                if PLAYWRIGHT_AVAILABLE and not self._page:
                    await self.initialize()
            except Exception as e:
                logger.warning(f"Playwright 초기화 실패 (네이버 이메일만 사용): {e}")

            # Playwright가 사용 가능한 경우에만 추가 추출 수행
            if self._page:
                # 1. 프로필 페이지에서 추출
                profile_contacts = await self._extract_from_profile(blog.blog_id)
                contacts_found.extend(profile_contacts)

                # 2. 블로그 메인에서 추출
                main_contacts = await self._extract_from_main(blog.blog_id)
                contacts_found.extend(main_contacts)

                # 3. 협찬/문의 관련 포스팅에서 추출
                post_contacts = await self._extract_from_contact_posts(blog.blog_id)
                contacts_found.extend(post_contacts)

            # 중복 제거 및 DB 저장
            saved_contacts = await self._save_contacts(blog, contacts_found)

            # 블로그 상태 업데이트
            if saved_contacts:
                blog.has_contact = True
                blog.status = BlogStatus.CONTACT_FOUND
                await self.db.commit()

            return {
                "success": True,
                "blog_id": blog_id,
                "contacts_found": len(saved_contacts),
                "contacts": saved_contacts,
                "naver_email_generated": auto_generate_naver_email and blog.blog_id is not None
            }

        except Exception as e:
            logger.error(f"연락처 추출 오류: {e}")
            return {"success": False, "error": str(e)}

    async def _extract_from_profile(self, naver_blog_id: str) -> List[Dict[str, Any]]:
        """프로필 페이지에서 연락처 추출"""
        contacts = []

        try:
            profile_url = f"https://blog.naver.com/profile/intro.naver?blogId={naver_blog_id}"
            await self._page.goto(profile_url, wait_until='domcontentloaded')
            await asyncio.sleep(1)

            # 페이지 전체 텍스트 추출
            content = await self._page.content()
            soup = BeautifulSoup(content, 'html.parser')
            text = soup.get_text()

            # 이메일 추출
            emails = self._extract_emails(text)
            for email in emails:
                contacts.append({
                    'email': email,
                    'source': ContactSource.PROFILE,
                    'source_url': profile_url
                })

            # 전화번호 추출
            phones = self._extract_phones(text)
            for phone in phones:
                contacts.append({
                    'phone': phone,
                    'source': ContactSource.PROFILE,
                    'source_url': profile_url
                })

            # 인스타그램 추출
            instagrams = self._extract_instagram(text)
            for ig in instagrams:
                contacts.append({
                    'instagram': ig,
                    'source': ContactSource.PROFILE,
                    'source_url': profile_url
                })

            # 링크에서 SNS 추출
            links = soup.find_all('a', href=True)
            for link in links:
                href = link.get('href', '')

                # 인스타그램 링크
                if 'instagram.com' in href:
                    ig_match = re.search(r'instagram\.com/([a-zA-Z0-9_.]+)', href)
                    if ig_match:
                        contacts.append({
                            'instagram': ig_match.group(1),
                            'source': ContactSource.PROFILE,
                            'source_url': profile_url
                        })

                # 유튜브 링크
                if 'youtube.com' in href or 'youtu.be' in href:
                    for pattern in self.YOUTUBE_PATTERNS:
                        yt_match = re.search(pattern, href)
                        if yt_match:
                            contacts.append({
                                'youtube': yt_match.group(1),
                                'source': ContactSource.PROFILE,
                                'source_url': profile_url
                            })
                            break

                # 카카오 채널
                if 'kakao' in href:
                    for pattern in self.KAKAO_PATTERNS:
                        kk_match = re.search(pattern, href)
                        if kk_match:
                            contacts.append({
                                'kakao_channel': kk_match.group(1),
                                'source': ContactSource.PROFILE,
                                'source_url': profile_url
                            })
                            break

        except Exception as e:
            logger.debug(f"프로필 연락처 추출 오류: {e}")

        return contacts

    async def _extract_from_main(self, naver_blog_id: str) -> List[Dict[str, Any]]:
        """블로그 메인 페이지에서 연락처 추출"""
        contacts = []

        try:
            blog_url = f"https://blog.naver.com/{naver_blog_id}"
            await self._page.goto(blog_url, wait_until='domcontentloaded')
            await asyncio.sleep(1)

            content = await self._page.content()
            soup = BeautifulSoup(content, 'html.parser')
            text = soup.get_text()

            # 이메일 추출
            emails = self._extract_emails(text)
            for email in emails:
                contacts.append({
                    'email': email,
                    'source': ContactSource.WIDGET,
                    'source_url': blog_url
                })

            # 사이드바/위젯에서 추출
            widget_selectors = ['.side', '.widget', '.banner', '.contact', '.profile_area']
            for selector in widget_selectors:
                widgets = soup.select(selector)
                for widget in widgets:
                    widget_text = widget.get_text()
                    widget_emails = self._extract_emails(widget_text)
                    for email in widget_emails:
                        contacts.append({
                            'email': email,
                            'source': ContactSource.WIDGET,
                            'source_url': blog_url
                        })

        except Exception as e:
            logger.debug(f"메인 페이지 연락처 추출 오류: {e}")

        return contacts

    async def _extract_from_contact_posts(self, naver_blog_id: str) -> List[Dict[str, Any]]:
        """협찬/문의 관련 포스팅에서 연락처 추출"""
        contacts = []

        try:
            # 협찬/문의 키워드로 블로그 내 검색
            for keyword in ["협찬문의", "비즈니스", "제휴문의", "광고문의"]:
                search_url = f"https://blog.naver.com/PostSearchList.naver?blogId={naver_blog_id}&searchText={keyword}"

                await self._page.goto(search_url, wait_until='domcontentloaded')
                await asyncio.sleep(1)

                # 검색 결과에서 첫 번째 포스팅 링크 가져오기
                post_links = await self._page.query_selector_all('a.pcol2')

                for i, link in enumerate(post_links[:3]):  # 최대 3개 포스팅만 확인
                    try:
                        href = await link.get_attribute('href')
                        if not href:
                            continue

                        # 포스팅 페이지로 이동
                        if not href.startswith('http'):
                            href = f"https://blog.naver.com{href}"

                        await self._page.goto(href, wait_until='domcontentloaded')
                        await asyncio.sleep(1)

                        # iframe 내용 추출 (네이버 블로그는 iframe 사용)
                        try:
                            iframe = await self._page.query_selector('#mainFrame')
                            if iframe:
                                frame = await iframe.content_frame()
                                if frame:
                                    content = await frame.content()
                                else:
                                    content = await self._page.content()
                            else:
                                content = await self._page.content()
                        except:
                            content = await self._page.content()

                        soup = BeautifulSoup(content, 'html.parser')
                        text = soup.get_text()

                        # 연락처 추출
                        emails = self._extract_emails(text)
                        for email in emails:
                            contacts.append({
                                'email': email,
                                'source': ContactSource.POST,
                                'source_url': href
                            })

                        phones = self._extract_phones(text)
                        for phone in phones:
                            contacts.append({
                                'phone': phone,
                                'source': ContactSource.POST,
                                'source_url': href
                            })

                        instagrams = self._extract_instagram(text)
                        for ig in instagrams:
                            contacts.append({
                                'instagram': ig,
                                'source': ContactSource.POST,
                                'source_url': href
                            })

                    except Exception as e:
                        logger.debug(f"포스팅 연락처 추출 오류: {e}")
                        continue

                await asyncio.sleep(1)

        except Exception as e:
            logger.debug(f"포스팅 검색 오류: {e}")

        return contacts

    def _extract_emails(self, text: str) -> List[str]:
        """텍스트에서 이메일 추출"""
        emails = set()
        for pattern in self.EMAIL_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # 정규화
                email = match.lower().strip()
                email = re.sub(r'\s+', '', email)
                email = email.replace('(at)', '@').replace('[at]', '@')

                # 유효성 검사
                if self._is_valid_email(email):
                    emails.add(email)

        return list(emails)

    def _extract_phones(self, text: str) -> List[str]:
        """텍스트에서 전화번호 추출"""
        phones = set()
        for pattern in self.PHONE_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                # 정규화
                phone = re.sub(r'[^0-9]', '', match)
                if len(phone) >= 10:
                    phones.add(phone)

        return list(phones)

    def _extract_instagram(self, text: str) -> List[str]:
        """텍스트에서 인스타그램 추출"""
        instagrams = set()
        for pattern in self.INSTAGRAM_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                ig = match.lower().strip()
                if len(ig) >= 3 and ig not in ['instagram', 'insta', 'ig']:
                    instagrams.add(ig)

        return list(instagrams)

    def _is_valid_email(self, email: str, allow_naver: bool = False) -> bool:
        """이메일 유효성 검사

        Args:
            email: 검사할 이메일 주소
            allow_naver: naver.com 도메인 허용 여부 (블로그 ID 기반 이메일용)
        """
        # 기본 형식 체크
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return False

        # 제외할 도메인
        excluded_domains = [
            'example.com', 'test.com', 'localhost',
        ]

        # naver.com은 allow_naver가 False일 때만 제외
        if not allow_naver:
            excluded_domains.append('naver.com')

        domain = email.split('@')[1].lower()
        if domain in excluded_domains:
            return False

        return True

    def _generate_naver_email(self, naver_blog_id: str) -> str:
        """네이버 블로그 ID로 네이버 이메일 주소 생성

        네이버 블로그 ID는 대부분 네이버 계정 ID와 동일하므로
        blogId@naver.com 형태로 이메일 발송 가능
        """
        # 블로그 ID 정규화 (소문자, 특수문자 제거)
        clean_id = naver_blog_id.lower().strip()
        return f"{clean_id}@naver.com"

    async def _save_contacts(
        self,
        blog: NaverBlog,
        contacts: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """추출된 연락처를 DB에 저장"""
        saved = []
        seen_emails = set()
        seen_phones = set()
        seen_instagrams = set()

        # 블로그 ID 기반 네이버 이메일을 가장 먼저 처리 (primary로 설정하기 위해)
        naver_id_emails = [c for c in contacts if c.get('is_naver_id_email')]
        other_contacts = [c for c in contacts if not c.get('is_naver_id_email')]
        sorted_contacts = naver_id_emails + other_contacts

        for contact_data in sorted_contacts:
            try:
                email = contact_data.get('email')
                phone = contact_data.get('phone')
                instagram = contact_data.get('instagram')
                is_naver_id_email = contact_data.get('is_naver_id_email', False)

                # 중복 체크
                if email and email in seen_emails:
                    continue
                if phone and phone in seen_phones:
                    continue
                if instagram and instagram in seen_instagrams:
                    continue

                # 기존 연락처 확인
                existing_query = select(BlogContact).where(BlogContact.blog_id == blog.id)
                if email:
                    existing_query = existing_query.where(BlogContact.email == email)
                elif phone:
                    existing_query = existing_query.where(BlogContact.phone == phone)
                elif instagram:
                    existing_query = existing_query.where(BlogContact.instagram == instagram)

                existing = await self.db.execute(existing_query)
                if existing.scalar_one_or_none():
                    continue

                # 새 연락처 저장
                contact = BlogContact(
                    blog_id=blog.id,
                    email=email,
                    phone=phone,
                    instagram=instagram,
                    youtube=contact_data.get('youtube'),
                    kakao_channel=contact_data.get('kakao_channel'),
                    source=contact_data.get('source', ContactSource.OTHER),
                    source_url=contact_data.get('source_url'),
                    is_primary=len(saved) == 0,  # 첫 번째 연락처를 primary로 (네이버 ID 이메일 우선)
                    is_verified=False  # 네이버 ID 이메일은 검증되지 않은 상태로 시작
                )
                self.db.add(contact)

                saved_info = {
                    'email': email,
                    'phone': phone,
                    'instagram': instagram,
                    'source': contact_data.get('source', ContactSource.OTHER).value
                }
                if is_naver_id_email:
                    saved_info['is_naver_id_email'] = True

                saved.append(saved_info)

                if email:
                    seen_emails.add(email)
                if phone:
                    seen_phones.add(phone)
                if instagram:
                    seen_instagrams.add(instagram)

            except Exception as e:
                logger.debug(f"연락처 저장 오류: {e}")

        await self.db.commit()
        return saved

    async def extract_contacts_batch(
        self,
        user_id: str,
        limit: int = 50,
        auto_generate_naver_email: bool = True
    ) -> Dict[str, Any]:
        """
        연락처가 없는 블로그들에서 일괄 추출

        Args:
            user_id: 사용자 ID
            limit: 최대 처리 개수
            auto_generate_naver_email: 블로그 ID 기반 네이버 이메일 자동 생성 여부

        Returns:
            추출 결과
        """
        try:
            # 연락처가 없는 블로그 조회
            result = await self.db.execute(
                select(NaverBlog).where(
                    and_(
                        NaverBlog.user_id == user_id,
                        NaverBlog.has_contact == False,
                        NaverBlog.status == BlogStatus.NEW
                    )
                ).limit(limit)
            )
            blogs = result.scalars().all()

            if not blogs:
                return {
                    "success": True,
                    "processed": 0,
                    "with_contacts": 0,
                    "naver_emails_generated": 0,
                    "message": "처리할 블로그가 없습니다"
                }

            total_contacts = 0
            naver_emails = 0
            processed = 0
            errors = 0

            for blog in blogs:
                try:
                    extract_result = await self.extract_contacts(
                        blog.id,
                        user_id,
                        auto_generate_naver_email=auto_generate_naver_email
                    )
                    if extract_result.get('success'):
                        contacts_count = extract_result.get('contacts_found', 0)
                        total_contacts += contacts_count
                        processed += 1

                        # 네이버 이메일 생성 여부 체크
                        if extract_result.get('naver_email_generated'):
                            naver_emails += 1
                    else:
                        errors += 1

                    # 딜레이 (네이버 이메일만 사용하는 경우 딜레이 최소화)
                    if self._page:
                        await asyncio.sleep(2)
                    else:
                        await asyncio.sleep(0.1)  # Playwright 없이 네이버 이메일만 생성하면 빠름

                except Exception as e:
                    logger.error(f"블로그 연락처 추출 오류 ({blog.id}): {e}")
                    errors += 1

            return {
                "success": True,
                "processed": processed,
                "with_contacts": total_contacts,
                "naver_emails_generated": naver_emails,
                "errors": errors
            }

        except Exception as e:
            logger.error(f"일괄 연락처 추출 오류: {e}")
            return {"success": False, "error": str(e)}


# 싱글톤
_extractor_instances: Dict[str, ContactExtractorService] = {}


async def get_contact_extractor(db: AsyncSession, user_id: str) -> ContactExtractorService:
    """사용자별 추출기 인스턴스 반환"""
    if user_id not in _extractor_instances:
        _extractor_instances[user_id] = ContactExtractorService(db)
    else:
        _extractor_instances[user_id].db = db
    return _extractor_instances[user_id]
