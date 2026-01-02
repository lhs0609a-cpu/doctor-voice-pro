"""
리드 이메일 추출 서비스
웹사이트 크롤링, 네이버 플레이스, 검색을 통한 이메일 수집
"""
import asyncio
import aiohttp
import re
import logging
from typing import List, Optional, Dict, Any, Set
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from datetime import datetime

logger = logging.getLogger(__name__)


class LeadEmailExtractor:
    """리드 이메일 추출기"""

    # 이메일 정규식 패턴
    EMAIL_PATTERN = re.compile(
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        re.IGNORECASE
    )

    # 제외할 이메일 도메인 (일반적인 예시 이메일)
    EXCLUDED_DOMAINS = {
        'example.com', 'test.com', 'sample.com', 'domain.com',
        'email.com', 'mail.com', 'yourcompany.com', 'company.com'
    }

    # 제외할 이메일 패턴 (일반적인 예시)
    EXCLUDED_PATTERNS = {
        'test@', 'example@', 'sample@', 'demo@', 'admin@example',
        'info@example', 'your@', 'name@', 'user@', 'email@'
    }

    # 우선순위 이메일 키워드 (비즈니스 이메일 가능성 높음)
    PRIORITY_KEYWORDS = ['contact', 'info', 'business', 'sales', 'inquiry', 'support', 'hello', 'admin', 'office']

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        """aiohttp 세션 가져오기"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout, headers=self.headers)
        return self.session

    async def close(self):
        """세션 닫기"""
        if self.session and not self.session.closed:
            await self.session.close()

    def _is_valid_email(self, email: str) -> bool:
        """유효한 비즈니스 이메일인지 확인"""
        email_lower = email.lower()

        # 도메인 확인
        domain = email_lower.split('@')[-1]
        if domain in self.EXCLUDED_DOMAINS:
            return False

        # 패턴 확인
        for pattern in self.EXCLUDED_PATTERNS:
            if pattern in email_lower:
                return False

        # 너무 짧거나 긴 이메일 제외
        if len(email) < 6 or len(email) > 100:
            return False

        # 숫자로만 된 로컬 파트 제외
        local_part = email_lower.split('@')[0]
        if local_part.isdigit():
            return False

        return True

    def _extract_emails_from_text(self, text: str) -> Set[str]:
        """텍스트에서 이메일 추출"""
        emails = set()
        matches = self.EMAIL_PATTERN.findall(text)

        for email in matches:
            email = email.lower().strip()
            if self._is_valid_email(email):
                emails.add(email)

        return emails

    def _prioritize_emails(self, emails: Set[str]) -> List[str]:
        """이메일 우선순위 정렬"""
        priority_emails = []
        normal_emails = []

        for email in emails:
            local_part = email.split('@')[0].lower()
            is_priority = any(kw in local_part for kw in self.PRIORITY_KEYWORDS)

            if is_priority:
                priority_emails.append(email)
            else:
                normal_emails.append(email)

        # 우선순위 이메일 먼저, 그 다음 일반 이메일
        return priority_emails + normal_emails

    async def extract_from_website(self, url: str, max_pages: int = 5) -> Dict[str, Any]:
        """웹사이트에서 이메일 추출"""
        result = {
            "success": False,
            "emails": [],
            "source_url": url,
            "pages_crawled": 0,
            "error": None
        }

        if not url:
            result["error"] = "URL이 없습니다"
            return result

        # URL 정규화
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        try:
            session = await self._get_session()
            all_emails: Set[str] = set()
            visited_urls: Set[str] = set()
            urls_to_visit = [url]
            base_domain = urlparse(url).netloc

            while urls_to_visit and len(visited_urls) < max_pages:
                current_url = urls_to_visit.pop(0)

                if current_url in visited_urls:
                    continue

                try:
                    async with session.get(current_url, ssl=False) as response:
                        if response.status != 200:
                            continue

                        content_type = response.headers.get('Content-Type', '')
                        if 'text/html' not in content_type:
                            continue

                        html = await response.text()
                        visited_urls.add(current_url)
                        result["pages_crawled"] += 1

                        # 이메일 추출
                        emails = self._extract_emails_from_text(html)
                        all_emails.update(emails)

                        # 추가 페이지 링크 수집 (연락처, 회사소개 등)
                        soup = BeautifulSoup(html, 'html.parser')

                        # mailto: 링크에서 이메일 추출
                        for mailto in soup.find_all('a', href=re.compile(r'^mailto:')):
                            href = mailto.get('href', '')
                            email_match = self.EMAIL_PATTERN.search(href)
                            if email_match:
                                email = email_match.group().lower()
                                if self._is_valid_email(email):
                                    all_emails.add(email)

                        # 관련 페이지 링크 수집
                        contact_keywords = ['contact', 'about', 'company', '연락', '문의', '회사소개', '오시는길']
                        for link in soup.find_all('a', href=True):
                            href = link.get('href', '')
                            link_text = link.get_text().lower()

                            # 키워드가 포함된 링크
                            if any(kw in href.lower() or kw in link_text for kw in contact_keywords):
                                full_url = urljoin(current_url, href)
                                parsed = urlparse(full_url)

                                # 같은 도메인만
                                if parsed.netloc == base_domain and full_url not in visited_urls:
                                    urls_to_visit.append(full_url)

                except Exception as e:
                    logger.debug(f"페이지 크롤링 오류 ({current_url}): {e}")
                    continue

                # 요청 간격
                await asyncio.sleep(0.5)

            result["success"] = True
            result["emails"] = self._prioritize_emails(all_emails)

        except Exception as e:
            logger.error(f"웹사이트 크롤링 오류: {e}")
            result["error"] = str(e)

        return result

    async def extract_from_naver_place(self, place_name: str, address: str) -> Dict[str, Any]:
        """네이버 플레이스에서 이메일/연락처 추출"""
        result = {
            "success": False,
            "emails": [],
            "phone": None,
            "website": None,
            "error": None
        }

        try:
            session = await self._get_session()

            # 네이버 플레이스 검색
            search_query = f"{place_name} {address}"
            search_url = f"https://search.naver.com/search.naver?query={search_query}"

            async with session.get(search_url, ssl=False) as response:
                if response.status != 200:
                    result["error"] = "검색 실패"
                    return result

                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')

                # 플레이스 정보 추출
                # 전화번호
                phone_patterns = [
                    r'tel:(\d{2,4}-\d{3,4}-\d{4})',
                    r'(\d{2,4}-\d{3,4}-\d{4})',
                    r'(\d{2,4}\.\d{3,4}\.\d{4})'
                ]
                for pattern in phone_patterns:
                    match = re.search(pattern, html)
                    if match:
                        result["phone"] = match.group(1) if match.lastindex else match.group()
                        break

                # 웹사이트 링크
                for link in soup.find_all('a', href=True):
                    href = link.get('href', '')
                    if 'homepage' in href.lower() or link.get_text().strip() in ['홈페이지', '웹사이트', 'Homepage']:
                        # 리다이렉트 URL에서 실제 URL 추출
                        if 'url=' in href:
                            import urllib.parse
                            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                            if 'url' in parsed:
                                result["website"] = parsed['url'][0]
                                break
                        elif href.startswith('http'):
                            result["website"] = href
                            break

                # 이메일 추출
                emails = self._extract_emails_from_text(html)
                result["emails"] = self._prioritize_emails(emails)

                # 웹사이트가 있으면 거기서도 이메일 추출
                if result["website"]:
                    website_result = await self.extract_from_website(result["website"], max_pages=3)
                    if website_result["success"] and website_result["emails"]:
                        result["emails"] = list(set(result["emails"] + website_result["emails"]))

                result["success"] = True

        except Exception as e:
            logger.error(f"네이버 플레이스 추출 오류: {e}")
            result["error"] = str(e)

        return result

    async def extract_from_search(self, business_name: str, address: str) -> Dict[str, Any]:
        """검색을 통한 이메일 추출"""
        result = {
            "success": False,
            "emails": [],
            "sources": [],
            "error": None
        }

        try:
            session = await self._get_session()
            all_emails: Set[str] = set()

            # 검색 쿼리 조합
            search_queries = [
                f"{business_name} 이메일",
                f"{business_name} {address} 연락처",
                f"{business_name} contact email"
            ]

            for query in search_queries[:2]:  # 처음 2개 쿼리만
                try:
                    # 네이버 검색
                    search_url = f"https://search.naver.com/search.naver?query={query}"

                    async with session.get(search_url, ssl=False) as response:
                        if response.status == 200:
                            html = await response.text()
                            emails = self._extract_emails_from_text(html)
                            all_emails.update(emails)

                            if emails:
                                result["sources"].append(f"네이버 검색: {query}")

                except Exception as e:
                    logger.debug(f"검색 오류 ({query}): {e}")

                await asyncio.sleep(1)

            result["success"] = True
            result["emails"] = self._prioritize_emails(all_emails)

        except Exception as e:
            logger.error(f"검색 추출 오류: {e}")
            result["error"] = str(e)

        return result

    async def extract_email_for_lead(
        self,
        business_name: str,
        address: str,
        website: Optional[str] = None,
        phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """리드의 이메일 종합 추출"""
        result = {
            "success": False,
            "email": None,
            "all_emails": [],
            "website": website,
            "phone": phone,
            "extraction_methods": [],
            "error": None
        }

        all_emails: Set[str] = set()

        try:
            # 1. 웹사이트가 있으면 웹사이트에서 추출
            if website:
                website_result = await self.extract_from_website(website)
                if website_result["success"] and website_result["emails"]:
                    all_emails.update(website_result["emails"])
                    result["extraction_methods"].append("website")

            # 2. 네이버 플레이스 검색
            if not all_emails:
                place_result = await self.extract_from_naver_place(business_name, address)
                if place_result["success"]:
                    if place_result["emails"]:
                        all_emails.update(place_result["emails"])
                        result["extraction_methods"].append("naver_place")
                    if place_result["website"] and not result["website"]:
                        result["website"] = place_result["website"]
                    if place_result["phone"] and not result["phone"]:
                        result["phone"] = place_result["phone"]

            # 3. 검색을 통한 추출
            if not all_emails:
                search_result = await self.extract_from_search(business_name, address)
                if search_result["success"] and search_result["emails"]:
                    all_emails.update(search_result["emails"])
                    result["extraction_methods"].append("search")

            # 결과 정리
            prioritized = self._prioritize_emails(all_emails)
            result["all_emails"] = prioritized
            result["email"] = prioritized[0] if prioritized else None
            result["success"] = True

        except Exception as e:
            logger.error(f"리드 이메일 추출 오류: {e}")
            result["error"] = str(e)

        return result

    async def batch_extract(
        self,
        leads: List[Dict[str, Any]],
        max_concurrent: int = 3
    ) -> List[Dict[str, Any]]:
        """배치 이메일 추출"""
        results = []
        semaphore = asyncio.Semaphore(max_concurrent)

        async def extract_one(lead: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                extraction = await self.extract_email_for_lead(
                    business_name=lead.get("business_name", ""),
                    address=lead.get("address", ""),
                    website=lead.get("website"),
                    phone=lead.get("phone")
                )
                return {
                    "lead_id": lead.get("id"),
                    "business_name": lead.get("business_name"),
                    **extraction
                }

        tasks = [extract_one(lead) for lead in leads]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 예외 처리
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "lead_id": leads[i].get("id"),
                    "business_name": leads[i].get("business_name"),
                    "success": False,
                    "error": str(result)
                })
            else:
                processed_results.append(result)

        return processed_results


# 싱글톤 인스턴스
lead_email_extractor = LeadEmailExtractor()
