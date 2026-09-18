"""
실측 색인 검증기 (문서 5장, blog_index_verifier) — 6신호

휴리스틱 점수는 '입력 신호로 추정한 값'이고, 이 모듈은 '관측 가능한 아웃풋
(실제로 검색에 뜨는가)'을 잰다. verify_index=True 일 때 이 결과를 주 판정으로 승격.

배경: 네이버는 블로그 지수 API를 공개하지 않으므로 100% 정확한 측정은 불가능하다.
현존 측정 도구(NSIDE, NVIEW, whereispost, 리드뷰)의 공개 방법론과 공식 문서
(C-Rank, DIA)에 나온 신호를 통합해 업계 합의에 가까운 추정치를 낸다.
  · NSIDE: 최근 50개 포스팅 + 인기글 상위 10 + 전체 태그 + 제목 검색 100위까지.
           매핑: NSIDE NB ↔ 우리 최적, NSIDE 최적 ↔ 우리 최적+
  · whereispost: 제목 정확매칭 검색 → 블로그탭 노출 여부. 레벨 0~10.
  · 저품질 판별(NSIDE 공개 기준): 30위 밖 미노출 = 저품질 강한 신호,
    게시 후 72h 지나도 미색인 = 휴면/저품질.
"""
from __future__ import annotations

import asyncio
import logging
import re
from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional, Tuple

from app.blogindex import DISCLAIMER_INDEX, normalize_blog_id
from app.blogindex import serp as serp_mod

logger = logging.getLogger(__name__)

# ── 5-1. 파라미터 ─────────────────────────────────────────────────────────
SAMPLE_SIZE_DEFAULT = 12       # NSIDE는 50개×100위지만 응답시간 절충
MAX_TITLE_LEN = 40
SEARCH_CONCURRENCY = 3
SEARCH_TOP_K = 50
LATENCY_VERY_FAST_HOURS = 12
LATENCY_NORMAL_HOURS = 24
LATENCY_SLOW_HOURS = 72

WEIGHTS = {
    "A": 0.35,   # 정확매칭 색인률
    "B": 0.20,   # 통합검색(VIEW) 노출률
    "C": 0.15,   # 색인 지연
    "D": 0.10,   # 주제 일관성
    "E": 0.10,   # 콘텐츠 품질
    "F": 0.10,   # 체인/참여 ← blog_stats 없으면 제외하고 나머지로 재정규화
}
SIGNAL_NAMES = {
    "A": "exact_match_index_rate", "B": "view_tab_exposure_rate", "C": "index_latency",
    "D": "topic_consistency", "E": "content_quality", "F": "chain_engagement",
}

THRESHOLD_OPTIMIZED_PLUS = 85.0
THRESHOLD_OPTIMIZED = 65.0
THRESHOLD_SUBOPTIMIZED = 35.0


# ── 5-2. 제목 정제 + 정확매칭 질의 ───────────────────────────────────────
def _clean_title(title: str) -> str:
    cleaned = re.sub(r"[^\w\sㄱ-ㅎㅏ-ㅣ가-힣]", " ", title or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:MAX_TITLE_LEN]


def _quoted(title: str) -> str:               # whereispost 방식
    c = _clean_title(title)
    return f'"{c}"' if c else ""


# ── 5-4. 키워드 추출 + 불용어 (여러 모듈이 공유) ─────────────────────────
_KOREAN_STOPWORDS = {
    "있는", "없는", "그리고", "하지만", "그래서", "이번", "오늘", "어제", "내일",
    "정말", "진짜", "완전", "그냥", "대한", "위한", "하는", "되는", "이런",
    "저런", "그런", "함께", "같이", "이야기", "리뷰", "후기", "추천",
}


def _extract_keywords(title: str) -> List[str]:
    tokens = re.findall(r"[가-힣]{2,}|[A-Za-z]{3,}", title or "")
    return [t for t in tokens if t not in _KOREAN_STOPWORDS]


