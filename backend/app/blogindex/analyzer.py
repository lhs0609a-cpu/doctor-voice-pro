"""
블로그 지수 조립: 수집(1장) → 가중치(3장) → 채점(2장) → 레벨(4장) → 스냅샷 저장.

데이터 흐름 (문서 0장):
  블로그ID
    ├─ 모바일/데스크톱 HTML  ──┐
    ├─ NVisitorgp4Ajax        ─┤→ stats {posts, neighbors, visitors, daily}
    ├─ RSS(최근 50개)          ─┤→ analysis {카테고리엔트로피, 발행간격, 최근성...}
    └─ 최근 글 15개 풀파싱     ─┘→ fullparse {길이, 이미지, 공감, 댓글, 문단, 소제목}
                     ▼ 3축 채점 → 가중치 결합 → extra_bonus → 소스 패널티 → × vitality
                     ▼ 백분위 모집단 ≥300 이면 percentile→level, 아니면 절대 기준표→level

정직성 규칙 (2-6..2-9, 14-3):
  · 측정 못 한 값은 None + unmeasured. 지어내지 않는다 (해시 시드 금지).
  · measurable=False 면 레벨을 만들어내지 않는다 (level None, "측정 불가").
  · 채점 실패는 캐시하지 않는다.
  · 내 블로그 점수는 항상 새로 잰다(use_cache=False). 남의 점수는 6시간 캐시.
"""
from __future__ import annotations

import asyncio
import os
import inspect
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import select

from app.blogindex import SCORING_VERSION, normalize_blog_id
from app.blogindex import collectors
from app.blogindex.scoring import (
    add_score_sample, compute_blog_index, get_blog_level_from_score,
    get_level_from_percentile, get_percentile, level_category,
)
from app.blogindex.weights import detect_keyword_category, resolve_scoring_weights

logger = logging.getLogger(__name__)

SNAPSHOT_TTL = timedelta(hours=1)          # 14-4: 블로그 분석 캐시 1h
SCORE_TTL = timedelta(hours=int(os.getenv("BLOGINDEX_SCORE_TTL_HOURS", "24")))   # 원본 10-3 은 6h. 경쟁자 점수는 하루 안에 크게 안 변해 24h 로(환경변수)
# 원본 10-3: SCORE_CONCURRENCY 8 / PER_BLOG_TIMEOUT 32. 원본은 다중 코어 워커였고, 여기 운영 머신은
# shared-cpu-1x 라 8개를 동시에 돌리면 전부 32초를 넘겨 "채점된 경쟁자 0개"가 났다(실측). 환경변수로 조정.
SCORE_CONCURRENCY = int(os.getenv("BLOGINDEX_SCORE_CONCURRENCY", "10"))
PER_BLOG_TIMEOUT = float(os.getenv("BLOGINDEX_PER_BLOG_TIMEOUT", "120"))
UNMEASURABLE_REASON = "네이버에서 블로그 지표를 가져오지 못했습니다."
_CANONICAL_CACHE: Dict[str, str] = {}   # 입력 id → 실제 블로그 주소 (프로세스 메모리)
_LAST_STAGE: Dict[str, str] = {}        # blog_id → 마지막으로 진입한 분석 단계(타임아웃 진단용)


async def canonicalize(blog_id: str) -> str:
    """로그인 ID 를 블로그 주소로 착각한 입력을 실제 blog_id 로 바꾼다. 못 찾으면 그대로."""
    bid = normalize_blog_id(blog_id)
    if not bid:
        return bid
    if bid in _CANONICAL_CACHE:
        return _CANONICAL_CACHE[bid]
    try:
        can = await collectors.resolve_canonical_blog_id(bid)
    except Exception:  # noqa: BLE001
        can = None
    _CANONICAL_CACHE[bid] = can or bid
    return _CANONICAL_CACHE[bid]

_score_semaphore = asyncio.Semaphore(SCORE_CONCURRENCY)


