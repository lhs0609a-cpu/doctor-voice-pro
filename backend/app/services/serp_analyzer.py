"""
네이버 모바일 통합검색(통검) SERP 분석 서비스

키워드별로 네이버 **모바일 통합검색** 결과 페이지에 어떤 블로그/카페 글이 노출되는지 수집하고,
노출된 글들의 본문 지표(키워드 등장 횟수, 이미지 수, 글자 수, 소제목 수)와
블로그 유형(병원 / 인플루언서 / 일상·육아 / 체험단)을 판별하여
"병원 블로그가 이 키워드로 통검에 진입할 수 있는가"를 판정한다.

- 글 본문 지표는 `app.services.top_post_analyzer.analyze_post` 를 재사용한다 (중복 파싱 없음).
- 이 모듈은 DB에 접근하지 않는다. 캐시 유효 시간(SERP_CACHE_HOURS)만 제공하고 저장은 호출자가 담당한다.
- 네트워크 오류 / 차단(captcha, 403, 429) 시 예외를 던지지 않고 error 필드에 기록한다.
"""

from __future__ import annotations

import asyncio
import math
import random
import re
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup, Tag

from app.services.top_post_analyzer import analyze_post

# ---------------------------------------------------------------------------
# 설정 상수
# ---------------------------------------------------------------------------

#: 호출자가 SERP 결과를 재사용해도 되는 시간 (시간 단위). DB 저장/조회는 호출자 책임.
SERP_CACHE_HOURS = 24

#: 통검 요청 URL 후보. 첫 번째가 비어 있으면 순서대로 폴백한다. `{q}` 는 URL-encoded 키워드.
SERP_URL_TEMPLATES = [
    "https://m.search.naver.com/search.naver?where=m&sm=mtp_hty.top&query={q}",
    "https://m.search.naver.com/search.naver?ssc=tab.m.all&sm=mtb_hty.top&query={q}",
    "https://m.search.naver.com/search.naver?where=m_view&sm=mtb_jum&query={q}",
]

#: 모바일 User-Agent 로테이션 (iPhone Safari 계열)
MOBILE_USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]

SERP_REFERER = "https://m.naver.com/"
SERP_TIMEOUT_SECONDS = 15.0
SERP_MAX_RESULTS = 15
#: 요청 직전 랜덤 지연 (초)
SERP_DELAY_RANGE = (0.8, 2.0)
#: 개별 글 분석 시 지연 (초) 및 동시 실행 수
POST_DELAY_RANGE = (0.5, 1.5)
POST_CONCURRENCY = 3
#: 응답 본문이 이 길이보다 짧으면 차단/빈 페이지로 간주
MIN_VALID_BODY_LENGTH = 3000

# ---------------------------------------------------------------------------
# 네이버 통검 DOM 셀렉터 (마크업이 자주 바뀌므로 방어적으로 여러 개를 나열)
# ---------------------------------------------------------------------------

#: 섹션(인기글/블로그/VIEW/카페/뉴스/이미지 등) 제목 요소. 앵커의 조상 컨테이너 안에서 이 순서로 탐색한다.
#: - 2026년 현재 모바일 통검은 "fender/sds" 마크업: 섹션 헤더는 .sds-comps-header > .sds-comps-header-title
#: - 구형 마크업: h2.api_title / .api_title
SECTION_HEADING_SELECTORS = [
    ".sds-comps-header-title",
    ".sds-comps-header [class*='text-type-headline']",
    ".fds-comps-header-headline",
    "h2.api_title",
    "h3.api_title",
    ".api_title",
    ".title_area .api_title_inner",
    "h2.tit",
    "h2",
    "h3",
]

#: 섹션 컨테이너로 인정할 조건. 컨테이너 조상 안에서만 제목을 찾는다.
#: - api_subject_bx : 통검의 개별 블록(카드) 컨테이너 (신/구 마크업 공통)
#: - sc_new, sp_*    : 구형 섹션 컨테이너
SECTION_CONTAINER_TAGS = {"section", "main"}
SECTION_CONTAINER_CLASS_HINTS = ("sc_new", "api_subject_bx", "sp_", "sc_page", "_svp_list", "lst_total")

