"""
네이버 카페 게시글 크롤러
httpx + BeautifulSoup 기반
"""

import asyncio
import logging
import random
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode, quote_plus

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class CafeCrawlerService:
    """네이버 카페 크롤러"""

    # User-Agent 로테이션
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]

    # 요청 간 딜레이 범위 (초)
    REQUEST_DELAY = (2, 5)

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """HTTP 클라이언트 반환"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers=self._get_headers()
            )
        return self._client

    def _get_headers(self) -> Dict[str, str]:
        """랜덤 헤더 생성"""
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    async def _delay(self):
        """랜덤 딜레이"""
        delay = random.uniform(*self.REQUEST_DELAY)
        await asyncio.sleep(delay)

    async def close(self):
        """클라이언트 종료"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def search_cafe_posts(
        self,
        cafe_id: str,
        keyword: str,
        limit: int = 20,
        sort: str = "date",  # date, sim (유사도)
        search_type: str = "0",  # 0: 전체, 1: 제목만, 2: 글작성자
        page: int = 1
    ) -> List[Dict[str, Any]]:
        """
        카페 내 게시글 검색

        Args:
            cafe_id: 카페 ID (URL의 카페명)
            keyword: 검색 키워드
            limit: 최대 수집 개수
            sort: 정렬 방식 (date/sim)
            search_type: 검색 범위
            page: 페이지 번호

        Returns:
            게시글 목록
        """
        try:
            client = await self._get_client()
            posts = []

            # 카페 검색 URL
            params = {
                "query": keyword,
                "searchBy": search_type,
                "sortBy": sort,
                "page": page,
            }

            url = f"https://cafe.naver.com/{cafe_id}"
            search_url = f"https://cafe.naver.com/ArticleSearchList.nhn?search.clubid=&search.media=0&search.searchdate=&search.exact=&search.include=&search.exclude=&search.query={quote_plus(keyword)}&search.searchBy={search_type}&search.sortBy={sort}&search.page={page}"

            # 먼저 카페 메인 페이지에서 clubid 추출
            response = await client.get(url, headers=self._get_headers())
            if response.status_code != 200:
                logger.error(f"카페 접근 실패: {cafe_id}, status={response.status_code}")
                return []

            # clubid 추출
            club_id = self._extract_club_id(response.text)
            if not club_id:
                logger.error(f"clubid 추출 실패: {cafe_id}")
                return []

            await self._delay()

            # 검색 실행 (모바일 버전이 더 파싱하기 쉬움)
            mobile_search_url = f"https://m.cafe.naver.com/ArticleSearchList.nhn?search.clubid={club_id}&search.query={quote_plus(keyword)}&search.sortBy={sort}&search.page={page}"

            response = await client.get(mobile_search_url, headers=self._get_headers())
            if response.status_code != 200:
                logger.error(f"검색 실패: status={response.status_code}")
                return []

            # HTML 파싱
            posts = self._parse_search_results(response.text, cafe_id, club_id)

            logger.info(f"카페 검색 완료: cafe={cafe_id}, keyword={keyword}, 결과={len(posts)}개")
            return posts[:limit]

        except Exception as e:
            logger.error(f"카페 검색 중 오류: {e}")
            return []

    def _extract_club_id(self, html: str) -> Optional[str]:
        """HTML에서 clubid 추출"""
        # 정규식으로 clubid 찾기
        patterns = [
            r'clubid["\s:=]+(\d+)',
            r'club\.id["\s:=]+(\d+)',
            r'cafeId["\s:=]+(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _parse_search_results(self, html: str, cafe_id: str, club_id: str) -> List[Dict[str, Any]]:
        """검색 결과 파싱"""
        soup = BeautifulSoup(html, "html.parser")
        posts = []

        # 게시글 목록 찾기
        article_items = soup.select(".article-board li") or \
                       soup.select(".board-list li") or \
                       soup.select(".article_lst li") or \
                       soup.select("ul.article_list li")

        for item in article_items:
            try:
                post = self._parse_post_item(item, cafe_id, club_id)
                if post:
                    posts.append(post)
            except Exception as e:
                logger.debug(f"게시글 파싱 오류: {e}")
                continue

        return posts

    def _parse_post_item(self, item, cafe_id: str, club_id: str) -> Optional[Dict[str, Any]]:
        """개별 게시글 항목 파싱"""
        # 제목 추출
        title_elem = item.select_one(".article-title") or \
                    item.select_one(".tit") or \
                    item.select_one("a.txt") or \
                    item.select_one(".board-txt a")

        if not title_elem:
            return None

        title = title_elem.get_text(strip=True)

        # 링크에서 article_id 추출
        link = title_elem.get("href", "")
        article_id = self._extract_article_id(link)

        if not article_id:
            return None

        # URL 생성
        url = f"https://cafe.naver.com/{cafe_id}/{article_id}"

        # 작성자
        author_elem = item.select_one(".nick") or \
                     item.select_one(".user") or \
                     item.select_one(".p-nick")
        author_name = author_elem.get_text(strip=True) if author_elem else ""

        # 날짜
        date_elem = item.select_one(".date") or \
                   item.select_one(".time") or \
                   item.select_one(".datetime")
        posted_at = self._parse_date(date_elem.get_text(strip=True) if date_elem else "")

        # 조회수
        view_elem = item.select_one(".view") or \
                   item.select_one(".read") or \
                   item.select_one(".hit")
        view_count = self._parse_number(view_elem.get_text(strip=True) if view_elem else "0")

        # 댓글수
        comment_elem = item.select_one(".comment") or \
                      item.select_one(".reply") or \
                      item.select_one(".cmt")
        comment_count = self._parse_number(comment_elem.get_text(strip=True) if comment_elem else "0")

        # 좋아요수
        like_elem = item.select_one(".like") or \
                   item.select_one(".likeit")
        like_count = self._parse_number(like_elem.get_text(strip=True) if like_elem else "0")

        # 게시판 정보
        board_elem = item.select_one(".board-name") or \
                    item.select_one(".menu") or \
                    item.select_one(".board")
        board_name = board_elem.get_text(strip=True) if board_elem else ""

        # 미리보기 내용
        preview_elem = item.select_one(".article-summary") or \
                      item.select_one(".txt") or \
                      item.select_one(".desc")
        content_preview = preview_elem.get_text(strip=True) if preview_elem else ""

        return {
            "naver_post_id": f"{club_id}_{article_id}",
            "article_id": article_id,
            "title": title,
            "content_preview": content_preview,
            "url": url,
            "author_name": author_name,
            "board_name": board_name,
            "view_count": view_count,
            "comment_count": comment_count,
            "like_count": like_count,
            "posted_at": posted_at,
            "cafe_id": cafe_id,
            "club_id": club_id,
        }

    def _extract_article_id(self, link: str) -> Optional[str]:
        """링크에서 article_id 추출"""
        # /cafename/123 형태
        match = re.search(r'/(\d+)(?:\?|$)', link)
        if match:
            return match.group(1)

        # articleid=123 형태
        match = re.search(r'articleid=(\d+)', link, re.IGNORECASE)
        if match:
            return match.group(1)

        return None

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """날짜 문자열 파싱"""
        if not date_str:
            return None

        date_str = date_str.strip()

        # 방금 전, N분 전, N시간 전
        if "방금" in date_str:
            return datetime.now()

        match = re.search(r'(\d+)분\s*전', date_str)
        if match:
            return datetime.now() - timedelta(minutes=int(match.group(1)))

        match = re.search(r'(\d+)시간\s*전', date_str)
        if match:
            return datetime.now() - timedelta(hours=int(match.group(1)))

        match = re.search(r'(\d+)일\s*전', date_str)
        if match:
            return datetime.now() - timedelta(days=int(match.group(1)))

        # YYYY.MM.DD 형태
        match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', date_str)
        if match:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))

        # MM.DD 형태 (올해로 가정)
        match = re.search(r'(\d{1,2})\.(\d{1,2})\.?$', date_str)
        if match:
            return datetime(datetime.now().year, int(match.group(1)), int(match.group(2)))

        return None

    def _parse_number(self, num_str: str) -> int:
        """숫자 문자열 파싱"""
        if not num_str:
            return 0

        # 숫자만 추출
        numbers = re.findall(r'\d+', num_str)
        if numbers:
            return int(numbers[0])
        return 0

    async def get_post_detail(
        self,
        cafe_id: str,
        article_id: str,
        club_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        게시글 상세 정보 수집

        Args:
            cafe_id: 카페 ID
            article_id: 글 번호
            club_id: 카페 고유 ID (없으면 자동 추출)

        Returns:
            게시글 상세 정보
        """
        try:
            client = await self._get_client()

            # 모바일 버전이 파싱하기 쉬움
            url = f"https://m.cafe.naver.com/ca-fe/web/cafes/{cafe_id}/articles/{article_id}"

            response = await client.get(url, headers=self._get_headers())
            if response.status_code != 200:
                logger.error(f"게시글 조회 실패: {url}, status={response.status_code}")
                return None

            soup = BeautifulSoup(response.text, "html.parser")

            # 제목
            title_elem = soup.select_one(".tit_area h2") or \
                        soup.select_one(".article_header .tit") or \
                        soup.select_one(".ArticleTitle")
            title = title_elem.get_text(strip=True) if title_elem else ""

            # 본문
            content_elem = soup.select_one(".article_container") or \
                          soup.select_one(".article_viewer") or \
                          soup.select_one(".ContentRenderer")
            content = ""
            if content_elem:
                # 불필요한 요소 제거
                for elem in content_elem.select("script, style, .comment"):
                    elem.decompose()
                content = content_elem.get_text(separator="\n", strip=True)

            # 작성자
            author_elem = soup.select_one(".nick_box") or \
                         soup.select_one(".article_writer .nick")
            author_name = author_elem.get_text(strip=True) if author_elem else ""

            # 작성일
            date_elem = soup.select_one(".date") or \
                       soup.select_one(".article_info .date")
            posted_at = self._parse_date(date_elem.get_text(strip=True) if date_elem else "")

            # 조회수
            view_elem = soup.select_one(".view_count") or \
                       soup.select_one(".article_info .no")
            view_count = self._parse_number(view_elem.get_text() if view_elem else "0")

            # 좋아요
            like_elem = soup.select_one(".like_count") or \
                       soup.select_one(".sympathyBtn .num")
            like_count = self._parse_number(like_elem.get_text() if like_elem else "0")

            # 댓글 수집
            comments = await self._get_comments(cafe_id, article_id, club_id)

            return {
                "naver_post_id": f"{club_id or cafe_id}_{article_id}",
                "article_id": article_id,
                "title": title,
                "content": content,
                "url": f"https://cafe.naver.com/{cafe_id}/{article_id}",
                "author_name": author_name,
                "view_count": view_count,
                "like_count": like_count,
                "posted_at": posted_at,
                "comment_count": len(comments),
                "comments": comments,
            }

        except Exception as e:
            logger.error(f"게시글 상세 조회 오류: {e}")
            return None

    async def _get_comments(
        self,
        cafe_id: str,
        article_id: str,
        club_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """게시글 댓글 수집"""
        try:
            if not club_id:
                return []

            client = await self._get_client()

            # 댓글 API (AJAX)
            url = f"https://apis.naver.com/cafe-web/cafe-mobile/CommentList"
            params = {
                "cafeId": club_id,
                "articleId": article_id,
                "page": 1,
                "pageSize": 50,
            }

            response = await client.get(url, params=params, headers=self._get_headers())
            if response.status_code != 200:
                return []

            data = response.json()
            comments = []

            for item in data.get("result", {}).get("comments", []):
                comments.append({
                    "comment_id": item.get("commentId"),
                    "content": item.get("content", ""),
                    "author_name": item.get("writerNickname", ""),
                    "created_at": item.get("writeDate"),
                    "like_count": item.get("likeCount", 0),
                    "reply_count": item.get("replyCount", 0),
                })

            return comments

        except Exception as e:
            logger.debug(f"댓글 수집 오류: {e}")
            return []

    async def get_recent_posts(
        self,
        cafe_id: str,
        board_id: Optional[str] = None,
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """
        최근 게시글 목록

        Args:
            cafe_id: 카페 ID
            board_id: 게시판 ID (None이면 전체)
            limit: 최대 수집 개수

        Returns:
            게시글 목록
        """
        try:
            client = await self._get_client()

            if board_id:
                url = f"https://m.cafe.naver.com/ArticleList.nhn?search.clubid=&search.menuid={board_id}"
            else:
                url = f"https://m.cafe.naver.com/{cafe_id}"

            response = await client.get(url, headers=self._get_headers())
            if response.status_code != 200:
                return []

            # clubid 추출
            club_id = self._extract_club_id(response.text)

            posts = self._parse_search_results(response.text, cafe_id, club_id or "")
            return posts[:limit]

        except Exception as e:
            logger.error(f"최근 게시글 조회 오류: {e}")
            return []

    async def search_across_cafes(
        self,
        cafes: List[Dict[str, str]],  # [{"cafe_id": "xxx", "club_id": "123"}, ...]
        keywords: List[str],
        limit_per_cafe: int = 10,
        total_limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        여러 카페 동시 검색

        Args:
            cafes: 카페 목록
            keywords: 키워드 목록
            limit_per_cafe: 카페당 최대 수집 개수
            total_limit: 전체 최대 개수

        Returns:
            수집된 게시글 목록
        """
        all_posts = []
        seen_ids = set()

        for cafe in cafes:
            cafe_id = cafe.get("cafe_id")
            if not cafe_id:
                continue

            for keyword in keywords:
                try:
                    posts = await self.search_cafe_posts(
                        cafe_id=cafe_id,
                        keyword=keyword,
                        limit=limit_per_cafe
                    )

                    for post in posts:
                        post_id = post.get("naver_post_id")
                        if post_id and post_id not in seen_ids:
                            seen_ids.add(post_id)
                            post["matched_keyword"] = keyword
                            all_posts.append(post)

                    await self._delay()

                    if len(all_posts) >= total_limit:
                        break

                except Exception as e:
                    logger.error(f"카페 검색 오류: cafe={cafe_id}, keyword={keyword}, error={e}")
                    continue

            if len(all_posts) >= total_limit:
                break

        # 최신순 정렬
        all_posts.sort(key=lambda x: x.get("posted_at") or datetime.min, reverse=True)
        return all_posts[:total_limit]

    async def verify_cafe_access(self, cafe_id: str) -> Dict[str, Any]:
        """
        카페 접근 가능 여부 확인

        Args:
            cafe_id: 카페 ID

        Returns:
            {accessible: bool, cafe_name: str, member_count: int, ...}
        """
        try:
            client = await self._get_client()
            url = f"https://cafe.naver.com/{cafe_id}"

            response = await client.get(url, headers=self._get_headers())

            if response.status_code != 200:
                return {"accessible": False, "error": f"HTTP {response.status_code}"}

            soup = BeautifulSoup(response.text, "html.parser")

            # 카페 이름
            name_elem = soup.select_one(".cafe-title") or \
                       soup.select_one(".tit_cafe") or \
                       soup.select_one("h1.cafe_name")
            cafe_name = name_elem.get_text(strip=True) if name_elem else cafe_id

            # 회원수
            member_elem = soup.select_one(".mem_cnt") or \
                         soup.select_one(".member_count")
            member_count = self._parse_number(member_elem.get_text() if member_elem else "0")

            # club_id
            club_id = self._extract_club_id(response.text)

            # 비공개 카페 확인
            if "비공개" in response.text or "가입 후 이용" in response.text:
                return {
                    "accessible": False,
                    "cafe_name": cafe_name,
                    "club_id": club_id,
                    "error": "비공개 카페 또는 가입 필요"
                }

            return {
                "accessible": True,
                "cafe_name": cafe_name,
                "club_id": club_id,
                "member_count": member_count,
            }

        except Exception as e:
            logger.error(f"카페 접근 확인 오류: {e}")
            return {"accessible": False, "error": str(e)}


# 전역 인스턴스
cafe_crawler = CafeCrawlerService()