async def _notify(progress: Optional[Callable], stage: str, **kw: Any) -> None:
    try:
        if kwargs.get("blog_id"):
            _LAST_STAGE[kwargs["blog_id"]] = stage
    except Exception:  # noqa: BLE001
        pass
    if progress is None:
        return
    try:
        r = progress(stage, **kw)
        if inspect.isawaitable(r):
            await r
    except Exception as e:  # noqa: BLE001
        logger.debug("progress 콜백 실패(%s): %s", stage, e)


def _empty_index() -> Dict[str, Any]:
    return {
        "total_score": None, "level": None, "grade": "측정 불가", "level_category": "측정 불가",
        "percentile": None, "level_basis": None, "level_source": "unavailable", "confidence": None,
        "vitality": None, "vitality_state": None, "days_since_last_post": None, "posts_last_90d": None,
        "rss_truncated": False, "extra_bonus": None, "unmeasured_dimensions": [],
        "measurement_complete": False, "level_heuristic": None, "grade_heuristic": None,
        "index_verification": None, "unmeasurable_reason": UNMEASURABLE_REASON,
        "score_breakdown": None,
    }


def _base_result(blog_id: str) -> Dict[str, Any]:
    """14-5 블로그 분석 스키마 — 모든 키를 항상 낸다(None 이라도)."""
    return {
        "blog_id": blog_id,
        "success": False,
        "error_code": None,
        "error_message": None,
        "canonical_blog_id": None,
        "stats": {
            "total_posts": None, "total_posts_min": None, "neighbor_count": None,
            "total_visitors": None, "daily_visitors": None, "recent_avg_visitors": None,
            "visitor_series": [], "visitor_measured": False,
        },
        "index": _empty_index(),
        "naver_level": None,
        "blog_name": None,
        "data_sources": [],
        "estimated_fields": [],
        "unmeasured": [],
        "rss_empty": False,
        "keyword": None,
        "keyword_category": "default",
        "scoring_version": SCORING_VERSION,
        "measured_at": None,
        "elapsed": None,
        "cached": False,
    }


async def _load_snapshot(db, blog_id: str, category: str) -> Optional[Dict[str, Any]]:
    from app.models.blog_index import BlogIndexSnapshot
    try:
        since = datetime.utcnow() - SNAPSHOT_TTL
        q = (select(BlogIndexSnapshot)
             .where(BlogIndexSnapshot.blog_id == blog_id)
             .where(BlogIndexSnapshot.success == True)  # noqa: E712
             .where(BlogIndexSnapshot.scoring_version == SCORING_VERSION)
             .where(BlogIndexSnapshot.keyword_category == category)
             .where(BlogIndexSnapshot.created_at >= since)
             .order_by(BlogIndexSnapshot.created_at.desc())
             .limit(1))
        row = (await db.execute(q)).scalars().first()
    except Exception as e:  # noqa: BLE001
        logger.debug("snapshot 조회 실패(%s): %s", blog_id, e)
        return None
    if row is None or not isinstance(row.result, dict):
        return None
    out = dict(row.result)
    out["cached"] = True
    return out


async def _store_snapshot(db, blog_id: str, category: str, result: Dict[str, Any]) -> None:
    from app.models.blog_index import BlogIndexSnapshot
    from app.blogindex.dbwrite import isolated_write
    idx = result.get("index") or {}

    async def _do(s):
        s.add(BlogIndexSnapshot(
            blog_id=blog_id, keyword_category=category, scoring_version=SCORING_VERSION,
            total_score=idx.get("total_score"), level=idx.get("level"), grade=idx.get("grade"),
            measurement_complete=bool(idx.get("measurement_complete")),
            success=bool(result.get("success")), result=result,
        ))

    await isolated_write(_do, what=f"snapshot {blog_id}")