#: 블록 식별 속성. fender 루트(div[data-fender-root]) 의 data-block-id 관측값 (2026-09 기준):
#:   review/prs_template_v2_review_blog_rra_mo.ts            블로그·카페 글 카드 (카페도 같은 템플릿 사용)
#:   review/prs_template_v2_review_ugc_single_intention_mo.ts UGC 묶음
#:   image/…, news/…, kin/…, web/…, qra/…                       이미지/뉴스/지식iN/웹문서/QnA
#: 조상 중 이 속성이 있으면 헤더 텍스트가 없을 때 섹션명을 유추한다 (카페 링크는 "카페"로 보정).
SECTION_BLOCK_ID_ATTR = "data-block-id"
SECTION_BLOCK_ID_HINTS = [
    ("popular", "인기글"),
    ("influencer", "인플루언서"),
    ("blog", "블로그"),
    ("cafe", "카페"),
    ("view", "VIEW"),
    ("ugc", "VIEW"),
]
#: 헤더도 block-id 도 없을 때의 섹션 라벨 (통검 본문에 개별 카드로 노출된 글)
SECTION_FALLBACK_LABEL = "통합"
#: 조상 탐색을 멈추는 상위 컨테이너 표시 (data-collection / data-slog-container 는 통검의 컬렉션 단위)
SECTION_STOP_ATTRS = ("data-collection", "data-slog-container")

#: 이 섹션에 속한 링크는 블로그 글 노출로 세지 않는다 (이미지/동영상/뉴스/지식iN 등)
EXCLUDED_SECTIONS = ("이미지", "동영상", "뉴스", "지식iN", "지식인", "쇼핑", "플레이스")
#: 광고성 섹션 힌트 (결과에 is_ad=True 로 표시하고 노출 판정에서는 제외)
AD_SECTION_HINTS = ("브랜드 콘텐츠", "브랜드콘텐츠", "파워링크", "광고")

#: 카드 안의 블로그 프로필(블로그명) 요소
PROFILE_SELECTORS = [
    "[data-sds-comp='Profile']",
    "[class*='sds-comps-profile']",
    ".user_box .name",
    ".sub_name",
    ".name",
]

#: 결과 항목의 제목 텍스트를 담는 요소 (앵커 텍스트가 비어 있을 때 앵커 내부/형제에서 탐색)
RESULT_TITLE_SELECTORS = [
    ".title_link",
    ".api_txt_lines.total_tit",
    ".total_tit",
    ".title_area",
    ".tit",
    ".name",
]

#: 차단/캡차 페이지 판별 문자열. 주의: 정상 통검 페이지의 JS 설정에도 "captcha" 문자열이 들어 있으므로
#: 단순 "captcha" 포함 여부로 판별하면 안 된다. <title> 과 아래의 구체적 마커만 본다.
BLOCKED_TITLE_MARKERS = ("captcha", "자동입력", "자동 입력", "접근 제한", "access denied", "error")
BLOCKED_BODY_MARKERS = (
    "자동입력 방지", "자동 입력 방지", "비정상적인 검색", "비정상적인 접근", "접근이 제한",
    "captcha_form", "id=\"captcha\"", "name=\"captcha\"",
)

# ---------------------------------------------------------------------------
# URL 패턴
# ---------------------------------------------------------------------------

# https://blog.naver.com/{id}/{postno}, https://m.blog.naver.com/{id}/{postno}
_BLOG_PATH_RE = re.compile(r"(?:m\.)?blog\.naver\.com/([A-Za-z0-9_\-.]+)/(\d{6,})")
# https://blog.naver.com/PostView.naver?blogId=..&logNo=..  (PostView.nhn 포함, 파라미터 순서 무관)
_BLOG_POSTVIEW_RE = re.compile(r"blog\.naver\.com/PostView(?:\.naver|\.nhn)?\?", re.IGNORECASE)
# https://cafe.naver.com/{club}/{article}, https://cafe.naver.com/ca-fe/web/cafes/{club}/articles/{article}
_CAFE_PATH_RE = re.compile(
    r"(?:m\.|article\.)?cafe\.naver\.com/(?:ca-fe/web/cafes/)?([A-Za-z0-9_\-.]+)(?:/articles)?/(\d+)"
)
_CAFE_ARTICLE_READ_RE = re.compile(r"cafe\.naver\.com/ArticleRead(?:\.naver|\.nhn)?\?", re.IGNORECASE)

