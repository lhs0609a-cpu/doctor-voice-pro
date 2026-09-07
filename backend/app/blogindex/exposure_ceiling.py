"""
노출 천장 (문서 7장, exposure_ceiling)

"블로그의 지수를 추정"하는 대신 관측 가능한 사실을 직접 잰다:
  **이 블로그가 실제로 상위노출에 성공한 키워드들의 검색량이 어디까지인가?**
그 상한선이 노출 천장이다. 새 키워드가 천장 아래면 가능성이 높고, 위면 어렵다.

배경(2026-07 리서치): 네이버는 "블로그 지수"를 공식 개념으로 인정하지 않으며,
숨은 지수 API에 의존하던 블덱스 등은 2025-12 서비스가 붕괴했다. 살아남은
방법론은 '관측 가능한 아웃풋(실제 SERP 노출)' 기반이다.

★ 천장 산정과 정답지 채점이 **동일한 순위 소스(실제 탭)** 를 써야 calibration이 유효하다.
  openapi는 프리필터 전용.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import statistics
import time
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set

from sqlalchemy import delete, func, select

from app.blogindex import DISCLAIMER_CEILING, normalize_blog_id
from app.blogindex import serp as serp_mod
from app.blogindex.verifier import _extract_keywords
from app.models.blog_index import CeilingCache

logger = logging.getLogger(__name__)

# ── 7-1. 파라미터 ─────────────────────────────────────────────────────────
SAMPLE_POSTS = 20          # RSS에서 볼 최근 글 수
MAX_KEYWORDS = 24          # 기본 프리필터 대상 상한
MAX_CANDIDATES = 40        # 확장 후보 총 상한
MAX_SCRAPE_CONFIRMS = 10   # 실제 스크래핑으로 확정할 최대 키워드 (비용 캡)
VOLUME_FLOOR = 10          # 이 미만 검색량은 '실수요 없음'
RANK_CUTOFF_PAGE1 = 10     # 1페이지 기준
RANK_CUTOFF_INDEXED = 30   # 색인 확인 상한
RANK_CONCURRENCY = 5       # openapi 프리필터 동시성
SCRAPE_CONCURRENCY = 2     # 스크래핑(봇탐지·비용)
CACHE_TTL = 86400          # 24h
CACHE_MAX_ROWS = 300       # 300개 넘으면 오래된 150개 제거
CACHE_PRUNE_ROWS = 150
EXPLORE = 2                # 7-4 explore 슬롯

# 7-5 ground truth 판별: 이 소스로 잰 행만 천장 근거로 인정
_SCRAPE_SOURCES = {"playwright", "http", "http_regex"}

# 실패 코드
ERR_NO_POSTS = "no_posts_via_rss"
ERR_NO_KEYWORDS = "no_keywords_extracted"
ERR_NO_VOLUME = "no_volume_data"
ERR_NO_DEMAND = "no_keywords_with_demand"
ERR_RANK_UNAVAILABLE = "rank_check_unavailable"   # (추가) 실제 탭 스크래핑이 전부 실패


# ── 7-3. 후보 확장 — 2글자 슁글 오버랩 ──────────────────────────────────
def _char_bigrams(text: str) -> Set[str]:
    grams: Set[str] = set()
    for run in re.findall(r"[가-힣A-Za-z0-9]{2,}", (text or "").lower()):
        for i in range(len(run) - 1):
            grams.add(run[i:i + 2])
    return grams


# 너무 흔해 주제 변별력이 없는 슁글 (과확장 방지)
_STOP_BIGRAMS = {"한의", "의원", "병원", "치료", "클리", "리닉", "센터", "효과", "가격", "후기", "추천"}


def _strip_tags(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def _norm_key(kw: str) -> str:
    """검색광고 relKeyword 는 공백 제거 형태로 온다 — 매칭도 공백 제거(+대문자)로."""
    return (kw or "").replace(" ", "").upper()


def _confidence(tested: int, ranked: int) -> str:
    if tested >= 12 and ranked >= 4:
        return "high"
    if tested >= 6 and ranked >= 2:
        return "medium"
    return "low"


# ── 7-6. 천장 계산 (순수 함수 — 라이브 측정과 백테스트가 공유) ──────────
def ceiling_from_observations(rows: List[Dict[str, Any]], extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """rows: [{keyword, volume, rank}]  (rank=None 은 미노출)"""
    ranked = [r for r in rows if r.get("rank") is not None]
    page1 = [r for r in ranked if r["rank"] <= RANK_CUTOFF_PAGE1]
    top30 = [r for r in ranked if r["rank"] <= RANK_CUTOFF_INDEXED]

    page1_vols = sorted((r["volume"] for r in page1), reverse=True)
    top30_vols = [r["volume"] for r in top30]
    n = len(rows)

    out = {
        "ok": True,
        "ceiling_volume": page1_vols[0] if page1_vols else None,                        # 최고 실적
        "ceiling_p50": int(statistics.median(page1_vols)) if page1_vols else None,      # 안정권
        "top30_ceiling": max(top30_vols) if top30_vols else None,
        "win_rate": round(len(page1) / n, 3) if n else 0.0,
        "ranked_keywords": sorted(
            [{"keyword": r["keyword"], "volume": r["volume"], "rank": r["rank"]} for r in top30],
            key=lambda x: x["volume"], reverse=True)[:15],
        "ranked_count": len(page1),
        "tested_count": n,
        "confidence": _confidence(n, len(page1)),
        "rank_source": "blog_tab_scraping",
    }
    if extra:
        out.update(extra)
    return out


# ── 캐시 ─────────────────────────────────────────────────────────────────
async def _cache_get(db, blog_id: str) -> Optional[Dict[str, Any]]:
    if db is None:
        return None
    try:
        row = await db.get(CeilingCache, blog_id)
    except Exception:  # noqa: BLE001
        return None
    if row is None or not row.measured_at:
        return None
    if datetime.utcnow() - row.measured_at > timedelta(seconds=CACHE_TTL):
        return None
    if not (row.result or {}).get("ok"):
        return None
    return dict(row.result)


async def _cache_put(db, blog_id: str, result: Dict[str, Any]) -> None:
    if db is None:
        return
    try:
        row = await db.get(CeilingCache, blog_id)
        if row is None:
            row = CeilingCache(blog_id=blog_id)
            db.add(row)
        row.result = result
        row.measured_at = datetime.utcnow()
        await db.commit()
        # 300개 넘으면 오래된 150개 제거
        total = (await db.execute(select(func.count()).select_from(CeilingCache))).scalar() or 0
        if total > CACHE_MAX_ROWS:
            old_ids = (await db.execute(
                select(CeilingCache.blog_id).order_by(CeilingCache.measured_at.asc()).limit(CACHE_PRUNE_ROWS)
            )).scalars().all()
            if old_ids:
                await db.execute(delete(CeilingCache).where(CeilingCache.blog_id.in_(list(old_ids))))
                await db.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning("[ceiling] 캐시 저장 실패: %s", e)
        with contextlib.suppress(Exception):
            await db.rollback()


def _emit(progress: Optional[Callable], stage: str, done: int, total: int) -> None:
    if progress is None:
        return
    try:
        progress(stage, done, total)
    except Exception:  # noqa: BLE001
        pass


# ── 검색광고 볼륨 + 공짜 연관키워드 확장 ─────────────────────────────────
async def _volumes_with_related(core: List[str]) -> tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]], bool]:
    """5개씩 배치 + 배치 간 0.2초 sleep(레이트리밋). (wanted, related, configured)"""
    from app.services import search_volume_service as svs
    if not svs.is_configured():
        return {}, {}, False
    wanted: Dict[str, Dict[str, Any]] = {}
    related: Dict[str, Dict[str, Any]] = {}
    batches = [core[i:i + svs.MAX_HINTS_PER_CALL] for i in range(0, len(core), svs.MAX_HINTS_PER_CALL)]
    for i, batch in enumerate(batches):
        if i > 0:
            await asyncio.sleep(0.2)
        try:
            w, r = await svs.fetch_with_related(batch)
        except Exception as e:  # noqa: BLE001
            logger.warning("[ceiling] 검색량 조회 실패 %s: %s", batch, e)
            continue
        wanted.update(w)
        for k, v in r.items():
            related.setdefault(k, v)
    return wanted, related, True


def _expand_candidates(core: List[str], wanted: Dict[str, Dict[str, Any]],
                       related: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """코어(볼륨 있는 것) + 슁글 오버랩 필터 통과한 연관키워드. 검색량 높은 순, MAX_CANDIDATES 상한."""
    cands: Dict[str, Dict[str, Any]] = {}
    for kw in core:
        m = wanted.get(_norm_key(kw))
        if m is None:
            continue
        cands[_norm_key(kw)] = {"keyword": kw, "volume": int(m.get("total_volume") or 0), "origin": "core"}

    # 필터: relKeyword 가 코어의 '변별력 있는'(스톱 제외) 슁글을 하나라도 공유하면 주제 내로 본다.
    core_grams: Set[str] = set()
    for kw in core:
        core_grams |= _char_bigrams(kw)
    distinct = core_grams - _STOP_BIGRAMS
    if not distinct:
        distinct = core_grams   # 코어가 죄다 흔한 말이면 전체 슁글로 폴백

    rel_rows: List[Dict[str, Any]] = []
    for nk, m in related.items():
        if nk in cands:
            continue
        rel_kw = m.get("keyword") or nk
        if not (_char_bigrams(rel_kw) & distinct):
            continue   # 흔한 슁글만 겹치는 건 제외
        rel_rows.append({"keyword": rel_kw, "volume": int(m.get("total_volume") or 0), "origin": "related", "_nk": nk})
    rel_rows.sort(key=lambda x: x["volume"], reverse=True)

    out = list(cands.values())
    for r in rel_rows:
        if len(out) >= MAX_CANDIDATES:
            break
        nk = r.pop("_nk")
        cands[nk] = r
        out.append(r)
    out.sort(key=lambda x: x["volume"], reverse=True)
    return out[:MAX_CANDIDATES]


def _plan_confirms(pre: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """7-4 스크래핑 예산 배분 (exploit / explore). pre 는 volume desc 정렬을 유지한다."""
    indexed = [c for c in pre if c.get("openapi_rank") is not None]
    non_indexed = [c for c in pre if c.get("openapi_rank") is None]
    n_explore = min(EXPLORE, len(non_indexed))
    n_exploit = MAX_SCRAPE_CONFIRMS - n_explore
    confirm = indexed[:n_exploit] + non_indexed[:n_explore]
    if len(confirm) < MAX_SCRAPE_CONFIRMS:
        chosen = {id(c) for c in confirm}
        for c in pre:  # 부족하면 남은 후보로 볼륨순 채움
            if len(confirm) >= MAX_SCRAPE_CONFIRMS:
                break
            if id(c) not in chosen:
                confirm.append(c)
                chosen.add(id(c))
    return confirm


# ── 공개 API ─────────────────────────────────────────────────────────────
async def measure_ceiling(db, blog_id: str, refresh: bool = False,
                          progress: Optional[Callable[[str, int, int], None]] = None) -> Dict[str, Any]:
    from app.blogindex import collectors  # 지연 import

    blog_id = normalize_blog_id(blog_id)
    t0 = time.monotonic()
    if not refresh:
        cached = await _cache_get(db, blog_id)
        if cached is not None:
            cached["cached"] = True
            return cached

    def fail(code: str, message: str, **extra) -> Dict[str, Any]:
        out = {"ok": False, "blog_id": blog_id, "error": code, "message": message,
               "elapsed": round(time.monotonic() - t0, 1), "disclaimer": DISCLAIMER_CEILING}
        out.update(extra)
        return out

    # 1) RSS로 최근 글 제목 + 본문요약 수집
    _emit(progress, "rss", 0, 1)
    try:
        rss = await collectors.fetch_rss(blog_id)
    except Exception as e:  # noqa: BLE001
        logger.warning("[ceiling] RSS 실패 %s: %s", blog_id, e)
        rss = None
    if not rss or not rss.get("ok") or not rss.get("items"):
        return fail(ERR_NO_POSTS, "RSS에서 최근 글을 가져오지 못했습니다.")
    items = list(rss["items"])[:SAMPLE_POSTS]

    # 2) 후보 키워드 추출 — 글당 1회씩만 카운트(set)해 빈도 집계
    counter: Counter = Counter()
    for it in items:
        counter.update(set(_extract_keywords(it.get("title") or "")))
        counter.update(set(_extract_keywords(_strip_tags(it.get("description") or ""))))
    core = [k for k, _ in counter.most_common(MAX_KEYWORDS)]
    if not core:
        return fail(ERR_NO_KEYWORDS, "최근 글에서 후보 키워드를 뽑지 못했습니다.")

    # 3) 검색광고 API로 core 볼륨 조회 + relKeyword 공짜 확장
    _emit(progress, "volume", 0, 1)
    wanted, related, configured = await _volumes_with_related(core)
    if not configured or (not wanted and not related):
        return fail(ERR_NO_VOLUME, "검색광고 API 검색량을 가져오지 못했습니다."
                    + ("(자격증명 미설정)" if not configured else ""), core_keywords=core)
    candidates = [c for c in _expand_candidates(core, wanted, related) if c["volume"] >= VOLUME_FLOOR]
    if not candidates:
        return fail(ERR_NO_DEMAND, f"검색량 {VOLUME_FLOOR} 이상인 후보 키워드가 없습니다.", core_keywords=core)

    # 4-a) openapi(sort=sim) 싼 프리필터 — 어느 키워드가 유망한지 스캔 (ground truth 아님)
    prefilter_available = serp_mod.openapi_configured()
    if prefilter_available:
        sem_rank = asyncio.Semaphore(RANK_CONCURRENCY)
        done = 0

        async def _pre(c: Dict[str, Any]) -> None:
            nonlocal done
            async with sem_rank:
                try:
                    c["openapi_rank"] = await serp_mod.openapi_blog_rank(c["keyword"], blog_id, display=RANK_CUTOFF_INDEXED)
                except Exception:  # noqa: BLE001
                    c["openapi_rank"] = None
            done += 1
            _emit(progress, "prefilter", done, len(candidates))

        await asyncio.gather(*[_pre(c) for c in candidates])
    else:
        for c in candidates:
            c["openapi_rank"] = None
    confirm = _plan_confirms(candidates)

    # 4-b) 유망 키워드만 실제 블로그탭 스크래핑으로 진짜 순위 확정 (비용 캡)
    sem_scrape = asyncio.Semaphore(SCRAPE_CONCURRENCY)
    done_c = 0

    async def _confirm(c: Dict[str, Any]) -> None:
        nonlocal done_c
        async with sem_scrape:
            async with serp_mod.fresh_session() as s:
                try:
                    serp = await serp_mod.blog_tab_serp(s, c["keyword"], limit=RANK_CUTOFF_INDEXED)
                except Exception as e:  # noqa: BLE001
                    logger.warning("[ceiling] 스크래핑 실패 %s: %s", c["keyword"], e)
                    serp = None
        # 7-5 ground truth 판별: 스크래핑 소스가 아니면 측정 불가 처리
        if serp is None or serp.get("source") not in _SCRAPE_SOURCES:
            c["measured"] = False
            c["rank"] = None
            c["rank_source"] = None
        else:
            c["measured"] = True
            c["rank_source"] = serp["source"]
            c["parse_mode"] = serp.get("parse_mode")
            c["rank"] = serp_mod._find_rank(serp["rows"], blog_id)
        done_c += 1
        _emit(progress, "confirm", done_c, len(confirm))

    await asyncio.gather(*[_confirm(c) for c in confirm])

    measured_rows = [c for c in confirm if c.get("measured")]
    if not measured_rows:
        return fail(ERR_RANK_UNAVAILABLE, "실제 블로그탭 순위를 한 건도 확인하지 못했습니다(검색 차단 가능).",
                    candidates=[{k: v for k, v in c.items() if not k.startswith("_")} for c in confirm])

    result = ceiling_from_observations(
        [{"keyword": c["keyword"], "volume": c["volume"], "rank": c["rank"]} for c in measured_rows],
        extra={
            "blog_id": blog_id,
            "blog_name": rss.get("blog_name"),
            "tested_keywords": [
                {"keyword": c["keyword"], "volume": c["volume"], "rank": c["rank"],
                 "openapi_rank": c.get("openapi_rank"), "rank_source": c.get("rank_source"),
                 "parse_mode": c.get("parse_mode"), "origin": c.get("origin")}
                for c in confirm
            ],
            "candidate_count": len(candidates),
            "core_keywords": core,
            "prefilter": "openapi" if prefilter_available else "unavailable",
            "unmeasured_count": len(confirm) - len(measured_rows),
            "measured_at": datetime.utcnow().isoformat(),
            "elapsed": round(time.monotonic() - t0, 1),
            "cached": False,
            "disclaimer": DISCLAIMER_CEILING,
        },
    )
    # 폴백 파싱 행이 섞이면 confidence 를 낮춘다 (14-3 규칙 6)
    if any(c.get("parse_mode") == "regex" for c in measured_rows):
        result["confidence"] = "low"
        result["parse_fallback"] = True
    await _cache_put(db, blog_id, result)
    return result
