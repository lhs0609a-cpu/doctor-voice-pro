"""
SERP 난이도 (문서 8장, serp_difficulty) — 경쟁자 체력

같은 검색량이라도 1페이지 경쟁자가 죽어가는 블로그들이면 뚫기 쉽고, 활발한
강자들이면 어렵다. 이 모듈이 그 '경쟁자 체력'을 본다.
가벼운 측정: 경쟁자당 RSS 1회. 전체 지수를 재계산하지 않는다.

⚠️ 이 단일 지표의 치명적 한계 (그래서 11장의 합성 난이도가 생겼다):
   활동성은 '마지막 글로부터 며칠'로만 계산되고 7일 이내면 1.0 이다.
   1페이지에 올라와 있는 블로그가 최근 일주일 안에 글을 안 썼을 리 없으므로
   중앙값은 거의 항상 1.0 → 난이도 100.0 → 'very_hard' 가 된다.
   실측: 340개 중 319개(93.8%)가 정확히 100.0, 338개가 very_hard.
   → 단독으로 쓰지 말고 11장 compute_difficulty 의 한 성분으로만 쓸 것.
"""
from __future__ import annotations

import asyncio
import logging
import statistics
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.blogindex import serp as serp_mod

logger = logging.getLogger(__name__)

TOP_N = 10
RSS_CONCURRENCY = 6
RSS_TIMEOUT = 6.0

LIMITATION_NOTE = (
    "활동성만 본다. 경쟁자의 콘텐츠 품질·권위는 보지 않는다. "
    "'죽은 블로그가 점유한 쉬운 SERP'를 걸러내는 게 1차 목적이다. "
    "1페이지가 활발한 블로그로 채워지면 거의 항상 100.0(very_hard)이 나오므로 "
    "단독 지표로 쓰지 말고 seo_difficulty.compute_difficulty 의 한 성분으로만 쓸 것."
)


def _vitality_from_gap(days_idle: Optional[float]) -> float:
    """days_idle → vitality. 2-7 과 **동일 기준**을 반드시 공유한다."""
    if days_idle is None:
        return 0.6   # 불명 → 중립보다 약간 아래
    if days_idle <= 7:
        return 1.0
    if days_idle <= 30:
        return 0.95
    if days_idle <= 60:
        return 0.82
    if days_idle <= 90:
        return 0.65
    if days_idle <= 180:
        return 0.42
    if days_idle <= 365:
        return 0.25
    return 0.15


def label_v1(score: float) -> str:
    """라벨(구버전 v1 기준)."""
    if score >= 75:
        return "very_hard"
    if score >= 55:
        return "hard"
    if score >= 35:
        return "moderate"
    if score >= 18:
        return "easy"
    return "very_easy"


def _confidence(measured: int) -> str:
    """실제로 잰 블로그 수 >= 7 → high / >= 4 → medium / else low"""
    if measured >= 7:
        return "high"
    if measured >= 4:
        return "medium"
    return "low"


async def _competitor_vitality(sem: asyncio.Semaphore, row: Dict[str, Any]) -> Dict[str, Any]:
    from app.blogindex import collectors  # 지연 import
    out = {"rank": row.get("rank"), "blog_id": row.get("blog_id"), "days_idle": None,
           "posts_last_90d": None, "measured": False, "blog_name": None}
    async with sem:
        try:
            rss = await asyncio.wait_for(collectors.fetch_rss(row["blog_id"]), RSS_TIMEOUT)
        except Exception as e:  # noqa: BLE001
            logger.debug("[serp_difficulty] RSS 실패 %s: %s", row.get("blog_id"), e)
            rss = None
    if rss and rss.get("ok") and not rss.get("rss_empty"):
        analysis = rss.get("analysis") or {}
        out["days_idle"] = analysis.get("recent_activity")
        out["posts_last_90d"] = analysis.get("posts_last_90d")
        out["blog_name"] = rss.get("blog_name")
        out["measured"] = out["days_idle"] is not None
    out["vitality"] = _vitality_from_gap(out["days_idle"])
    return out


async def serp_difficulty(db, keyword: str, top_n: int = TOP_N) -> Dict[str, Any]:
    """1) 블로그탭 상위 N개 블로그 (중복 제거·순위 보존) 2) 각 경쟁자 RSS 3) days_idle → vitality"""
    serp = await serp_mod.blog_tab_serp(db, keyword, limit=top_n)
    if serp is None:
        return {"ok": False, "keyword": keyword, "error": "serp_unavailable",
                "message": "네이버 검색 결과를 가져오지 못했습니다(일시적 차단 가능)."}
    rows = serp["rows"][:top_n]
    if not rows:
        return {"ok": False, "keyword": keyword, "error": "no_blog_results",
                "message": "블로그탭에 결과가 없습니다.", "serp_source": serp.get("source"),
                "serp_parse_mode": serp.get("parse_mode")}

    sem = asyncio.Semaphore(RSS_CONCURRENCY)
    comps: List[Dict[str, Any]] = await asyncio.gather(*[_competitor_vitality(sem, r) for r in rows])

    n = len(comps)
    vitalities = [c["vitality"] for c in comps]
    median_v = statistics.median(vitalities)
    difficulty_score = round(median_v * 100, 1)
    alive = sum(1 for c in comps if c["days_idle"] is not None and c["days_idle"] <= 30)
    dormant = sum(1 for c in comps if c["days_idle"] is not None and c["days_idle"] > 90)
    measured = sum(1 for c in comps if c["measured"])
    confidence = _confidence(measured)
    if serp.get("parse_mode") == "regex":
        confidence = "low"   # 폴백 파싱 — 순위 신뢰도 낮음

    return {
        "ok": True,
        "keyword": keyword,
        "difficulty_score": difficulty_score,
        "difficulty_label": label_v1(difficulty_score),
        "median_vitality": round(median_v, 3),
        "alive_ratio": round(alive / n, 3),
        "dormant_ratio": round(dormant / n, 3),
        "competitors": comps,
        "competitor_count": n,
        "measured_count": measured,
        "confidence": confidence,
        "serp_source": serp.get("source"),
        "serp_parse_mode": serp.get("parse_mode"),
        "serp_cached": serp.get("cached"),
        "measured_at": datetime.utcnow().isoformat(),
        "note": LIMITATION_NOTE,
    }