# ---------------------------------------------------------------------------
# 블로그 유형 판별 패턴
# ---------------------------------------------------------------------------

HOSPITAL_TERMS_KO = (
    "한의원", "병원", "의원", "클리닉", "피부과", "치과", "정형외과", "내과", "외과", "안과",
    "이비인후과", "산부인과", "비뇨기과", "재활의학과", "성형외과", "신경외과", "정신건강의학과",
    "소아과", "소아청소년과", "가정의학과", "통증의학과", "한방", "의료진", "원장",
)
HOSPITAL_TERMS_LATIN = (
    "clinic", "hospital", "dental", "derma", "doctor", "medical", "medi", "hanui", "hanbang",
    "plastic", "ortho", "surgery", "hanmed", "oriental",
)
EXPERIENCE_TERMS = (
    "체험단", "협찬", "제공받", "원고료", "소정의", "지원받아", "지원을 받아", "서포터즈", "앰배서더",
    "광고 포함", "유료광고", "제공 받",
)
INFLUENCER_TERMS_KO = ("인플루언서", "리뷰어", "블로거", "파워블로거", "리뷰블로그", "크리에이터")
INFLUENCER_TERMS_LATIN = ("influencer", "reviewer", "blogger", "review", "creator")
DAILY_TERMS_KO = ("육아", "일상", "맘", "엄마", "아기", "워킹맘", "새댁", "주부", "다이어리", "브이로그", "라이프")
DAILY_TERMS_LATIN = ("mom", "mama", "mommy", "daily", "life", "diary", "vlog", "baby", "lovely", "happy")

BLOG_TYPES = ("hospital", "influencer", "daily", "experience", "unknown")


# ---------------------------------------------------------------------------
# 유틸리티
# ---------------------------------------------------------------------------

def normalize_keyword(kw: str) -> str:
    """키워드 정규화: 모든 공백 제거 + 라틴 문자 대문자화. (캐시 키 용도)"""
    if not kw:
        return ""
    return re.sub(r"\s+", "", kw).upper()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_headers() -> Dict[str, str]:
    return {
        "User-Agent": random.choice(MOBILE_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": SERP_REFERER,
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-site",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }


def _is_blocked(status_code: int, body: str) -> bool:
    """캡차/차단 페이지 판별. 정상 페이지에도 'captcha' 문자열이 있으므로 title 과 구체적 마커만 사용."""
    if status_code in (403, 429):
        return True
    if len(body) < MIN_VALID_BODY_LENGTH:
        return True
    title_match = re.search(r"<title[^>]*>(.*?)</title>", body[:20000], re.IGNORECASE | re.DOTALL)
    title = (title_match.group(1) if title_match else "").strip().lower()
    if title and any(marker in title for marker in BLOCKED_TITLE_MARKERS):
        return True
    head = body[:60000]
    return any(marker in head for marker in BLOCKED_BODY_MARKERS)


def _parse_result_link(href: str) -> Optional[Dict[str, str]]:
    """
    href 에서 블로그/카페 글 식별자를 추출한다.
    Returns {"kind", "blog_id", "post_no", "url"} 또는 None (글 링크가 아닐 때).
    """
    if not href:
        return None
    href = href.strip()
    if href.startswith("//"):
        href = "https:" + href

    # 블로그: PostView.naver?blogId=..&logNo=..
    if _BLOG_POSTVIEW_RE.search(href):
        qs = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query)
        blog_id = (qs.get("blogId") or [""])[0]
        post_no = (qs.get("logNo") or [""])[0]
        if blog_id and post_no.isdigit():
            return {
                "kind": "blog",
                "blog_id": blog_id,
                "post_no": post_no,
                "url": f"https://blog.naver.com/{blog_id}/{post_no}",
            }
        return None

    # 블로그: /{id}/{postno}
    m = _BLOG_PATH_RE.search(href)
    if m:
        blog_id, post_no = m.group(1), m.group(2)
        if blog_id.lower() in ("postview.naver", "postview.nhn", "postlist.naver"):
            return None
        return {
            "kind": "blog",
            "blog_id": blog_id,
            "post_no": post_no,
            "url": f"https://blog.naver.com/{blog_id}/{post_no}",
        }

    # 카페: ArticleRead.nhn?clubid=..&articleid=..
    if _CAFE_ARTICLE_READ_RE.search(href):
        qs = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query)
        club = (qs.get("clubid") or qs.get("clubId") or [""])[0]
        article = (qs.get("articleid") or qs.get("articleId") or [""])[0]
        if club and article:
            return {"kind": "cafe", "blog_id": club, "post_no": article, "url": href}
        return None

    # 카페: /{club}/{article}
    m = _CAFE_PATH_RE.search(href)
    if m:
        return {"kind": "cafe", "blog_id": m.group(1), "post_no": m.group(2), "url": href}

    return None