async def analyze_blog(db, blog_id: str, *, keyword: Optional[str] = None, fullparse: bool = True,
                       use_cache: bool = True, verify_index: bool = False,
                       progress: Optional[Callable] = None, _canonical_hop: bool = False,
                       fullparse_n: Optional[int] = None) -> Dict[str, Any]:
    """블로그 지수 분석 본체 → 14-5 스키마."""
    t0 = time.monotonic()
    blog_id = normalize_blog_id(blog_id)
    category = detect_keyword_category(keyword) if keyword else "default"
    result = _base_result(blog_id)
    result["keyword"] = keyword
    result["keyword_category"] = category

    if not blog_id:
        result["error_code"] = "INVALID_BLOG_ID"
        result["error_message"] = "블로그 아이디가 비어 있습니다."
        return result

    if use_cache and db is not None:
        cached = await _load_snapshot(db, blog_id, category)
        if cached is not None:
            await _notify(progress, "cached", blog_id=blog_id)
            return cached

    # ── 1) 수집: 통계 + 실측 일방문 + RSS 동시 ─────────────────────────────
    await _notify(progress, "collect", blog_id=blog_id)
    scrape, visitors, rss = await asyncio.gather(
        collectors.scrape_blog_stats(blog_id),
        collectors.fetch_visitor_series(blog_id),
        collectors.fetch_rss(blog_id),
        return_exceptions=True,
    )
    if isinstance(scrape, Exception):
        logger.warning("scrape_blog_stats 예외(%s): %s", blog_id, scrape)
        scrape = {"success": False, "error_code": "FETCH_FAILED", "error_message": str(scrape)}
    if isinstance(visitors, Exception):
        logger.warning("fetch_visitor_series 예외(%s): %s", blog_id, visitors)
        visitors = {"measured": False, "series": [], "today": None, "recent_avg": None}
    if isinstance(rss, Exception):
        logger.warning("fetch_rss 예외(%s): %s", blog_id, rss)
        rss = {"ok": False, "rss_empty": False, "blog_name": None, "items": [], "analysis": {}}

    rss_items = rss.get("items") or []
    rss_ok = bool(rss.get("ok")) and len(rss_items) > 0
    result["rss_empty"] = bool(rss.get("rss_empty"))
    result["blog_name"] = rss.get("blog_name")
    result["naver_level"] = scrape.get("naver_level")
    result["canonical_blog_id"] = scrape.get("canonical_blog_id")

    # 주소 오입력(로그인 ID 등) → 진짜 블로그 주소로 다시 잰다. 그래야 통계(scrape)가 잡히고
    # SERP 의 blog_id 와도 맞는다. (예: lhs0609c → platonmarketing)
    canonical = scrape.get("canonical_blog_id")
    if canonical and canonical != blog_id and not _canonical_hop:
        logger.info("canonical 재분석 %s → %s", blog_id, canonical)
        _CANONICAL_CACHE[blog_id] = canonical
        res2 = await analyze_blog(db, canonical, keyword=keyword, fullparse=fullparse, use_cache=use_cache,
                                  verify_index=verify_index, progress=progress, _canonical_hop=True,
                                  fullparse_n=fullparse_n)
        res2["requested_blog_id"] = blog_id
        res2["canonical_blog_id"] = canonical
        return res2

    # 존재하지 않음 / 비공개 / 주소 오입력 — RSS 에도 글이 없으면 실패로 확정
    if scrape.get("error_code") in ("NOT_FOUND", "PRIVATE_BLOG", "MOVED") and not rss_ok:
        result["error_code"] = scrape["error_code"]
        result["error_message"] = scrape.get("error_message")
        result["measured_at"] = datetime.utcnow().isoformat()
        result["elapsed"] = round(time.monotonic() - t0, 2)
        return result   # 실패는 캐시하지 않는다

    # ── 2) fullparse (RSS 아이템 의존) ─────────────────────────────────────
    fp: Dict[str, Any] = {"sample_size": 0}
    if fullparse and rss_items:
        n_fp = int(fullparse_n or collectors.FULLPARSE_SAMPLE_SIZE)
        await _notify(progress, "fullparse", blog_id=blog_id, total=min(len(rss_items), n_fp))
        try:
            fp = await collectors.fullparse_recent(db, blog_id, rss_items, n=n_fp)
        except Exception as e:  # noqa: BLE001
            logger.warning("fullparse_recent 예외(%s): %s", blog_id, e)
            fp = {"sample_size": 0}

    # ── 3) stats / analysis / data_sources 조립 ────────────────────────────
    data_sources: List[str] = []
    estimated: List[str] = []
    unmeasured: List[str] = []
    if scrape.get("success"):
        data_sources.append("scrape")
    if rss_ok:
        data_sources.append("rss")
    if fp.get("sample_size"):
        data_sources.append("fullparse")

    ra = dict(rss.get("analysis") or {})
    total_posts = scrape.get("total_posts")
    total_posts_min = ra.get("total_posts_min")
    if total_posts is None and ra.get("total_posts_rss") is not None:
        total_posts = ra["total_posts_rss"]     # RSS len(items) 폴백 (48개 미만일 때만)
        estimated.append("total_posts")
    neighbor_count = scrape.get("neighbor_count")
    total_visitors = scrape.get("total_visitors")
    cumulative_real = bool(scrape.get("cumulative_visitors_real"))

    # 2-9: scrape 없이 rss만인데 neighbor/visitors 값이 있으면 estimated
    if "scrape" not in data_sources:
        if neighbor_count is not None:
            estimated.append("neighbor_count")
        if total_visitors is not None:
            estimated.append("total_visitors")
    elif total_visitors is not None and not cumulative_real:
        estimated.append("total_visitors")

    visitor_measured = bool(visitors.get("measured"))
    daily_visitors = visitors.get("today") if visitor_measured else None
    recent_avg = visitors.get("recent_avg") if visitor_measured else None
    if daily_visitors is None and scrape.get("daily_visitors_fallback") is not None:
        # 하이드레이션 dayVisitorCount — 표시용 폴백. 실측(NVisitorgp) 아니므로 점수에는 반영 안 함
        daily_visitors = scrape["daily_visitors_fallback"]
        estimated.append("daily_visitors")

    stats = {
        "total_posts": total_posts,
        "total_posts_min": total_posts_min,
        "neighbor_count": neighbor_count,
        "total_visitors": total_visitors,
        "daily_visitors": daily_visitors,
        "recent_avg_visitors": recent_avg,
        "visitor_series": visitors.get("series") or [],
        "visitor_measured": visitor_measured,
    }
    for k in ("total_posts", "neighbor_count", "total_visitors", "daily_visitors"):
        if stats[k] is None:
            unmeasured.append(k)
    if not rss_ok:
        for k in ("recent_activity", "posting_interval_days", "category_entropy", "avg_post_length"):
            unmeasured.append(k)
    if not fp.get("sample_size"):
        unmeasured.append("fullparse")

    analysis = {
        "avg_post_length": ra.get("avg_post_length"),
        "avg_image_count": ra.get("avg_image_count"),
        "avg_word_count": ra.get("avg_word_count"),
        "category_count": ra.get("category_count"),
        "category_entropy": ra.get("category_entropy"),
        "recent_activity": ra.get("recent_activity"),
        "rss_window_days": ra.get("rss_window_days"),
        "rss_truncated": bool(ra.get("rss_truncated")),
        "posts_last_90d": ra.get("posts_last_90d"),
        "posting_interval_days": ra.get("posting_interval_days"),
        "posting_burstiness": ra.get("posting_burstiness"),
        "fullparse_avg_content_length": fp.get("fullparse_avg_content_length"),
        "fullparse_avg_images": fp.get("fullparse_avg_images"),
        "fullparse_avg_headings": fp.get("fullparse_avg_headings"),
        "fullparse_avg_paragraphs": fp.get("fullparse_avg_paragraphs"),
        "fullparse_avg_likes": fp.get("fullparse_avg_likes"),
        "fullparse_avg_comments": fp.get("fullparse_avg_comments"),
        "fullparse_sample_size": fp.get("sample_size") or 0,
    }

    result["stats"] = stats
    result["data_sources"] = data_sources
    result["estimated_fields"] = estimated
    result["unmeasured"] = unmeasured

    # ── 4) 가중치 → 채점 ────────────────────────────────────────────────────
    await _notify(progress, "score", blog_id=blog_id)
    W = resolve_scoring_weights(keyword, learned_weights=None, scoring_version=SCORING_VERSION)
    computed = compute_blog_index(stats, analysis, data_sources, W)

    index = _empty_index()
    index.update({
        "total_score": computed["total_score"],
        "vitality": computed["vitality"],
        "vitality_state": computed["vitality_state"],
        "days_since_last_post": computed["days_since_last_post"],
        "posts_last_90d": computed["posts_last_90d"],
        "rss_truncated": computed["rss_truncated"],
        "extra_bonus": computed["extra_bonus"],
        "unmeasured_dimensions": computed["unmeasured_dimensions"],
        "measurement_complete": computed["measurement_complete"],
        "score_breakdown": computed["breakdown"],
    })

    # ── 5) 2-8 측정 가능성 게이트 → 레벨 ───────────────────────────────────
    measurable = ("scrape" in data_sources) or ("rss" in data_sources)
    if not measurable:
        index.update({
            "level": None, "grade": "측정 불가", "level_category": "측정 불가",
            "percentile": None, "level_basis": None, "level_source": "unavailable",
            "unmeasurable_reason": UNMEASURABLE_REASON,
        })
        result["success"] = False
        result["error_code"] = scrape.get("error_code") or "UNMEASURABLE"
        result["error_message"] = scrape.get("error_message") or UNMEASURABLE_REASON
    else:
        score = index["total_score"]
        percentile = None
        if db is not None:
            await add_score_sample(db, blog_id, score)        # 모집단에 기여
            try:
                percentile = await get_percentile(db, score)
            except Exception as e:  # noqa: BLE001
                logger.debug("get_percentile 실패: %s", e)
                percentile = None
        if percentile is not None:
            level, grade = get_level_from_percentile(percentile)
            basis = "percentile"
        else:
            level, grade = get_blog_level_from_score(score)
            basis = "absolute"
        index.update({
            "level": level, "grade": grade, "level_category": level_category(level),
            "percentile": percentile, "level_basis": basis, "level_source": "heuristic",
            "unmeasurable_reason": None,
        })
        result["success"] = True

    # ── 6) (선택) 실측 색인 검증 → 등급 승격 (4-4) ─────────────────────────
    if verify_index and result["success"]:
        await _notify(progress, "verify", blog_id=blog_id)
        try:
            from app.blogindex import verifier  # noqa: WPS433
            v = await verifier.verify_index(db, blog_id)
            index["index_verification"] = v
            if isinstance(v, dict) and v.get("ok") and v.get("level") is not None:
                index["level_heuristic"] = index["level"]
                index["grade_heuristic"] = index["grade"]
                index["level"] = v["level"]
                index["grade"] = v.get("grade")
                index["level_category"] = level_category(v["level"])
                index["level_source"] = "measured"
                index["confidence"] = v.get("confidence")
        except Exception as e:  # noqa: BLE001
            logger.warning("verify_index 실패(%s): %s", blog_id, e)
            index["index_verification"] = {"ok": False, "error": str(e)}

    result["index"] = index
    result["measured_at"] = datetime.utcnow().isoformat()
    result["elapsed"] = round(time.monotonic() - t0, 2)

    # ── 7) 스냅샷 저장 (실패는 저장하지 않는다) ───────────────────────────
    if db is not None and result["success"]:
        await _store_snapshot(db, blog_id, category, result)
    await _notify(progress, "done", blog_id=blog_id, score=index.get("total_score"))
    return result


