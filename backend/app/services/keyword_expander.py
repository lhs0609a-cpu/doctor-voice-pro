"""
연관 키워드 확장 엔진 (Keyword Expander)

하나의 시드 키워드(예: 임플란트)에서 출발하여
네이버 자동완성 / 연관검색어 / 구글 자동완성을 재귀적으로 확장해
목표 개수(300, 400, 500 ...)만큼 롱테일 키워드를 수집한다.

수집 전략
---------
1) 0단계 (시드 완전 확장)
   - 시드 그대로 자동완성
   - 시드 + 초성/음절/숫자/알파벳 조합 (붙여쓰기 + 띄어쓰기)
   - 시드 + 의도 수식어 (후기, 가격, 잘하는곳, 맛집 ...)
   - 지역명 + 시드 (강남 임플란트 ...)
   - 네이버 검색 결과 페이지의 연관검색어 (가능한 경우)
2) 1단계 이상 (허브 키워드 재확장)
   - 0단계에서 나온 키워드 중 허브(짧고 시드를 포함한 키워드)를 골라
     다시 자동완성을 돌려 하위 연관검색어를 캔다.
   - 목표 개수에 도달하거나 시간 예산이 끝날 때까지 반복.

결과는 부모-자식 관계(트리)를 유지하므로
임플란트 -> 임플란트 후기 -> 임플란트 후기 디시 처럼
서브로 연결된 연관검색어를 그대로 보여줄 수 있다.
"""

import re
import json
import time
import asyncio
import httpx
from typing import List, Dict, Set, Optional
from bs4 import BeautifulSoup


# ============================================================
# 확장용 사전
# ============================================================

# 초성 (자동완성은 초성 입력에도 반응한다)
CHOSUNG = list("ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ")

# 대표 음절
SYLLABLES = list("가나다라마바사아자차카타파하")

# 숫자 / 알파벳
DIGITS = [str(i) for i in range(10)]
ALPHABET = list("abcdefghijklmnopqrstuvwxyz")

# 검색 의도 수식어 - 이 조합이 실제 롱테일의 핵심이다
MODIFIER_SUFFIXES = [
    # 정보 탐색형
    "후기", "리뷰", "방법", "과정", "종류", "차이", "비교", "장단점",
    "효과", "원리", "기간", "수명", "주의사항", "부작용", "통증", "회복",
    "관리", "실패", "재수술", "나이", "조건", "자격", "기준", "순서",
    # 상거래형
    "가격", "비용", "견적", "할인", "이벤트", "저렴한곳", "싼곳",
    "추천", "잘하는곳", "유명한곳", "명의", "순위", "리스트", "best",
    "보험", "실비", "지원", "무료", "혜택", "상담", "문의", "예약",
    # 장소/업체형
    "병원", "치과", "의원", "센터", "클리닉", "맛집", "전문",
    # 커뮤니티형
    "디시", "블로그", "카페", "지식인", "실제후기", "솔직후기",
]

# 지역 수식어 (지역 + 키워드 조합은 로컬 비즈니스에서 가장 중요한 롱테일)
REGION_PREFIXES = [
    "서울", "강남", "서초", "송파", "잠실", "강동", "노원", "홍대", "신촌",
    "종로", "여의도", "목동", "구로", "은평", "성북", "건대", "왕십리",
    "경기", "수원", "성남", "분당", "판교", "용인", "일산", "고양",
    "부천", "안양", "평택", "화성", "동탄", "의정부", "남양주",
    "인천", "송도", "부평", "부산", "서면", "해운대", "대구", "동성로",
    "대전", "둔산", "광주", "울산", "천안", "청주", "전주", "창원",
    "포항", "김해", "제주",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://search.naver.com/",
}

MOBILE_HEADERS = {
    **HEADERS,
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Referer": "https://m.search.naver.com/",
}

# 키워드 유형 분류용
COMMERCIAL_HINTS = [
    "가격", "비용", "견적", "할인", "이벤트", "저렴", "싼", "추천",
    "잘하는", "유명", "명의", "순위", "best", "보험", "실비", "지원",
    "무료", "혜택", "상담", "문의", "예약", "만원", "원대",
]
INFO_HINTS = [
    "후기", "리뷰", "방법", "과정", "종류", "차이", "비교", "장단점",
    "효과", "원리", "기간", "수명", "주의", "부작용", "통증", "회복",
    "관리", "실패", "재수술", "이유", "의미",
]
PLACE_HINTS = ["병원", "치과", "의원", "센터", "클리닉", "맛집", "지점"]