def _is_section_container(el: Tag) -> bool:
    if el.name in SECTION_CONTAINER_TAGS:
        return True
    classes = " ".join(el.get("class", []) or [])
    return any(hint in classes for hint in SECTION_CONTAINER_CLASS_HINTS)


def _heading_text_in(container: Tag) -> str:
    for selector in SECTION_HEADING_SELECTORS:
        try:
            heading = container.select_one(selector)
        except Exception:
            heading = None
        if heading is not None:
            text = re.sub(r"\s+", " ", heading.get_text(" ", strip=True))
            if text and len(text) <= 40:
                return text
    return ""


def _section_from_block_id(block_id: str) -> str:
    lowered = (block_id or "").lower()
    for hint, label in SECTION_BLOCK_ID_HINTS:
        if hint in lowered:
            return label
    return ""


def _find_card_container(anchor: Tag, max_depth: int = 14) -> Optional[Tag]:
    """앵커를 감싸는 가장 가까운 카드/섹션 컨테이너 (.api_subject_bx, .sc_new, section ...)."""
    node: Optional[Tag] = anchor
    for _ in range(max_depth):
        node = node.parent if isinstance(node.parent, Tag) else None
        if node is None or node.name in ("[document]", "body", "html"):
            return None
        if _is_section_container(node):
            return node
    return None


def _find_section_heading(anchor: Tag, max_depth: int = 16) -> str:
    """
    앵커에서 조상 방향으로 올라가며 섹션명을 결정한다.
    1) 컨테이너 조상(.api_subject_bx / .sc_new / section) 안의 헤더 텍스트 (예: "뉴스", "이미지", "인기글")
    2) 없으면 조상의 data-block-id 로 유추 (예: "...review_blog..." → "블로그")
    3) data-collection / data-slog-container 조상 또는 body 에 도달하면 중단, SECTION_FALLBACK_LABEL 반환
    """
    node: Optional[Tag] = anchor
    block_id_label = ""
    depth = 0
    while node is not None and depth < max_depth:
        node = node.parent if isinstance(node.parent, Tag) else None
        depth += 1
        if node is None or node.name in ("[document]", "body", "html"):
            break
        if not block_id_label and node.get(SECTION_BLOCK_ID_ATTR):
            block_id_label = _section_from_block_id(str(node.get(SECTION_BLOCK_ID_ATTR)))
        if _is_section_container(node):
            text = _heading_text_in(node)
            if text:
                return text
        if any(node.get(attr) for attr in SECTION_STOP_ATTRS):
            break
    return block_id_label or SECTION_FALLBACK_LABEL


def _find_blog_name(anchor: Tag, blog_id: str) -> str:
    """카드 컨테이너 안에서 블로그명(프로필 텍스트)을 찾는다. 없으면 ""."""
    container = _find_card_container(anchor)
    if container is None:
        return ""
    # 1) 블로그 홈 링크 (…/blog.naver.com/{blog_id}) 의 텍스트
    home_re = re.compile(r"blog\.naver\.com/" + re.escape(blog_id) + r"/?(?:[?#].*)?$")
    for a in container.find_all("a", href=True):
        if home_re.search(a["href"]):
            text = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
            if text and len(text) <= 60:
                return text
    # 2) 프로필 요소의 첫 텍스트 조각
    for selector in PROFILE_SELECTORS:
        try:
            prof = container.select_one(selector)
        except Exception:
            prof = None
        if prof is not None:
            for s in prof.stripped_strings:
                s = s.strip()
                if s and len(s) <= 60:
                    return s
    return ""