async def _load_competitor_score(db, blog_id: str) -> Optional[Dict[str, Any]]:
    from app.models.blog_index import CompetitorScore
    try:
        row = await db.get(CompetitorScore, blog_id)
    except Exception as e:  # noqa: BLE001
        logger.debug("competitor score 조회 실패(%s): %s", blog_id, e)
        return None
    if row is None or row.scoring_version != SCORING_VERSION or row.measured_at is None:
        return None
    if datetime.utcnow() - row.measured_at > SCORE_TTL:
        return None
    return {
        "score": row.score, "level": row.level, "grade": row.grade,
        "recent_activity_days": row.recent_activity_days, "blog_name": row.blog_name,
        "measured_at": row.measured_at.isoformat(), "cached": True,
    }


async def _store_competitor_score(db, blog_id: str, light: Dict[str, Any]) -> None:
    from app.models.blog_index import CompetitorScore
    from app.blogindex.dbwrite import isolated_write

    async def _do(s):
        row = await s.get(CompetitorScore, blog_id)
        now = datetime.utcnow()
        if row is None:
            s.add(CompetitorScore(
                blog_id=blog_id, blog_name=light.get("blog_name"), score=light["score"],
                level=light.get("level"), grade=light.get("grade"),
                recent_activity_days=light.get("recent_activity_days"),
                scoring_version=SCORING_VERSION, measured_at=now,
            ))
        else:
            row.blog_name = light.get("blog_name")
            row.score = light["score"]
            row.level = light.get("level")
            row.grade = light.get("grade")
            row.recent_activity_days = light.get("recent_activity_days")
            row.scoring_version = SCORING_VERSION
            row.measured_at = now

    await isolated_write(_do, what=f"competitor score {blog_id}")


