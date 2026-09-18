"""
순위 조회 (문서 1-6) — 두 가지 소스와 그 신뢰도 차이 ★가장 중요한 함정

  (a) 네이버 검색 OpenAPI  ─ 싸다. 그러나 **실제 순서와 다르다.** → 프리필터 전용.
  (b) 실제 블로그탭 스크래핑 ─ 무겁다. 그러나 이것만이 ground truth.
  (c) VIEW탭(통합검색) 순위 ─ HTML 파싱.

정직성 규칙(14-3):
  · None = 측정 불가(스크래핑 실패). 빈 rows = 결과 없음. 둘을 섞지 않는다.
  · openapi 크레덴셜이 없으면 None 을 돌려준다(0 이나 임의값 금지).
  · 폴백 결과(parse_mode="regex")는 실측으로 착각하지 않는다 — 호출부가 confidence 를 낮춘다.

캐시: SerpCache — 키워드 단위 **공용** 6h (사용자가 달라도 1회만 조회, 10-3).
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import re
import time
import urllib.parse
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import delete, select

from app.blogindex import normalize_blog_id, normalize_keyword
from app.core.config import settings
from app.models.blog_index import SerpCache

logger = logging.getLogger(__name__)

# ── 상수 (10-3) ───────────────────────────────────────────────────────────
SERP_TTL = 6 * 3600            # 키워드 단위 공용 SERP 캐시
SERP_PAGE_TIMEOUT = 20.0       # HTTP 1회 상한 (원본 12초 — 운영 1 CPU 에서 워커와 겹치면 모자라 20초로)
PLAYWRIGHT_TIMEOUT = 150.0     # 브라우저 경로 전체 하드타임아웃
PLAYWRIGHT_GOTO_TIMEOUT_MS = 25_000
PLAYWRIGHT_WAIT_SELECTOR_MS = 12_000
BROWSER_IDLE_CLOSE = 600       # 상주 브라우저 idle 종료(초)

# 실측 스크래핑으로 인정하는 소스 (7-5 ground truth 판별)
SCRAPE_SOURCES = {"playwright", "http", "http_regex"}

DESKTOP_BLOG_TAB_URL = "https://search.naver.com/search.naver?ssc=tab.blog.all&query={enc}&start={start}"
MOBILE_BLOG_TAB_URL = "https://m.search.naver.com/search.naver?ssc=tab.m_blog.all&query={enc}&start={start}"
VIEW_TAB_URL = "https://search.naver.com/search.naver?where=view&query={enc}"
OPENAPI_BLOG_URL = "https://openapi.naver.com/v1/search/blog.json"

# ★ 2026-08-13 실측 기준 마크업: 본문 결과 목록은 아래 컨테이너 하나에 들어 있다.
#   그 바깥의 li.info_item(인기주제 캐러셀)·기관 블로그 띠는 순위가 아니다.
#   클래스명 대부분이 해시(q8qyx0TaRoC1n7jj)라 못 쓰고, fds- 접두만 안정적이다.
CONTAINER_SELECTORS = (
    'div[class*="fds-ugc-single-intention-item-list-tab"]',
    'div[class*="fds-ugc-single-intention-item-list"]',       # 2순위
)
PLAYWRIGHT_WAIT_SELECTOR = 'div[class*="fds-ugc-single-intention-item-list"]'
ANCHOR_SELECTOR = 'a[href*="blog.naver.com"]'

# 링크 파싱 정규식: blog_id / post_no
_LINK_RE = re.compile(r"blog\.naver\.com/([A-Za-z0-9_-]+)/(\d+)")
# 제목 정제: 끝의 "새 창 열림" 제거
_NEW_WINDOW_RE = re.compile(r"새\s*창\s*열림\s*$")
# VIEW탭 href 추출
_VIEW_HREF_RE = re.compile(r'href="(https?://blog\.naver\.com/[^"]+)"')
_POST_ID_RE = re.compile(r"blog\.naver\.com/([^/]+)/(\d+)")
_LOGNO_RE = re.compile(r"logNo=(\d+)")
# openapi bloggerlink / link 에서 blog_id
_OPENAPI_BLOG_RE = re.compile(r"blog\.naver\.com/([^/?]+)")

# UA 로테이션 (데스크톱 랜덤)
_DESKTOP_UAS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
)
_MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

# 마지막 HTTP 시도의 진단 정보 (테스트/리포트용: 차단 여부를 정확히 보고하기 위해)
LAST_HTTP_DEBUG: Dict[str, Any] = {}

# ★ '결과 없음'(측정된 빈 결과)과 '축소/차단 페이지'(측정 불가)를 구분하는 마커.
#   실측(2026-09-04, 로컬): 정확매칭 질의에 결과가 없으면 200 + 링크 0 이지만
#   <div id="notfound" class="api_noresult_wrap"> … '…'에 대한 검색결과가 없습니다. 가 들어 있다.
#   문서가 말하는 클라우드 축소 페이지(70KB, 링크 0)에는 이 마커가 없다 → None(측정불가).
_NO_RESULT_MARKERS = ("api_noresult_wrap", "에 대한 검색결과가 없습니다", "검색결과가 없습니다")


def is_no_result_page(html: str) -> bool:
    h = html or ""
    return any(m in h for m in _NO_RESULT_MARKERS)


# ── 세션 헬퍼 ────────────────────────────────────────────────────────────
@contextlib.asynccontextmanager
async def fresh_session():
    """동시 작업(세마포어 병렬)마다 별도 AsyncSession. 한 세션을 여러 코루틴이
    동시에 쓰면 SQLAlchemy 가 깨진다 — 병렬 채점·병렬 스크래핑은 반드시 이걸 쓴다."""
    from app.db.database import AsyncSessionLocal
    async with AsyncSessionLocal() as s:
        yield s


def _headers(mobile: bool = False) -> Dict[str, str]:
    return {
        "User-Agent": _MOBILE_UA if mobile else random.choice(_DESKTOP_UAS),
        "Referer": "https://m.search.naver.com/" if mobile else "https://search.naver.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def rank_label(rank: Optional[int]) -> str:
    """순위 분류(표시용): None → 노출안됨 / 1~3 상위권 / 4~7 중위권 / 8~10 하위권."""
    if rank is None:
        return "노출안됨"
    if rank <= 3:
        return "상위권"
    if rank <= 7:
        return "중위권"
    return "하위권"


def _clean_title(text: str) -> str:
    t = re.sub(r"\s+", " ", (text or "")).strip()
    return _NEW_WINDOW_RE.sub("", t).strip()


# ── (b) 블로그탭 HTML 파싱 ───────────────────────────────────────────────
def parse_blog_tab_html(html: str) -> Tuple[List[Dict[str, Any]], str, bool]:
    """
    → (rows, parse_mode, container_found)
      parse_mode "list"  = 컨테이너에서 파싱 (신뢰)
      parse_mode "regex" = 컨테이너를 못 찾아 전역 정규식 폴백 (순위 신뢰도 낮음)
    rows: [{rank, blog_id, post_no, post_url, title}]  blog_id 중복 제거, 등장 순서 = rank
    """
    rows: List[Dict[str, Any]] = []
    seen: Dict[str, int] = {}
    container = None
    try:
        soup = BeautifulSoup(html or "", "lxml")
        for sel in CONTAINER_SELECTORS:
            container = soup.select_one(sel)
            if container is not None:
                break
    except Exception as e:  # noqa: BLE001
        logger.warning("[serp] HTML 파싱 실패: %s", e)
        soup = None

    if container is not None:
        for a in container.select(ANCHOR_SELECTOR):
            href = a.get("href") or ""
            m = _LINK_RE.search(href)
            if not m:
                continue
            blog_id, post_no = m.group(1), m.group(2)
            title = _clean_title(a.get_text(" ", strip=True))
            key = blog_id.lower()
            if key in seen:
                # 같은 글의 두 번째 앵커(썸네일→제목)에서 제목만 보충. 순위는 첫 등장.
                idx = seen[key]
                if not rows[idx]["title"] and title and rows[idx]["post_no"] == post_no:
                    rows[idx]["title"] = title
                continue
            seen[key] = len(rows)
            rows.append({
                "rank": len(rows) + 1,
                "blog_id": blog_id,
                "post_no": post_no,
                "post_url": f"https://blog.naver.com/{blog_id}/{post_no}",
                "title": title,
            })
        return rows, "list", True

    # 전역 정규식 폴백 — 인기주제 캐러셀이 1~12위로 잡힐 수 있어 순위 신뢰도 낮음
    for m in _LINK_RE.finditer(html or ""):
        blog_id, post_no = m.group(1), m.group(2)
        key = blog_id.lower()
        if key in seen:
            continue
        seen[key] = len(rows)
        rows.append({
            "rank": len(rows) + 1,
            "blog_id": blog_id,
            "post_no": post_no,
            "post_url": f"https://blog.naver.com/{blog_id}/{post_no}",
            "title": "",
        })
    return rows, "regex", False


async def _http_get(url: str, mobile: bool = False, attempts: int = 2) -> Optional[httpx.Response]:
    """HTTP GET. 일시 오류(타임아웃·연결)는 한 번 더 시도한다 — 워커가 바쁠 때 첫 요청이 늦어지는 일이 잦다."""
    last: Optional[Exception] = None
    for i in range(attempts):
        try:
            async with httpx.AsyncClient(timeout=SERP_PAGE_TIMEOUT, follow_redirects=True) as client:
                return await client.get(url, headers=_headers(mobile))
        except Exception as e:  # noqa: BLE001
            last = e
            if i + 1 < attempts:
                await asyncio.sleep(1.5 + random.random())
    logger.warning("[serp] HTTP 실패 %s: %s", url[:80], last)
    return None


async def _fetch_blog_tab_http(keyword: str, start: int = 1, mobile: bool = False) -> Optional[Dict[str, Any]]:
    """HTTP GET 1회. → {rows, source, parse_mode, endpoint} | None(차단/실패).
    ⚠️ 클라우드 IP에서는 200 을 주면서도 blog.naver.com 링크가 한 개도 없는 축소 페이지
       (70KB, 로컬 491KB, 캡차 아님)를 준다 → None 으로 보고해 브라우저 폴백을 유도한다."""
    enc = urllib.parse.quote(keyword)
    tmpl = MOBILE_BLOG_TAB_URL if mobile else DESKTOP_BLOG_TAB_URL
    url = tmpl.format(enc=enc, start=start)
    resp = await _http_get(url, mobile=mobile)
    dbg = {"endpoint": "mobile" if mobile else "desktop", "url": url, "status": None,
           "size": 0, "links": 0, "parse_mode": None}
    if resp is None:
        dbg["error"] = "request_failed"
        LAST_HTTP_DEBUG.update(dbg)
        return None
    html = resp.text or ""
    dbg["status"] = resp.status_code
    dbg["size"] = len(html)
    if resp.status_code != 200:
        LAST_HTTP_DEBUG.update(dbg)
        logger.warning("[serp] 블로그탭 HTTP %s (%s)", resp.status_code, keyword)
        return None
    rows, parse_mode, container_found = await asyncio.to_thread(parse_blog_tab_html, html)  # 470KB 파싱은 스레드로
    dbg["links"] = len(_LINK_RE.findall(html))
    dbg["parse_mode"] = parse_mode
    dbg["container_found"] = container_found
    LAST_HTTP_DEBUG.update(dbg)
    if not container_found and dbg["links"] == 0:
        if is_no_result_page(html):
            # 측정된 '결과 없음' — 미노출. 차단이 아니다.
            dbg["no_results"] = True
            return {"rows": [], "source": "http", "parse_mode": "list", "endpoint": dbg["endpoint"],
                    "html_size": len(html), "no_results": True}
        # 200 + 링크 0 + 결과없음 마커도 없음 = 축소/차단 페이지. 결과가 JS/차단 뒤에 있다.
        logger.warning("[serp] 축소 페이지 감지 (200, %dB, 링크 0) — 브라우저 폴백 필요", len(html))
        return None
    return {
        "rows": rows,
        "source": "http" if parse_mode == "list" else "http_regex",
        "parse_mode": parse_mode,
        "endpoint": dbg["endpoint"],
        "html_size": len(html),
    }


# ── Playwright 폴백 (프로덕션 이미지에는 없을 수 있다 — 지연 import, 우아한 저하) ──
class _BrowserPool:
    """chromium 상주. 콜드 기동이 이 경로 비용의 대부분이라 요청 간 재사용하고,
    컨텍스트만 닫는다(쿠키 격리 유지). idle 600초면 종료. 타임아웃 난 브라우저는 폐기."""

    def __init__(self) -> None:
        self._pw = None
        self._browser = None
        self._lock = asyncio.Lock()
        self._last_used = 0.0
        self._watchdog: Optional[asyncio.Task] = None
        self.available: Optional[bool] = None  # None=미확인

    async def _ensure(self):
        async with self._lock:
            if self._browser is not None:
                try:
                    if self._browser.is_connected():
                        return self._browser
                except Exception:  # noqa: BLE001
                    pass
                await self._close_quiet()
            try:
                from playwright.async_api import async_playwright  # 지연 import
            except Exception:  # noqa: BLE001
                self.available = False
                return None
            try:
                self._pw = await async_playwright().start()
                self._browser = await self._pw.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
                )
                self.available = True
            except Exception as e:  # noqa: BLE001
                logger.warning("[serp] chromium 기동 실패 — 브라우저 폴백 불가: %s", e)
                self.available = False
                await self._close_quiet()
                return None
            if self._watchdog is None or self._watchdog.done():
                self._watchdog = asyncio.create_task(self._idle_watchdog())
            return self._browser

    async def _close_quiet(self) -> None:
        b, pw = self._browser, self._pw
        self._browser, self._pw = None, None
        try:
            if b is not None:
                await b.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            if pw is not None:
                await pw.stop()
        except Exception:  # noqa: BLE001
            pass

    async def discard(self) -> None:
        """타임아웃 난 브라우저는 폐기하고 다음 요청에 재사용하지 않는다."""
        async with self._lock:
            await self._close_quiet()

    async def _idle_watchdog(self) -> None:
        while True:
            await asyncio.sleep(30)
            if self._browser is None:
                return
            if time.monotonic() - self._last_used >= BROWSER_IDLE_CLOSE:
                await self.discard()
                return

    async def _fetch_inner(self, url: str, mobile: bool) -> Optional[str]:
        browser = await self._ensure()
        if browser is None:
            return None
        self._last_used = time.monotonic()
        ctx = await browser.new_context(
            user_agent=_MOBILE_UA if mobile else random.choice(_DESKTOP_UAS),
            locale="ko-KR",
            viewport={"width": 390, "height": 844} if mobile else {"width": 1280, "height": 900},
            extra_http_headers={"Accept-Language": "ko-KR,ko;q=0.9", "Referer": "https://search.naver.com/"},
        )
        try:
            # 이미지/폰트/미디어/스타일시트 차단 — SERP 썸네일 수십 개가 저사양 워커에서 시간을 지배한다
            async def _route(route):
                try:
                    if route.request.resource_type in {"image", "font", "media", "stylesheet"}:
                        await route.abort()
                    else:
                        await route.continue_()
                except Exception:  # noqa: BLE001
                    pass
            await ctx.route("**/*", _route)
            page = await ctx.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=PLAYWRIGHT_GOTO_TIMEOUT_MS)
            try:
                await page.wait_for_selector(PLAYWRIGHT_WAIT_SELECTOR, timeout=PLAYWRIGHT_WAIT_SELECTOR_MS)
            except Exception:  # noqa: BLE001
                pass  # 컨테이너가 없어도 content 는 회수한다(정규식 폴백/빈 결과 판정용)
            return await page.content()
        finally:
            self._last_used = time.monotonic()
            with contextlib.suppress(Exception):
                await ctx.close()

    async def fetch_html(self, url: str, mobile: bool = False) -> Optional[str]:
        """전체 하드타임아웃 150초. wait_for 로 감싸되 shield 로 분리 —
        wait_for 는 취소한 코루틴이 끝날 때까지 기다리는데, 매달린 브라우저를 정리하는
        finally 가 같이 매달리면 상한이 안 지켜진다."""
        if self.available is False:
            return None
        task = asyncio.create_task(self._fetch_inner(url, mobile))
        try:
            return await asyncio.wait_for(asyncio.shield(task), PLAYWRIGHT_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning("[serp] 브라우저 하드타임아웃(%ss) — 브라우저 폐기", PLAYWRIGHT_TIMEOUT)
            asyncio.create_task(self.discard())
            return None
        except Exception as e:  # noqa: BLE001
            logger.warning("[serp] 브라우저 경로 실패: %s", e)
            return None


_POOL = _BrowserPool()


async def _fetch_blog_tab_playwright(keyword: str, start: int = 1, mobile: bool = False) -> Optional[Dict[str, Any]]:
    enc = urllib.parse.quote(keyword)
    tmpl = MOBILE_BLOG_TAB_URL if mobile else DESKTOP_BLOG_TAB_URL
    html = await _POOL.fetch_html(tmpl.format(enc=enc, start=start), mobile=mobile)
    if html is None:
        return None
    rows, parse_mode, container_found = parse_blog_tab_html(html)
    if not container_found and not rows:
        if is_no_result_page(html):
            return {"rows": [], "source": "playwright", "parse_mode": "list",
                    "endpoint": "mobile" if mobile else "desktop", "html_size": len(html), "no_results": True}
        return None  # 브라우저로도 결과 목록이 없다 = 측정 불가
    return {"rows": rows, "source": "playwright", "parse_mode": parse_mode,
            "endpoint": "mobile" if mobile else "desktop", "html_size": len(html)}


def _prefer_browser() -> bool:
    """클라우드 환경이면 HTTP 시도를 건너뛰고 처음부터 브라우저로 가는 게 빠르다
    (HTTP 2회 시도에 120초를 태우고 예산 부족으로 브라우저가 죽었던 실측).
    BLOGINDEX_SERP_PREFER_BROWSER=1 로 켠다. 브라우저가 없으면 HTTP 로 되돌아간다."""
    import os
    return os.environ.get("BLOGINDEX_SERP_PREFER_BROWSER", "").strip() in {"1", "true", "yes"}


async def _fetch_blog_tab(keyword: str, start: int = 1) -> Optional[Dict[str, Any]]:
    """데스크톱 HTTP → 모바일 HTTP → 브라우저(있으면) 순으로 시도. 전부 실패면 None."""
    if _prefer_browser() and _POOL.available is not False:
        got = await _fetch_blog_tab_playwright(keyword, start=start, mobile=False)
        if got is not None:
            return got
    got = await _fetch_blog_tab_http(keyword, start=start, mobile=False)
    if got is not None:
        return got
    got = await _fetch_blog_tab_http(keyword, start=start, mobile=True)
    if got is not None:
        return got
    if _prefer_browser():
        return None   # 이미 브라우저를 시도했다
    return await _fetch_blog_tab_playwright(keyword, start=start, mobile=False)


# ── 캐시 ─────────────────────────────────────────────────────────────────
async def _cache_get(db, keyword_norm: str, tab: str) -> Optional[SerpCache]:
    if db is None:
        return None
    try:
        cutoff = datetime.utcnow() - timedelta(seconds=SERP_TTL)
        row = (await db.execute(
            select(SerpCache)
            .where(SerpCache.keyword_norm == keyword_norm, SerpCache.tab == tab,
                   SerpCache.fetched_at >= cutoff)
            .order_by(SerpCache.fetched_at.desc())
            .limit(1)
        )).scalars().first()
        return row
    except Exception as e:  # noqa: BLE001
        logger.warning("[serp] 캐시 조회 실패: %s", e)
        return None


async def _cache_put(db, keyword: str, keyword_norm: str, tab: str, rows: list, source: str, parse_mode: str) -> None:
    if db is None:
        return
    try:
        await db.execute(delete(SerpCache).where(SerpCache.keyword_norm == keyword_norm, SerpCache.tab == tab))
        db.add(SerpCache(keyword_norm=keyword_norm, keyword=keyword, tab=tab, rows=rows,
                         source=source, parse_mode=parse_mode, fetched_at=datetime.utcnow()))
        await db.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning("[serp] 캐시 저장 실패: %s", e)
        with contextlib.suppress(Exception):
            await db.rollback()


async def _serp_page(db, keyword: str, tab: str, start: int, use_cache: bool) -> Optional[Dict[str, Any]]:
    kn = normalize_keyword(keyword)
    if not kn:
        return None
    if use_cache:
        row = await _cache_get(db, kn, tab)
        if row is not None:
            return {"rows": list(row.rows or []), "source": row.source, "parse_mode": row.parse_mode,
                    "measured_at": row.fetched_at.isoformat() if row.fetched_at else None, "cached": True}
    got = await _fetch_blog_tab(keyword, start=start)
    if got is None:
        return None
    await _cache_put(db, keyword, kn, tab, got["rows"], got["source"], got["parse_mode"])
    return {"rows": got["rows"], "source": got["source"], "parse_mode": got["parse_mode"],
            "measured_at": datetime.utcnow().isoformat(), "cached": False,
            "endpoint": got.get("endpoint"), "html_size": got.get("html_size")}


# ── 공개 API ─────────────────────────────────────────────────────────────
async def blog_tab_serp(db, keyword: str, limit: int = 20, use_cache: bool = True) -> Optional[Dict[str, Any]]:
    """실제 블로그탭 SERP 1페이지(start=1).
    → {rows:[{rank, blog_id, post_no, post_url, title}], source, parse_mode, measured_at, cached} | None
      None = 측정 불가(스크래핑 실패). 빈 rows = 결과 없음."""
    got = await _serp_page(db, keyword, "blog", 1, use_cache)
    if got is None:
        return None
    got["rows"] = got["rows"][:limit]
    got["keyword"] = keyword
    return got


async def _serp_rows_upto(db, keyword: str, max_results: int, use_cache: bool = True) -> Optional[List[Dict[str, Any]]]:
    """1페이지(≈30) + 필요하면 2페이지(start=31). None = 1페이지조차 측정 불가."""
    first = await _serp_page(db, keyword, "blog", 1, use_cache)
    if first is None:
        return None
    rows = list(first["rows"])
    if max_results > len(rows) and len(rows) >= 30:
        second = await _serp_page(db, keyword, "blog_p2", 31, use_cache)
        if second is not None:
            seen = {r["blog_id"].lower() for r in rows}
            for r in second["rows"]:
                if r["blog_id"].lower() in seen:
                    continue
                seen.add(r["blog_id"].lower())
                rows.append({**r, "rank": len(rows) + 1})
    return rows[:max_results]


def _find_rank(rows: List[Dict[str, Any]], blog_id: str) -> Optional[int]:
    target = normalize_blog_id(blog_id).lower()
    for r in rows:
        if (r.get("blog_id") or "").lower() == target:
            return int(r["rank"])
    return None


async def blog_tab_true_rank(db, keyword: str, blog_id: str, limit: int = 30) -> Optional[int]:
    """실제 블로그탭 순위. ⚠️ None 은 (a) 상위 limit 내 미노출 (b) 스크래핑 실패 가 섞인다.
    둘을 구분해야 하는 호출부는 blog_tab_serp() 를 직접 써서 None(측정불가)과 빈 순위(미노출)를 구분할 것."""
    serp = await blog_tab_serp(db, keyword, limit=limit)
    if serp is None:
        return None
    return _find_rank(serp["rows"], blog_id)


async def check_blog_tab_rank(db, query: str, blog_id: str, max_results: int = 50) -> Optional[int]:
    """정확매칭(따옴표) 질의 등 임의 query 로 블로그탭 순위(최대 max_results). None 의 의미는 위와 같다."""
    rows = await _serp_rows_upto(db, query, max_results)
    if rows is None:
        return None
    return _find_rank(rows, blog_id)


# ── (c) VIEW탭(통합검색) ─────────────────────────────────────────────────
def _normalize_post_url(url: str) -> str:
    u = (url or "").replace("&amp;", "&")
    return u.split("?", 1)[0].split("#", 1)[0].rstrip("/")


def parse_view_tab_html(html: str) -> List[Dict[str, Any]]:
    """href="(https?://blog\\.naver\\.com/[^"]+)" 전부 추출 → 'ad=' / 'partner=' 제외,
    URL 정규화(쿼리 제거) 후 중복 제거. post_id 는 blog\\.naver\\.com/([^/]+)/(\\d+) 2번 그룹 또는 logNo=(\\d+)."""
    rows: List[Dict[str, Any]] = []
    seen = set()
    for raw in _VIEW_HREF_RE.findall(html or ""):
        href = raw.replace("&amp;", "&")
        if "ad=" in href or "partner=" in href:
            continue
        blog_id, post_no = None, None
        m = _POST_ID_RE.search(href)
        if m:
            blog_id, post_no = m.group(1), m.group(2)
        else:
            m2 = _LOGNO_RE.search(href)
            if m2:
                post_no = m2.group(1)
                m3 = re.search(r"blogId=([A-Za-z0-9_-]+)", href)
                blog_id = m3.group(1) if m3 else None
        if not post_no:
            continue
        norm = _normalize_post_url(href) if m else f"{blog_id}/{post_no}"
        if norm in seen:
            continue
        seen.add(norm)
        rows.append({"rank": len(rows) + 1, "blog_id": blog_id, "post_no": post_no,
                     "post_url": norm if m else href, "title": ""})
    return rows


async def view_tab_serp(db, query: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
    """VIEW탭 결과(블로그 링크만). None = 측정 불가."""
    kn = normalize_keyword(query)
    if not kn:
        return None
    if use_cache:
        row = await _cache_get(db, kn, "view")
        if row is not None:
            return {"rows": list(row.rows or []), "source": row.source, "parse_mode": row.parse_mode,
                    "measured_at": row.fetched_at.isoformat() if row.fetched_at else None, "cached": True}
    url = VIEW_TAB_URL.format(enc=urllib.parse.quote(query))
    resp = await _http_get(url)
    if resp is None or resp.status_code != 200:
        return None
    html = resp.text or ""
    rows = parse_view_tab_html(html)
    if not rows and "blog.naver.com" not in html:
        # 링크가 하나도 없는 축소 페이지 → 측정 불가 (미노출과 구분)
        return None
    await _cache_put(db, query, kn, "view", rows, "http", "regex")
    return {"rows": rows, "source": "http", "parse_mode": "regex",
            "measured_at": datetime.utcnow().isoformat(), "cached": False}


def _post_no_of(post_url: str) -> Optional[str]:
    m = _POST_ID_RE.search(post_url or "")
    if m:
        return m.group(2)
    m = _LOGNO_RE.search(post_url or "")
    return m.group(1) if m else None


async def check_view_tab_rank(db, query: str, post_url: str, max_results: int = 50) -> Optional[int]:
    """VIEW탭에서 타겟 글(post_no 매칭)의 순위. None = 미노출 또는 측정 불가."""
    target = _post_no_of(post_url)
    if not target:
        return None
    serp = await view_tab_serp(db, query)
    if serp is None:
        return None
    for r in serp["rows"][:max_results]:
        if r.get("post_no") == target:
            return int(r["rank"])
    return None


# ── (a) OpenAPI — 프리필터 전용. ★ ground truth 아님 ────────────────────
def openapi_configured() -> bool:
    return bool(settings.NAVER_CLIENT_ID and settings.NAVER_CLIENT_SECRET)


async def openapi_blog_search(query: str, display: int = 30) -> Optional[List[Dict[str, Any]]]:
    """GET /v1/search/blog.json (sort=sim). → items | None(크레덴셜 없음/실패 = 측정불가).
    ⚠️ sort=sim 순서는 실제 블로그탭 노출 순서와 다르다. 색인 여부 스캔(프리필터) 전용."""
    if not openapi_configured():
        return None
    try:
        async with httpx.AsyncClient(timeout=SERP_PAGE_TIMEOUT) as client:
            resp = await client.get(
                OPENAPI_BLOG_URL,
                params={"query": query, "display": min(int(display), 30), "start": 1, "sort": "sim"},
                headers={"X-Naver-Client-Id": settings.NAVER_CLIENT_ID,
                         "X-Naver-Client-Secret": settings.NAVER_CLIENT_SECRET},
            )
        if resp.status_code != 200:
            logger.warning("[serp] openapi %s: %s", resp.status_code, resp.text[:120])
            return None
        return list((resp.json() or {}).get("items") or [])
    except Exception as e:  # noqa: BLE001
        logger.warning("[serp] openapi 실패: %s", e)
        return None


async def openapi_blog_rank(query: str, blog_id: str, display: int = 30) -> Optional[int]:
    """items[i].bloggerlink 또는 link 에서 blog_id 매칭 → 1-based 인덱스. 없으면/실패 None.
    ★ 천장 산정·정답지 채점의 ground truth 로 쓰지 말 것 (프리필터 전용)."""
    items = await openapi_blog_search(query, display)
    if items is None:
        return None
    target = normalize_blog_id(blog_id).lower()
    for i, it in enumerate(items, start=1):
        for field in ("bloggerlink", "link"):
            m = _OPENAPI_BLOG_RE.search(it.get(field) or "")
            if m and m.group(1).lower() == target:
                return i
    return None