# 노이즈 제거용 (기업 IR / 자극적 키워드가 섞여 들어오는 것을 막는다)
NOISE_PATTERNS = re.compile(r"(주가|주식|채용|연봉|공시|배당|상장|횡령)")

# 시드 뒤에 조사만 붙은 조각 (임플란트를, 임플란트가 ...) 은 키워드로 쓸 수 없다
TRAILING_PARTICLES = {
    "은", "는", "이", "가", "을", "를", "와", "과", "도", "만", "의",
    "에", "로", "으로", "에서", "부터", "까지", "라", "란", "이란",
    "하고", "하는", "한", "할", "해", "해서", "이나", "나",
}

MAX_KEYWORD_LENGTH = 40


# ============================================================
# 수집 소스
# ============================================================

async def fetch_naver_autocomplete(
    client: httpx.AsyncClient,
    query: str,
    sem: asyncio.Semaphore,
) -> List[str]:
    """네이버 자동완성 API 호출"""
    url = "https://ac.search.naver.com/nx/ac"
    params = {
        "q": query,
        "con": "1",
        "frm": "nv",
        "ans": "2",
        "r_format": "json",
        "r_enc": "UTF-8",
        "r_unicode": "0",
        "t_koreng": "1",
        "run": "2",
        "rev": "4",
        "q_enc": "UTF-8",
        "st": "100",
    }

    async with sem:
        try:
            response = await client.get(url, params=params, headers=HEADERS)
            if response.status_code != 200:
                return []
            data = response.json()
        except Exception:
            return []

    results: List[str] = []
    for group in data.get("items", []) or []:
        if not isinstance(group, list):
            continue
        for item in group:
            if isinstance(item, list) and item:
                text = item[0]
            elif isinstance(item, str):
                text = item
            else:
                continue
            if isinstance(text, str) and text.strip():
                results.append(text.strip())
    return results


async def fetch_google_autocomplete(
    client: httpx.AsyncClient,
    query: str,
    sem: asyncio.Semaphore,
) -> List[str]:
    """구글 자동완성(한국어) - 네이버에 없는 질문형 롱테일을 보완한다"""
    url = "https://suggestqueries.google.com/complete/search"
    params = {"client": "firefox", "hl": "ko", "gl": "kr", "q": query}

    async with sem:
        try:
            response = await client.get(url, params=params, headers=HEADERS)
            if response.status_code != 200:
                return []
            data = json.loads(response.text)
        except Exception:
            return []

    if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
        return [s.strip() for s in data[1] if isinstance(s, str) and s.strip()]
    return []


async def fetch_naver_related_search(
    client: httpx.AsyncClient,
    keyword: str,
    sem: asyncio.Semaphore,
) -> List[str]:
    """
    네이버 검색 결과 페이지의 연관검색어 영역 파싱 (best-effort)

    네이버가 연관검색어 영역을 자주 바꾸기 때문에 여러 셀렉터를 시도하고,
    실패해도 자동완성 기반 확장만으로 동작하도록 예외를 삼킨다.
    """
    url = "https://m.search.naver.com/search.naver"
    params = {"where": "m", "query": keyword}

    async with sem:
        try:
            response = await client.get(url, params=params, headers=MOBILE_HEADERS)
            if response.status_code != 200:
                return []
            html = response.text
        except Exception:
            return []

    related: List[str] = []
    try:
        soup = BeautifulSoup(html, "html.parser")
        selectors = [
            ".related_srch .keyword",
            ".related_srch .tit",
            ".lst_related_srch .item .keyword",
            ".related_srch_area a",
            ".api_subject_bx .related_srch a",
            ".sc_related_keyword a",
            "[class*=relatedKeyword] a",
        ]
        for selector in selectors:
            for node in soup.select(selector):
                text = node.get_text(strip=True)
                if text:
                    related.append(text)
    except Exception:
        pass

    return related


# ============================================================
# 정제 / 분류
# ============================================================

def normalize(keyword: str) -> str:
    """공백 정리"""
    return re.sub(r"\s+", " ", keyword or "").strip()


def strip_seed(keyword: str, seed: str) -> str:
    """키워드에서 시드를 걷어내고 남은 부분(수식어)만 돌려준다"""
    rest = keyword.replace(seed, " ")
    seed_nospace = seed.replace(" ", "")
    if seed_nospace and seed_nospace != seed:
        rest = rest.replace(seed_nospace, " ")
    return normalize(rest)