def _extract_title(anchor: Tag) -> str:
    """앵커 자체 텍스트 → 내부 제목 요소 → title 속성 → 가장 가까운 항목 컨테이너 안의 제목 요소 순으로 탐색."""
    text = anchor.get_text(" ", strip=True)
    if text and len(text) > 1:
        return re.sub(r"\s+", " ", text)
    for selector in RESULT_TITLE_SELECTORS:
        el = anchor.select_one(selector)
        if el is not None:
            t = el.get_text(" ", strip=True)
            if t:
                return re.sub(r"\s+", " ", t)
    attr_title = (anchor.get("title") or anchor.get("aria-label") or "").strip()
    if attr_title:
        return attr_title
    # 썸네일 앵커인 경우: 형제/부모 컨테이너 안에서 제목 요소 탐색 (3단계)
    node: Optional[Tag] = anchor
    for _ in range(3):
        node = node.parent if isinstance(node.parent, Tag) else None
        if node is None:
            break
        for selector in RESULT_TITLE_SELECTORS:
            el = node.select_one(selector)
            if el is not None:
                t = el.get_text(" ", strip=True)
                if t:
                    return re.sub(r"\s+", " ", t)
    return ""


def parse_mobile_serp_html(html: str) -> List[Dict[str, Any]]:
    """
    통검 HTML 에서 블로그/카페 글 링크를 DOM 순서대로 추출한다. (네트워크 없음 — 테스트 용이)
    (blog_id, post_no) 기준 중복 제거, SERP_MAX_RESULTS 개로 제한.
    """
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    results: List[Dict[str, Any]] = []
    index: Dict[tuple, Dict[str, Any]] = {}
    skipped: set = set()

    for anchor in soup.find_all("a", href=True):
        parsed = _parse_result_link(anchor["href"])
        if parsed is None:
            continue
        key = (parsed["blog_id"], parsed["post_no"])
        if key in skipped:
            continue
        title = _extract_title(anchor)
        if key in index:
            # 썸네일 앵커가 먼저 잡혀 제목이 비어 있으면 뒤의 텍스트 앵커로 채운다
            if not index[key]["title"] and title:
                index[key]["title"] = title
            if not index[key]["blog_name"]:
                index[key]["blog_name"] = _find_blog_name(anchor, parsed["blog_id"])
            continue
        section = _find_section_heading(anchor)
        if parsed["kind"] == "cafe" and section == "블로그":
            section = "카페"  # 카페 카드도 review_blog 템플릿을 쓰므로 링크 종류로 보정
        if any(ex in section for ex in EXCLUDED_SECTIONS):
            skipped.add(key)
            continue
        if len(results) >= SERP_MAX_RESULTS:
            # 이미 수집된 항목의 제목 보강만 계속하고 새 항목은 추가하지 않음
            continue
        item = {
            "url": parsed["url"],
            "blog_id": parsed["blog_id"],
            "post_no": parsed["post_no"],
            "title": title,
            "blog_name": _find_blog_name(anchor, parsed["blog_id"]),
            "section": section,
            "position": len(results) + 1,
            "kind": parsed["kind"],
            "is_ad": any(hint in section for hint in AD_SECTION_HINTS),
        }
        index[key] = item
        results.append(item)

    return results


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------

