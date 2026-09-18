"""
경쟁도 정밀 분석 (문서 12장, competition_analyzer) — 진입확률(%)

상위 10개 글의 **문서 단위 데이터**와 블로그 점수 리스트로 경쟁도를 5축 분해하고
진입확률(%)을 낸다. (10장 v2와는 별개 경로 — '안전 키워드 선정'에 쓰인다)

  WEIGHTS = {blog_score 0.30, content_relevance 0.25, freshness 0.15,
             engagement 0.15, keyword_expertise 0.15(미구현)}
  종합점수 = Σ(축점수 × 가중치) / (전체가중치 - keyword_expertise 가중치)
"""
from __future__ import annotations

import asyncio
import logging
import statistics
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.blogindex import normalize_blog_id
from app.blogindex import serp as serp_mod

logger = logging.getLogger(__name__)

TOP_N = 10
POST_CONCURRENCY = 4
SCORE_CONCURRENCY = 8
PER_BLOG_TIMEOUT = 32.0
PER_POST_TIMEOUT = 20.0

WEIGHTS = {
    "blog_score": 0.30,
    "content_relevance": 0.25,
    "freshness": 0.15,
    "engagement": 0.15,
    "keyword_expertise": 0.15,   # 미구현 — 분모에서 제외
}
UNIMPLEMENTED_AXES = {"keyword_expertise"}


@dataclass
class BlogStats:
    avg_score: float = 0.0
    min_score: float = 0.0
    max_score: float = 0.0
    std_score: float = 0.0
    high_scorer_count: int = 0     # 70점 이상
    elite_scorer_count: int = 0    # 85점 이상
    n: int = 0
    score: Optional[float] = None


@dataclass
class ContentRelevance:
    title_keyword_ratio: float = 0.0
    avg_density: float = 0.0
    high_relevance_count: int = 0
    n: int = 0
    score: Optional[float] = None


@dataclass
class Freshness:
    recent_7days_ratio: float = 0.0
    recent_30days_ratio: float = 0.0
    avg_post_age_days: float = 0.0
    n: int = 0
    score: Optional[float] = None


@dataclass
class Engagement:
    avg_like: float = 0.0
    avg_comment: float = 0.0
    high_engagement_count: int = 0
    n: int = 0
    score: Optional[float] = None


# ── 12-1. 축별 점수 (모두 "높을수록 경쟁 치열") ──────────────────────────
def content_relevance_axis(posts: List[Dict[str, Any]]) -> ContentRelevance:
    total = len(posts)
    cr = ContentRelevance(n=total)
    if total == 0:
        return cr
    cr.title_keyword_ratio = sum(1 for p in posts if p.get("title_has_keyword")) / total
    densities = [float(p.get("keyword_density") or 0) for p in posts]
    positive = [d for d in densities if d > 0]
    cr.avg_density = statistics.fmean(positive) if positive else 0.0
    cr.high_relevance_count = sum(1 for d in densities if d > 1.0)
    cr.score = (cr.title_keyword_ratio * 100 * 0.4
                + min(100, cr.avg_density * 50) * 0.3          # 밀도 2 = 100점
                + (cr.high_relevance_count / total * 100) * 0.3)
    return cr


def freshness_axis(posts: List[Dict[str, Any]]) -> Freshness:
    ages = [float(p["post_age_days"]) for p in posts if p.get("post_age_days") is not None]
    fr = Freshness(n=len(ages))
    if not ages:
        return fr
    n = len(ages)
    fr.recent_7days_ratio = sum(1 for a in ages if a <= 7) / n
    fr.recent_30days_ratio = sum(1 for a in ages if a <= 30) / n
    fr.avg_post_age_days = statistics.fmean(ages)
    fr.score = (fr.recent_7days_ratio * 100 * 0.5
                + fr.recent_30days_ratio * 100 * 0.3
                + max(0, 100 - (fr.avg_post_age_days / 365 * 100)) * 0.2)   # 평균 7일≈100, 365일=0
    return fr