def is_valid_keyword(keyword: str, seed: str) -> bool:
    """수집 대상으로 삼을 만한 키워드인지 판정"""
    if not keyword:
        return False
    if len(keyword) > MAX_KEYWORD_LENGTH:
        return False
    if keyword == seed:
        return False
    # 초성 조각이 붙은 미완성 키워드 제거
    if re.search(r"[ㄱ-ㆎ]", keyword):
        return False
    # URL / 특수문자 덩어리 제거
    if re.search(r"(https?://|www\.|[<>{}\[\]|\\^~])", keyword):
        return False
    if NOISE_PATTERNS.search(keyword):
        return False
    # 한글/영문/숫자가 하나도 없는 경우 제외
    if not re.search(r"[가-힣a-zA-Z0-9]", keyword):
        return False
    # 시드 뒤에 조사만 붙은 조각 제거 (임플란트를, 임플란트란 ...)
    if strip_seed(keyword, seed) in TRAILING_PARTICLES:
        return False
    return True


def classify_keyword(keyword: str) -> str:
    """키워드 유형 분류 (마케팅 관점)"""
    lowered = keyword.lower()
    if any(region in keyword for region in REGION_PREFIXES):
        return "지역형"
    if any(hint in lowered for hint in COMMERCIAL_HINTS):
        return "상업형"
    if any(hint in lowered for hint in INFO_HINTS):
        return "정보형"
    if any(hint in lowered for hint in PLACE_HINTS):
        return "장소형"
    return "일반"


def build_seed_queries(
    seed: str,
    use_regions: bool = True,
    use_modifiers: bool = True,
    use_alphabet: bool = False,
) -> List[str]:
    """시드 키워드를 완전 확장하기 위한 자동완성 질의 목록"""
    queries: List[str] = [seed]

    # 초성/음절/숫자 - 붙여쓰기와 띄어쓰기 둘 다
    for token in CHOSUNG + SYLLABLES + DIGITS:
        queries.append(f"{seed}{token}")
        queries.append(f"{seed} {token}")

    if use_alphabet:
        for token in ALPHABET:
            queries.append(f"{seed} {token}")

    if use_modifiers:
        for modifier in MODIFIER_SUFFIXES:
            queries.append(f"{seed} {modifier}")

    if use_regions:
        for region in REGION_PREFIXES:
            queries.append(f"{region} {seed}")

    # 중복 제거 (순서 유지)
    seen: Set[str] = set()
    unique: List[str] = []
    for query in queries:
        if query not in seen:
            seen.add(query)
            unique.append(query)
    return unique


def build_child_queries(keyword: str) -> List[str]:
    """허브 키워드를 한 단계 더 파고들기 위한 가벼운 질의 목록"""
    queries = [keyword]
    for token in CHOSUNG + SYLLABLES:
        queries.append(f"{keyword} {token}")
    return queries


# ============================================================
# 메인 확장 엔진
# ============================================================

