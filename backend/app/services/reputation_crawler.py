"""
평판 모니터링 - 크롤러 서비스
전 플랫폼 리뷰/멘션 수집을 위한 크롤러 플러그인 구조
"""
import asyncio
import re
import uuid
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List, Dict, Any

import aiohttp
from bs4 import BeautifulSoup

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reputation import (
    MonitorProfile, Mention, ReputationCrawlJob,
    MentionPlatform, MentionSentiment, RiskLevel, MentionStatus, CrawlJobStatus
)

logger = logging.getLogger(__name__)

# 공통 HTTP 헤더
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}


class BasePlatformCrawler(ABC):
    """플랫폼 크롤러 인터페이스"""

    platform: MentionPlatform = MentionPlatform.OTHER

    def __init__(self, db: AsyncSession):
        self.db = db
        self.request_delay = 2  # 요청 간 딜레이 (초)

    @abstractmethod
    async def crawl(self, profile: MonitorProfile) -> List[Dict[str, Any]]:
        """
        프로필의 플랫폼별 ID를 사용해서 리뷰/멘션을 크롤링합니다.

        Returns:
            [{
                "platform_post_id": str,
                "source_url": str,
                "author_name": str,
                "author_id": str,
                "title": str | None,
                "content": str,
                "rating": float | None,
                "images": list | None,
                "published_at": datetime | None,
                "platform_data": dict | None,
            }]
        """
        pass

    async def save_mentions(
        self,
        profile: MonitorProfile,
        raw_mentions: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        """크롤링 결과를 Mention 테이블에 저장 (중복 제외)"""
        found = 0
        new_count = 0

        for raw in raw_mentions:
            found += 1
            platform_post_id = raw.get("platform_post_id")

            # 중복 체크
            if platform_post_id:
                existing = await self.db.execute(
                    select(Mention).where(and_(
                        Mention.profile_id == profile.id,
                        Mention.platform == self.platform,
                        Mention.platform_post_id == platform_post_id,
                    ))
                )
                if existing.scalar_one_or_none():
                    continue

            mention = Mention(
                id=str(uuid.uuid4()),
                profile_id=profile.id,
                user_id=profile.user_id,
                platform=self.platform,
                platform_post_id=platform_post_id,
                source_url=raw.get("source_url"),
                author_name=raw.get("author_name"),
                author_id=raw.get("author_id"),
                title=raw.get("title"),
                content=raw.get("content", ""),
                rating=raw.get("rating"),
                images=raw.get("images"),
                published_at=raw.get("published_at"),
                platform_data=raw.get("platform_data"),
                status=MentionStatus.NEW,
            )
            self.db.add(mention)
            new_count += 1

        if new_count > 0:
            await self.db.commit()

        return {"found": found, "new": new_count}


class NaverPlaceCrawler(BasePlatformCrawler):
    """네이버 플레이스 리뷰 크롤러"""

    platform = MentionPlatform.NAVER_PLACE

    async def crawl(self, profile: MonitorProfile) -> List[Dict[str, Any]]:
        """네이버 플레이스 리뷰 수집"""
        place_id = profile.naver_place_id
        if not place_id:
            logger.warning(f"프로필 {profile.id}: 네이버 플레이스 ID 없음")
            return []

        reviews = []

        try:
            # 네이버 플레이스 리뷰 API (비공식)
            url = f"https://pcmap-api.place.naver.com/graphql"
            payload = [
                {
                    "operationName": "getVisitorReviews",
                    "variables": {
                        "input": {
                            "businessId": place_id,
                            "bookingBusinessId": None,
                            "businessType": "restaurant",
                            "item": "0",
                            "page": 1,
                            "size": 50,
                            "isPhotoUsed": False,
                            "includeContent": True,
                            "getUserStats": True,
                            "includeReceiptPhotos": True,
                            "cidList": [],
                        },
                        "id": place_id,
                    },
                    "query": """query getVisitorReviews($input: VisitorReviewsInput) {
                        visitorReviews(input: $input) {
                            items {
                                id
                                rating
                                author {
                                    nickname
                                    from
                                    imageUrl
                                    objectId
                                    url
                                    review {
                                        totalCount
                                        imageCount
                                        avgRating
                                        created
                                    }
                                }
                                body
                                thumbnail
                                media {
                                    type
                                    thumbnail
                                }
                                tags
                                status
                                visitCount
                                viewCount
                                visited
                                created
                                reply {
                                    body
                                    editUrl
                                    created
                                    replyTitle
                                    modifyDate
                                }
                            }
                            starDistribution {
                                score
                                count
                            }
                            total
                        }
                    }"""
                }
            ]

            headers = {
                **DEFAULT_HEADERS,
                "Content-Type": "application/json",
                "Referer": f"https://pcmap.place.naver.com/restaurant/{place_id}/review/visitor",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status != 200:
                        logger.error(f"네이버 플레이스 API 응답 오류: {resp.status}")
                        # fallback: HTML 크롤링
                        return await self._crawl_html(profile, place_id)

                    data = await resp.json()

            # GraphQL 응답 파싱
            if data and isinstance(data, list) and len(data) > 0:
                visitor_reviews = data[0].get("data", {}).get("visitorReviews", {})
                items = visitor_reviews.get("items", [])

                for item in items:
                    author = item.get("author", {})
                    review_data = {
                        "platform_post_id": str(item.get("id", "")),
                        "source_url": f"https://pcmap.place.naver.com/restaurant/{place_id}/review/visitor",
                        "author_name": author.get("nickname", "익명"),
                        "author_id": author.get("objectId"),
                        "title": None,
                        "content": item.get("body", ""),
                        "rating": float(item.get("rating", 0)) if item.get("rating") else None,
                        "images": [m.get("thumbnail") for m in (item.get("media") or []) if m.get("thumbnail")],
                        "published_at": self._parse_date(item.get("created")),
                        "platform_data": {
                            "visit_count": item.get("visitCount"),
                            "view_count": item.get("viewCount"),
                            "tags": item.get("tags"),
                            "has_reply": bool(item.get("reply")),
                            "reply_body": item.get("reply", {}).get("body") if item.get("reply") else None,
                        },
                    }
                    if review_data["content"]:
                        reviews.append(review_data)

        except Exception as e:
            logger.error(f"네이버 플레이스 크롤링 오류: {e}")
            # fallback
            try:
                reviews = await self._crawl_html(profile, place_id)
            except Exception as e2:
                logger.error(f"네이버 플레이스 HTML 크롤링도 실패: {e2}")

        return reviews

    async def _crawl_html(self, profile: MonitorProfile, place_id: str) -> List[Dict[str, Any]]:
        """HTML 기반 fallback 크롤링"""
        reviews = []
        url = f"https://m.place.naver.com/restaurant/{place_id}/review/visitor"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=DEFAULT_HEADERS) as resp:
                if resp.status != 200:
                    return reviews
                html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")

        # 리뷰 항목 파싱 (네이버 모바일 구조)
        review_items = soup.select("li.pui__X35jYm")
        if not review_items:
            review_items = soup.select("[class*='review']")

        for item in review_items[:50]:
            try:
                content_el = item.select_one("[class*='text']") or item.select_one("p")
                author_el = item.select_one("[class*='nickname']") or item.select_one("[class*='name']")
                rating_el = item.select_one("[class*='star']") or item.select_one("[class*='rating']")

                content = content_el.get_text(strip=True) if content_el else ""
                if not content:
                    continue

                author_name = author_el.get_text(strip=True) if author_el else "익명"

                rating = None
                if rating_el:
                    rating_text = rating_el.get_text(strip=True)
                    rating_match = re.search(r"(\d+\.?\d*)", rating_text)
                    if rating_match:
                        rating = float(rating_match.group(1))

                reviews.append({
                    "platform_post_id": f"naver_place_{place_id}_{len(reviews)}",
                    "source_url": url,
                    "author_name": author_name,
                    "author_id": None,
                    "title": None,
                    "content": content,
                    "rating": rating,
                    "images": None,
                    "published_at": None,
                    "platform_data": None,
                })
            except Exception:
                continue

        return reviews

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            try:
                return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                return None


class GoogleMapsCrawler(BasePlatformCrawler):
    """구글 맵 리뷰 크롤러 (Phase 2)"""

    platform = MentionPlatform.GOOGLE_MAPS

    async def crawl(self, profile: MonitorProfile) -> List[Dict[str, Any]]:
        place_id = profile.google_place_id
        if not place_id:
            return []

        reviews = []
        try:
            # Google Places API 사용 (API 키 필요)
            from app.core.config import settings
            api_key = getattr(settings, "GOOGLE_PLACES_API_KEY", None)
            if not api_key:
                logger.warning("Google Places API 키가 설정되지 않았습니다.")
                return []

            url = f"https://maps.googleapis.com/maps/api/place/details/json"
            params = {
                "place_id": place_id,
                "fields": "reviews",
                "language": "ko",
                "key": api_key,
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()

            for review in data.get("result", {}).get("reviews", []):
                reviews.append({
                    "platform_post_id": f"google_{place_id}_{review.get('time', '')}",
                    "source_url": review.get("author_url"),
                    "author_name": review.get("author_name", "익명"),
                    "author_id": review.get("author_url"),
                    "title": None,
                    "content": review.get("text", ""),
                    "rating": float(review.get("rating", 0)),
                    "images": None,
                    "published_at": datetime.fromtimestamp(review.get("time", 0)) if review.get("time") else None,
                    "platform_data": {
                        "relative_time": review.get("relative_time_description"),
                        "language": review.get("language"),
                    },
                })

        except Exception as e:
            logger.error(f"구글 맵 크롤링 오류: {e}")

        return reviews


class KakaoMapCrawler(BasePlatformCrawler):
    """카카오맵 리뷰 크롤러 (Phase 2)"""

    platform = MentionPlatform.KAKAO_MAP

    async def crawl(self, profile: MonitorProfile) -> List[Dict[str, Any]]:
        place_id = profile.kakao_place_id
        if not place_id:
            return []

        reviews = []
        try:
            url = f"https://place.map.kakao.com/commentlist/v/{place_id}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=DEFAULT_HEADERS) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()

            for comment in data.get("comment", {}).get("list", []):
                reviews.append({
                    "platform_post_id": str(comment.get("commentid", "")),
                    "source_url": f"https://place.map.kakao.com/{place_id}",
                    "author_name": comment.get("username", "익명"),
                    "author_id": comment.get("userid"),
                    "title": None,
                    "content": comment.get("contents", ""),
                    "rating": float(comment.get("point", 0)) if comment.get("point") else None,
                    "images": [p.get("url") for p in comment.get("photoList", []) if p.get("url")],
                    "published_at": None,
                    "platform_data": {
                        "like_count": comment.get("likeCnt"),
                    },
                })

        except Exception as e:
            logger.error(f"카카오맵 크롤링 오류: {e}")

        return reviews


class NaverBlogMentionCrawler(BasePlatformCrawler):
    """네이버 블로그 멘션 크롤러 (키워드 검색)"""

    platform = MentionPlatform.NAVER_BLOG

    async def crawl(self, profile: MonitorProfile) -> List[Dict[str, Any]]:
        keywords = profile.keywords or [profile.business_name]
        mentions = []

        for keyword in keywords[:5]:
            try:
                # 네이버 검색 API 사용
                from app.core.config import settings
                client_id = getattr(settings, "NAVER_CLIENT_ID", None)
                client_secret = getattr(settings, "NAVER_CLIENT_SECRET", None)

                if not client_id or not client_secret:
                    logger.warning("네이버 검색 API 키가 설정되지 않았습니다.")
                    break

                url = "https://openapi.naver.com/v1/search/blog.json"
                params = {
                    "query": keyword,
                    "display": 20,
                    "start": 1,
                    "sort": "date",
                }
                headers = {
                    "X-Naver-Client-Id": client_id,
                    "X-Naver-Client-Secret": client_secret,
                }

                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params, headers=headers) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.json()

                for item in data.get("items", []):
                    # HTML 태그 제거
                    title = re.sub(r"<[^>]+>", "", item.get("title", ""))
                    description = re.sub(r"<[^>]+>", "", item.get("description", ""))

                    mentions.append({
                        "platform_post_id": item.get("link", ""),
                        "source_url": item.get("link"),
                        "author_name": item.get("bloggername", "익명"),
                        "author_id": item.get("bloggerlink"),
                        "title": title,
                        "content": description,
                        "rating": None,
                        "images": None,
                        "published_at": self._parse_naver_date(item.get("postdate")),
                        "platform_data": {
                            "search_keyword": keyword,
                        },
                    })

                await asyncio.sleep(self.request_delay)

            except Exception as e:
                logger.error(f"네이버 블로그 검색 오류 (키워드: {keyword}): {e}")

        return mentions

    def _parse_naver_date(self, date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y%m%d")
        except Exception:
            return None


class NaverCafeMentionCrawler(BasePlatformCrawler):
    """네이버 카페 멘션 크롤러 (키워드 검색)"""

    platform = MentionPlatform.NAVER_CAFE

    async def crawl(self, profile: MonitorProfile) -> List[Dict[str, Any]]:
        keywords = profile.keywords or [profile.business_name]
        mentions = []

        for keyword in keywords[:5]:
            try:
                from app.core.config import settings
                client_id = getattr(settings, "NAVER_CLIENT_ID", None)
                client_secret = getattr(settings, "NAVER_CLIENT_SECRET", None)

                if not client_id or not client_secret:
                    break

                url = "https://openapi.naver.com/v1/search/cafearticle.json"
                params = {
                    "query": keyword,
                    "display": 20,
                    "start": 1,
                    "sort": "date",
                }
                headers = {
                    "X-Naver-Client-Id": client_id,
                    "X-Naver-Client-Secret": client_secret,
                }

                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params, headers=headers) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.json()

                for item in data.get("items", []):
                    title = re.sub(r"<[^>]+>", "", item.get("title", ""))
                    description = re.sub(r"<[^>]+>", "", item.get("description", ""))

                    mentions.append({
                        "platform_post_id": item.get("link", ""),
                        "source_url": item.get("link"),
                        "author_name": item.get("cafename", ""),
                        "author_id": None,
                        "title": title,
                        "content": description,
                        "rating": None,
                        "images": None,
                        "published_at": None,
                        "platform_data": {
                            "cafe_name": item.get("cafename"),
                            "cafe_url": item.get("cafeurl"),
                            "search_keyword": keyword,
                        },
                    })

                await asyncio.sleep(self.request_delay)

            except Exception as e:
                logger.error(f"네이버 카페 검색 오류 (키워드: {keyword}): {e}")

        return mentions


class CommunityMentionCrawler(BasePlatformCrawler):
    """커뮤니티 멘션 크롤러 (DC인사이드, FM코리아, 더쿠 등)"""

    COMMUNITY_CONFIGS = {
        MentionPlatform.DCINSIDE: {
            "search_url": "https://search.dcinside.com/post/p/1/sort/date/q/{keyword}",
            "item_selector": "li.ub-content",
            "title_selector": ".search_tit a",
            "content_selector": ".search_txt",
            "author_selector": ".search_name",
            "date_selector": ".search_date",
        },
        MentionPlatform.FMKOREA: {
            "search_url": "https://www.fmkorea.com/search?keyword={keyword}&search_target=title_content",
            "item_selector": "li.searchResult",
            "title_selector": ".title a",
            "content_selector": ".searchResult_text",
            "author_selector": ".author",
            "date_selector": ".date",
        },
        MentionPlatform.THEQOO: {
            "search_url": "https://theqoo.net/search?keyword={keyword}&search_target=title_content",
            "item_selector": "li.item",
            "title_selector": ".title a",
            "content_selector": ".text",
            "author_selector": ".author",
            "date_selector": ".date",
        },
    }

    def __init__(self, db: AsyncSession, platform: MentionPlatform):
        super().__init__(db)
        self.platform = platform
        self.config = self.COMMUNITY_CONFIGS.get(platform, {})

    async def crawl(self, profile: MonitorProfile) -> List[Dict[str, Any]]:
        if not self.config:
            return []

        keywords = profile.keywords or [profile.business_name]
        mentions = []

        for keyword in keywords[:3]:
            try:
                search_url = self.config["search_url"].format(keyword=keyword)

                async with aiohttp.ClientSession() as session:
                    async with session.get(search_url, headers=DEFAULT_HEADERS) as resp:
                        if resp.status != 200:
                            continue
                        html = await resp.text()

                soup = BeautifulSoup(html, "html.parser")
                items = soup.select(self.config.get("item_selector", "li"))

                for item in items[:20]:
                    try:
                        title_el = item.select_one(self.config.get("title_selector", "a"))
                        content_el = item.select_one(self.config.get("content_selector", "p"))
                        author_el = item.select_one(self.config.get("author_selector", ".author"))

                        title = title_el.get_text(strip=True) if title_el else ""
                        content = content_el.get_text(strip=True) if content_el else ""
                        author = author_el.get_text(strip=True) if author_el else "익명"

                        href = title_el.get("href", "") if title_el else ""
                        if href and not href.startswith("http"):
                            href = f"https://{self.config['search_url'].split('/')[2]}{href}"

                        if title or content:
                            mentions.append({
                                "platform_post_id": href or f"{self.platform.value}_{keyword}_{len(mentions)}",
                                "source_url": href,
                                "author_name": author,
                                "author_id": None,
                                "title": title,
                                "content": content or title,
                                "rating": None,
                                "images": None,
                                "published_at": None,
                                "platform_data": {
                                    "search_keyword": keyword,
                                },
                            })
                    except Exception:
                        continue

                await asyncio.sleep(self.request_delay)

            except Exception as e:
                logger.error(f"{self.platform.value} 크롤링 오류 (키워드: {keyword}): {e}")

        return mentions


# ==================== 크롤러 서비스 (오케스트레이터) ====================

class ReputationCrawlerService:
    """크롤링 작업 관리 서비스"""

    # 플랫폼별 크롤러 매핑
    CRAWLER_MAP = {
        MentionPlatform.NAVER_PLACE: NaverPlaceCrawler,
        MentionPlatform.GOOGLE_MAPS: GoogleMapsCrawler,
        MentionPlatform.KAKAO_MAP: KakaoMapCrawler,
        MentionPlatform.NAVER_BLOG: NaverBlogMentionCrawler,
        MentionPlatform.NAVER_CAFE: NaverCafeMentionCrawler,
    }

    COMMUNITY_PLATFORMS = {
        MentionPlatform.DCINSIDE,
        MentionPlatform.FMKOREA,
        MentionPlatform.THEQOO,
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    def get_crawler(self, platform: MentionPlatform) -> Optional[BasePlatformCrawler]:
        """플랫폼에 해당하는 크롤러 인스턴스 반환"""
        if platform in self.COMMUNITY_PLATFORMS:
            return CommunityMentionCrawler(self.db, platform)

        crawler_class = self.CRAWLER_MAP.get(platform)
        if crawler_class:
            return crawler_class(self.db)
        return None

    async def run_crawl_job(self, job_id: str, profile: MonitorProfile):
        """크롤링 작업 실행"""
        # 작업 상태 업데이트
        result = await self.db.execute(
            select(ReputationCrawlJob).where(ReputationCrawlJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        if not job:
            return

        job.status = CrawlJobStatus.RUNNING
        job.started_at = datetime.utcnow()
        await self.db.commit()

        try:
            crawler = self.get_crawler(job.platform)
            if not crawler:
                job.status = CrawlJobStatus.FAILED
                job.error_message = f"지원하지 않는 플랫폼: {job.platform.value}"
                await self.db.commit()
                return

            # 크롤링 실행
            raw_mentions = await crawler.crawl(profile)

            # 멘션 저장
            save_result = await crawler.save_mentions(profile, raw_mentions)

            # 작업 완료
            job.status = CrawlJobStatus.COMPLETED
            job.mentions_found = save_result["found"]
            job.mentions_new = save_result["new"]
            job.completed_at = datetime.utcnow()
            await self.db.commit()

            # 새 멘션이 있으면 AI 분석 트리거
            if save_result["new"] > 0:
                try:
                    from app.services.reputation_analyzer import ReputationAnalyzer
                    analyzer = ReputationAnalyzer()
                    await analyzer.analyze_new_mentions(self.db, profile.id)
                except Exception as e:
                    logger.error(f"AI 분석 트리거 오류: {e}")

            logger.info(
                f"크롤링 완료: {job.platform.value} | "
                f"발견: {save_result['found']}, 신규: {save_result['new']}"
            )

        except Exception as e:
            job.status = CrawlJobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            await self.db.commit()
            logger.error(f"크롤링 실패 ({job.platform.value}): {e}")