# ── 5-5. 가중점수 → 카테고리 + 1~15 세부 레벨 (선형 보간) ────────────────
def _to_detailed_level(s: float) -> Tuple[int, str]:
    s = max(0.0, min(100.0, s))
    if s < 35:
        return 1, "일반"
    if s < 65:                       # 35~65 → 준최1~준최7 (7단계)
        idx = int((s - 35) / (65 - 35) * 7)
        idx = max(0, min(6, idx))
        return 2 + idx, f"준최{idx + 1}"
    if s < 85:                       # 65~85 → 최적1~최적3 (3단계)
        idx = int((s - 65) / (85 - 65) * 3)
        idx = max(0, min(2, idx))
        return 9 + idx, f"최적{idx + 1}"
    idx = int((s - 85) / (100 - 85) * 4)   # 85~100 → 최적1+~4+
    idx = max(0, min(3, idx))
    return 12 + idx, f"최적{idx + 1}+"


def _level_category(level: Optional[int]) -> str:
    try:
        from app.blogindex import scoring  # 다른 에이전트가 작성 — 있으면 공용 함수 사용
        return scoring.level_category(level)
    except Exception:  # noqa: BLE001
        if level is None:
            return "측정 불가"
        if level >= 12:
            return "최적+"
        if level >= 9:
            return "최적"
        if level >= 2:
            return "준최"
        return "일반"