# 경쟁자 채점 표본. 원본은 내 블로그와 같은 15개인데, 경쟁자 10명 × 15글 = 키워드당 150 페이지가
# 시간의 대부분이다. 경쟁자는 컷라인(하위 2개 평균)·중앙값에만 쓰이므로 10개로도 충분히 안정적이다.
# 내 블로그는 항상 15개(blog_index_jobs 에서 명시). 환경변수로 되돌릴 수 있다.
COMPETITOR_FULLPARSE = int(os.getenv("BLOGINDEX_COMPETITOR_FULLPARSE", "10"))


async def score_blog_light(db, blog_id: str, *, keyword: Optional[str] = None, use_cache: bool = True,
                           timeout: float = PER_BLOG_TIMEOUT, fullparse_n: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """경쟁자 채점용 경량 인터페이스 (10-3). 6h 디스크 캐시, 실패는 캐시하지 않는다.
    → {score, level, grade, recent_activity_days, blog_name, measured_at} | None"""
    blog_id = normalize_blog_id(blog_id)
    if not blog_id:
        return None
    if use_cache and db is not None:
        cached = await _load_competitor_score(db, blog_id)
        if cached is not None:
            return cached

    async def _run():
        async with _score_semaphore:      # 세마포어 대기 시간도 타임아웃 안에 넣는다(대기 적체 방지)
            return await analyze_blog(db, blog_id, keyword=keyword, fullparse=True, use_cache=False,
                                      fullparse_n=fullparse_n or COMPETITOR_FULLPARSE)

    if True:
        try:
            res = await asyncio.wait_for(_run(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("score_blog_light timeout(%.0fs): %s (마지막 단계: %s)", timeout, blog_id, _LAST_STAGE.get(blog_id))
            try:
                if db is not None:
                    await db.rollback()
            except Exception:  # noqa: BLE001
                pass
            return None
        except Exception as e:  # noqa: BLE001
            logger.warning("score_blog_light 실패(%s): %s", blog_id, e)
            return None

    if not res or not res.get("success"):
        return None
    idx = res.get("index") or {}
    if idx.get("total_score") is None:
        return None
    light = {
        "score": idx["total_score"],
        "level": idx.get("level"),
        "grade": idx.get("grade"),
        "recent_activity_days": idx.get("days_since_last_post"),
        "blog_name": res.get("blog_name"),
        "measured_at": res.get("measured_at") or datetime.utcnow().isoformat(),
        "cached": False,
    }
    if db is not None:
        await _store_competitor_score(db, blog_id, light)   # 성공만 저장
    return light
