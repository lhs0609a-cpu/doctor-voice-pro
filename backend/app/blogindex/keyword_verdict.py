"""
키워드 판정 v2 (문서 10장, keyword_verdict) — 컷라인 기반 로지스틱 ★현재 주력

질문을 바꾼다:
  v1  "이 키워드 검색량 vs 내가 뚫어본 최대 검색량"
  v2  "그 키워드 1페이지에 **실제로 앉아 있는 블로그들**을 내 블로그와 같은
       채점기(2장)로 채점해서 진입 **컷라인**을 구하고, 내 점수를 그 자리에 놓아본다."

10-2. 신뢰도 규칙 (이 모듈의 존재 이유) ★
  1. **순위는 실제 SERP만 쓴다.** openapi(sort=sim) 순서는 실제 블로그탭 순서와
     다르므로 순위 근거로 절대 쓰지 않는다. 검색 HTML 파싱만 ground truth.
  2. **측정 실패는 '어려움'이 아니라 '측정 실패'다.** SERP 조회 실패·내 블로그
     채점 실패는 unknown 으로 나가고 확률(=채점 대상)을 만들지 않는다.
  3. **확률은 보정 가능한 형태로만 낸다.** 상수 분기가 아니라 로지스틱 결합이며,
     계수는 외부 JSON 파일로 교체 가능하다. 정답지가 쌓이면 fit 값을 얹는다.
  4. **표본이 얇으면 확신을 줄인다.** base rate(0.35)로 수축한다.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import math
import os
import statistics
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from app.blogindex import (DIFFICULTY_VERSION, DISCLAIMER_VERDICT, VERDICT_MODEL_VERSION,
                           normalize_blog_id, normalize_keyword)
from app.blogindex import serp as serp_mod
from app.blogindex import seo_difficulty
from app.blogindex.serp_difficulty import _vitality_from_gap
from app.models.blog_index import CeilingCache, VerdictResult

logger = logging.getLogger(__name__)

# ── 10-3. 상수 ────────────────────────────────────────────────────────────
PAGE1_CUTOFF = 10          # 1페이지 = 상위 10위
SERP_LIMIT = 20            # 조회 범위(2페이지) — 11~30위 색인 신호까지 본다
SERP_TTL = 6 * 3600        # 키워드 단위 **공용** SERP 캐시 (사용자가 달라도 1회만)
# 원본 10-3: SCORE_CONCURRENCY 8 / PER_BLOG_TIMEOUT 32. 원본은 다중 코어 워커였고, 여기 운영 머신은
# shared-cpu-1x 라 8개를 동시에 돌리면 전부 32초를 넘겨 "채점된 경쟁자 0개"가 났다(실측). 환경변수로 조정.
SCORE_CONCURRENCY = int(os.getenv("BLOGINDEX_SCORE_CONCURRENCY", "10"))
PER_BLOG_TIMEOUT = float(os.getenv("BLOGINDEX_PER_BLOG_TIMEOUT", "120"))
RETRY_MISSING = 6          # 1차에서 못 잰 경쟁자 재시도 상한
STAGE2_BUDGET = float(os.getenv("BLOGINDEX_STAGE2_BUDGET", "300"))   # 키워드 1개 판정 총 예산(초). 넘으면 재시도 생략
SERP_PAGE_TIMEOUT = 12.0
PLAYWRIGHT_TIMEOUT = 150.0
SCORE_TTL = 6 * 3600       # 경쟁자 점수 디스크 캐시
BROWSER_IDLE_CLOSE = 600   # 상주 브라우저 idle 종료
CEILING_TTL = 86400        # 노출 천장 캐시(7장)는 있을 때만 보조 피처

# ── 10-5. 확률 모델 (교체 가능한 계수) ───────────────────────────────────
_DEFAULT_MODEL: Dict[str, Any] = {
    "version": VERDICT_MODEL_VERSION,   # "v1-heuristic"
    "bias": -0.90,
    "weights": {
        "score_margin": 1.15,   # (내 점수 - 1페이지 진입문턱) / 8점
        "median_margin": 0.45,  # (내 점수 - 1페이지 중앙값)   / 8점
        "topical_fit": 0.90,    # 내 RSS 내 주제글 수 (0~1 정규화)
        "vacancy": 1.00,        # 1페이지 휴면 경쟁자 비율
        "ceiling_head": 0.50,   # log10(내 안정권 검색량 / 이 키워드 검색량)
        "indexed30": 0.60,      # 이미 11~30위에 색인돼 있음
    },
    "base_rate": 0.35,
    "shrink": {"high": 1.0, "medium": 0.75, "low": 0.45},
    "thresholds": {"likely": 0.62, "contested": 0.32},
}
# data/keyword_verdict_model.json 이 있으면 그 계수로 덮어쓴다(정답지 fit 결과 주입용)
MODEL_OVERRIDE_PATH = Path(__file__).resolve().parents[2] / "data" / "keyword_verdict_model.json"
_model_cache: Dict[str, Any] = {"mtime": None, "model": None}


def load_model() -> Dict[str, Any]:
    try:
        mtime = os.path.getmtime(MODEL_OVERRIDE_PATH)
    except OSError:
        mtime = None
    if _model_cache["model"] is not None and _model_cache["mtime"] == mtime:
        return _model_cache["model"]
    model = json.loads(json.dumps(_DEFAULT_MODEL))
    if mtime is not None:
        try:
            with open(MODEL_OVERRIDE_PATH, "r", encoding="utf-8") as f:
                override = json.load(f) or {}
            for k, v in override.items():
                if isinstance(v, dict) and isinstance(model.get(k), dict):
                    model[k].update(v)
                else:
                    model[k] = v
            logger.info("[verdict] 모델 계수 오버라이드 적용: %s (version=%s)", MODEL_OVERRIDE_PATH, model.get("version"))
        except Exception as e:  # noqa: BLE001
            logger.warning("[verdict] 모델 파일 로드 실패(기본값 사용): %s", e)
    _model_cache.update(mtime=mtime, model=model)
    return model


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


# ── 10-4. 주제 적합도 (topical fit) ──────────────────────────────────────
_GENERIC_PARTS = {"방법", "추천", "후기", "확인", "정보", "비교", "순위", "리뷰",
                  "best", "top", "종류", "가격", "사이트", "사용법", "차이",
                  "장단점", "정리", "소개", "알아보기", "모음", "총정리"}


def count_keyword_related_posts(keyword: str, posts: List[Dict[str, Any]]) -> int:
    """내 블로그 RSS 최근 글(최대 50개) 중 이 키워드 주제 글 수.
    None(측정불가) 과 0(진짜 없음) 은 호출부에서 구분한다 — 여기선 리스트가 주어졌을 때만 센다."""
    kw = (keyword or "").lower().strip()
    keyword_parts = [p for p in kw.split() if len(p) >= 2]
    significant_parts = [p for p in keyword_parts if p not in _GENERIC_PARTS] or keyword_parts
    full_count = 0
    partial_count = 0
    for p in posts or []:
        title = (p.get("title") or "").lower()
        desc = (p.get("description") or "").lower()
        category = (p.get("category") or "").lower()
        text = title + " " + desc
        if kw and kw in text:                                                     # 1)
            full_count += 1
        elif len(significant_parts) >= 2 and all(sp in text for sp in significant_parts):   # 2)
            full_count += 1
        elif significant_parts and sum(1 for sp in significant_parts if sp in text) >= max(1, len(significant_parts) // 2):  # 3)
            partial_count += 1
        elif category and any(sp in category for sp in significant_parts):       # 4)
            partial_count += 1
    return full_count + max(0, partial_count // 2)     # 부분매칭 2건 = 1건


# ── 10-6. compute_verdict (원본 그대로) + 10-7 근거 문장 ──────────────────
def compute_verdict(*, my: Optional[Dict[str, Any]], competitors: List[Dict[str, Any]], volume: Optional[int],
                    my_rank: Optional[int], topical: Optional[int], ceiling: Optional[Dict[str, Any]],
                    serp_reliable: bool = True) -> Dict[str, Any]:
    model = load_model()
    w = model["weights"]
    volume = volume or 0
    page1 = [c for c in competitors if (c.get("rank") if c.get("rank") is not None else 99) <= PAGE1_CUTOFF]
    scored = [c for c in page1 if c.get("score")]

    # ── 측정 실패는 판정하지 않는다 ──
    if my is None or my.get("score") is None:
        return {"verdict": "unknown", "probability": None, "confidence": "low",
                "reasons": ["내 블로그 채점에 실패했습니다(비공개·삭제·일시 오류)."],
                "features": {}, "cut_line": None, "median_score": None, "model_version": model["version"]}
    if len(scored) < 3:
        return {"verdict": "unknown", "probability": None, "confidence": "low",
                "reasons": [f"1페이지 경쟁자 중 채점된 블로그가 {len(scored)}개뿐이라 "
                            "컷라인을 낼 수 없습니다(인플루언서·카페·광고 비중이 높은 SERP)."],
                "features": {}, "cut_line": None, "median_score": None, "model_version": model["version"]}

    scores = sorted(c["score"] for c in scored)
    cut_line = scores[0]                       # 1페이지 최하위 = 표시용 문턱
    # ★ 피처는 최하위 1개가 아니라 하위 2개 평균을 쓴다. 유난히 약한 블로그 하나가
    #   우연히 10위에 앉아 있으면 min 만으로는 "누구나 들어간다"가 돼 과대확신이 난다.
    entry_bar = statistics.fmean(scores[:2]) if len(scores) >= 2 else cut_line
    median_score = statistics.median(scores)
    my_score = my["score"]

    dormant = [c for c in scored if (c.get("recent_activity_days") or 0) > 90]
    vacancy = len(dormant) / len(scored)

    f = {
        # 상한(+2)을 하한(-3)보다 좁게 잡는다 — "훨씬 세다"가 무한히 확신으로
        # 변환되면 검증 안 된 모델이 과대확신한다. 크게 모자란 건 확실한 신호.
        "score_margin": _clamp((my_score - entry_bar) / 8.0, -3, 2),
        "median_margin": _clamp((my_score - median_score) / 8.0, -3, 3),
        "topical_fit": (min(topical, 8) / 8.0) if topical is not None else 0.25,
        "vacancy": vacancy,
        "ceiling_head": 0.0,
        "indexed30": 1.0 if (my_rank is not None and my_rank > 10) else 0.0,
    }
    if ceiling and ceiling.get("ceiling_p50") and volume > 0:
        f["ceiling_head"] = _clamp(math.log10((ceiling["ceiling_p50"] + 1) / (volume + 1)), -2, 2)

    z = model["bias"] + sum(w.get(k, 0.0) * v for k, v in f.items())
    prob = 1.0 / (1.0 + math.exp(-_clamp(z, -12, 12)))

    # 신뢰도: 컷라인을 몇 개로 냈는가 + 주제적합도 측정 여부
    if len(scored) >= 7 and topical is not None:
        confidence = "high"
    elif len(scored) >= 5:
        confidence = "medium"
    else:
        confidence = "low"
    if not serp_reliable:
        confidence = "low"   # 폴백 파싱

    base = model["base_rate"]
    shrink = model["shrink"].get(confidence, 0.45)
    # 상한 0.90 — 아직 실측 정답지로 보정되지 않은 모델이라 "확실"을 팔지 않는다.
    prob = round(_clamp(base + shrink * (prob - base), 0.02, 0.90), 3)

    th = model["thresholds"]
    verdict = ("likely" if prob >= th["likely"]
               else "contested" if prob >= th["contested"] else "unlikely")

    # ── 10-7. 근거 문장 (숫자 그대로 — 사용자가 검산할 수 있어야 한다) ──
    reasons: List[str] = []
    gap = my_score - cut_line
    if gap >= 0:
        reasons.append(f"1페이지 진입 컷라인은 {cut_line:.1f}점(현재 10위권 최하위)이고 "
                       f"내 블로그는 {my_score:.1f}점 — {gap:.1f}점 위입니다.")
    else:
        reasons.append(f"1페이지 진입 컷라인은 {cut_line:.1f}점인데 내 블로그는 {my_score:.1f}점 — "
                       f"{abs(gap):.1f}점 모자랍니다.")
    reasons.append(f"1페이지 중앙값 {median_score:.1f}점, 채점된 경쟁자 {len(scored)}명.")
    if vacancy > 0:
        reasons.append(f"1페이지 중 {len(dormant)}자리가 90일 이상 방치된 블로그입니다(뚫을 공석).")
    if topical is not None and topical >= 3:
        reasons.append(f"내 블로그 최근 글 중 이 주제 글이 {topical}개 — 주제 적합도가 있습니다.")
    elif topical == 0:
        reasons.append("내 블로그 최근 글에 이 주제 글이 없습니다 — 주제 적합도가 약합니다.")
    if my_rank is not None and my_rank > 10:
        reasons.append(f"이미 {my_rank}위로 색인돼 있습니다(1페이지 근접 신호).")
    if not serp_reliable:
        reasons.append("⚠️ 검색 결과 목록 파싱이 폴백 경로여서 순위 정확도가 낮습니다 — 판정을 참고용으로만 보세요.")

    return {"verdict": verdict, "probability": prob, "confidence": confidence,
            "reasons": reasons, "features": {k: round(v, 3) for k, v in f.items()},
            "cut_line": round(cut_line, 1), "entry_bar": round(entry_bar, 1),
            "median_score": round(median_score, 1), "my_score": round(my_score, 1),
            "scored_competitors": len(scored), "vacancy_count": len(dormant),
            "model_version": model["version"]}


# ── STAGE 1 (facts) — 반박 불가능한 사실만. 실제 블로그탭 SERP 1회 조회 ────
async def _keyword_volume(db, keyword: str) -> tuple[Optional[int], bool]:
    """검색광고 월검색량. (volume, measured). 자격증명 없음/실패 → (None, False) — 0 으로 채우지 않는다."""
    try:
        from app.services import search_volume_service as svs
        if not svs.is_configured():
            return None, False
        rows = await svs.get_keyword_metrics(db, [keyword])
        if not rows:
            return None, False
        return int(rows[0].get("total_volume") or 0), True
    except Exception as e:  # noqa: BLE001
        logger.warning("[verdict] 검색량 조회 실패 %s: %s", keyword, e)
        return None, False


async def stage1_facts(db, blog_id: str, keyword: str) -> Dict[str, Any]:
    blog_id = normalize_blog_id(blog_id)
    keyword = (keyword or "").strip()
    t0 = time.monotonic()
    serp_task = asyncio.create_task(serp_mod.blog_tab_serp(db, keyword, limit=SERP_LIMIT))
    serp = None
    try:
        serp = await serp_task
    except Exception as e:  # noqa: BLE001
        logger.warning("[verdict] SERP 조회 예외 %s: %s", keyword, e)
    volume, volume_measured = await _keyword_volume(db, keyword)

    base = {"blog_id": blog_id, "keyword": keyword, "keyword_norm": normalize_keyword(keyword),
            "elapsed": round(time.monotonic() - t0, 1)}
    if serp is None:
        return {**base, "ok": False, "verdict": "unknown",
                "message": "네이버 검색 결과를 가져오지 못했습니다(일시적 차단 가능).",
                "facts": {"volume": volume, "volume_measured": volume_measured, "my_rank": None,
                          "already_page1": False, "serp_source": None, "serp_parse_mode": None,
                          "serp_cached": None, "serp_measured_at": None, "serp_size": None, "page1": []},
                "rows": []}

    rows = serp["rows"]
    my_rank = serp_mod._find_rank(rows, blog_id)
    page1 = [{"rank": r["rank"], "blog_id": r["blog_id"], "blog_name": None,
              "post_title": r.get("title") or "", "post_url": r.get("post_url")}
             for r in rows if r["rank"] <= PAGE1_CUTOFF]
    return {
        **base,
        "ok": True,
        "facts": {
            "volume": volume,
            "volume_measured": volume_measured,
            "my_rank": my_rank,
            "already_page1": my_rank is not None and my_rank <= PAGE1_CUTOFF,
            "serp_source": serp.get("source"),
            "serp_parse_mode": serp.get("parse_mode"),
            "serp_cached": serp.get("cached"),
            "serp_measured_at": serp.get("measured_at"),
            "serp_size": len(rows),
            "page1": page1,
        },
        "rows": rows,
    }


# ── STAGE 2 (cutline) — 판정 ──────────────────────────────────────────────
async def _score_blog_inner(blog_id: str, keyword: str, use_cache: bool) -> Optional[Dict[str, Any]]:
    from app.blogindex import analyzer  # 지연 import
    try:
        async with serp_mod.fresh_session() as s:
            return await analyzer.score_blog_light(s, blog_id, keyword=keyword, use_cache=use_cache)
    except Exception as e:  # noqa: BLE001
        logger.warning("[verdict] 채점 실패 %s: %s", blog_id, e)
        return None


async def _score_blog(blog_id: str, keyword: str, use_cache: bool) -> Optional[Dict[str, Any]]:
    """경쟁자/내 블로그 채점 1건 — 별도 세션, PER_BLOG_TIMEOUT. 실패는 None (캐시하지 않는다).
    원본은 shield 로 뒤에서 계속 돌게 뒀지만, 그러면 시간초과 난 채점이 analyzer 세마포어를
    계속 쥔 채 쌓여 다음 키워드까지 전부 90초 대기→시간초과로 번졌다(운영 실측).
    캐시 쓰기는 dbwrite 로 격리돼 있어 취소가 안전하므로 이제는 취소한다."""
    try:
        return await asyncio.wait_for(_score_blog_inner(blog_id, keyword, use_cache), PER_BLOG_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning("[verdict] 채점 타임아웃 %s (%.0fs) — 취소", blog_id, PER_BLOG_TIMEOUT)
        return None
    except Exception as e:  # noqa: BLE001
        logger.warning("[verdict] 채점 실패 %s: %s", blog_id, e)
        return None


async def _topical_fit(blog_id: str, keyword: str) -> tuple[Optional[int], Optional[str]]:
    """(topical_posts, blog_name). None = RSS 조회 실패(측정 불가), 0 = 진짜로 없음."""
    try:
        from app.blogindex import collectors  # 지연 import
        rss = await collectors.fetch_rss(blog_id)
    except Exception as e:  # noqa: BLE001
        logger.warning("[verdict] 내 RSS 실패 %s: %s", blog_id, e)
        return None, None
    if not rss or not rss.get("ok"):
        return None, None
    items = rss.get("items") or []
    if not items and rss.get("rss_empty"):
        return None, rss.get("blog_name")   # 빈 피드(비공개/미발행)는 측정 불가로 남긴다
    return count_keyword_related_posts(keyword, items[:50]), rss.get("blog_name")


async def _ceiling_from_cache(db, blog_id: str) -> Optional[Dict[str, Any]]:
    """노출 천장은 **캐시가 있을 때만** 보조 피처로 쓴다. 없다고 새로 측정하지 않는다."""
    if db is None:
        return None
    try:
        row = await db.get(CeilingCache, blog_id)
    except Exception:  # noqa: BLE001
        return None
    if row is None or not row.measured_at or not (row.result or {}).get("ok"):
        return None
    if datetime.utcnow() - row.measured_at > timedelta(seconds=CEILING_TTL):
        return None
    r = row.result
    return {"ceiling_p50": r.get("ceiling_p50"), "ceiling_volume": r.get("ceiling_volume"),
            "confidence": r.get("confidence")}


async def _record(db, *, user_id, blog_id, keyword, out: Dict[str, Any], error: Optional[str] = None) -> None:
    if db is None:
        return
    try:
        db.add(VerdictResult(
            user_id=user_id, blog_id=blog_id, keyword=keyword, keyword_norm=normalize_keyword(keyword),
            verdict=out.get("verdict"), probability=out.get("probability"),
            my_score=(out.get("my") or {}).get("score") if isinstance(out.get("my"), dict) else out.get("my_score"),
            cut_line=out.get("cut_line"), model_version=out.get("model_version") or load_model()["version"],
            result=out, error=error,
        ))
        await db.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning("[verdict] 결과 기록 실패: %s", e)
        with contextlib.suppress(Exception):
            await db.rollback()


def _emit(progress: Optional[Callable], done: int, total: int) -> None:
    if progress is None:
        return
    try:
        progress(done, total)
    except Exception:  # noqa: BLE001
        pass


def _difficulty_block(competitors: List[Dict[str, Any]], volume: Optional[int]) -> Dict[str, Any]:
    """11장 compute_difficulty 를 판정 결과에 얹는다 (추가 네트워크 호출 0)."""
    scored = [c for c in competitors if c.get("rank") is not None and c["rank"] <= PAGE1_CUTOFF and c.get("score")]
    if scored:
        scores = [c["score"] for c in scored]
        top10_min, top10_avg = min(scores), statistics.fmean(scores)
        median_v = statistics.median(_vitality_from_gap(c.get("recent_activity_days")) for c in scored)
    else:
        top10_min = top10_avg = median_v = None
    score, label, breakdown = seo_difficulty.compute_difficulty(
        top10_min_score=top10_min, top10_avg_score=top10_avg, median_vitality=median_v, search_volume=volume)
    return {"score": score, "label": label, "breakdown": breakdown, "version": DIFFICULTY_VERSION,
            "inputs": {"top10_min_score": None if top10_min is None else round(top10_min, 1),
                       "top10_avg_score": None if top10_avg is None else round(top10_avg, 1),
                       "median_vitality": median_v, "search_volume": volume}}


async def stage2_verdict(db, blog_id: str, keyword: str, facts: Optional[Dict[str, Any]] = None,
                         progress: Optional[Callable[[int, int], None]] = None, user_id: Optional[str] = None,
                         my: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """14-5 키워드 판정(v2) 스키마를 돌려준다. VerdictResult 에 한 행을 남긴다."""
    blog_id = normalize_blog_id(blog_id)
    keyword = (keyword or "").strip()
    t0 = time.monotonic()
    model = load_model()

    if facts is None or not facts.get("facts"):
        facts = await stage1_facts(db, blog_id, keyword)
    fx = facts.get("facts") or {}
    volume = fx.get("volume")

    # 10-8: SERP 조회 실패 → unknown (측정 실패는 '어려움'이 아니다)
    if not facts.get("ok"):
        out = {"ok": False, "blog_id": blog_id, "keyword": keyword, "facts": fx, "competitors": [], "my": None,
               "topical_posts": None, "ceiling": None, "verdict": "unknown", "probability": None,
               "confidence": "low", "reasons": [facts.get("message") or "네이버 검색 결과를 가져오지 못했습니다(일시적 차단 가능)."],
               "features": {}, "cut_line": None, "entry_bar": None, "median_score": None, "my_score": None,
               "scored_competitors": 0, "vacancy_count": 0, "model_version": model["version"],
               "difficulty": _difficulty_block([], volume),
               "elapsed": round(time.monotonic() - t0, 1), "disclaimer": DISCLAIMER_VERDICT}
        await _record(db, user_id=user_id, blog_id=blog_id, keyword=keyword, out=out, error="serp_unavailable")
        return out

    # 10-8: already_page1 → 판정 불필요. **사실이 예측을 이긴다.**
    if fx.get("already_page1"):
        my_rank = fx["my_rank"]
        out = {"ok": True, "blog_id": blog_id, "keyword": keyword, "facts": fx, "competitors": [], "my": my,
               "topical_posts": None, "ceiling": None, "verdict": "already_ranked", "probability": 1.0,
               "confidence": "high", "reasons": [f"이미 이 키워드로 블로그탭 {my_rank}위에 노출 중입니다."],
               "features": {}, "cut_line": None, "entry_bar": None, "median_score": None,
               "my_score": (my or {}).get("score"), "scored_competitors": 0, "vacancy_count": 0,
               "model_version": model["version"], "difficulty": _difficulty_block([], volume),
               "elapsed": round(time.monotonic() - t0, 1), "disclaimer": DISCLAIMER_VERDICT}
        await _record(db, user_id=user_id, blog_id=blog_id, keyword=keyword, out=out)
        return out

    rows = facts.get("rows") or []
    page1_rows = [r for r in rows if r["rank"] <= PAGE1_CUTOFF]
    competitors: List[Dict[str, Any]] = [
        {"rank": r["rank"], "blog_id": r["blog_id"], "blog_name": None, "post_title": r.get("title") or "",
         "post_url": r.get("post_url"), "score": None, "level": None, "grade": None,
         "recent_activity_days": None, "measured": False}
        for r in page1_rows
    ]
    total_units = len(competitors) + (0 if my else 1)
    done = 0
    sem = asyncio.Semaphore(SCORE_CONCURRENCY)

    def _apply(c: Dict[str, Any], res: Optional[Dict[str, Any]]) -> None:
        if res and res.get("score") is not None:
            c.update(score=res.get("score"), level=res.get("level"), grade=res.get("grade"),
                     recent_activity_days=res.get("recent_activity_days"),
                     blog_name=res.get("blog_name") or c.get("blog_name"), measured=True,
                     measured_at=res.get("measured_at"))

    async def _one(c: Dict[str, Any]) -> None:
        nonlocal done
        async with sem:
            res = await _score_blog(c["blog_id"], keyword, use_cache=True)
        _apply(c, res)
        done += 1
        _emit(progress, done, total_units)

    # ★ 내 블로그 점수는 항상 새로 잰다(use_cache=False) — my 가 넘어오면 그것을 쓴다.
    my_result: Optional[Dict[str, Any]] = my
    my_holder: Dict[str, Any] = {}

    async def _mine() -> None:
        nonlocal done
        async with sem:
            my_holder["res"] = await _score_blog(blog_id, keyword, use_cache=False)
        done += 1
        _emit(progress, done, total_units)

    tasks = [_one(c) for c in competitors]
    if my_result is None:
        tasks.append(_mine())
    topical_task = asyncio.create_task(_topical_fit(blog_id, keyword))

    async def _bounded_gather(coros, label: str) -> None:
        """예산 안에서만 기다린다. 넘으면 남은 채점을 취소하고 잰 것만으로 판정한다(측정 실패 ≠ 어려움)."""
        remain = STAGE2_BUDGET - (time.monotonic() - t0)
        if remain <= 0 or not coros:
            for c in coros:
                c.close()
            return
        group = asyncio.gather(*coros, return_exceptions=True)
        try:
            await asyncio.wait_for(group, remain)
        except asyncio.TimeoutError:
            unmeasured = [c["blog_id"] for c in competitors if not c["measured"]]
            logger.warning("[verdict] %s %s 예산(%.0fs) 초과 — 미채점 %s", keyword, label, STAGE2_BUDGET, unmeasured)

    await _bounded_gather(tasks, "1차 채점")
    if my_result is None:
        my_result = my_holder.get("res")

    # 10-8 재시도: 1차에서 못 잰 경쟁자를 **병렬**로 재시도 (내 블로그도 같이)
    missing = [c for c in competitors if not c["measured"]][:RETRY_MISSING]
    retry_tasks = [ _one(c) for c in missing ]
    if my_result is None:
        retry_tasks.append(_mine())
    if retry_tasks and (time.monotonic() - t0) + PER_BLOG_TIMEOUT > STAGE2_BUDGET:
        logger.info("[verdict] %s 예산 초과로 재시도 생략(%d건)", keyword, len(retry_tasks))
        retry_tasks = []
    if retry_tasks:
        total_units += len(retry_tasks)
        await _bounded_gather(retry_tasks, "재시도")
        if my_result is None:
            my_result = my_holder.get("res")

    topical, my_blog_name = await topical_task
    ceiling = await _ceiling_from_cache(db, blog_id)
    serp_reliable = fx.get("serp_parse_mode") == "list"

    verdict = compute_verdict(my=my_result, competitors=competitors, volume=volume, my_rank=fx.get("my_rank"),
                              topical=topical, ceiling=ceiling, serp_reliable=serp_reliable)
    # page1 사실에 채점된 blog_name 보충
    names = {c["blog_id"]: c.get("blog_name") for c in competitors}
    for p in fx.get("page1") or []:
        p["blog_name"] = p.get("blog_name") or names.get(p["blog_id"])

    my_block = None
    if my_result:
        my_block = {"score": my_result.get("score"), "level": my_result.get("level"), "grade": my_result.get("grade"),
                    "blog_name": my_result.get("blog_name") or my_blog_name,
                    "recent_activity_days": my_result.get("recent_activity_days")}

    out = {
        "ok": True,
        "blog_id": blog_id,
        "keyword": keyword,
        "facts": fx,
        "competitors": competitors,
        "my": my_block,
        "topical_posts": topical,
        "ceiling": ceiling,
        **verdict,
        "difficulty": _difficulty_block(competitors, volume),
        "elapsed": round(time.monotonic() - t0, 1),
        "disclaimer": DISCLAIMER_VERDICT,
    }
    await _record(db, user_id=user_id, blog_id=blog_id, keyword=keyword, out=out,
                  error=None if verdict.get("verdict") != "unknown" else "unknown")
    return out