def engagement_axis(posts: List[Dict[str, Any]]) -> Engagement:
    eg = Engagement(n=len(posts))
    if not posts:
        return eg
    likes = [float(p.get("like_count") or 0) for p in posts]
    comments = [float(p.get("comment_count") or 0) for p in posts]
    eg.avg_like = statistics.fmean(likes)
    eg.avg_comment = statistics.fmean(comments)
    eg.high_engagement_count = sum(1 for l, c in zip(likes, comments) if l + c > 50)
    eg.score = (min(100, eg.avg_like) * 0.4
                + min(100, eg.avg_comment * 2) * 0.3
                + (eg.high_engagement_count / len(posts) * 100) * 0.3)
    return eg


def blog_score_axis(scores: List[float]) -> BlogStats:
    bs = BlogStats(n=len(scores))
    if not scores:
        return bs
    bs.avg_score = statistics.fmean(scores)
    bs.min_score = min(scores)
    bs.max_score = max(scores)
    bs.std_score = statistics.pstdev(scores) if len(scores) > 1 else 0.0
    bs.high_scorer_count = sum(1 for s in scores if s >= 70)
    bs.elite_scorer_count = sum(1 for s in scores if s >= 85)
    n = len(scores)
    bs.score = ((bs.avg_score / 100) * 100 * 0.4
                + (bs.high_scorer_count / n * 100) * 0.35
                + (bs.elite_scorer_count / n * 100) * 0.25)
    return bs


# ── 12-2. 난이도 라벨 ─────────────────────────────────────────────────────
def difficulty_label(total: float) -> tuple[str, str, str]:
    """→ (한글 라벨, 코드, 진입률 설명)"""
    if total >= 70:
        return "매우어려움", "VERY_HARD", "30% 미만 진입"
    if total >= 55:
        return "어려움", "HARD", "30-49%"
    if total >= 40:
        return "보통", "MODERATE", "50-69%"
    if total >= 25:
        return "쉬움", "EASY", "70-89%"
    return "매우쉬움", "VERY_EASY", "90%+"


# ── 12-3. 진입 확률(%) ────────────────────────────────────────────────────
def calculate_entry_probability(my_score: Optional[float], competition_score: float,
                                blog_stats: BlogStats, content_rel: ContentRelevance) -> int:
    if my_score is None:                       # 내 점수 없으면 경쟁도만으로 추정
        if competition_score < 30:
            return 75
        if competition_score < 50:
            return 55
        if competition_score < 70:
            return 35
        return 15

    base_prob = max(10, 100 - competition_score)      # 경쟁도에 반비례

    score_gap = my_score - blog_stats.min_score       # 1페이지 최하위 대비
    if score_gap >= 15:
        score_bonus = 20
    elif score_gap >= 5:
        score_bonus = 10
    elif score_gap >= 0:
        score_bonus = 0
    elif score_gap >= -10:
        score_bonus = -15
    else:
        score_bonus = -30

    if content_rel.title_keyword_ratio > 0.7:
        content_penalty = -10
    elif content_rel.title_keyword_ratio > 0.5:
        content_penalty = -5
    else:
        content_penalty = 0

    if blog_stats.elite_scorer_count >= 3:
        elite_penalty = -15
    elif blog_stats.high_scorer_count >= 5:
        elite_penalty = -10
    else:
        elite_penalty = 0

    return max(5, min(95, int(base_prob + score_bonus + content_penalty + elite_penalty)))