async def fetch_mobile_serp(keyword: str) -> dict:
    """
    네이버 모바일 통합검색 결과 페이지에서 블로그/카페 글 노출 목록을 수집한다.

    Returns:
        {
          "keyword": str, "fetched_at": ISO8601,
          "results": [{"url","blog_id","post_no","title","blog_name","section","position",
                       "kind": "blog"|"cafe", "is_ad": bool}],
          "raw_count": int, "error": None | "blocked" | "empty" | "network: ..." ,
        }
    - position 은 페이지 DOM 순서 (카페/블로그 통합 순번).
    - section 은 헤더 텍스트 또는 data-block-id 유추값, 없으면 "통합".
    - 이미지/뉴스/지식iN 등 EXCLUDED_SECTIONS 안의 링크는 제외, 브랜드 콘텐츠 등은 is_ad=True.
    절대 예외를 던지지 않는다.
    """
    out: Dict[str, Any] = {
        "keyword": keyword,
        "fetched_at": _now_iso(),
        "results": [],
        "raw_count": 0,
        "error": None,
    }
    if not keyword or not keyword.strip():
        out["error"] = "empty keyword"
        return out

    encoded = urllib.parse.quote(keyword.strip())
    last_error: Optional[str] = None

    try:
        async with httpx.AsyncClient(timeout=SERP_TIMEOUT_SECONDS, follow_redirects=True) as client:
            for template in SERP_URL_TEMPLATES:
                url = template.format(q=encoded)
                await asyncio.sleep(random.uniform(*SERP_DELAY_RANGE))
                try:
                    response = await client.get(url, headers=_build_headers())
                except (httpx.HTTPError, asyncio.TimeoutError, OSError) as exc:
                    last_error = f"network: {type(exc).__name__}: {exc}"
                    print(f"[통검 분석] 요청 실패 ({url}): {last_error}")
                    continue

                body = response.text or ""
                print(f"[통검 분석] 응답 {response.status_code}, {len(body)} bytes, 키워드: {keyword}")

                if _is_blocked(response.status_code, body):
                    out["error"] = "blocked"
                    out["fetched_at"] = _now_iso()
                    return out

                if response.status_code != 200:
                    last_error = f"http {response.status_code}"
                    continue

                results = parse_mobile_serp_html(body)
                if results:
                    out["results"] = results
                    out["raw_count"] = len(results)
                    out["fetched_at"] = _now_iso()
                    return out
                last_error = "empty"
    except Exception as exc:  # 방어: 어떤 경우에도 예외를 밖으로 내보내지 않음
        last_error = f"network: {type(exc).__name__}: {exc}"

    out["error"] = last_error or "empty"
    out["fetched_at"] = _now_iso()
    return out


def classify_blog_type(blog_id: str, title: str, post_metrics: dict | None) -> str:
    """
    블로그 유형을 휴리스틱으로 판별하는 순수 함수.

    Args:
        blog_id: 네이버 블로그 ID (예: "seoulskinclinic")
        title: 노출된 글 제목
        post_metrics: analyze_post() 결과 dict 또는 None. 존재하면 "blog_name" 과 "title" 키를 추가 신호로 사용.

    Returns:
        "hospital"    - 병원/의원/클리닉 등 의료기관이 직접 운영하는 블로그로 추정
        "experience"  - 체험단/협찬/제공받은 후기 (병원 키워드가 있어도 우선)
        "influencer"  - 리뷰어/블로거/인플루언서 성격
        "daily"       - 육아/일상/맘 블로그
        "unknown"     - 판단 근거 없음

    우선순위: experience > hospital > influencer > daily > unknown.
    (체험단 글은 병원명이 제목에 들어가므로 체험단 신호를 먼저 본다.)
    """
    blog_id_l = (blog_id or "").lower()
    title_s = title or ""
    blog_name = ""
    if post_metrics:
        blog_name = str(post_metrics.get("blog_name") or "")
        if not title_s:
            title_s = str(post_metrics.get("title") or "")
    text_ko = f"{title_s} {blog_name}"
    text_l = text_ko.lower()

    if any(term in text_ko for term in EXPERIENCE_TERMS):
        return "experience"

    if any(term in text_ko for term in HOSPITAL_TERMS_KO):
        return "hospital"
    if any(term in blog_id_l for term in HOSPITAL_TERMS_LATIN):
        return "hospital"
    if any(term in text_l for term in HOSPITAL_TERMS_LATIN):
        return "hospital"

    if any(term in text_ko for term in INFLUENCER_TERMS_KO):
        return "influencer"
    if any(term in blog_id_l for term in INFLUENCER_TERMS_LATIN):
        return "influencer"

    if any(term in text_ko for term in DAILY_TERMS_KO):
        return "daily"
    if any(term in blog_id_l for term in DAILY_TERMS_LATIN):
        return "daily"
    if any(term in text_l for term in DAILY_TERMS_LATIN):
        return "daily"

    return "unknown"


async def _analyze_one_post(
    item: Dict[str, Any],
    keyword: str,
    semaphore: asyncio.Semaphore,
) -> Optional[Dict[str, Any]]:
    """세마포어 + 지터를 적용해 analyze_post 를 호출. 실패 시 None."""
    async with semaphore:
        await asyncio.sleep(random.uniform(*POST_DELAY_RANGE))
        try:
            metrics = await analyze_post(item["url"], keyword)
        except Exception as exc:
            print(f"[통검 분석] 글 분석 실패 ({item['url']}): {exc}")
            return None
        if not metrics or not metrics.get("data_fetched"):
            return None
        return metrics