# ── 날짜 유틸 ────────────────────────────────────────────────────────────
def parse_pub_date(value: Any) -> Optional[datetime]:
    """RSS pubDate(RFC822) / ISO / datetime 무엇이 와도 aware datetime(UTC)로. 실패 None."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip()
        dt = None
        try:
            dt = parsedate_to_datetime(s)
        except Exception:  # noqa: BLE001
            try:
                dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            except Exception:  # noqa: BLE001
                m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", s)
                if m:
                    dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def age_hours(pub: Optional[datetime]) -> Optional[float]:
    if pub is None:
        return None
    return max(0.0, (datetime.now(timezone.utc) - pub).total_seconds() / 3600.0)


# ── 5-3. 신호별 점수 ─────────────────────────────────────────────────────
def _latency_score(age_h: Optional[float], indexed: bool) -> Tuple[float, str]:
    """C. 색인 지연 (가장 최근 글 기준)."""
    if age_h is None:
        return 50.0, "no_pub_date"
    if indexed:
        if age_h < LATENCY_VERY_FAST_HOURS:
            return 100.0, "very_fast"
        if age_h < LATENCY_NORMAL_HOURS:
            return 80.0, "normal"
        if age_h < LATENCY_SLOW_HOURS:
            return 50.0, "slow"
        return 30.0, "very_slow_but_indexed"
    if age_h >= LATENCY_NORMAL_HOURS:
        return 0.0, "missing_after_24h"        # 저품질 강한 신호
    return 40.0, "too_recent_to_judge"


def _topic_consistency(titles: List[str]) -> Tuple[float, Dict[str, Any]]:
    """D. 주제 일관성 (C-Rank Context 프록시)."""
    counter: Counter = Counter()
    for t in titles:
        counter.update(_extract_keywords(t))
    total = sum(counter.values())
    if total < 5:
        return 50.0, {"total_tokens": total, "concentration": None, "top": []}
    top5 = counter.most_common(5)
    concentration = sum(c for _, c in top5) / total
    score = (100 if concentration >= 0.50 else 80 if concentration >= 0.35 else
             60 if concentration >= 0.25 else 40 if concentration >= 0.15 else 20)
    return float(score), {"total_tokens": total, "concentration": round(concentration, 3),
                          "top": [k for k, _ in top5]}


def _content_quality(items: List[Dict[str, Any]]) -> Tuple[float, Dict[str, Any]]:
    """E. 콘텐츠 품질 (DIA 프록시, RSS description 길이 기준 — 보수적)."""
    if not items:
        return 50.0, {"avg_len": None}
    lens = [len(it.get("description") or "") for it in items if it.get("description")]
    if not lens:
        return 40.0, {"avg_len": None}
    avg_len = sum(lens) / len(lens)
    score = (100 if avg_len >= 1500 else 80 if avg_len >= 800 else 60 if avg_len >= 400
             else 40 if avg_len >= 200 else 25)
    return float(score), {"avg_len": round(avg_len)}


def _chain_engagement(stats: Optional[Dict[str, Any]]) -> Tuple[Optional[float], Dict[str, Any]]:
    """F. 체인/참여 (선택): neighbors==0 또는 visitors==0 이면 None (가중치에서 제외)."""
    if not stats:
        return None, {"reason": "no_blog_stats"}
    neighbors = stats.get("neighbor_count")
    visitors = stats.get("total_visitors")
    posts = stats.get("total_posts")
    if not neighbors or not visitors or not posts:
        return None, {"reason": "neighbors_or_visitors_zero"}
    vpp = visitors / posts
    score = 100 if vpp >= 500 else 80 if vpp >= 100 else 60 if vpp >= 30 else 40 if vpp >= 10 else 20
    return float(score), {"visitors_per_post": round(vpp, 1), "neighbors": neighbors,
                          "visitors": visitors, "posts": posts}


# ── 표본 1개 조회 ────────────────────────────────────────────────────────
async def _check_sample(sem: asyncio.Semaphore, blog_id: str, item: Dict[str, Any]) -> Dict[str, Any]:
    """각 글마다 동시에 두 가지 조회:
       check_blog_tab_rank(quoted, blog_id, 50) → indexed_blog_tab
       check_view_tab_rank(quoted, post_url, 50) → indexed_view_tab
    스크래핑 자체가 실패(None 측정불가)한 표본은 미노출로 오해하지 않도록 measured=False."""
    title = item.get("title") or ""
    post_url = item.get("link") or ""
    quoted = _quoted(title)
    out = {"title": title, "post_url": post_url, "pub_date": item.get("pub_date"), "query": quoted,
           "blog_tab_rank": None, "view_tab_rank": None, "blog_tab_measured": False,
           "view_tab_measured": False}
    if not quoted:
        return out
    async with sem:
        async with serp_mod.fresh_session() as s:
            try:
                rows = await serp_mod._serp_rows_upto(s, quoted, SEARCH_TOP_K)
                if rows is not None:
                    out["blog_tab_measured"] = True
                    out["blog_tab_rank"] = serp_mod._find_rank(rows, blog_id)
            except Exception as e:  # noqa: BLE001
                logger.warning("[verifier] 블로그탭 조회 실패 (%s): %s", title[:20], e)
            try:
                vs = await serp_mod.view_tab_serp(s, quoted)
                if vs is not None:
                    out["view_tab_measured"] = True
                    target = serp_mod._post_no_of(post_url)
                    for r in vs["rows"][:SEARCH_TOP_K]:
                        if target and r.get("post_no") == target:
                            out["view_tab_rank"] = int(r["rank"])
                            break
            except Exception as e:  # noqa: BLE001
                logger.warning("[verifier] VIEW탭 조회 실패 (%s): %s", title[:20], e)
    return out


# ── 공개 API ─────────────────────────────────────────────────────────────
async def verify_index(db, blog_id: str, sample_size: int = SAMPLE_SIZE_DEFAULT) -> Dict[str, Any]:
    from app.blogindex import collectors  # 지연 import (동시 작성 중인 모듈)

    blog_id = normalize_blog_id(blog_id)
    rss_task = asyncio.create_task(collectors.fetch_rss(blog_id))
    stats_task = asyncio.create_task(collectors.scrape_blog_stats(blog_id))
    rss = None
    try:
        rss = await rss_task
    except Exception as e:  # noqa: BLE001
        logger.warning("[verifier] RSS 실패 %s: %s", blog_id, e)
    stats = None
    try:
        stats = await stats_task
        if stats and not stats.get("success"):
            stats = None
    except Exception as e:  # noqa: BLE001
        logger.warning("[verifier] stats 실패 %s: %s", blog_id, e)

    if not rss or not rss.get("ok") or not rss.get("items"):
        return {"ok": False, "blog_id": blog_id, "error": "no_posts_via_rss",
                "message": "RSS에서 글을 가져오지 못해 색인 검증을 할 수 없습니다.",
                "disclaimer": DISCLAIMER_INDEX}

    items: List[Dict[str, Any]] = list(rss["items"])
    samples_in = items[:max(1, int(sample_size))]
    sem = asyncio.Semaphore(SEARCH_CONCURRENCY)
    samples = await asyncio.gather(*[_check_sample(sem, blog_id, it) for it in samples_in])

    measured = [s for s in samples if s["blog_tab_measured"]]
    n = len(measured)
    signals: Dict[str, Dict[str, Any]] = {}

    # A. 정확매칭 색인률 / B. VIEW탭 노출률
    if n > 0:
        idx_blog = sum(1 for s in measured if s["blog_tab_rank"] is not None)
        signals["A"] = {"score": round(idx_blog / n * 100, 1), "raw": {"indexed": idx_blog, "n": n}}
        view_measured = [s for s in samples if s["view_tab_measured"]]
        if view_measured:
            idx_view = sum(1 for s in view_measured if s["view_tab_rank"] is not None)
            signals["B"] = {"score": round(idx_view / len(view_measured) * 100, 1),
                            "raw": {"indexed": idx_view, "n": len(view_measured)}}
    # C. 색인 지연 (가장 최근 글)
    dated = [(parse_pub_date(s.get("pub_date")), s) for s in measured]
    dated = [(d, s) for d, s in dated if d is not None]
    if measured:
        if dated:
            latest_dt, latest = max(dated, key=lambda x: x[0])
            c_score, c_state = _latency_score(age_hours(latest_dt), latest["blog_tab_rank"] is not None)
            signals["C"] = {"score": c_score, "raw": {"state": c_state, "age_hours": round(age_hours(latest_dt) or 0, 1),
                                                     "title": latest["title"]}}
        else:
            signals["C"] = {"score": 50.0, "raw": {"state": "no_pub_date"}}
    # D. 주제 일관성
    d_score, d_raw = _topic_consistency([it.get("title") or "" for it in items])
    signals["D"] = {"score": d_score, "raw": d_raw}
    # E. 콘텐츠 품질
    e_score, e_raw = _content_quality(items)
    signals["E"] = {"score": e_score, "raw": e_raw}
    # F. 체인/참여 (선택)
    f_score, f_raw = _chain_engagement(stats)
    if f_score is not None:
        signals["F"] = {"score": f_score, "raw": f_raw}

    for k, v in signals.items():
        v["name"] = SIGNAL_NAMES[k]
        v["weight"] = WEIGHTS[k]

    # weighted_score = Σ(score*weight) / Σ(weight)  ← 실제 쓴 신호만으로 정규화
    used = {k: v for k, v in signals.items() if v.get("score") is not None}
    wsum = sum(WEIGHTS[k] for k in used)
    if n == 0 or wsum <= 0:
        return {"ok": False, "blog_id": blog_id, "blog_name": rss.get("blog_name"),
                "error": "serp_unavailable",
                "message": "네이버 검색 결과를 가져오지 못해(차단 가능) 색인률을 잴 수 없습니다.",
                "signals": signals, "samples": samples, "disclaimer": DISCLAIMER_INDEX}
    weighted = sum(v["score"] * WEIGHTS[k] for k, v in used.items()) / wsum
    level, grade = _to_detailed_level(weighted)

    # confidence: n>=6 이고 engagement 측정됨 → high / n>=4 → medium / else low
    if n >= 6 and f_score is not None:
        confidence = "high"
    elif n >= 4:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "ok": True,
        "blog_id": blog_id,
        "blog_name": rss.get("blog_name"),
        "weighted_score": round(weighted, 1),
        "level": level,
        "grade": grade,
        "category": _level_category(level),
        "confidence": confidence,
        "sample_size": n,
        "sample_requested": len(samples_in),
        "thresholds": {"optimized_plus": THRESHOLD_OPTIMIZED_PLUS, "optimized": THRESHOLD_OPTIMIZED,
                       "suboptimized": THRESHOLD_SUBOPTIMIZED},
        "signals": signals,
        "samples": samples,
        "measured_at": datetime.utcnow().isoformat(),
        "disclaimer": DISCLAIMER_INDEX,
    }
