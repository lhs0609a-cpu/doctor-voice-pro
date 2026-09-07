"""
데이터 수집 계층 (문서 1장) — 모든 외부 엔드포인트와 파싱 규칙.

  1-1 scrape_blog_stats     : 포스트수 / 이웃수 / 누적방문자 / 네이버레벨 (데스크톱+모바일 동시)
  1-2 fetch_visitor_series  : NVisitorgp4Ajax 실측 일별 방문자 (조작 불가능한 진짜 트래픽 신호)
  1-3 fetch_rss             : RSS 50개 캡 — 활동성·주제·콘텐츠의 원자료
  1-4 analyze_post          : 글 1개 풀파싱 (PostView __PRELOADED_STATE__ → 모바일 HTML 폴백)
      fullparse_recent      : 최근 글 N개(기본 15) 풀파싱 평균 + URL 키 영구 캐시

정직성 규칙: 측정 못 한 값은 None. 0 은 유효한 측정값(`is not None` 판정).
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import math
import multiprocessing
import os
import random
import re
import statistics
import weakref
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

# ── 공유 HTTP 클라이언트 ─────────────────────────────────────────────
# 예전엔 글 1개마다 AsyncClient 를 새로 만들어 TLS 핸드셰이크를 150번씩 했다(키워드 1개당).
# 이벤트루프별로 하나를 재사용해 keep-alive 로 연결을 돌려쓴다.
_SHARED_CLIENTS: Dict[int, httpx.AsyncClient] = {}


def shared_client() -> httpx.AsyncClient:
    loop = asyncio.get_running_loop()
    key = id(loop)
    c = _SHARED_CLIENTS.get(key)
    if c is None or c.is_closed:
        c = httpx.AsyncClient(
            follow_redirects=True,
            limits=httpx.Limits(max_connections=int(os.getenv("BLOGINDEX_HTTP_MAX_CONN", "48")),
                                max_keepalive_connections=24, keepalive_expiry=30.0),
        )
        _SHARED_CLIENTS[key] = c
    return c


def _soup(html: str) -> "BeautifulSoup":
    """lxml 우선, 실패 시 html.parser. (동기 파싱 함수 안에서만 호출 — 이벤트루프에서 직접 부르지 말 것)"""
    try:
        return BeautifulSoup(html or "", "lxml")
    except Exception:  # noqa: BLE001
        return BeautifulSoup(html or "", "html.parser")


logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# CPU 파싱 프로세스 풀 (1-4 글 풀파싱)
# ──────────────────────────────────────────────────────────────────────────────
# 글 1개(모바일 HTML ≈130KB)의 BeautifulSoup(lxml) + 정규식 파싱은 순수 CPU 0.3~1초다. 이걸 이벤트루프에서
# (또는 GIL 을 쥔 스레드에서) 돌리면 블로그 3개 × 4글 동시 처리 중 다른 글의 HTTP read 가 굶어 12초
# 타임아웃이 무더기로 났다(운영 공유 vCPU 1~2개 실측; 같은 시각 네이버 직접 프로브는 0.2~0.7초 응답).
# → I/O 와 CPU 를 분리한다: 파싱은 별도 프로세스에서, 이벤트루프는 네트워크만.
#   BLOGINDEX_PARSE_PROCS=0 이면 프로세스 풀을 쓰지 않고 스레드로 돌린다(디버그/비상용).
PARSE_PROCS = int(os.getenv("BLOGINDEX_PARSE_PROCS", "2"))
_parse_pool: Optional[concurrent.futures.ProcessPoolExecutor] = None
_parse_pool_broken = False
_parse_pool_warned = False


def _get_parse_pool() -> Optional[concurrent.futures.ProcessPoolExecutor]:
    """첫 사용 시 지연 생성. 생성 실패 시 None (→ 스레드 폴백).
    항상 spawn 컨텍스트: Windows 는 spawn 만 지원하고, Linux 에서도 이벤트루프·스레드가 살아 있는
    프로세스를 fork 하는 것은 위험하다. spawn 자식은 이 모듈을 top-level 에서 다시 import 하므로
    실행 함수(extract_post_from_html 등)는 반드시 모듈 최상위에 있어야 한다."""
    global _parse_pool, _parse_pool_broken, _parse_pool_warned
    if _parse_pool_broken or PARSE_PROCS <= 0:
        return None
    if _parse_pool is None:
        try:
            _parse_pool = concurrent.futures.ProcessPoolExecutor(
                max_workers=PARSE_PROCS, mp_context=multiprocessing.get_context("spawn"))
        except Exception as e:  # noqa: BLE001
            _parse_pool_broken = True
            if not _parse_pool_warned:
                _parse_pool_warned = True
                logger.warning("blogindex parse pool 생성 실패 → asyncio.to_thread 폴백: %s", e)
            return None
    return _parse_pool


async def _run_cpu(fn: Callable[..., Any], *args: Any) -> Any:
    """CPU 파싱 함수를 프로세스 풀에서 실행. 풀이 깨지면(BrokenProcessPool 등) 경고 1회 후 스레드 폴백."""
    global _parse_pool, _parse_pool_broken, _parse_pool_warned
    pool = _get_parse_pool()
    if pool is not None:
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(pool, fn, *args)
        except (concurrent.futures.BrokenExecutor, RuntimeError, OSError) as e:
            # RuntimeError 는 executor 가 닫힌 경우("cannot schedule new futures after shutdown")만 풀 문제로 본다.
            # 파싱 함수 자체가 던진 RuntimeError 는 예전처럼 호출자에게 그대로 올린다.
            if isinstance(e, RuntimeError) and not isinstance(e, concurrent.futures.BrokenExecutor)                     and "shutdown" not in str(e):
                raise
            _parse_pool_broken = True
            if not _parse_pool_warned:
                _parse_pool_warned = True
                logger.warning("blogindex parse pool 실패 → asyncio.to_thread 폴백 (이후 계속 스레드): %s", e)
            try:
                pool.shutdown(wait=False, cancel_futures=True)
            except Exception:  # noqa: BLE001
                pass
            _parse_pool = None
    return await asyncio.to_thread(fn, *args)

# ──────────────────────────────────────────────────────────────────────────────
# User-Agent / 타임아웃
# ──────────────────────────────────────────────────────────────────────────────
DESKTOP_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]
# 1-1 모바일 UA — 원본 문자열 그대로
IPHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
             "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
# 1-4 방법 2 — Android Chrome
ANDROID_UA = ("Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

TIMEOUT = 5.0                       # 1-1 / 1-2 / 1-3(분석 경로)
RSS_TIMEOUT_LIST = 15.0             # 1-3 글목록 경로
# 1-4 원본: connect 3 / read 6 (빠른 실패 후 재시도). 운영(Fly nrt)에서는 네이버 모바일 글 페이지가 그보다 느려
# 동시 채점 중 절반이 타임아웃 났다(실측) → 환경변수로 늘릴 수 있게. 기본 connect 5 / read 12.
POST_TIMEOUT = httpx.Timeout(connect=float(os.getenv("BLOGINDEX_POST_CONNECT_TIMEOUT", "5")),
                             read=float(os.getenv("BLOGINDEX_POST_READ_TIMEOUT", "12")), write=6.0, pool=6.0)
FULLPARSE_SAMPLE_SIZE = 15          # ★ 예전엔 3개 — 표본이 아니었다 (지수 ±8~11 요동)
FULLPARSE_CONCURRENCY = int(os.getenv("BLOGINDEX_FULLPARSE_CONCURRENCY", "8"))   # 블로그 1개 안에서 글 풀파싱 동시성
# 프로세스 전체에서 네이버 글 페이지를 동시에 여는 상한. 블로그 3개 × 4 = 12 동시 요청이 되면 운영 IP 에서
# 응답이 한꺼번에 밀려 타임아웃이 무더기로 났다(실측 08:35:39 에 6건 동시 타임아웃). 전역으로 묶는다.
POST_FETCH_GLOBAL = int(os.getenv("BLOGINDEX_POST_FETCH_GLOBAL", "24"))
TRY_POSTVIEW = os.getenv("BLOGINDEX_TRY_POSTVIEW", "0") == "1"
_post_fetch_gate = asyncio.Semaphore(POST_FETCH_GLOBAL)
RSS_HARD_CAP = 50                   # 네이버 RSS 하드캡
RSS_TRUNCATED_MIN = 48              # 48개 이상이면 잘린 것으로 본다


def _desktop_ua() -> str:
    return random.choice(DESKTOP_UAS)


def _to_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _first_int(patterns: List[str], text: str) -> Optional[int]:
    """정규식 우선순위 순서대로 첫 매치의 정수. 0 도 유효한 값이다."""
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            v = _to_int(m.group(1))
            if v is not None:
                return v
    return None


# ══════════════════════════════════════════════════════════════════════════════
# 1-1. 블로그 통계 (포스트수 / 이웃수 / 누적방문자 / 네이버레벨)
# ══════════════════════════════════════════════════════════════════════════════
# ★ 모바일 하이드레이션 JSON 키 (1차 소스 — 데스크톱 값보다 우선)
_MOBILE_POSTS = [r'"postCount"\s*:\s*(\d+)', r'"postCnt"\s*:\s*(\d+)']
_MOBILE_NEIGHBORS = [r'"subscriberCount"\s*:\s*(\d+)', r'"buddyCount"\s*:\s*(\d+)', r'"buddyCnt"\s*:\s*(\d+)']
_MOBILE_VISITORS = [r'"totalVisitorCount"\s*:\s*(\d+)', r'"visitorcnt"\s*:\s*"?(\d+)"?']
_MOBILE_DAILY = [r'"dayVisitorCount"\s*:\s*(\d+)']
# 데스크톱 JSON 패턴 (보조)
_DESKTOP_POSTS = [r'"countPost"\s*:\s*(\d+)', r'"postCnt"\s*:\s*(\d+)']
_DESKTOP_NEIGHBORS = [r'"countBuddy"\s*:\s*(\d+)', r'"buddyCnt"\s*:\s*(\d+)']
_DESKTOP_VISITORS = [r'"visitorcnt"\s*:\s*"?(\d+)"?', r'"countVisitor"\s*:\s*(\d+)']
# 텍스트 폴백 (하이드레이션 키가 바뀐 경우에만) — 실제 마크업은 "387,798명의 이웃" (숫자가 앞)
_TEXT_NEIGHBORS = [r'(\d[\d,]*)\s*명의\s*이웃']
# 네이버 공식 레벨 (Lv.1~4) — 값이 1~4 범위일 때만 채택.
# ⚠️ 예전의 r'"level":(\d+)' / r'Lv\.?\s*(\d+)' 는 fontType, style 같은 무관한 값을 잡아
#    가짜 레벨을 만들었다. 절대 쓰지 말 것.
_NAVER_LEVEL = [r'"bloggerLevel"\s*:\s*(\d+)', r'"blogLevel"\s*:\s*(\d+)', r'"userLevel"\s*:\s*(\d+)']

_NOT_FOUND_TEXTS = ("존재하지 않는 블로그", "게시물이 삭제되었거나 다른 페이지로 변경되었습니다")
_PRIVATE_TEXTS = ("비공개 블로그", "이 블로그는 공개설정이")
_CANONICAL_RE = re.compile(r"rss\.blog\.naver\.com/([^/?.]+)")


async def _get(client: httpx.AsyncClient, url: str, headers: Dict[str, str],
               timeout: float = TIMEOUT) -> Optional[httpx.Response]:
    try:
        return await client.get(url, headers=headers, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        logger.debug("GET %s 실패: %s", url, e)
        return None


def _naver_level_from(text: str) -> Optional[int]:
    for pat in _NAVER_LEVEL:
        for m in re.finditer(pat, text):
            v = _to_int(m.group(1))
            if v is not None and 1 <= v <= 4:
                return v
    return None


async def resolve_canonical_blog_id(blog_id: str) -> Optional[str]:
    """NOT_FOUND 시 주소 오입력 교정: rss 리다이렉트 Location 에서 진짜 id 추출.
    (사용자가 로그인 ID를 블로그 주소로 착각하는 경우가 잦다)"""
    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=TIMEOUT) as client:
            r = await client.get(f"https://rss.blog.naver.com/{blog_id}.xml",
                                 headers={"User-Agent": _desktop_ua()})
        loc = r.headers.get("location") or r.headers.get("Location") or ""
        m = _CANONICAL_RE.search(loc)
        if m and m.group(1) and m.group(1) != blog_id:
            return m.group(1)
    except Exception as e:  # noqa: BLE001
        logger.debug("canonical 조회 실패(%s): %s", blog_id, e)
    return None


async def scrape_blog_stats(blog_id: str) -> Dict[str, Any]:
    """1-1. 데스크톱과 모바일을 동시 요청. 지표 본체는 모바일에 있다.
    (데스크톱 blog.naver.com/{id} 는 프레임 껍데기 ≈2.8KB)"""
    result: Dict[str, Any] = {
        "success": False,
        "error_code": None,
        "error_message": None,
        "canonical_blog_id": None,
        "total_posts": None,
        "neighbor_count": None,
        "total_visitors": None,
        "daily_visitors_fallback": None,   # "dayVisitorCount" (1-2 실측이 없을 때만 표시용)
        "naver_level": None,
        "data_source": None,
        "cumulative_visitors_real": False,
    }
    desktop_headers = {"User-Agent": _desktop_ua(), "Referer": "https://blog.naver.com/",
                       "Accept-Language": "ko-KR,ko;q=0.9"}
    mobile_headers = {"User-Agent": IPHONE_UA, "Referer": "https://m.blog.naver.com/",
                      "Accept-Language": "ko-KR,ko;q=0.9"}

    async with httpx.AsyncClient(follow_redirects=True) as client:
        d_resp, m_resp = await asyncio.gather(
            _get(client, f"https://blog.naver.com/{blog_id}", desktop_headers),
            _get(client, f"https://m.blog.naver.com/{blog_id}", mobile_headers),
        )

    d_text = d_resp.text if d_resp is not None else ""
    m_text = m_resp.text if m_resp is not None else ""
    m_final_url = str(m_resp.url) if m_resp is not None else ""

    if d_resp is None and m_resp is None:
        result["error_code"] = "FETCH_FAILED"
        result["error_message"] = "네이버 블로그 페이지에 접속하지 못했습니다."
        return result

    # ★ 비공개 / 존재하지 않는 블로그 감지 (네이버는 없는 주소에도 HTTP 200을 준다)
    error_code = None
    if "MobileErrorView" in m_final_url:                      # 1) 가장 확실
        error_code = "NOT_FOUND"
    elif (m_resp is not None and m_resp.status_code == 404) or \
         (d_resp is not None and d_resp.status_code == 404):  # 2) 404
        error_code = "NOT_FOUND"
    else:
        for t in _NOT_FOUND_TEXTS:                            # 2)/3) 본문 문구
            if t in m_text or t in d_text:
                error_code = "NOT_FOUND"
                break
        if error_code is None:
            for t in _PRIVATE_TEXTS:                          # 4) 비공개
                if t in m_text or t in d_text:
                    error_code = "PRIVATE_BLOG"
                    break

    if error_code == "NOT_FOUND":
        canonical = await resolve_canonical_blog_id(blog_id)
        if canonical:
            result["error_code"] = "MOVED"
            result["canonical_blog_id"] = canonical
            result["error_message"] = f"블로그 주소가 '{canonical}' 로 확인됩니다. 입력한 아이디는 블로그 주소가 아닐 수 있습니다."
        else:
            result["error_code"] = "NOT_FOUND"
            result["error_message"] = "존재하지 않는 블로그입니다."
        return result
    if error_code == "PRIVATE_BLOG":
        result["error_code"] = "PRIVATE_BLOG"
        result["error_message"] = "비공개 블로그입니다."
        return result

    # 모바일 하이드레이션 JSON 우선, 데스크톱 보조, 텍스트 폴백
    total_posts = _first_int(_MOBILE_POSTS, m_text)
    if total_posts is None:
        total_posts = _first_int(_DESKTOP_POSTS, d_text)

    neighbor_count = _first_int(_MOBILE_NEIGHBORS, m_text)
    if neighbor_count is None:
        neighbor_count = _first_int(_DESKTOP_NEIGHBORS, d_text)
    if neighbor_count is None:
        neighbor_count = _first_int(_TEXT_NEIGHBORS, m_text)
        if neighbor_count is None:
            neighbor_count = _first_int(_TEXT_NEIGHBORS, d_text)

    total_visitors = _first_int(_MOBILE_VISITORS, m_text)
    if total_visitors is None:
        total_visitors = _first_int(_DESKTOP_VISITORS, d_text)

    daily_fallback = _first_int(_MOBILE_DAILY, m_text)

    naver_level = _naver_level_from(m_text)
    if naver_level is None:
        naver_level = _naver_level_from(d_text)

    result.update({
        "total_posts": total_posts,
        "neighbor_count": neighbor_count,
        "total_visitors": total_visitors,
        "daily_visitors_fallback": daily_fallback,
        "naver_level": naver_level,
        "cumulative_visitors_real": total_visitors is not None,
    })
    # 성공 판정: 셋 중 하나라도 not None (postCount=0 도 측정 결과다)
    if total_posts is not None or neighbor_count is not None or total_visitors is not None:
        result["success"] = True
        result["data_source"] = "scrape"
    else:
        result["error_code"] = "PARSE_FAILED"
        result["error_message"] = "블로그 페이지에서 지표(포스트/이웃/방문자)를 찾지 못했습니다."
        logger.info("scrape_blog_stats(%s): 지표 없음 (desktop %s bytes, mobile %s bytes, final=%s)",
                    blog_id, len(d_text), len(m_text), m_final_url)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 1-2. 실측 일별 방문자 (NVisitorgp4Ajax)
# ══════════════════════════════════════════════════════════════════════════════
_VISITOR_RE = re.compile(r'<visitorcnt\s+id="(\d{8})"\s+cnt="(\d+)"')


async def fetch_visitor_series(blog_id: str) -> Dict[str, Any]:
    """최근 5일치 일별 방문 수(누적 아님). measured=True 일 때만 점수에 반영."""
    out: Dict[str, Any] = {"measured": False, "series": [], "today": None, "recent_avg": None}
    headers = {
        "User-Agent": _desktop_ua(),
        "Referer": f"https://blog.naver.com/{blog_id}",
        "Accept": "application/xml,text/xml,*/*;q=0.8",
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=TIMEOUT) as client:
            r = await client.get(f"https://blog.naver.com/NVisitorgp4Ajax.naver",
                                 params={"blogId": blog_id}, headers=headers)
    except Exception as e:  # noqa: BLE001
        logger.debug("visitor series 실패(%s): %s", blog_id, e)
        return out
    if r.status_code != 200:
        return out
    daily = [(d, int(c)) for d, c in _VISITOR_RE.findall(r.text)]
    if not daily:
        return out
    daily.sort(key=lambda x: x[0])   # 오래된→최신
    series = [{"date": d, "count": c} for d, c in daily]
    today = daily[-1][1]
    prev = [c for _, c in daily[:-1]]   # 마지막(오늘, 진행 중일 수 있음) 제외
    recent_avg = round(statistics.fmean(prev), 1) if prev else round(statistics.fmean([c for _, c in daily]), 1)
    out.update({"measured": True, "series": series, "today": today, "recent_avg": recent_avg})
    return out


# ══════════════════════════════════════════════════════════════════════════════
# 1-3. RSS 피드
# ══════════════════════════════════════════════════════════════════════════════
_TAG_RE = re.compile(r"<[^>]+>")
_POSTNO_RE1 = re.compile(r"blog\.naver\.com/([^/]+)/(\d+)")
_POSTNO_RE2 = re.compile(r"blogId=([^&]+).*logNo=(\d+)")


def _post_no_from_url(url: str) -> Optional[str]:
    m = _POSTNO_RE1.search(url or "")
    if m:
        return m.group(2)
    m = _POSTNO_RE2.search(url or "")
    if m:
        return m.group(2)
    return None


def _blog_id_from_url(url: str) -> Optional[str]:
    m = _POSTNO_RE1.search(url or "")
    if m:
        return m.group(1)
    m = _POSTNO_RE2.search(url or "")
    if m:
        return m.group(1)
    return None


def _parse_pubdate(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        dt = parsedate_to_datetime(s.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:  # noqa: BLE001
        pass
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
    return None


def _strip_tags(html: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", html or "")).strip()


def _parse_rss_items(xml_text: str) -> Dict[str, Any]:
    """RSS 2.0 → {title, items}. ElementTree 실패 시 정규식 폴백."""
    channel_title = None
    items: List[Dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
        channel = root.find("channel")
        if channel is not None:
            channel_title = (channel.findtext("title") or "").strip() or None
            for it in channel.findall("item"):
                items.append({
                    "title": (it.findtext("title") or "").strip(),
                    "link": (it.findtext("link") or "").strip(),
                    "description": it.findtext("description") or "",
                    "pub_date_raw": (it.findtext("pubDate") or "").strip(),
                    "category": (it.findtext("category") or "").strip(),
                })
    except ET.ParseError:
        m = re.search(r"<channel>.*?<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", xml_text, re.S)
        channel_title = m.group(1).strip() if m else None
        for block in re.findall(r"<item>(.*?)</item>", xml_text, re.S):
            def _f(tag: str) -> str:
                mm = re.search(rf"<{tag}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{tag}>", block, re.S)
                return (mm.group(1) if mm else "")
            items.append({
                "title": _f("title").strip(), "link": _f("link").strip(),
                "description": _f("description"), "pub_date_raw": _f("pubDate").strip(),
                "category": _f("category").strip(),
            })
    return {"title": channel_title, "items": items}


def _rss_analysis(items: List[Dict[str, Any]], now: datetime) -> Dict[str, Any]:
    """1-3 분석 필드 계산."""
    analysis: Dict[str, Any] = {
        "total_posts_rss": None,        # len(items) 폴백 (48개 미만일 때만)
        "total_posts_min": None,        # 48개 이상이면 하한값으로만 표기
        "avg_post_length": None,
        "avg_image_count": None,
        "avg_word_count": None,
        "category_count": None,
        "category_entropy": None,
        "recent_activity": None,
        "rss_window_days": None,
        "rss_truncated": False,
        "posts_last_90d": None,
        "posting_interval_days": None,
        "posting_burstiness": None,
    }
    if not items:
        return analysis

    n = len(items)
    if n >= RSS_TRUNCATED_MIN:
        analysis["total_posts_min"] = n
    else:
        analysis["total_posts_rss"] = n

    # 처음 10개 description 기준
    head = items[:10]
    lengths, imgs, words = [], [], []
    for it in head:
        desc = it.get("description") or ""
        if not desc:
            continue
        lengths.append(len(desc))                       # 원문 길이 (태그 포함)
        imgs.append(desc.count("<img"))
        toks = [w for w in _strip_tags(desc).split() if len(w) >= 2]
        words.append(len(toks))
    if lengths:
        analysis["avg_post_length"] = round(statistics.fmean(lengths), 1)
        analysis["avg_image_count"] = round(sum(imgs) / len(lengths), 2)
        analysis["avg_word_count"] = round(statistics.fmean(words), 1)

    # 카테고리 유니크 개수 (없으면 3) + Shannon entropy(bits)
    cats = [it.get("category") for it in items if it.get("category")]
    if cats:
        counts: Dict[str, int] = {}
        for c in cats:
            counts[c] = counts.get(c, 0) + 1
        analysis["category_count"] = len(counts)
        total = len(cats)
        ent = -sum((c / total) * math.log2(c / total) for c in counts.values())
        analysis["category_entropy"] = round(ent, 4)
    else:
        analysis["category_count"] = 3

    dates = [d for d in (_parse_pubdate(it.get("pub_date_raw")) for it in items) if d is not None]
    if dates:
        dates.sort(reverse=True)     # 최신 → 오래된
        latest, oldest = dates[0], dates[-1]
        analysis["recent_activity"] = max(0, (now - latest).days)
        analysis["rss_window_days"] = max(0, (now - oldest).days)
        analysis["rss_truncated"] = len(dates) >= RSS_TRUNCATED_MIN and analysis["rss_window_days"] < 90
        cutoff = now - timedelta(days=90)
        analysis["posts_last_90d"] = sum(1 for d in dates if d >= cutoff)

        # posting_interval_days: 최근 20개의 인접 간격 + ★ 마지막 글→오늘 공백(gap_days) 포함
        recent = dates[:20]
        intervals = [max(0.0, (recent[i] - recent[i + 1]).total_seconds() / 86400.0)
                     for i in range(len(recent) - 1)]
        gap_days = max(0.0, (now - latest).total_seconds() / 86400.0)
        intervals.append(gap_days)
        analysis["posting_interval_days"] = round(statistics.fmean(intervals), 2)
        # burstiness: 간격 4개 이상일 때 pstdev/mean (변동계수)
        if len(intervals) >= 4:
            mean = statistics.fmean(intervals)
            if mean > 0:
                analysis["posting_burstiness"] = round(statistics.pstdev(intervals) / mean, 3)
    return analysis


async def fetch_rss(blog_id: str, timeout: float = TIMEOUT) -> Dict[str, Any]:
    """1-3. RSS 피드. ⚠️ 하드캡 50개. ⚠️ 미발행/비공개는 404가 아니라 빈 피드 200."""
    out: Dict[str, Any] = {
        "ok": False, "rss_empty": False, "blog_name": None, "items": [],
        "analysis": _rss_analysis([], datetime.now(timezone.utc)),
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            r = await client.get(f"https://rss.blog.naver.com/{blog_id}.xml",
                                 headers={"User-Agent": _desktop_ua(), "Accept": "application/rss+xml,application/xml,text/xml,*/*"})
    except Exception as e:  # noqa: BLE001
        logger.debug("rss 실패(%s): %s", blog_id, e)
        return out
    if r.status_code != 200 or not r.text:
        return out
    parsed = _parse_rss_items(r.text)
    out["ok"] = True
    title = parsed.get("title")
    if title and title != blog_id:
        out["blog_name"] = title
    items = []
    for it in parsed["items"][:RSS_HARD_CAP]:
        dt = _parse_pubdate(it.get("pub_date_raw"))
        items.append({
            "title": it.get("title") or "",
            "link": it.get("link") or "",
            "description": it.get("description") or "",
            "pub_date": dt.isoformat() if dt else None,
            "pub_date_raw": it.get("pub_date_raw") or "",
            "category": it.get("category") or "",
            "post_no": _post_no_from_url(it.get("link") or ""),
        })
    out["items"] = items
    out["rss_empty"] = len(items) == 0
    out["analysis"] = _rss_analysis(parsed["items"][:RSS_HARD_CAP], datetime.now(timezone.utc))
    return out


# ══════════════════════════════════════════════════════════════════════════════
# 1-4. 글 1개 풀파싱 (analyze_post)
# ══════════════════════════════════════════════════════════════════════════════
_PRELOADED_RE = re.compile(r"__PRELOADED_STATE__\s*=\s*(\{.+?\});?\s*</script>", re.S)
# raw content(HTML)에서 추출
_HEADING_RE1 = re.compile(r'<(h[2-4]|strong|b)[^>]*class="[^"]*se-[^"]*"[^>]*>', re.I)
_HEADING_RE2 = re.compile(r'<(h[2-4])[^>]*>', re.I)
_PARA_RE1 = re.compile(r'<(p|div)[^>]*class="[^"]*se-text-paragraph[^"]*"[^>]*>', re.I)
_PARA_RE2 = re.compile(r'<p[^>]*>', re.I)
_MAP_RE = re.compile(r'se-map|class="map|map\.naver|place_thumb', re.I)
_HREF_RE = re.compile(r'href="(https?://[^"]+)"')
_IMG_RE = re.compile(r'<img[^>]+>', re.I)
# 공감/댓글 인라인 폴백
_LIKE_INLINE_RE = re.compile(r'(?:sympathyCnt|sympathyCount|likeCount)\s*=\s*["\']?(\d+)["\']?')
_COMMENT_INLINE_RE = re.compile(r'commentCount\s*=\s*["\']?(\d+)["\']?')
# 작성일 5단계 폴백
_DATE_SEL = ".se_publishDate, .se-date, ._postAddDate, .post_date, .date, .blog_date, time"
_DATE_YMD_RE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")
_DATE_TS14_RE = re.compile(r'(?:addDate|logDate|publishDate|date)["\'\s:=]+["\']?(\d{14})')
_DATE_META_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_DATE_ANY_RE = re.compile(r"(20[12][0-9])[\.\-/]([01]?[0-9])[\.\-/]([0-3]?[0-9])")

# 모바일 HTML 셀렉터 (원본 그대로)
_SEL_TITLE = [".se-title-text", ".tit_h3", "._postTitleText", ".post_tit", "h3.se_textarea", ".tit_view"]
_SEL_CONTENT = [".se-main-container", "._postView", ".post_ct", "#postViewArea", ".se_component_wrap", ".__viewer_container"]
_SEL_CONTENT_FB = ["article", ".post_article", ".blog_view_content"]
_SEL_IMAGES = '.se-image-resource, img.se_mediaImage, ._postView img, .post_ct img, img[src*="blogfiles"], img[src*="postfiles"]'
_SEL_VIDEOS = '.se-video, iframe[src*="video"], iframe[src*="youtube"], iframe[src*="tv.naver"], .video_player'
_SEL_HEADINGS = ".se-section-title, .se-text-paragraph-align-center, h2, h3, h4, .se-title, strong.se-text-paragraph"
_SEL_PARAGRAPHS = ".se-text-paragraph, p, .se-module-text"
_SEL_MAP = '.se-map, iframe[src*="map"], .map_area, .place_thumb, .se-place'
_SEL_EXT_LINK = 'a[href*="http"]:not([href*="naver.com"]):not([href*="naver.net"])'
_SEL_LIKES = ".u_cnt, .sympathy_count, ._sympathyCount, .like_count, .btn_like_count"
_SEL_COMMENTS = ".comment_count, ._commentCount, .cmt_count, .btn_comment_count"


def _empty_post(post_url: str) -> Dict[str, Any]:
    return {
        "success": False, "post_url": post_url, "blog_id": None, "post_no": None,
        "title": None, "content_length": None, "image_count": None, "video_count": None,
        "heading_count": None, "paragraph_count": None, "has_map": None, "has_link": None,
        "like_count": None, "comment_count": None, "post_age_days": None, "publish_date": None,
        "title_has_keyword": None, "title_keyword_position": None,
        "keyword_count": None, "keyword_density": None,
        "fetch_method": None, "cached": False, "error": None,
    }


def _safe_date(y: str, m: str, d: str) -> Optional[datetime]:
    try:
        return datetime(int(y), int(m), int(d), tzinfo=timezone.utc)
    except ValueError:
        return None


def _date_from_value(v: Any) -> Optional[datetime]:
    """PostView addDate/logDate — epoch ms / 14자리 / 'YYYY.MM.DD' 등."""
    if v is None:
        return None
    s = str(v).strip()
    if re.fullmatch(r"\d{13}", s):
        try:
            return datetime.fromtimestamp(int(s) / 1000, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if re.fullmatch(r"\d{10}", s):
        try:
            return datetime.fromtimestamp(int(s), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if re.fullmatch(r"\d{14}", s):
        return _safe_date(s[0:4], s[4:6], s[6:8])
    m = _DATE_YMD_RE.search(s)
    if m:
        return _safe_date(*m.groups())
    return None


def _date_from_html(html: str, soup: Optional[BeautifulSoup]) -> Optional[datetime]:
    """1-4 작성일 폴백 1)~4) (5)는 RSS)."""
    # 1) 날짜 셀렉터
    if soup is not None:
        try:
            for el in soup.select(_DATE_SEL):
                txt = el.get_text(" ", strip=True) or el.get("datetime", "") or ""
                m = _DATE_YMD_RE.search(txt)
                if m:
                    dt = _safe_date(*m.groups())
                    if dt:
                        return dt
        except Exception:  # noqa: BLE001
            pass
    # 2) 14자리 타임스탬프
    m = _DATE_TS14_RE.search(html)
    if m:
        s = m.group(1)
        dt = _safe_date(s[0:4], s[4:6], s[6:8])
        if dt:
            return dt
    # 3) meta article:published_time / name=date
    if soup is not None:
        try:
            for sel in ['meta[property="article:published_time"]', 'meta[name="date"]']:
                el = soup.select_one(sel)
                if el and el.get("content"):
                    m = _DATE_META_RE.search(el["content"])
                    if m:
                        dt = _safe_date(*m.groups())
                        if dt:
                            return dt
        except Exception:  # noqa: BLE001
            pass
    # 4) HTML 전체
    m = _DATE_ANY_RE.search(html)
    if m:
        dt = _safe_date(*m.groups())
        if dt:
            return dt
    return None


async def _date_from_rss(blog_id: str, post_no: str, rss_items: Optional[List[Dict[str, Any]]] = None) -> Optional[datetime]:
    """5) RSS에서 해당 post_no의 pubDate (가장 확실)."""
    if rss_items:
        for it in rss_items:
            if str(it.get("post_no")) == str(post_no):
                dt = _parse_pubdate(it.get("pub_date_raw")) or (
                    datetime.fromisoformat(it["pub_date"]) if it.get("pub_date") else None)
                if dt:
                    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=TIMEOUT) as client:
            r = await client.get(f"https://rss.blog.naver.com/{blog_id}.xml",
                                 headers={"User-Agent": _desktop_ua()})
        if r.status_code == 200:
            m = re.search(rf"<item>.*?<link>[^<]*/{re.escape(str(post_no))}</link>.*?<pubDate>([^<]+)</pubDate>", r.text, re.S)
            if m:
                return _parse_pubdate(m.group(1))
    except Exception as e:  # noqa: BLE001
        logger.debug("rss 날짜 폴백 실패(%s/%s): %s", blog_id, post_no, e)
    return None


def _keyword_fields(title: str, content_text: str, keyword: Optional[str]) -> Dict[str, Any]:
    """제목 키워드 위치 + 키워드 밀도(1000자당)."""
    if not keyword:
        return {"title_has_keyword": None, "title_keyword_position": None,
                "keyword_count": None, "keyword_density": None}
    kw = keyword.replace(" ", "").lower()
    t = (title or "").replace(" ", "").lower()
    pos = t.find(kw) if kw else -1
    if pos < 0:
        position = -1
    elif pos == 0:
        position = 0            # 맨앞
    elif pos > len(t) * 0.7:
        position = 2            # 끝
    else:
        position = 1            # 중간
    body = (content_text or "").replace(" ", "").lower()
    count = body.count(kw) if kw else 0
    length = len(content_text or "")
    density = round(count * 1000 / length, 3) if length > 0 else 0.0   # 1000자당 등장 횟수
    return {"title_has_keyword": position != -1, "title_keyword_position": position,
            "keyword_count": count, "keyword_density": density}


def _analyze_raw_content(content_html: str) -> Dict[str, Any]:
    """PostView raw content(HTML) 정규식 추출 (1-4 방법 1)."""
    heading_count = len(_HEADING_RE1.findall(content_html)) + len(_HEADING_RE2.findall(content_html))
    paragraph_count = len(_PARA_RE1.findall(content_html)) + len(_PARA_RE2.findall(content_html))
    has_map = bool(_MAP_RE.search(content_html))
    has_link = any(("naver.com" not in h and "naver.net" not in h) for h in _HREF_RE.findall(content_html))
    image_count = len(_IMG_RE.findall(content_html))
    content_text = _strip_tags(content_html)
    return {"heading_count": heading_count, "paragraph_count": paragraph_count,
            "has_map": has_map, "has_link": has_link, "image_count": image_count,
            "content_text": content_text}


async def _fetch_postview(client: httpx.AsyncClient, blog_id: str, post_no: str) -> Optional[Dict[str, Any]]:
    """방법 1 — PostView API. 프리로드 JSON json['post']['post']."""
    url = f"https://blog.naver.com/PostView.naver?blogId={blog_id}&logNo={post_no}&redirect=Dlog"
    r = await _get(client, url, {"User-Agent": IPHONE_UA, "Referer": "https://search.naver.com/",
                                 "Accept-Language": "ko-KR,ko;q=0.9"}, timeout=POST_TIMEOUT)
    if r is None or r.status_code != 200:
        return None
    html = r.text
    m = _PRELOADED_RE.search(html)
    if not m:
        return None
    try:
        state = json.loads(m.group(1))
    except Exception:  # noqa: BLE001
        return None
    post = ((state.get("post") or {}).get("post")) if isinstance(state, dict) else None
    if not isinstance(post, dict):
        return None
    content_html = post.get("content") or post.get("text") or ""
    raw = _analyze_raw_content(content_html)
    out = {
        "title": post.get("title"),
        "content_html": content_html,
        "content_text": raw["content_text"],
        "image_count": _to_int(post.get("imageCount")) if post.get("imageCount") is not None else raw["image_count"],
        "video_count": _to_int(post.get("videoCount")) or 0,
        "like_count": _to_int(post.get("sympathyCount")),
        "comment_count": _to_int(post.get("commentCount")),
        "heading_count": raw["heading_count"],
        "paragraph_count": raw["paragraph_count"],
        "has_map": raw["has_map"],
        "has_link": raw["has_link"],
        "publish_dt": _date_from_value(post.get("addDate") if post.get("addDate") is not None else post.get("logDate")),
        "html": html,
    }
    if out["image_count"] is None:
        out["image_count"] = raw["image_count"]
    return out


def _first_number_in(elements) -> Optional[int]:
    for el in elements:
        txt = el.get_text(" ", strip=True)
        m = re.search(r"\d[\d,]*", txt or "")
        if m:
            v = _to_int(m.group(0))
            if v is not None:
                return v
    return None


def extract_post_from_html(html: str, keyword: Optional[str], blog_id: str, post_no: str) -> Dict[str, Any]:
    """방법 2 의 CPU 부분 전부 — 모바일 HTML 문자열 → 1-4 필드 dict. **순수 동기 함수** (프로세스 풀에서 실행).

    반환값은 str/int/bool/None 만 담는다(pickle 안전). publish_dt 는 ISO 문자열(또는 None) 이며
    호출자(async)가 datetime 으로 되돌린다. 셀렉터·정규식·폴백 순서는 이식 전과 동일(스펙 이식).
    parser_pid 는 어느 프로세스가 파싱했는지 확인용(호출자가 1회 로그 후 제거)."""
    soup = _soup(html)

    # 제목
    title = None
    for sel in _SEL_TITLE:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            title = el.get_text(" ", strip=True)
            break
    if not title:
        og = soup.select_one('meta[property="og:title"]')
        title = og["content"].strip() if og and og.get("content") else None

    # 본문
    fetch_method = "mobile_html"
    content_el = None
    for sel in _SEL_CONTENT + _SEL_CONTENT_FB:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            content_el = el
            break
    if content_el is not None:
        content_text = re.sub(r"\s+", " ", content_el.get_text(" ", strip=True)).strip()
        content_length = len(content_text)
    else:
        ogd = soup.select_one('meta[property="og:description"]')
        desc = ogd["content"].strip() if ogd and ogd.get("content") else ""
        content_text = desc
        content_length = len(desc) * 8          # og:description 길이×8 로 추정
        fetch_method = "og_fallback"

    scope = content_el if content_el is not None else soup

    def _count(sel: str, root=None) -> int:
        try:
            return len((root if root is not None else soup).select(sel))
        except Exception:  # noqa: BLE001
            return 0

    image_count = _count(_SEL_IMAGES)
    if image_count == 0:
        image_count = _count('meta[property="og:image"]')
    video_count = _count(_SEL_VIDEOS)
    heading_count = _count(_SEL_HEADINGS, scope)
    try:
        paragraph_count = sum(1 for el in scope.select(_SEL_PARAGRAPHS)
                              if len(el.get_text(" ", strip=True)) > 10)   # 텍스트 10자 초과만 유효
    except Exception:  # noqa: BLE001
        paragraph_count = 0
    has_map = _count(_SEL_MAP) > 0
    has_link = _count(_SEL_EXT_LINK, scope) > 0

    like_count = _first_number_in(soup.select(_SEL_LIKES))
    if like_count is None:
        m = _LIKE_INLINE_RE.search(html)
        like_count = _to_int(m.group(1)) if m else None
    comment_count = _first_number_in(soup.select(_SEL_COMMENTS))
    if comment_count is None:
        m = _COMMENT_INLINE_RE.search(html)
        comment_count = _to_int(m.group(1)) if m else None

    # 작성일 1)~4) (5 RSS 는 호출자). 예전엔 analyze_post 가 같은 soup 로 한 번 더 시도했지만 입력이 같아
    # 결과도 같으므로(None) 여기서 한 번만 한다.
    publish_dt = _date_from_html(html, soup)

    out: Dict[str, Any] = {
        "blog_id": blog_id, "post_no": post_no,
        "title": title, "content_text": content_text, "content_length": content_length,
        "image_count": image_count, "video_count": video_count,
        "heading_count": heading_count, "paragraph_count": paragraph_count,
        "has_map": has_map, "has_link": has_link,
        "like_count": like_count, "comment_count": comment_count,
        "publish_dt": publish_dt.isoformat() if publish_dt else None,
        "fetch_method": fetch_method,
        "parser_pid": os.getpid(),
    }
    # 키워드 필드는 _finalize_post 와 동일하게 캐시 저장 본문(30000자 컷) 기준으로 계산한다.
    out.update(_keyword_fields(title or "", content_text[:30000], keyword))
    return out


def extract_date_from_html(html: str) -> Optional[str]:
    """PostView 경로용 작성일 폴백 1)~4) — **순수 동기 함수** (프로세스 풀). ISO 문자열 또는 None."""
    try:
        soup: Optional[BeautifulSoup] = _soup(html)
    except Exception:  # noqa: BLE001
        soup = None
    dt = _date_from_html(html, soup)
    return dt.isoformat() if dt else None


_parser_pid_logged = False


async def _fetch_mobile_post(client: httpx.AsyncClient, blog_id: str, post_no: str,
                             keyword: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """방법 2 — 모바일 HTML (본문이 100자 미만이면 폴백). 빠른 실패 후 1회 재시도.
    I/O 만 여기서(이벤트루프) 하고, 파싱은 통째로 extract_post_from_html 을 프로세스 풀에서 돌린다."""
    global _parser_pid_logged
    url = f"https://m.blog.naver.com/{blog_id}/{post_no}"
    headers = {"User-Agent": ANDROID_UA, "Referer": "https://m.search.naver.com/",
               "Accept-Language": "ko-KR,ko;q=0.9"}
    r = None
    for _ in range(2):
        async with _post_fetch_gate:
            r = await _get(client, url, headers, timeout=POST_TIMEOUT)
        if r is not None:
            break
    if r is None or r.status_code != 200:
        return None
    html = r.text
    data = await _run_cpu(extract_post_from_html, html, keyword, blog_id, post_no)
    pid = data.pop("parser_pid", None)
    if not _parser_pid_logged:
        _parser_pid_logged = True
        logger.info("blogindex parse: %s (worker pid=%s, main pid=%s)",
                    "process pool" if pid is not None and pid != os.getpid() else "thread fallback",
                    pid, os.getpid())
    iso = data.get("publish_dt")
    data["publish_dt"] = datetime.fromisoformat(iso) if iso else None
    return data


# AsyncSession 은 동시 사용이 안전하지 않다 — 풀파싱은 글 4개를 동시에 읽으므로
# 세션당 락으로 DB 접근만 직렬화한다 (네트워크 I/O 는 그대로 동시).
_db_locks: "weakref.WeakKeyDictionary[Any, asyncio.Lock]" = weakref.WeakKeyDictionary()


def _db_lock(db) -> asyncio.Lock:
    try:
        lock = _db_locks.get(db)
        if lock is None:
            lock = asyncio.Lock()
            _db_locks[db] = lock
        return lock
    except TypeError:            # weakref 불가 객체 → 공용 락
        global _fallback_lock
        try:
            return _fallback_lock
        except NameError:
            _fallback_lock = asyncio.Lock()
            return _fallback_lock


async def _load_post_cache(db, post_url: str) -> Optional[Dict[str, Any]]:
    if db is None:
        return None
    from app.models.blog_index import PostAnalysisCache
    try:
        async with _db_lock(db):
            row = await db.get(PostAnalysisCache, post_url)
    except Exception as e:  # noqa: BLE001
        logger.debug("post cache 조회 실패(%s): %s", post_url, e)
        return None
    if row is None or not isinstance(row.data, dict) or not row.data.get("success"):
        return None
    return dict(row.data)


async def _save_post_cache(db, post_url: str, blog_id: str, post_no: str, data: Dict[str, Any]) -> None:
    """URL 키 영구 캐시 저장. 분석 세션과 분리된 자기 세션으로 짧게 커밋한다(dbwrite 참고)."""
    if db is None:
        return
    from app.models.blog_index import PostAnalysisCache
    from app.blogindex.dbwrite import isolated_write

    async def _do(s):
        existing = await s.get(PostAnalysisCache, post_url)
        if existing is None:
            s.add(PostAnalysisCache(post_url=post_url, blog_id=blog_id, post_no=post_no,
                                    data=data, fetch_method=data.get("fetch_method")))
        else:
            existing.data = data
            existing.fetch_method = data.get("fetch_method")

    await isolated_write(_do, what=f"post cache {post_url[:60]}")


def _finalize_post(base: Dict[str, Any], keyword: Optional[str]) -> Dict[str, Any]:
    """캐시 데이터(키워드 무관) + 키워드 의존 필드 → 1-4 스키마."""
    out = dict(base)
    out.update(_keyword_fields(out.get("title") or "", out.get("content_text") or "", keyword))
    return out


async def analyze_post(db, post_url: str, keyword: Optional[str] = None,
                       rss_items: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """1-4. 글 1개 풀파싱. URL 키 영구 캐시(발행된 글은 변하지 않는다).
    키워드 의존 필드(제목 위치/밀도)는 캐시된 제목·본문으로 매번 계산한다."""
    result = _empty_post(post_url)
    blog_id = _blog_id_from_url(post_url)
    post_no = _post_no_from_url(post_url)
    if not blog_id or not post_no:
        result["error"] = "URL 파싱 실패"
        return result
    result["blog_id"], result["post_no"] = blog_id, post_no

    cached = await _load_post_cache(db, post_url)
    if cached is not None:
        out = _finalize_post(cached, keyword)
        out["cached"] = True
        out["post_url"] = post_url
        return out

    data: Optional[Dict[str, Any]] = None
    fetch_method = None
    html_for_date = ""      # PostView 경로에서만 채운다 — 모바일 경로는 extract_post_from_html 이 이미 1)~4) 를 시도했다
    client = shared_client()
    if True:
        pv = None
        try:
            # 방법 1(PostView 프리로드 JSON)은 2026-09 현재 네이버가 __PRELOADED_STATE__ 를 더 이상 내려주지
            # 않아 항상 실패한다(실측). 글마다 326KB 요청 하나가 통째로 낭비되므로 기본은 건너뛰고,
            # 마크업이 되살아나면 BLOGINDEX_TRY_POSTVIEW=1 로 다시 켠다. 정규식·키 목록은 그대로 둔다.
            pv = await _fetch_postview(client, blog_id, post_no) if TRY_POSTVIEW else None
        except Exception as e:  # noqa: BLE001
            logger.debug("PostView 실패(%s/%s): %s", blog_id, post_no, e)
        if pv is not None and len(pv.get("content_text") or "") >= 100:
            data = pv
            fetch_method = "postview_api"
            html_for_date = pv.get("html") or ""
            data["content_length"] = len(pv["content_text"])
        else:
            mb = None
            try:
                mb = await _fetch_mobile_post(client, blog_id, post_no, keyword)
            except Exception as e:  # noqa: BLE001
                logger.debug("mobile post 실패(%s/%s): %s", blog_id, post_no, e)
            if mb is not None:
                data = mb
                fetch_method = mb.get("fetch_method") or "mobile_html"
                # PostView 에서 잡힌 공감/댓글/날짜가 있으면 보존 (모바일이 못 잡은 경우)
                if pv is not None:
                    for k in ("like_count", "comment_count"):
                        if data.get(k) is None and pv.get(k) is not None:
                            data[k] = pv[k]
                    if data.get("publish_dt") is None and pv.get("publish_dt") is not None:
                        data["publish_dt"] = pv["publish_dt"]
            elif pv is not None:
                # 본문은 짧지만 PostView 는 응답함 → 그대로 채택 (지어내지 않음)
                data = pv
                fetch_method = "postview_api"
                html_for_date = pv.get("html") or ""
                data["content_length"] = len(pv["content_text"])

    if data is None:
        result["error"] = "본문 조회 실패"
        return result

    publish_dt = data.get("publish_dt")
    if publish_dt is None and html_for_date:
        try:
            iso = await _run_cpu(extract_date_from_html, html_for_date)
        except Exception as e:  # noqa: BLE001
            logger.debug("html 날짜 폴백 실패(%s/%s): %s", blog_id, post_no, e)
            iso = None
        publish_dt = datetime.fromisoformat(iso) if iso else None
    if publish_dt is None:
        publish_dt = await _date_from_rss(blog_id, post_no, rss_items)

    now = datetime.now(timezone.utc)
    post_age_days = max(0, (now - publish_dt).days) if publish_dt else None

    content_text = data.get("content_text") or ""
    base = {
        "success": True, "post_url": post_url, "blog_id": blog_id, "post_no": post_no,
        "title": data.get("title"),
        "content_length": data.get("content_length") if data.get("content_length") is not None else len(content_text),
        "content_text": content_text[:30000],
        "image_count": data.get("image_count") or 0,
        "video_count": data.get("video_count") or 0,
        "heading_count": data.get("heading_count") or 0,
        "paragraph_count": data.get("paragraph_count") or 0,
        "has_map": bool(data.get("has_map")),
        "has_link": bool(data.get("has_link")),
        "like_count": data.get("like_count"),
        "comment_count": data.get("comment_count"),
        "post_age_days": post_age_days,
        "publish_date": publish_dt.date().isoformat() if publish_dt else None,
        "fetch_method": fetch_method,
        "cached": False, "error": None,
    }
    await _save_post_cache(db, post_url, blog_id, post_no, base)
    return _finalize_post(base, keyword)


def _avg(vals: List[Optional[float]]) -> Optional[float]:
    xs = [v for v in vals if v is not None]
    return round(statistics.fmean(xs), 2) if xs else None


async def fullparse_recent(db, blog_id: str, items: List[Dict[str, Any]], n: int = FULLPARSE_SAMPLE_SIZE,
                           keyword: Optional[str] = None, per_post_timeout: float = 20.0) -> Dict[str, Any]:
    """최근 글 n개 풀파싱 평균. 동시성 ≤4, 글당 상한 시간. 하나도 못 읽으면 전부 None."""
    targets = []
    for it in (items or []):
        link = it.get("link") or ""
        pn = it.get("post_no") or _post_no_from_url(link)
        if not pn:
            continue
        url = link if _POSTNO_RE1.search(link) else f"https://blog.naver.com/{blog_id}/{pn}"
        targets.append(url)
        if len(targets) >= n:
            break

    sem = asyncio.Semaphore(FULLPARSE_CONCURRENCY)

    async def _one(url: str) -> Optional[Dict[str, Any]]:
        async with sem:
            try:
                return await asyncio.wait_for(analyze_post(db, url, keyword, rss_items=items), timeout=per_post_timeout)
            except asyncio.TimeoutError:
                logger.info("fullparse timeout: %s", url)
            except Exception as e:  # noqa: BLE001
                logger.info("fullparse 실패 %s: %s", url, e)
            return None

    results = await asyncio.gather(*[_one(u) for u in targets]) if targets else []
    posts = [r for r in results if r and r.get("success")]
    out = {
        "fullparse_avg_content_length": _avg([p.get("content_length") for p in posts]),
        "fullparse_avg_images": _avg([p.get("image_count") for p in posts]),
        "fullparse_avg_headings": _avg([p.get("heading_count") for p in posts]),
        "fullparse_avg_paragraphs": _avg([p.get("paragraph_count") for p in posts]),
        "fullparse_avg_likes": _avg([p.get("like_count") for p in posts]),
        "fullparse_avg_comments": _avg([p.get("comment_count") for p in posts]),
        "sample_size": len(posts),
        "attempted": len(targets),
        "cached_hits": sum(1 for p in posts if p.get("cached")),
        "fetch_methods": sorted({p.get("fetch_method") for p in posts if p.get("fetch_method")}),
    }
    return out
