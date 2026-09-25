"""검색 결과를 초안 프롬프트가 쓸 수 있는 형태로 바꾼다.

LLM 심사 20점 중 originality(-2.7)와 intent(-1.6)는 재료 없이는 움직이지 않는다.
심사 프롬프트가 "같은 키워드로 검색하면 나오는 흔한 글과 구별되는가", "읽고 나서 다시
검색해야 하면 0~1점" 이라고 못박고 있어서, 남들이 뭘 썼고 뭘 안 썼는지를 모르면
모델이 피할 수도 채울 수도 없다.

serp_research_service 는 이미 그걸 계산해 두고도 어느 생성기에도 붙어 있지 않았다
(/top-posts/writing-spec 에서 사람이 복사해 쓰라고 JSON 으로 뱉을 뿐이었다).

여기서 지키는 것 셋.
1) 생성을 절대 붙잡지 않는다. 시간이 넘으면 빈 문자열을 돌려주고 그냥 쓴다.
2) 같은 키워드를 다시 조사하지 않는다(하루). 크롤이라 느리고 남의 서버를 두드린다.
3) 참고자료일 뿐 사실 출처가 아니다 — 여기 적힌 것을 사실로 쓰지 말라고 프롬프트에 박는다.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

TIME_BUDGET = 20.0          # 초. 넘으면 조사 없이 쓴다
CACHE_TTL = 24 * 3600       # 같은 키워드는 하루에 한 번만 조사한다
CACHE_MAX = 200

_cache: Dict[str, Tuple[float, str]] = {}


def _lines(items: List, key: str, limit: int) -> List[str]:
    out = []
    for it in items or []:
        text = (it.get(key) if isinstance(it, dict) else str(it)) or ""
        text = " ".join(text.split())[:60]
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def build_block(research: Optional[Dict]) -> str:
    """조사 결과 → 프롬프트 블록. 쓸 만한 것이 없으면 빈 문자열."""
    if not research:
        return ""
    common = _lines(research.get("common_topics"), "topic", 6)
    gaps = _lines(research.get("content_gaps"), "topic", 6)
    questions = _lines(research.get("questions"), "question", 6)
    if not (common or gaps or questions):
        return ""

    parts = ["", "<검색해 보니 이렇더라>",
             "무엇을 쓸지 고르는 참고자료다. 여기 적힌 것을 사실이나 출처로 쓰지 않는다.",
             "표현을 그대로 가져오지 않는다. 원본에 없는 사실은 여전히 만들지 않는다."]
    if common:
        parts += ["", "이미 어디서나 다루는 것 — 똑같이 반복하면 평범한 글이 된다:",
                  *[f"- {t}" for t in common]]
    if gaps:
        parts += ["", "아무도 제대로 답하지 않은 것 — 이 중 아는 것이 있으면 거기에 힘을 준다:",
                  *[f"- {t}" for t in gaps]]
    if questions:
        parts += ["", "검색한 사람이 실제로 묻는 것 — 최소 셋은 본문에서 답한다:",
                  *[f"- {q}" for q in questions],
                  "", "모르는 것은 답하지 말고 건드리지 않는다."]
    parts.append("</검색해 보니 이렇더라>")
    return "\n".join(parts)


async def for_keyword(keyword: str) -> str:
    """이 키워드의 참고자료 블록. 느리거나 실패하면 빈 문자열 — 생성은 멈추지 않는다."""
    keyword = (keyword or "").strip()
    if not keyword:
        return ""
    now = time.time()
    hit = _cache.get(keyword)
    if hit and now - hit[0] < CACHE_TTL:
        return hit[1]

    block = ""
    try:
        from app.services import serp_research_service
        research = await asyncio.wait_for(
            serp_research_service.research_keyword(keyword, top_n=5, max_related=60,
                                                  related_time_budget=10.0),
            timeout=TIME_BUDGET,
        )
        block = build_block(research)
    except asyncio.TimeoutError:
        logger.info("[리서치] '%s' 가 %.0f초 안에 안 끝나 조사 없이 씁니다", keyword, TIME_BUDGET)
    except Exception as error:  # noqa: BLE001  조사는 있으면 좋은 것이지 필수가 아니다
        logger.info("[리서치] '%s' 실패, 조사 없이 씁니다: %s", keyword, error)

    if len(_cache) >= CACHE_MAX:
        _cache.pop(min(_cache, key=lambda k: _cache[k][0]), None)
    _cache[keyword] = (now, block)
    return block