def _mean(values: List[float]) -> float:
    return (sum(values) / len(values)) if values else 0.0


def _build_summary(posts: List[Dict[str, Any]], cafe_count: int) -> Dict[str, Any]:
    exposed_count = len(posts)
    analyzed = [p for p in posts if p.get("analyzed")]
    analyzed_count = len(analyzed)

    hospital_count = sum(1 for p in posts if p["blog_type"] == "hospital")
    influencer_count = sum(1 for p in posts if p["blog_type"] == "influencer")
    daily_count = sum(1 for p in posts if p["blog_type"] == "daily")
    experience_count = sum(1 for p in posts if p["blog_type"] == "experience")
    hospital_ratio = round(hospital_count / exposed_count, 3) if exposed_count else 0.0

    avg_kw = _mean([p["kw_count"] for p in analyzed])
    avg_img = _mean([p["image_count"] for p in analyzed])
    avg_chars = _mean([p["chars"] for p in analyzed])
    avg_headings = _mean([p["headings"] for p in analyzed])

    return {
        "exposed_count": exposed_count,
        "analyzed_count": analyzed_count,
        "cafe_count": cafe_count,
        "hospital_count": hospital_count,
        "hospital_ratio": hospital_ratio,
        "influencer_count": influencer_count,
        "daily_count": daily_count,
        "experience_count": experience_count,
        "has_influencer": influencer_count > 0,
        "avg_kw_count": round(avg_kw, 1),
        "avg_image_count": round(avg_img, 1),
        "avg_chars": round(avg_chars),
        "avg_headings": round(avg_headings, 1),
        "recommended_kw_count": max(3, round(avg_kw * 1.1)),
        "recommended_image_count": max(5, math.ceil(avg_img) + 1),
        "recommended_chars": max(1200, round(avg_chars * 1.1)),
    }


def _decide_verdict(summary: Dict[str, Any], error: Optional[str]) -> tuple[str, str]:
    exposed = summary["exposed_count"]
    hospital = summary["hospital_count"]
    ratio = summary["hospital_ratio"]
    influencer = summary["influencer_count"]
    has_influencer = summary["has_influencer"]
    daily = summary["daily_count"]

    if error == "blocked":
        return "unknown", "네이버가 요청을 차단하여 통검 결과를 확인하지 못했습니다."
    if exposed == 0:
        if error:
            return "unknown", f"통검 결과를 가져오지 못했습니다 ({error})."
        return "unknown", "통검에 노출된 블로그 글이 없어 판단할 수 없습니다."

    influencer_txt = f"인플루언서 {influencer}건" if has_influencer else "인플루언서 없음"
    base = f"통검 노출 {exposed}건 중 병원 블로그 {hospital}건({ratio * 100:.0f}%), {influencer_txt}"
    if daily:
        base += f", 일상·육아 {daily}건"

    if ratio >= 0.4 or exposed <= 3:
        if exposed <= 3 and ratio < 0.4:
            return "possible", f"{base} — 노출 글 수가 {exposed}건으로 적어 병원 블로그 진입 여지가 있습니다."
        return "possible", f"{base} — 병원 블로그 비중이 높아 진입 가능합니다."
    if 0.15 <= ratio < 0.4 or (has_influencer and hospital >= 1):
        return "contested", f"{base} — 병원과 비병원 블로그가 경쟁 중인 키워드입니다."
    if hospital == 0 and exposed >= 4:
        return "avoid", f"{base} — 병원 블로그가 전혀 노출되지 않아 진입이 어렵습니다."
    # 남는 경우: 병원 1건 이상이지만 비중 15% 미만, 인플루언서 없음
    return "contested", f"{base} — 병원 블로그 비중이 낮지만 노출 사례가 있어 경쟁 가능성이 있습니다."


