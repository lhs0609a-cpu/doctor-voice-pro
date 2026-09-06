"""
키워드 딥리서치 서비스 (SERP Research)

글을 쓰기 '전'에, 그 키워드로 지금 1페이지에 앉아 있는 글들을 실제로 읽고
"무엇을 다뤄야 하고 무엇이 비어 있는지"를 뽑아낸다.

rank_feasibility_service 가 '이 키워드를 쓸까 말까'(숫자 판정)를 답한다면,
여기서는 '쓴다면 무슨 내용을 어떤 목차로'(내용 설계)를 답한다.

수집하는 것
-----------
1. 상위글 실측 지표      - 글자수/이미지/소제목/키워드밀도 (분량 규격의 근거)
2. 상위글 목차(소제목)   - 경쟁글이 실제로 다루는 주제
3. 상위글 도입부         - 검색자를 붙잡는 방식
4. 연관검색어/자동완성   - 검색자가 실제로 함께 궁금해하는 것
5. 질문형 롱테일         - 왜/어떻게/얼마/언제 형태 = 본문에서 답해야 할 질문
6. 콘텐츠 갭             - 검색자는 궁금해하는데 상위글이 안 다루는 주제

LLM 을 쓰지 않는다. 전부 실측/규칙 기반이라 결과가 재현 가능하고 비용이 없다.
"""

import re
import asyncio
import logging
from collections import Counter
from typing import Dict, List, Set

from app.services.top_post_analyzer import analyze_top_posts
from app.services import keyword_expander

logger = logging.getLogger(__name__)

# 네이버 크롤 동시성 제한 (차단 완충)
_SEM = asyncio.Semaphore(3)

# 질문형 신호 - 자동완성에서 이런 게 붙으면 검색자가 답을 원하는 질문이다
QUESTION_MARKERS = [
    "왜", "어떻게", "언제", "어디", "얼마", "몇", "무엇", "뭐",
    "이유", "방법", "차이", "비교", "기준", "조건", "순서", "과정",
    "인가요", "인가", "될까", "할까", "하나요", "되나요", "있나요",
]

# 목차 후보에서 걸러낼 잡음 (네이버 블로그 공통 UI/상투구)
HEADING_NOISE = re.compile(
    r"(공지|이웃추가|구독|카카오톡|블로그|오시는\s*길|진료\s*시간|목차|댓글|"
    r"본\s*포스팅|소정의|원고료|제공받아|바로가기|더보기|카테고리)"
)

# 주제 토큰 추출 시 버릴 일반어
STOPWORDS = {
    "그리고", "하지만", "그래서", "때문", "위해", "통해", "대해", "관련",
    "경우", "정도", "생각", "가지", "때문에", "여러분", "안녕하세요",
    "있습니다", "합니다", "입니다", "것을", "것이", "수도", "정말", "많이",
    "이런", "저런", "그런", "어떤", "무엇", "우리", "저희", "자신", "본인",
    "다음", "이번", "지금", "오늘", "여기", "거기", "모두", "함께", "바로",
}

# 그대로 소제목이 될 수 있는 주제어 (keyword_expander 의 의도 수식어 사전을 재사용)
_CONTENT_ANGLES = set(keyword_expander.MODIFIER_SUFFIXES)

# 서술어로 끝나는 토큰은 주제가 아니다 (있는, 확인해야, 하는 ...)
_VERBAL_TOKEN = re.compile(
    r"(?:하는|되는|있는|없는|해야|되야|돼야|한다|된다|이다|하고|되고|"
    r"에서|으로|처럼|보다|까지|부터|만큼|대로|였다|했다)$"
)


# 토큰 끝에 붙는 조사 - 떼어내야 "임플란트가"와 "임플란트"가 같은 주제로 묶인다
_JOSA = re.compile(r"(?:이|가|은|는|을|를|의|에|로|으로|와|과|도|만|께|에서|부터|까지|라도)$")


