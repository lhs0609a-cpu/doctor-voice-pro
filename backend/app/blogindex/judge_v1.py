"""
키워드 판정 v1 (문서 9장, judge_keyword) — 천장 대비 수요

입력: ceiling(내 공급 능력), target_volume(수요), serp(경쟁 강도, 선택)
출력: {verdict, probability, reason, confidence, serp_adjustment}
  verdict: "likely" | "contested" | "unlikely" | "unknown"
  probability: 1페이지 진입 확률 0~1. unknown 이면 None(채점 제외).

★ v1의 근본 한계 (그래서 10장 v2가 생겼다):
  검색량은 난이도의 **대리변수**일 뿐이다. 월 300짜리 전문 키워드의 1페이지가
  최적3들로 채워져 있고, 월 5,000짜리 롱테일의 1페이지가 휴면 블로그들일 때
  검색량 비교는 정확히 반대로 답한다.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

_VERDICT_RANK = {"likely": 3, "contested": 2, "unlikely": 1, "unknown": 0}
_BASE_RATE = 0.35


def judge_keyword(ceiling: Dict[str, Any], target_volume: int, serp: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    ceiling = ceiling or {}
    if not ceiling.get("ok") or ceiling.get("ceiling_volume") is None:
        # 천장 미상이어도 SERP가 매우 쉬우면 최소 단서는 준다
        if serp and serp.get("ok") and serp.get("difficulty_label") in ("very_easy", "easy"):
            return {"verdict": "contested", "probability": 0.30, "confidence": "low",
                    "serp_adjustment": "none",
                    "reason": "상위노출 실적이 부족해 천장은 미상이지만, 1페이지가 "
                              f"휴면 블로그 위주({serp['difficulty_label']})라 시도해볼 만합니다."}
        return {"verdict": "unknown", "probability": None, "confidence": "low",
                "serp_adjustment": "none",
                "reason": "이 블로그의 노출 천장을 아직 측정하지 못했습니다(상위노출 실적 부족)."}

    p50 = ceiling.get("ceiling_p50") or 0
    ceil = ceiling["ceiling_volume"]
    conf = ceiling.get("confidence", "low")

    # 1차: 내 천장 대비 수요 위치
    if target_volume <= p50:
        verdict, base_prob = "likely", 0.75
        reason = f"검색량 {target_volume:,}은 안정적으로 상위노출해온 수준(중앙값 {p50:,}) 이하입니다."
    elif target_volume <= ceil:
        verdict, base_prob = "contested", 0.45
        reason = f"검색량 {target_volume:,}은 최고 실적({ceil:,})과 안정권({p50:,}) 사이입니다."
    else:
        verdict = "unlikely"
        base_prob = max(0.03, 0.20 * (ceil / max(target_volume, 1)))
        reason = f"검색량 {target_volume:,}은 지금까지 뚫은 최고치({ceil:,})를 넘습니다."

    # 2차: 경쟁자 체력 보정 (한 단계 상/하향)
    adjustment = "none"
    if serp and serp.get("ok"):
        label = serp.get("difficulty_label")
        rank = _VERDICT_RANK[verdict]
        if label in ("very_easy", "easy") and rank < 3:
            rank += 1
            adjustment = "up"
            base_prob += 0.12
        elif label in ("very_hard",) and rank > 1:
            rank -= 1
            adjustment = "down"
            base_prob -= 0.12
        elif label == "hard":
            base_prob -= 0.06
        verdict = {v: k for k, v in _VERDICT_RANK.items()}[rank]

    # 3차: 표본이 적으면 base rate 로 수축 (과대확신 방지)
    shrink = {"high": 1.0, "medium": 0.6, "low": 0.35}.get(conf, 0.35)
    probability = _BASE_RATE + shrink * (base_prob - _BASE_RATE)
    probability = round(min(0.95, max(0.02, probability)), 3)

    return {"verdict": verdict, "probability": probability, "reason": reason,
            "confidence": conf, "serp_adjustment": adjustment}