# ── 12-4. 자동 인사이트/경고/추천 문구 규칙 ──────────────────────────────
def build_messages(cr: ContentRelevance, fr: Freshness, eg: Engagement, bs: BlogStats,
                   competition: Optional[float]) -> Dict[str, List[str]]:
    insights: List[str] = []
    warnings: List[str] = []
    recommendations: List[str] = []

    if cr.n:
        pct = round(cr.title_keyword_ratio * 100)
        if cr.title_keyword_ratio >= 0.8:
            warnings.append(f"상위 {pct}%가 제목에 키워드 포함 - SEO 최적화 필수")
        elif cr.title_keyword_ratio >= 0.5:
            insights.append(f"상위 {pct}%가 제목에 키워드를 포함합니다")
        else:
            insights.append("제목 키워드 최적화가 덜 된 키워드 - 기회 있음")
            recommendations.append("제목 맨 앞에 핵심 키워드를 넣으면 상대 우위를 잡을 수 있습니다")
        if cr.high_relevance_count >= 5:
            warnings.append(f"키워드 특화 블로그 {cr.high_relevance_count}개 - 전문성 필요")
    if fr.n:
        if fr.recent_7days_ratio >= 0.3:
            warnings.append(f"최근 7일 내 글이 {round(fr.recent_7days_ratio * 100)}% - 치열한 경쟁")
        elif fr.recent_30days_ratio >= 0.5:
            insights.append(f"최근 30일 내 글이 {round(fr.recent_30days_ratio * 100)}%입니다")
        else:
            insights.append("오래된 글이 많음 - 최신 글로 밀어낼 가능성")
            recommendations.append("최신 정보를 담은 새 글로 오래된 상위 글을 밀어낼 수 있습니다")
        if fr.avg_post_age_days < 30:
            warnings.append(f"평균 글 나이 {round(fr.avg_post_age_days)}일 - 활발한 키워드")
    if eg.n:
        if eg.avg_like >= 50:
            warnings.append(f"평균 공감 {round(eg.avg_like)}개 - 참여도 높은 경쟁 글")
        elif eg.avg_like >= 20:
            insights.append(f"평균 공감 {round(eg.avg_like)}개")
        if eg.high_engagement_count >= 3:
            insights.append(f"공감+댓글 50 초과 글 {eg.high_engagement_count}개")
    if bs.n:
        if bs.elite_scorer_count >= 3:
            warnings.append(f"85점+ 엘리트 블로거 {bs.elite_scorer_count}명 - 진입 매우 어려움")
        elif bs.high_scorer_count >= 5:
            warnings.append(f"70점+ 고점자 {bs.high_scorer_count}명 - 진입 어려움")
        if bs.avg_score < 50:
            insights.append(f"평균 점수 {round(bs.avg_score)}점 - 진입 기회")
        if bs.std_score > 15:
            insights.append("점수 편차가 큼 - 순위 변동 가능성")
    if competition is not None:
        if competition >= 70:
            insights.append("🔴 경쟁이 매우 치열")
        elif competition >= 50:
            insights.append("🟡 보통")
        else:
            insights.append("🟢 기회!")
    return {"insights": insights, "warnings": warnings, "recommendations": recommendations}


# ── 수집 ──────────────────────────────────────────────────────────────────
async def _with_session(coro_factory, label: str) -> Optional[Dict[str, Any]]:
    try:
        async with serp_mod.fresh_session() as s:
            return await coro_factory(s)
    except Exception as e:  # noqa: BLE001
        logger.warning("[competition] %s 실패: %s", label, e)
        return None


async def _timed(coro_factory, label: str, timeout: float) -> Optional[Dict[str, Any]]:
    """타임아웃 시 취소하지 않고(shield) 뒤에서 끝나게 둔다 — DB 커밋 도중 취소는 연결을 오염시킨다."""
    task = asyncio.ensure_future(_with_session(coro_factory, label))
    try:
        return await asyncio.wait_for(asyncio.shield(task), timeout)
    except asyncio.TimeoutError:
        logger.info("[competition] %s 타임아웃(%.0fs) — 백그라운드에서 계속", label, timeout)
        return None
    except Exception as e:  # noqa: BLE001
        logger.warning("[competition] %s 실패: %s", label, e)
        return None


async def _parse_post(sem: asyncio.Semaphore, post_url: str, keyword: str) -> Optional[Dict[str, Any]]:
    from app.blogindex import collectors
    async with sem:
        return await _timed(lambda s: collectors.analyze_post(s, post_url, keyword=keyword),
                            f"글 파싱 {post_url}", PER_POST_TIMEOUT)


async def _score_blog(sem: asyncio.Semaphore, blog_id: str, keyword: str, use_cache: bool) -> Optional[Dict[str, Any]]:
    from app.blogindex import analyzer
    async with sem:
        return await _timed(lambda s: analyzer.score_blog_light(s, blog_id, keyword=keyword, use_cache=use_cache),
                            f"채점 {blog_id}", PER_BLOG_TIMEOUT)


def _asdict(o) -> Dict[str, Any]:
    d = dict(o.__dict__)
    for k, v in d.items():
        if isinstance(v, float):
            d[k] = round(v, 3)
    return d