async def analyze_keyword(keyword: str, max_posts: int = 8, fetch_post_metrics: bool = True) -> dict:
    """
    키워드 하나에 대한 통검 노출 분석 (SERP 수집 → 글 지표 수집 → 요약/판정).

    Returns:
        {
          "keyword", "fetched_at",
          "posts": [{url,title,blog_id,blog_name,post_no,section,position,blog_type,analyzed,
                     kw_count,image_count,chars,headings,published_at}],
          "summary": {...}, "verdict": "possible"|"contested"|"avoid"|"unknown",
          "verdict_reason": str, "error": None|str,
        }
    posts 에는 통검에 자연 노출된(is_ad=False) 블로그 글 전체(최대 SERP_MAX_RESULTS)가 들어가며,
    앞쪽 max_posts 건만 본문 지표를 수집한다 (analyzed=True; 미수집 글의 지표는 None).
    카페 글은 cafe_count 로만 집계하고 병원 비율 계산에서는 제외한다.
    """
    serp = await fetch_mobile_serp(keyword)
    error = serp.get("error")
    organic = [r for r in serp["results"] if not r.get("is_ad")]
    blog_results = [r for r in organic if r["kind"] == "blog"]
    serp_source = "mobile_integrated"
    # 모바일 통검 페이지는 클라우드 IP 에서 종종 결과 없는 축소본으로 온다(2026-09 운영 실측: error="empty").
    # 그때는 데스크톱 블로그탭 SERP(app.blogindex.serp — 운영에서 정상 동작)로 대체한다.
    if not blog_results:
        try:
            from app.blogindex import serp as bt
            async with bt.fresh_session() as s:
                tab = await bt.blog_tab_serp(s, keyword, limit=20, use_cache=True)
            rows = (tab or {}).get("rows") or []
            if rows:
                blog_results = [{
                    "url": r.get("post_url"), "blog_id": r.get("blog_id"), "post_no": r.get("post_no"),
                    "title": r.get("title") or "", "section": "블로그탭", "position": r.get("rank"),
                    "kind": "blog", "is_ad": False, "blog_name": None,
                } for r in rows]
                organic = list(blog_results)
                serp_source = f"blog_tab_{(tab or {}).get('source') or 'http'}"
                error = None
        except Exception as e:  # noqa: BLE001
            logger.warning("[serp] 블로그탭 폴백 실패(%s): %s", keyword, e)
    cafe_count = sum(1 for r in organic if r["kind"] == "cafe")

    metrics_by_key: Dict[tuple, Optional[Dict[str, Any]]] = {}
    if fetch_post_metrics and blog_results and max_posts > 0:
        semaphore = asyncio.Semaphore(POST_CONCURRENCY)
        targets = blog_results[:max_posts]
        gathered = await asyncio.gather(
            *[_analyze_one_post(item, keyword, semaphore) for item in targets],
            return_exceptions=True,
        )
        for item, result in zip(targets, gathered):
            if isinstance(result, Exception):
                print(f"[통검 분석] 글 분석 예외 ({item['url']}): {result}")
                result = None
            metrics_by_key[(item["blog_id"], item["post_no"])] = result

    posts: List[Dict[str, Any]] = []
    for item in blog_results:
        metrics = metrics_by_key.get((item["blog_id"], item["post_no"]))
        title = item["title"] or (metrics.get("title") if metrics else "") or ""
        # 분류 신호: 글 지표 + 통검 카드에서 얻은 블로그명
        signals: Dict[str, Any] = dict(metrics or {})
        if item.get("blog_name") and not signals.get("blog_name"):
            signals["blog_name"] = item["blog_name"]
        posts.append({
            "url": item["url"],
            "title": title,
            "blog_id": item["blog_id"],
            "blog_name": item.get("blog_name", ""),
            "post_no": item["post_no"],
            "section": item["section"],
            "position": item["position"],
            "blog_type": classify_blog_type(item["blog_id"], title, signals or None),
            "analyzed": metrics is not None,
            "kw_count": int(metrics.get("keyword_count", 0)) if metrics else None,
            "image_count": int(metrics.get("image_count", 0)) if metrics else None,
            "chars": int(metrics.get("content_length", 0)) if metrics else None,
            "headings": int(metrics.get("heading_count", 0)) if metrics else None,
            "published_at": (metrics.get("post_date") if metrics else None) or None,
        })

    summary = _build_summary(posts, cafe_count)
    verdict, reason = _decide_verdict(summary, error)

    return {
        "keyword": keyword,
        "fetched_at": serp["fetched_at"],
        "posts": posts,
        "summary": summary,
        "verdict": verdict,
        "verdict_reason": reason,
        "error": error,
    }