def _tokenize(text: str) -> List[str]:
    """한글 2글자 이상 / 영문 3글자 이상 토큰만 뽑고, 조사를 떼어낸다"""
    tokens: List[str] = []
    for raw in re.findall(r"[가-힣]{2,}|[A-Za-z]{3,}", text or ""):
        token = raw
        if len(token) >= 3:
            stripped = _JOSA.sub("", token)
            if len(stripped) >= 2:
                token = stripped
        if token in STOPWORDS or _VERBAL_TOKEN.search(token):
            continue
        tokens.append(token)
    return tokens


def _clean_heading(text: str) -> str:
    """소제목에서 번호/기호/군더더기를 걷어낸다"""
    text = re.sub(r"^\s*[\d]+\s*[.)\]]\s*", "", text or "")
    text = re.sub(r"^[\-·•▶▷◆◇■□★☆*#]+\s*", "", text)
    return re.sub(r"\s+", " ", text).strip()


def is_question_like(keyword: str, seed: str) -> bool:
    """이 연관검색어가 '질문'인가"""
    rest = keyword_expander.strip_seed(keyword, seed)
    if not rest:
        return False
    return any(marker in keyword for marker in QUESTION_MARKERS)


async def _collect_related(
    seed: str,
    max_keywords: int,
    time_budget: float,
) -> Dict:
    """연관검색어 수집 (keyword_expander 재사용, 얕고 빠르게)"""
    try:
        return await keyword_expander.expand_keyword(
            seed=seed,
            target_count=max_keywords,
            max_depth=1,          # 딥리서치에서는 시드 직속 연관어면 충분하다
            use_google=True,      # 질문형 롱테일은 구글 쪽이 잘 나온다
            use_regions=False,    # 지역 조합은 목차 설계에 도움이 안 된다
            time_budget=time_budget,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("[딥리서치] 연관검색어 수집 실패(%s): %s", seed, e)
        return {"keywords": [], "groups": [], "hubs": []}


def _extract_competitor_outline(results: List[Dict]) -> List[Dict]:
    """상위글별 목차(소제목) 정리"""
    outline: List[Dict] = []
    for item in results:
        headings = [
            _clean_heading(h)
            for h in (item.get("headings") or [])
        ]
        headings = [
            h for h in headings
            if h and len(h) >= 3 and not HEADING_NOISE.search(h)
        ]
        if not headings and not item.get("title"):
            continue
        outline.append({
            "rank": item.get("rank"),
            "title": item.get("title", ""),
            "content_length": item.get("content_length", 0),
            "image_count": item.get("image_count", 0),
            "headings": headings[:12],
            "intro": (item.get("intro") or "")[:200],
        })
    return outline


def _common_topics(outline: List[Dict], seed: str = "", min_sources: int = 2) -> List[Dict]:
    """
    여러 상위글이 공통으로 다루는 주제 = 이 키워드에서 '빠뜨리면 안 되는' 것

    소제목 토큰이 서로 다른 글 몇 개에서 나오는지로 센다.
    """
    token_sources: Dict[str, Set[int]] = {}
    token_examples: Dict[str, str] = {}
    # 시드 키워드 자체는 당연히 공통이라 주제로 세지 않는다
    seed_tokens = set(_tokenize(seed)) if seed else set()

    for idx, post in enumerate(outline):
        seen_in_post: Set[str] = set()
        for heading in post["headings"]:
            for token in _tokenize(heading):
                if token in seen_in_post or token in seed_tokens:
                    continue
                seen_in_post.add(token)
                token_sources.setdefault(token, set()).add(idx)
                token_examples.setdefault(token, heading)

    common = [
        {
            "topic": token,
            "sources": len(sources),
            "example_heading": token_examples.get(token, ""),
        }
        for token, sources in token_sources.items()
        if len(sources) >= min_sources
    ]
    common.sort(key=lambda t: (-t["sources"], t["topic"]))
    return common[:20]


def _content_gaps(
    seed: str,
    related_keywords: List[str],
    outline: List[Dict],
    limit: int = 12,
) -> List[Dict]:
    """
    콘텐츠 갭 = 검색자는 궁금해하는데(연관검색어에 있는데)
                상위글 소제목/본문에는 안 나오는 주제

    이게 상위글을 넘어설 실질적인 무기다.
    """
    covered = " ".join(
        post["title"] + " " + " ".join(post["headings"]) + " " + (post.get("intro") or "")
        for post in outline
    )
    covered_tokens = set(_tokenize(covered))
    seed_tokens = set(_tokenize(seed))

    gaps: List[Dict] = []
    seen: Set[str] = set()
    for keyword in related_keywords:
        rest = keyword_expander.strip_seed(keyword, seed)
        if not rest:
            continue
        tokens = [t for t in _tokenize(rest) if t not in seed_tokens]
        if not tokens:
            continue
        # 하나라도 상위글에서 안 다뤄진 토큰이 있으면 갭 후보
        missing = [t for t in tokens if t not in covered_tokens]
        if not missing:
            continue
        key = missing[0]
        if key in seen:
            continue
        seen.add(key)
        gaps.append({
            "topic": key,
            "from_keyword": keyword,
            "is_question": is_question_like(keyword, seed),
            # 사전에 있는 수식어(가격/기간/부작용...)는 곧바로 소제목이 되는 글감이다.
            # 반면 상호·제조사명(임플란트타워, 임플란트회사)은 글감이 못 된다.
            "is_content_angle": key in _CONTENT_ANGLES,
        })

    # 글감이 되는 것 > 질문형 > 짧은 것 순
    gaps.sort(
        key=lambda g: (
            not g["is_content_angle"],
            not g["is_question"],
            len(g["from_keyword"]),
        )
    )

    # 글감이 충분하면 상호·브랜드성 토큰은 아예 뺀다
    angles = [g for g in gaps if g["is_content_angle"] or g["is_question"]]
    if len(angles) >= 5:
        return angles[:limit]
    return gaps[:limit]


# 질문형 롱테일을 직접 캐기 위한 프로브. 연관검색어에 섞여 나오길 기다리지 않고
# "임플란트 왜", "임플란트 얼마" 처럼 대놓고 물어본다.
QUESTION_PROBES = [
    "왜", "어떻게", "언제", "얼마", "몇", "어디",
    "이유", "차이", "기준", "주의", "단점", "부작용",
]


async def _probe_questions(seed: str, time_budget: float = 12.0) -> List[str]:
    """자동완성에 질문 프로브를 붙여 실제 질문형 검색어를 수집한다"""
    import asyncio as _asyncio
    import httpx as _httpx

    queries = [f"{seed} {probe}" for probe in QUESTION_PROBES]
    found: List[str] = []
    sem = _asyncio.Semaphore(8)

    try:
        async with _httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
            tasks = [
                keyword_expander.fetch_naver_autocomplete(client, q, sem)
                for q in queries
            ] + [
                keyword_expander.fetch_google_autocomplete(client, q, sem)
                for q in queries[:6]
            ]
            results = await _asyncio.wait_for(
                _asyncio.gather(*tasks, return_exceptions=True),
                timeout=time_budget,
            )
        for result in results:
            if isinstance(result, BaseException) or not result:
                continue
            found.extend(result)
    except Exception as e:  # noqa: BLE001
        logger.warning("[딥리서치] 질문 프로브 실패(%s): %s", seed, e)

    return found


def _questions(
    seed: str,
    related_keywords: List[str],
    probed: List[str] = None,
    limit: int = 12,
) -> List[str]:
    """본문에서 답해줘야 할 질문 목록"""
    pool: List[str] = []
    seen: Set[str] = set()
    for keyword in list(probed or []) + list(related_keywords):
        keyword = keyword_expander.normalize(keyword)
        if not keyword or keyword in seen or keyword == seed:
            continue
        if not keyword_expander.is_valid_keyword(keyword, seed):
            continue
        if not is_question_like(keyword, seed):
            continue
        seen.add(keyword)
        pool.append(keyword)

    # 시드를 포함한 질문을 먼저, 그 다음 짧은 순
    pool.sort(key=lambda k: (seed.replace(" ", "") not in k.replace(" ", ""), len(k)))
    return pool[:limit]


def _intent(seed: str, related_keywords: List[str]) -> Dict:
    """
    검색 의도 추정 - 연관검색어 구성비로 본다.

    상업형이 많으면 '고르려는 사람', 정보형이 많으면 '알아보려는 사람'.
    글의 톤과 CTA 강도가 여기서 갈린다.
    """
    counts = Counter(keyword_expander.classify_keyword(k) for k in related_keywords)
    total = sum(counts.values()) or 1
    commercial = (counts.get("상업형", 0) + counts.get("지역형", 0) + counts.get("장소형", 0)) / total
    informational = counts.get("정보형", 0) / total

    if commercial >= 0.45:
        primary = "상업형"
        description = "업체·비용을 비교해 고르려는 단계입니다. 선택 기준과 비용 구조를 명확히 주고 상담으로 연결하세요."
    elif informational >= 0.35:
        primary = "정보형"
        description = "증상·원리·방법을 알아보는 단계입니다. 먼저 궁금증을 완전히 해소한 뒤 자연스럽게 상담을 제안하세요."
    else:
        primary = "혼합형"
        description = "정보 탐색과 업체 비교가 섞여 있습니다. 정보로 신뢰를 쌓고 후반부에 선택 기준을 제시하세요."

    return {
        "primary": primary,
        "description": description,
        "distribution": dict(counts),
        "commercial_ratio": round(commercial, 2),
        "informational_ratio": round(informational, 2),
    }


async def research_keyword(
    keyword: str,
    top_n: int = 5,
    max_related: int = 120,
    related_time_budget: float = 25.0,
) -> Dict:
    """
    키워드 하나를 딥리서치한다.

    Args:
        keyword: 대상 키워드
        top_n: 분석할 상위글 수 (많을수록 목차 표본이 좋아지지만 느려진다)
        max_related: 수집할 연관검색어 수
        related_time_budget: 연관검색어 수집 시간 예산(초)

    Returns:
        상위글 목차 / 공통주제 / 콘텐츠갭 / 질문 / 검색의도 / 실측 지표
    """
    keyword = (keyword or "").strip()
    if not keyword:
        return {}

    # 상위글 크롤과 연관검색어 수집은 서로 독립이라 같이 돌린다
    async def _top_posts() -> Dict:
        async with _SEM:
            try:
                return await analyze_top_posts(keyword, top_n=top_n, db=None)
            except Exception as e:  # noqa: BLE001
                logger.warning("[딥리서치] 상위글 분석 실패(%s): %s", keyword, e)
                return {}

    top_result, related_result, probed_questions = await asyncio.gather(
        _top_posts(),
        _collect_related(keyword, max_related, related_time_budget),
        _probe_questions(keyword),
    )

    results = [r for r in (top_result.get("results") or []) if r.get("data_fetched")]
    summary = top_result.get("summary")
    outline = _extract_competitor_outline(results)

    related_keywords = [k["keyword"] for k in (related_result.get("keywords") or [])]

    return {
        "keyword": keyword,
        "category": top_result.get("category", "general"),
        "category_name": top_result.get("category_name", "일반"),
        "analyzed_count": len(results),
        "summary": summary,
        "competitor_outline": outline,
        "competitor_titles": [p["title"] for p in outline if p["title"]],
        "common_topics": _common_topics(outline, keyword),
        "content_gaps": _content_gaps(keyword, related_keywords, outline),
        "questions": _questions(keyword, related_keywords, probed_questions),
        "related_keywords": related_keywords[:60],
        "intent": _intent(keyword, related_keywords),
    }


async def research_keywords(
    keywords: List[str],
    top_n: int = 5,
    max_related: int = 120,
) -> List[Dict]:
    """여러 키워드를 동시에 리서치 (내부 Semaphore 로 크롤 부하 제한)"""
    tasks = [research_keyword(k, top_n=top_n, max_related=max_related) for k in keywords]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out: List[Dict] = []
    for keyword, result in zip(keywords, results):
        if isinstance(result, BaseException):
            logger.warning("[딥리서치] 실패(%s): %s", keyword, result)
            out.append({"keyword": keyword, "error": str(result)})
        else:
            out.append(result)
    return out
