"""
합성 진입 난이도 (문서 11장, seo_difficulty) — DIFFICULTY_VERSION 2

8장의 단일 지표가 천장에 붙어버린 문제를 해결한 합성 눈금.
이미 재고 있으면서 쓰지 않던 값들을 쓴다. **추가 네트워크 호출 0.**

  성분과 가중치:
    entry_bar   top10_min_score   45%  1페이지 최하위 = 10번째 자리를 뺏으려면
                                       실제로 넘어야 하는 문턱. 상위권이 아무리
                                       세도 꼴찌가 약하면 자리는 열려 있다.
    field       top10_avg_score   30%  판 전체의 두께.
    vitality    median_vitality   15%  기존 축(×100). 버리진 않고 비중만 낮춘다.
    demand      log10(검색량)      10%  수요가 크면 경쟁이 계속 유입된다.

  실측 분포(같은 340개): 30.4 ~ 80.1, 중앙값 62.8. 라벨 5종 중 4종이 채워진다.

⚠️ 눈금을 바꾸면 예전 점수와 같은 선에 그릴 수 없다. DIFFICULTY_VERSION 을 함께 저장하고,
   프론트는 버전이 다른 값을 나란히 비교하지 않는다.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple

DIFFICULTY_VERSION = 2
_WEIGHTS = {"entry_bar": 45.0, "field": 30.0, "vitality": 15.0, "demand": 10.0}


def _demand_pressure(volume: Optional[float]) -> Optional[float]:
    """월 10회=20, 1천=60, 10만=100. 선형이면 상위 몇 개가 전부를 먹는다."""
    if not volume or volume <= 0:
        return None
    return min(100.0, 20.0 * math.log10(max(float(volume), 10.0)))


def label_for(score: Optional[float]) -> str:
    if score is None:
        return "unknown"     # 안 잰 것을 쉬움/어려움으로 말하지 않는다
    if score >= 72:
        return "very_hard"
    if score >= 58:
        return "hard"
    if score >= 44:
        return "moderate"
    if score >= 30:
        return "easy"
    return "very_easy"


def compute_difficulty(*, top10_min_score: Optional[float], top10_avg_score: Optional[float],
                       median_vitality: Optional[float], search_volume: Optional[float]
                       ) -> Tuple[Optional[float], str, Dict[str, Any]]:
    avg = top10_avg_score if top10_avg_score is not None else 0.0
    if avg <= 0:
        # 경쟁도 측정 실패. 활동성만으로는 진입 난이도를 말할 수 없다.
        return None, "unknown", {"reason": "top10_score_missing"}
    mn = top10_min_score if top10_min_score is not None else avg

    parts = [("entry_bar", max(0.0, min(100.0, float(mn)))),
             ("field", max(0.0, min(100.0, float(avg))))]
    if median_vitality is not None:
        parts.append(("vitality", max(0.0, min(100.0, float(median_vitality) * 100.0))))
    d = _demand_pressure(search_volume)
    if d is not None:
        parts.append(("demand", d))

    total_w = sum(_WEIGHTS[k] for k, _ in parts)
    score = round(sum(v * _WEIGHTS[k] for k, v in parts) / total_w, 1)
    breakdown = {k: {"value": round(v, 1), "weight": round(_WEIGHTS[k] / total_w, 3)}
                 for k, v in parts}
    return score, label_for(score), breakdown