async def expand_keyword(
    seed: str,
    target_count: int = 300,
    max_depth: int = 2,
    use_google: bool = True,
    use_regions: bool = True,
    use_related_search: bool = True,
    concurrency: int = 12,
    time_budget: float = 150.0,
) -> Dict:
    """
    시드 키워드에서 연관 키워드를 target_count 개까지 확장 수집

    Args:
        seed: 시드 키워드 (예: 임플란트)
        target_count: 목표 수집 개수 (300이면 300개까지)
        max_depth: 확장 깊이 (1=시드 확장만, 2=허브 재확장, 3=손자까지)
        use_google: 구글 자동완성 병행 사용
        use_regions: 지역명 조합 사용
        use_related_search: 네이버 연관검색어 영역 파싱 시도
        concurrency: 동시 요청 수
        time_budget: 최대 소요 시간(초). 초과 시 지금까지 모은 결과를 반환

    Returns:
        수집 결과 딕셔너리 (keywords / groups / stats)
    """
    seed = normalize(seed)
    if not seed:
        return {
            "seed": seed,
            "target_count": target_count,
            "collected_count": 0,
            "keywords": [],
            "groups": [],
            "stats": {},
            "truncated": False,
            "elapsed_seconds": 0.0,
        }

    target_count = max(10, min(target_count, 3000))
    started = time.monotonic()

    # keyword -> {source, depth, parent}
    collected: Dict[str, Dict] = {}
    source_counts: Dict[str, int] = {}

    def remember(keyword: str, source: str, depth: int, parent: Optional[str]) -> bool:
        keyword = normalize(keyword)
        if not is_valid_keyword(keyword, seed):
            return False
        if keyword in collected:
            return False
        collected[keyword] = {
            "keyword": keyword,
            "source": source,
            "depth": depth,
            "parent": parent,
        }
        source_counts[source] = source_counts.get(source, 0) + 1
        return True

    def out_of_budget() -> bool:
        return (time.monotonic() - started) >= time_budget

    limits = httpx.Limits(
        max_connections=concurrency,
        max_keepalive_connections=concurrency,
    )
    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(timeout=8.0, limits=limits, follow_redirects=True) as client:

        async def run_queries(
            jobs: List[tuple],
            source: str,
            depth: int,
        ) -> None:
            """
            (질의, 부모키워드) 묶음을 나눠서 동시에 실행하고 결과를 수집한다.

            허브 여러 개를 한 배치에 섞어 넣어야 네트워크 대기 시간이 겹쳐
            깊은 단계 확장도 빠르게 끝난다.
            """
            batch_size = concurrency * 4
            for start in range(0, len(jobs), batch_size):
                if out_of_budget() or len(collected) >= target_count:
                    return
                batch = jobs[start:start + batch_size]
                tasks = [fetch_naver_autocomplete(client, q, sem) for q, _ in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for (_, parent), result in zip(batch, results):
                    if isinstance(result, BaseException) or not result:
                        continue
                    for item in result:
                        remember(item, source, depth, parent)

        # ---- 0단계: 시드 완전 확장 ----------------------------------
        seed_queries = build_seed_queries(seed, use_regions=use_regions)
        await run_queries([(q, seed) for q in seed_queries], "naver_autocomplete", 1)

        # 구글 자동완성은 시드 + 주요 수식어에만 적용 (질문형 롱테일 보완)
        if use_google and not out_of_budget() and len(collected) < target_count:
            google_queries = [seed] + [f"{seed} {m}" for m in MODIFIER_SUFFIXES[:20]]
            google_tasks = [fetch_google_autocomplete(client, q, sem) for q in google_queries]
            google_results = await asyncio.gather(*google_tasks, return_exceptions=True)
            for result in google_results:
                if isinstance(result, BaseException) or not result:
                    continue
                for item in result:
                    remember(item, "google_autocomplete", 1, seed)

        # 네이버 연관검색어 영역 (파싱되면 보너스)
        if use_related_search and not out_of_budget():
            for item in await fetch_naver_related_search(client, seed, sem):
                remember(item, "naver_related", 1, seed)

        # ---- 1단계 이상: 허브 키워드 재확장 --------------------------
        expanded: Set[str] = {seed}
        current_depth = 2

        while (
            current_depth <= max_depth
            and len(collected) < target_count
            and not out_of_budget()
        ):
            # 허브 후보: 아직 확장하지 않은 키워드 중
            #   1) 시드를 포함하고  2) 짧은 것 (짧을수록 상위 개념 = 하위 확장 여지가 크다)
            candidates = [
                kw for kw in collected
                if kw not in expanded and seed.replace(" ", "") in kw.replace(" ", "")
            ]
            if not candidates:
                candidates = [kw for kw in collected if kw not in expanded]
            if not candidates:
                break

            candidates.sort(key=lambda k: (len(k), k))
            # 남은 목표량에 비례해 확장할 허브 수를 정한다
            remaining = target_count - len(collected)
            hub_limit = max(5, min(40, remaining // 5 + 5))
            hubs = candidates[:hub_limit]

            # 모든 허브의 질의를 한 리스트로 합쳐서 동시에 돌린다
            hub_jobs: List[tuple] = []
            for hub in hubs:
                expanded.add(hub)
                hub_jobs.extend((q, hub) for q in build_child_queries(hub))

            await run_queries(hub_jobs, "naver_autocomplete", current_depth)

            current_depth += 1

    elapsed = round(time.monotonic() - started, 2)

    # ---- 결과 정리 ------------------------------------------------
    keywords = list(collected.values())

    # 정렬: 깊이(가까운 연관 우선) -> 짧은 것(검색량 큰 헤드) -> 가나다
    keywords.sort(key=lambda k: (k["depth"], len(k["keyword"]), k["keyword"]))
    keywords = keywords[:target_count]

    for item in keywords:
        item["type"] = classify_keyword(item["keyword"])
        item["contains_seed"] = seed.replace(" ", "") in item["keyword"].replace(" ", "")
        item["word_count"] = len(item["keyword"].split())

    groups = build_groups(seed, keywords)

    type_counts: Dict[str, int] = {}
    for item in keywords:
        type_counts[item["type"]] = type_counts.get(item["type"], 0) + 1

    return {
        "seed": seed,
        "target_count": target_count,
        "collected_count": len(keywords),
        "keywords": keywords,
        "groups": groups,
        # 서브 연관검색어를 대표하는 허브 키워드 (임플란트 후기, 임플란트 가격 ...)
        "hubs": [
            {"keyword": g["hub"], "count": g["count"], "type": g["type"]}
            for g in groups if g["hub"] != "기타"
        ],
        "stats": {
            "by_source": source_counts,
            "by_type": type_counts,
            "total_discovered": len(collected),
            "group_count": len(groups),
            "max_depth_reached": max((k["depth"] for k in keywords), default=0),
        },
        "truncated": len(collected) > len(keywords),
        "elapsed_seconds": elapsed,
    }


KNOWN_TOKENS = set(MODIFIER_SUFFIXES) | set(REGION_PREFIXES)


def extract_tokens(keyword: str, seed: str) -> List[str]:
    """
    키워드에서 시드를 뺀 나머지에서 그룹핑용 토큰을 뽑는다.

    임플란트 후기 디시 -> [후기, 디시]
    대구임플란트잘하는곳 -> [대구, 잘하는곳]  (붙여 쓴 경우도 사전으로 잡아낸다)
    """
    rest = strip_seed(keyword, seed)
    if not rest:
        return []

    tokens: List[str] = [t for t in rest.split(" ") if len(t) >= 2]

    # 띄어쓰기 없이 붙은 경우를 대비해 사전 토큰을 추가로 스캔
    for known in KNOWN_TOKENS:
        if known in rest and known not in tokens:
            tokens.append(known)

    return tokens


def build_groups(seed: str, keywords: List[Dict], min_group_size: int = 2) -> List[Dict]:
    """
    수식어(토큰)를 기준으로 허브 키워드 -> 하위 연관검색어 그룹을 만든다.

    예) 임플란트로 검색하면
        임플란트 후기   -> 임플란트 후기 디시, 앞니 임플란트 후기, ...
        임플란트 가격   -> 임플란트 1개 가격, 어금니 임플란트 가격, ...
        강남 임플란트   -> 강남 임플란트 치과, 강남 임플란트 25만원, ...
    처럼 서브로 연결된 연관검색어가 한 덩어리로 묶인다.
    """
    if not keywords:
        return []

    # 1) 토큰 빈도 집계
    token_counts: Dict[str, int] = {}
    keyword_tokens: Dict[str, List[str]] = {}
    for item in keywords:
        tokens = extract_tokens(item["keyword"], seed)
        keyword_tokens[item["keyword"]] = tokens
        for token in tokens:
            token_counts[token] = token_counts.get(token, 0) + 1

    def token_rank(token: str) -> tuple:
        # 자주 등장하는 토큰 > 사전에 있는 토큰 > 긴 토큰 순으로 대표성이 높다
        return (token_counts.get(token, 0), 1 if token in KNOWN_TOKENS else 0, len(token))

    # 2) 각 키워드를 가장 대표적인 토큰 그룹에 배정
    buckets: Dict[str, List[Dict]] = {}
    orphans: List[Dict] = []
    for item in keywords:
        tokens = keyword_tokens[item["keyword"]]
        candidates = [t for t in tokens if token_counts.get(t, 0) >= min_group_size]
        if not candidates:
            orphans.append(item)
            continue
        best = max(candidates, key=token_rank)
        buckets.setdefault(best, []).append(item)

    # 3) 그룹마다 허브(가장 짧은 = 가장 상위 개념인 키워드)를 뽑는다
    groups: List[Dict] = []
    for token, members in buckets.items():
        members.sort(key=lambda k: (len(k["keyword"]), k["keyword"]))
        hub_item = members[0]
        preferred_hub = f"{seed} {token}"
        # 시드+토큰 형태가 실제 수집됐다면 그것을 허브로 승격
        for member in members:
            if member["keyword"] == preferred_hub:
                hub_item = member
                break

        children = [m for m in members if m["keyword"] != hub_item["keyword"]]
        groups.append({
            "token": token,
            "hub": hub_item["keyword"],
            "type": hub_item.get("type") or classify_keyword(hub_item["keyword"]),
            "children": children,
            "count": len(members),
        })

    # 하위 키워드가 많은 허브부터 (= 실제로 파고들 여지가 큰 주제)
    groups.sort(key=lambda g: (-g["count"], len(g["hub"])))

    if orphans:
        orphans.sort(key=lambda k: (len(k["keyword"]), k["keyword"]))
        groups.append({
            "token": "",
            "hub": "기타",
            "type": "일반",
            "children": orphans,
            "count": len(orphans),
        })

    return groups
