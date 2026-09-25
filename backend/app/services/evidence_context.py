"""공공기관 본문을 실제로 가져와 근거로 쓸 수 있게 한다.

trust.evidence 5점은 네 번 실측 모두 0점이었다. 이유가 두 겹이다.
- 근거 표현(학회·질병관리청·연구·임상)이 두 군데는 있어야 하는데 하나도 없다.
- 그렇다고 지어내면 더 깎인다. 채점기는 원본에 없는 기관명을 인용하면 근거 점수를
  최대 80%까지 깎는다(허위 출처에 점수를 주지 않으려는 장치다).

그래서 '지어내지 말라'와 '근거를 넣어라'가 동시에 걸려 모델이 아무것도 못 쓴다.
푸는 길은 하나뿐이다 — **진짜 근거를 손에 쥐여 준다.**
질병관리청·NHS·MedlinePlus 본문을 가져와 프롬프트에 넣고, 같은 본문을 채점기의
대조본(source_text)에도 넘긴다. 그러면 인용이 검증을 통과한다.

없으면 없는 대로 간다. 근거가 없다고 글을 못 쓰게 만들지는 않는다.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

TIME_BUDGET = 18.0
CACHE_TTL = 7 * 24 * 3600      # 공공기관 문서는 자주 안 바뀐다
CACHE_MAX = 200
BODY_CHARS = 1200              # 기관당 본문 길이 상한

_cache: Dict[str, Tuple[float, Tuple[str, str]]] = {}


def _relevant(source: Dict, keyword: str) -> bool:
    """이 자료가 정말 이 주제를 다루는가.

    검색이 걸리는 대로 가져오면 '국가건강정보포털 사업 개요' 같은 소개 문서가 온다
    (2026-09-25 실측: 무릎통증으로 검색했는데 포털 운영 배경 문서가 왔다).
    주제가 안 맞는 자료를 쥐여 주고 인용하라고 하면 그게 곧 조작이다. 안 맞으면 버린다."""
    body = (source.get("excerpt") or source.get("text") or "")
    if not body:
        return False
    # 띄어쓰기가 다르면 못 맞춘다 — "무릎통증" 과 "무릎 통증" 은 같은 말이다. 공백을 지우고 센다.
    flat = re.sub(r"\s+", "", body)
    bare = re.sub(r"\s+", "", keyword)
    terms = {bare}
    if len(bare) >= 4:
        terms.add(bare[:2])       # 머리말(무릎통증 -> 무릎)이 본문에 반복되면 같은 주제로 본다
    return any(len(t) >= 2 and flat.count(t) >= 2 for t in terms)


def build(sources: List[Dict], keyword: str = "") -> Tuple[str, str]:
    """(프롬프트 블록, 채점 대조에 덧붙일 본문). 쓸 것이 없으면 둘 다 빈 문자열."""
    # content_evidence.read_source 는 본문을 'excerpt' 에 담는다('text' 가 아니다).
    usable = [s for s in (sources or []) if (s.get("excerpt") or s.get("text") or "").strip()]
    if keyword:
        usable = [s for s in usable if _relevant(s, keyword)]
    if not usable:
        return "", ""
    lines = ["", "<확인된 공식 자료>",
             "아래는 실제로 가져온 공공기관 본문이다. 여기 있는 내용만 근거로 인용한다.",
             "기관 이름을 댈 때는 아래에 적힌 이름 그대로 쓴다. 다른 기관을 지어내지 않는다.",
             "인용은 한두 군데면 충분하다. 자료에 없는 내용은 인용 표현을 붙이지 않는다."]
    corpus = []
    for s in usable[:2]:
        name = (s.get("title") or s.get("url") or "").strip()[:80]
        body = " ".join((s.get("excerpt") or s.get("text") or "").split())[:BODY_CHARS]
        lines += ["", f"[{name}]", body]
        corpus.append(f"{name}\n{body}")
    lines.append("</확인된 공식 자료>")
    return "\n".join(lines), "\n\n".join(corpus)


async def for_keyword(keyword: str) -> Tuple[str, str]:
    """이 키워드의 공식 근거. 느리거나 없으면 ('', '') — 생성은 그대로 진행한다."""
    keyword = (keyword or "").strip()
    if not keyword:
        return "", ""
    now = time.time()
    hit = _cache.get(keyword)
    if hit and now - hit[0] < CACHE_TTL:
        return hit[1]

    built = ("", "")
    try:
        from app.services import content_evidence
        sources = await asyncio.wait_for(content_evidence.collect(keyword), timeout=TIME_BUDGET)
        built = build(sources, keyword)
    except asyncio.TimeoutError:
        logger.info("[근거] '%s' 가 %.0f초 안에 안 끝나 근거 없이 씁니다", keyword, TIME_BUDGET)
    except Exception as error:  # noqa: BLE001  키가 없거나 자료가 없을 수 있다
        logger.info("[근거] '%s' 확보 실패, 근거 없이 씁니다: %s", keyword, error)

    if len(_cache) >= CACHE_MAX:
        _cache.pop(min(_cache, key=lambda k: _cache[k][0]), None)
    _cache[keyword] = (now, built)
    return built