async def analyze_competition(db, keyword: str, my_blog_id: Optional[str] = None) -> Dict[str, Any]:
    keyword = (keyword or "").strip()
    t0 = time.monotonic()
    serp = await serp_mod.blog_tab_serp(db, keyword, limit=TOP_N)
    if serp is None:
        return {"ok": False, "keyword": keyword, "error": "serp_unavailable",
                "message": "네이버 검색 결과를 가져오지 못했습니다(일시적 차단 가능)."}
    rows = serp["rows"][:TOP_N]
    if not rows:
        return {"ok": False, "keyword": keyword, "error": "no_blog_results", "message": "블로그탭에 결과가 없습니다."}

    sem_post = asyncio.Semaphore(POST_CONCURRENCY)
    sem_score = asyncio.Semaphore(SCORE_CONCURRENCY)
    post_tasks = [_parse_post(sem_post, r["post_url"], keyword) for r in rows]
    score_tasks = [_score_blog(sem_score, r["blog_id"], keyword, True) for r in rows]
    my_task = None
    if my_blog_id:
        my_task = asyncio.create_task(_score_blog(sem_score, normalize_blog_id(my_blog_id), keyword, False))
    posts_raw, scores_raw = await asyncio.gather(asyncio.gather(*post_tasks), asyncio.gather(*score_tasks))
    my_res = await my_task if my_task else None
    my_score = my_res.get("score") if my_res else None

    posts = [p for p in posts_raw if p]
    scores = [float(s["score"]) for s in scores_raw if s and s.get("score") is not None]

    cr = content_relevance_axis(posts)
    fr = freshness_axis(posts)
    eg = engagement_axis(posts)
    bs = blog_score_axis(scores)
    axis_scores = {"blog_score": bs.score, "content_relevance": cr.score, "freshness": fr.score, "engagement": eg.score}

    # 종합점수 = Σ(축점수 × 가중치) / (전체가중치 - keyword_expertise 가중치)
    # 못 잰 축(None)은 0으로 깔지 않고 분모에서도 제외한다 (14-3 규칙 4).
    measured = {k: v for k, v in axis_scores.items() if v is not None}
    unmeasured = [k for k, v in axis_scores.items() if v is None]
    denom = sum(WEIGHTS[k] for k in WEIGHTS if k not in UNIMPLEMENTED_AXES and k not in unmeasured)
    competition = round(sum(v * WEIGHTS[k] for k, v in measured.items()) / denom, 1) if measured and denom > 0 else None

    if competition is None:
        label, code, band = "측정불가", "UNKNOWN", None
        entry_prob = None
    else:
        label, code, band = difficulty_label(competition)
        entry_prob = calculate_entry_probability(my_score, competition, bs, cr)

    msgs = build_messages(cr, fr, eg, bs, competition)
    top_posts = []
    for r, p, s in zip(rows, posts_raw, scores_raw):
        top_posts.append({
            "rank": r["rank"], "blog_id": r["blog_id"], "post_url": r["post_url"], "title": r.get("title") or (p or {}).get("title"),
            "blog_score": (s or {}).get("score"), "blog_grade": (s or {}).get("grade"),
            "title_has_keyword": (p or {}).get("title_has_keyword"), "keyword_density": (p or {}).get("keyword_density"),
            "content_length": (p or {}).get("content_length"), "image_count": (p or {}).get("image_count"),
            "like_count": (p or {}).get("like_count"), "comment_count": (p or {}).get("comment_count"),
            "post_age_days": (p or {}).get("post_age_days"), "post_parsed": p is not None,
        })
    return {
        "ok": True,
        "keyword": keyword,
        "my_blog_id": normalize_blog_id(my_blog_id) if my_blog_id else None,
        "my_score": my_score,
        "my_grade": (my_res or {}).get("grade"),
        "competition_score": competition,
        "difficulty_label": label,
        "difficulty_code": code,
        "entry_band": band,
        "entry_probability": entry_prob,
        "axes": {"blog_score": _asdict(bs), "content_relevance": _asdict(cr), "freshness": _asdict(fr),
                 "engagement": _asdict(eg), "keyword_expertise": {"score": None, "reason": "unimplemented"}},
        "weights": WEIGHTS,
        "unmeasured_axes": unmeasured,
        "posts_parsed": len(posts),
        "blogs_scored": len(scores),
        "top_posts": top_posts,
        "insights": msgs["insights"],
        "warnings": msgs["warnings"],
        "recommendations": msgs["recommendations"],
        "serp_source": serp.get("source"),
        "serp_parse_mode": serp.get("parse_mode"),
        "measured_at": datetime.utcnow().isoformat(),
        "elapsed": round(time.monotonic() - t0, 1),
    }
