"""
네이버 지식인 크롤러 서비스
키워드 기반 질문 검색 및 수집
"""

import re
import random
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import urlencode, urlparse, parse_qs

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class KinCrawlerService:
    """네이버 지식인 크롤러"""

    def __init__(self):
        self.base_url = "https://kin.naver.com"
        self.search_url = "https://kin.naver.com/search/list.naver"
        self.detail_url = "https://kin.naver.com/qna/detail.naver"

        # User-Agent 로테이션
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        ]

        self.default_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        # 요청 간격 (초)
        self.min_delay = 2
        self.max_delay = 5

    def _get_headers(self) -> Dict[str, str]:
        """랜덤 User-Agent로 헤더 생성"""
        headers = self.default_headers.copy()
        headers["User-Agent"] = random.choice(self.user_agents)
        return headers

    async def _delay(self):
        """요청 간 랜덤 딜레이"""
        delay = random.uniform(self.min_delay, self.max_delay)
        await asyncio.sleep(delay)

    async def search_questions(
        self,
        keyword: str,
        limit: int = 20,
        sort: str = "date",  # date: 최신순, point: 내공순
        period: str = "all",  # all, 1d, 1w, 1m, 6m, 1y
        answered: Optional[bool] = None,  # None: 전체, False: 미답변만
    ) -> List[Dict[str, Any]]:
        """
        키워드로 지식인 질문 검색

        Args:
            keyword: 검색 키워드
            limit: 최대 수집 개수
            sort: 정렬 방식 (date/point)
            period: 기간 필터
            answered: 답변 여부 필터

        Returns:
            질문 목록
        """
        questions = []
        page = 1
        per_page = 10  # 네이버 지식인 기본 페이지당 개수

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                while len(questions) < limit:
                    # 검색 파라미터 구성
                    params = {
                        "query": keyword,
                        "sort": "date" if sort == "date" else "none",
                        "section": "kin",
                        "page": page,
                    }

                    # 기간 필터
                    if period != "all":
                        params["period"] = period

                    # 미답변 필터
                    if answered is False:
                        params["answer"] = "0"

                    logger.info(f"지식인 검색: {keyword} (페이지 {page})")

                    response = await client.get(
                        self.search_url,
                        params=params,
                        headers=self._get_headers()
                    )

                    if response.status_code != 200:
                        logger.warning(f"검색 실패: HTTP {response.status_code}")
                        break

                    # HTML 파싱
                    soup = BeautifulSoup(response.text, "html.parser")
                    items = self._parse_search_results(soup)

                    if not items:
                        logger.info("더 이상 검색 결과 없음")
                        break

                    questions.extend(items)
                    page += 1

                    # 충분히 수집했으면 종료
                    if len(items) < per_page:
                        break

                    # 요청 간 딜레이
                    await self._delay()

        except Exception as e:
            logger.error(f"질문 검색 중 오류: {e}")

        return questions[:limit]

    def _parse_search_results(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """검색 결과 페이지 파싱"""
        questions = []

        # 검색 결과 리스트 찾기
        result_list = soup.select("ul.basic1 > li")

        if not result_list:
            # 새로운 검색 결과 형식 시도
            result_list = soup.select("div.search_list ul > li")

        for item in result_list:
            try:
                question = self._parse_search_item(item)
                if question:
                    questions.append(question)
            except Exception as e:
                logger.debug(f"검색 결과 항목 파싱 오류: {e}")
                continue

        return questions

    def _parse_search_item(self, item) -> Optional[Dict[str, Any]]:
        """개별 검색 결과 항목 파싱"""
        # 제목 및 URL 추출
        title_elem = item.select_one("dt a") or item.select_one(".title a")
        if not title_elem:
            return None

        title = title_elem.get_text(strip=True)
        url = title_elem.get("href", "")

        # 절대 URL로 변환
        if url.startswith("/"):
            url = f"https://kin.naver.com{url}"

        # docId 추출
        doc_id = self._extract_doc_id(url)
        if not doc_id:
            return None

        # 본문 미리보기
        content_elem = item.select_one("dd") or item.select_one(".txt")
        content_preview = content_elem.get_text(strip=True) if content_elem else ""

        # 메타 정보 추출
        meta = self._parse_meta_info(item)

        return {
            "naver_question_id": doc_id,
            "title": title,
            "content": content_preview,
            "url": url,
            "view_count": meta.get("view_count", 0),
            "answer_count": meta.get("answer_count", 0),
            "reward_points": meta.get("reward_points", 0),
            "is_chosen": meta.get("is_chosen", False),
            "question_date": meta.get("question_date"),
            "category": meta.get("category"),
            "author_name": meta.get("author_name"),
        }

    def _extract_doc_id(self, url: str) -> Optional[str]:
        """URL에서 docId 추출"""
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            doc_id = params.get("docId", [None])[0]
            return doc_id
        except:
            # URL 패턴에서 직접 추출 시도
            match = re.search(r'docId=(\d+)', url)
            if match:
                return match.group(1)
            return None

    def _parse_meta_info(self, item) -> Dict[str, Any]:
        """메타 정보 파싱 (조회수, 답변수, 내공 등)"""
        meta = {}

        # 다양한 메타 정보 셀렉터 시도
        meta_text = ""
        meta_elem = item.select_one(".info") or item.select_one(".etc")
        if meta_elem:
            meta_text = meta_elem.get_text()

        # 조회수
        view_match = re.search(r'조회\s*(\d+)', meta_text)
        if view_match:
            meta["view_count"] = int(view_match.group(1))

        # 답변수
        answer_match = re.search(r'답변\s*(\d+)', meta_text)
        if answer_match:
            meta["answer_count"] = int(answer_match.group(1))

        # 내공
        point_match = re.search(r'내공\s*(\d+)', meta_text)
        if point_match:
            meta["reward_points"] = int(point_match.group(1))

        # 채택 여부
        if "채택" in meta_text or item.select_one(".ico_best"):
            meta["is_chosen"] = True

        # 작성일
        date_elem = item.select_one(".date") or item.select_one("dd.date")
        if date_elem:
            date_text = date_elem.get_text(strip=True)
            meta["question_date"] = self._parse_date(date_text)

        # 카테고리
        category_elem = item.select_one(".dir")
        if category_elem:
            meta["category"] = category_elem.get_text(strip=True)

        # 작성자
        author_elem = item.select_one(".name") or item.select_one(".user")
        if author_elem:
            meta["author_name"] = author_elem.get_text(strip=True)

        return meta

    def _parse_date(self, date_text: str) -> Optional[datetime]:
        """날짜 텍스트 파싱"""
        try:
            # "2024.01.15." 형식
            match = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', date_text)
            if match:
                return datetime(
                    int(match.group(1)),
                    int(match.group(2)),
                    int(match.group(3))
                )

            # "1시간 전", "2일 전" 등 상대 시간
            if "분 전" in date_text:
                minutes = int(re.search(r'(\d+)', date_text).group(1))
                return datetime.utcnow()
            elif "시간 전" in date_text:
                return datetime.utcnow()
            elif "일 전" in date_text:
                return datetime.utcnow()

        except:
            pass
        return None

    async def get_question_detail(
        self,
        question_id: str,
        url: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        질문 상세 정보 수집

        Args:
            question_id: 질문 ID (docId)
            url: 질문 URL (없으면 자동 생성)

        Returns:
            상세 질문 정보
        """
        if not url:
            # 기본 URL 구성 (d1id는 알 수 없으므로 모바일 URL 사용)
            url = f"https://m.kin.naver.com/mobile/qna/detail.naver?docId={question_id}"

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url, headers=self._get_headers())

                if response.status_code != 200:
                    logger.warning(f"상세 조회 실패: HTTP {response.status_code}")
                    return None

                soup = BeautifulSoup(response.text, "html.parser")
                return self._parse_detail_page(soup, question_id)

        except Exception as e:
            logger.error(f"상세 조회 중 오류: {e}")
            return None

    def _parse_detail_page(
        self,
        soup: BeautifulSoup,
        question_id: str
    ) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        result = {
            "naver_question_id": question_id,
            "title": "",
            "content": "",
            "author_name": "",
            "author_level": "",
            "view_count": 0,
            "answer_count": 0,
            "reward_points": 0,
            "is_chosen": False,
            "is_closed": False,
            "category": "",
            "question_date": None,
        }

        # 제목
        title_elem = (
            soup.select_one("div.question h1") or
            soup.select_one(".question_title") or
            soup.select_one("h2.title")
        )
        if title_elem:
            result["title"] = title_elem.get_text(strip=True)

        # 본문
        content_elem = (
            soup.select_one("div.question_detail") or
            soup.select_one(".question_content") or
            soup.select_one("div.c-heading__content")
        )
        if content_elem:
            result["content"] = content_elem.get_text(strip=True)

        # 작성자 정보
        author_elem = soup.select_one(".questioner") or soup.select_one(".user_info")
        if author_elem:
            name_elem = author_elem.select_one(".nickname") or author_elem.select_one(".name")
            if name_elem:
                result["author_name"] = name_elem.get_text(strip=True)

            level_elem = author_elem.select_one(".grade") or author_elem.select_one(".level")
            if level_elem:
                result["author_level"] = level_elem.get_text(strip=True)

        # 조회수, 답변수, 내공
        meta_text = soup.get_text()

        view_match = re.search(r'조회\s*(\d+)', meta_text)
        if view_match:
            result["view_count"] = int(view_match.group(1))

        answer_match = re.search(r'답변\s*(\d+)', meta_text)
        if answer_match:
            result["answer_count"] = int(answer_match.group(1))

        point_match = re.search(r'내공\s*(\d+)', meta_text)
        if point_match:
            result["reward_points"] = int(point_match.group(1))

        # 채택 여부
        if soup.select_one(".ico_best") or "채택" in meta_text:
            result["is_chosen"] = True

        # 마감 여부
        if soup.select_one(".closed") or "마감" in meta_text:
            result["is_closed"] = True

        # 카테고리
        category_elem = soup.select_one(".category") or soup.select_one(".dir_txt")
        if category_elem:
            result["category"] = category_elem.get_text(strip=True)

        return result

    async def check_answerable(
        self,
        question_id: str,
        url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        답변 가능 여부 확인

        Returns:
            {
                "answerable": bool,
                "reason": str (불가 시 사유)
            }
        """
        detail = await self.get_question_detail(question_id, url)

        if not detail:
            return {
                "answerable": False,
                "reason": "질문 정보를 가져올 수 없습니다."
            }

        # 채택 완료된 질문
        if detail.get("is_chosen"):
            return {
                "answerable": False,
                "reason": "이미 채택이 완료된 질문입니다."
            }

        # 마감된 질문
        if detail.get("is_closed"):
            return {
                "answerable": False,
                "reason": "마감된 질문입니다."
            }

        return {
            "answerable": True,
            "reason": ""
        }

    async def search_and_collect(
        self,
        keywords: List[str],
        limit_per_keyword: int = 10,
        total_limit: int = 50,
        filter_answerable: bool = True,
        min_reward_points: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        여러 키워드로 질문 검색 및 수집

        Args:
            keywords: 검색 키워드 목록
            limit_per_keyword: 키워드당 최대 수집 개수
            total_limit: 전체 최대 수집 개수
            filter_answerable: 답변 가능한 질문만 필터링
            min_reward_points: 최소 내공 점수

        Returns:
            필터링된 질문 목록
        """
        all_questions = []
        seen_ids = set()

        for keyword in keywords:
            if len(all_questions) >= total_limit:
                break

            logger.info(f"키워드 '{keyword}' 검색 중...")

            questions = await self.search_questions(
                keyword=keyword,
                limit=limit_per_keyword,
                sort="date",
                answered=False if filter_answerable else None
            )

            for q in questions:
                # 중복 제거
                if q["naver_question_id"] in seen_ids:
                    continue
                seen_ids.add(q["naver_question_id"])

                # 내공 필터
                if q.get("reward_points", 0) < min_reward_points:
                    continue

                # 채택 완료 필터
                if filter_answerable and q.get("is_chosen"):
                    continue

                # 매칭 키워드 추가
                q["matched_keyword"] = keyword
                all_questions.append(q)

                if len(all_questions) >= total_limit:
                    break

            # 키워드 간 딜레이
            await self._delay()

        logger.info(f"총 {len(all_questions)}개 질문 수집 완료")
        return all_questions


# 싱글톤 인스턴스
kin_crawler = KinCrawlerService()
