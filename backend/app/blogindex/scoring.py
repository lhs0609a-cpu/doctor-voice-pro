"""
블로그 지수 채점 (문서 2장 — SCORING_VERSION 6), 레벨 판정(4장), 포스트 점수(6장).

정직성 규칙(2-9, 14-3):
  · 측정 못 한 값을 지어내지 않는다. None + unmeasured 로 남긴다.
  · 차원을 못 재면 0으로 깔지 말고 정규화에서 제외하되 measurement_complete=False 로 남긴다.
  · 활동성은 곱셈이다.
  · 0은 유효한 측정값이다. `if value:` 가 아니라 `is not None`.
  · 채점식을 바꾸면 SCORING_VERSION 을 올린다.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select

from app.blogindex import SCORING_VERSION

logger = logging.getLogger(__name__)

__all__ = [
    "SCORING_VERSION", "compute_blog_index", "_LEVEL_CUTS", "get_blog_level_from_score",
    "get_level_from_percentile", "level_category", "MIN_POPULATION_FOR_PERCENTILE",
    "add_score_sample", "get_percentile", "calculate_post_score",
]


# ══════════════════════════════════════════════════════════════════════════════
# 2-11. 참조 구현 — compute_blog_index (원본 그대로)
# ══════════════════════════════════════════════════════════════════════════════
def compute_blog_index(stats: Dict[str, Any], a: Dict[str, Any], data_sources: List[str],
                       W: Dict[str, Any]) -> Dict[str, Any]:
    """stats/a(analysis_data)/data_sources/W(=resolve_scoring_weights 결과) → index dict

    stats = {total_posts, neighbor_count, total_visitors, daily_visitors,
             recent_avg_visitors, visitor_measured}
    """
    stats = stats or {}
    a = a or {}
    data_sources = list(data_sources or [])
    W = W or {}

    # ── C-Rank ────────────────────────────────────────────────
    # Context Score — 주제 집중도. 기본 50.
    #   normalized 0(완벽 집중)=95점, 1(완전 분산)=35점 선형
    context_score = 50
    entropy = a.get("category_entropy"); cats = a.get("category_count") or 0
    if entropy is not None and cats > 0:
        max_entropy = math.log2(cats) if cats > 1 else 1.0
        normalized = entropy / max_entropy if max_entropy > 0 else 0
        context_score = max(35, min(95, round(95 - normalized * 60)))
    elif cats > 0:
        # 폴백, 카테고리 개수 휴리스틱
        context_score = 90 if cats <= 3 else 75 if cats <= 5 else 60 if cats <= 10 else 40

    # Content Score — 길이+이미지+단어수+구조
    avg_len = a.get("avg_post_length") or 0
    if 0 < avg_len < 500:
        # ★ 보정: RSS description은 요약이라 실제 본문의 약 1/7 수준으로 짧게 온다
        avg_len = avg_len * 7
    length_score = (95 if avg_len >= 3000 else 85 if avg_len >= 2000 else
                    75 if avg_len >= 1500 else 65 if avg_len >= 1000 else
                    50 if avg_len >= 500 else 35)
    # img_bonus (풀파싱 avg_images 우선, 없으면 RSS avg_image_count)
    avg_imgs = a.get("fullparse_avg_images") or a.get("avg_image_count") or 0
    img_bonus = 15 if avg_imgs >= 10 else 10 if avg_imgs >= 5 else 5 if avg_imgs >= 2 else 0
    avg_words = a.get("avg_word_count") or 0
    word_bonus = 10 if avg_words >= 200 else 5 if avg_words >= 100 else 0
    avg_h = a.get("fullparse_avg_headings") or 0
    avg_p = a.get("fullparse_avg_paragraphs") or 0
    struct_bonus = 8 if (avg_h >= 3 or avg_p >= 8) else 4 if (avg_h >= 1 or avg_p >= 4) else 0
    content_score = min(100, length_score + img_bonus + word_bonus + struct_bonus)

    # Chain Score — 연결성/참여 연쇄. 기본 50.
    chain_score = 50
    al, ac = a.get("fullparse_avg_likes"), a.get("fullparse_avg_comments")
    if al is not None or ac is not None:
        # 풀파싱 공감/댓글 (진짜 신호 우선). 댓글이 더 강한 신호
        e = (al or 0) + (ac or 0) * 2
        chain_score = (95 if e >= 100 else 85 if e >= 50 else 75 if e >= 25 else
                       65 if e >= 10 else 55 if e >= 5 else 45 if e >= 1 else 30)
    elif stats.get("neighbor_count"):
        # 폴백: 이웃 수
        n = stats["neighbor_count"]
        chain_score = (95 if n >= 5000 else 85 if n >= 2000 else 75 if n >= 1000 else
                       65 if n >= 500 else 55 if n >= 200 else 45 if n >= 100 else 35)

    # C-Rank 결합 — 기본값 context 0.40 / content 0.50 / chain 0.10
    #   근거: B 검증(n=67) context ρ=+0.134, content ρ=+0.153, chain ρ=-0.045
    cs = (W.get('c_rank') or {}).get('sub_weights', {})
    ctx_w = cs.get('context', 0.40); cnt_w = cs.get('content', 0.50); chn_w = cs.get('chain', 0.10)
    c_rank_score = context_score*ctx_w + content_score*cnt_w + chain_score*chn_w

    # ── D.I.A. ────────────────────────────────────────────────
    # Depth — 총 발행량. total_posts 가 None 이면 50 (중립, 지어내지 않음).
    depth_score = 50
    if stats.get("total_posts") is not None:
        p = stats["total_posts"]
        depth_score = (95 if p >= 2000 else 85 if p >= 1000 else 75 if p >= 500 else
                       65 if p >= 200 else 55 if p >= 100 else 45 if p >= 50 else 35)

    # Information — 최근성 + 발행 꾸준함
    ra = a.get("recent_activity")
    if ra is not None:
        d = ra
        recency = (95 if d <= 1 else 85 if d <= 3 else 75 if d <= 7 else 65 if d <= 14 else
                   50 if d <= 30 else 38 if d <= 60 else 28 if d <= 90 else
                   18 if d <= 180 else 10 if d <= 365 else 5)
    else:
        recency = 50  # 측정 불가 시 50
    iv = a.get("posting_interval_days")
    if iv is not None:
        ivs = 95 if iv <= 3 else 80 if iv <= 7 else 65 if iv <= 14 else 45 if iv <= 30 else 25
        info_score = round(recency * 0.7 + ivs * 0.3)
    else:
        info_score = recency

    # Accuracy — 트래픽 신뢰도
    #   우선순위 1: 실측 일별 방문자(NVisitorgp). dv = recent_avg or daily
    #   우선순위 2: 스크랩된 누적 방문자 (반드시 "scrape" 소스일 때만)
    #   그 외: 중립 50 유지. ★ 조작값(해시 시드 가짜 방문자)으로 점수를 부풀리지 않는다.
    accuracy_score = 50
    if stats.get("visitor_measured") and stats.get("daily_visitors") is not None:
        dv = stats.get("recent_avg_visitors") or stats["daily_visitors"]
        accuracy_score = (95 if dv >= 3000 else 85 if dv >= 1000 else 75 if dv >= 500 else
                          65 if dv >= 200 else 55 if dv >= 100 else 45 if dv >= 30 else
                          35 if dv >= 10 else 25)
    elif stats.get("total_visitors") and "scrape" in data_sources:
        v = stats["total_visitors"]
        accuracy_score = (95 if v >= 10_000_000 else 88 if v >= 5_000_000 else
                          80 if v >= 1_000_000 else 70 if v >= 500_000 else
                          60 if v >= 100_000 else 50 if v >= 50_000 else
                          40 if v >= 10_000 else 30)

    # D.I.A. 결합 — 기본값 depth 0.20 / information 0.50 / accuracy 0.30
    #   근거: B 검증(n=67) ρ — depth +0.022, information -0.090, accuracy -0.054
    ds = (W.get('dia') or {}).get('sub_weights', {})
    dw = ds.get('depth', 0.20); iw = ds.get('information', 0.50); aw = ds.get('accuracy', 0.30)
    dia_score = depth_score*dw + info_score*iw + accuracy_score*aw

    # ── Content factors ───────────────────────────────────────
    # ★ 이 축은 예전 코드에서 계산 자체를 하지 않아 총점 상한이 56점에 묶였다. 반드시 살릴 것.
    #   키워드 의존 항목(keyword_count/keyword_density/title_keyword)은 블로그 단위 분석에서
    #   측정 불가 → 측정 가능한 항목만 쓰고 그 하위 가중치로 재정규화한다.
    cf_sub = (W.get('content_factors') or {}).get('sub_weights', {}) or {}
    parts, detail = [], {}

    cf_len = a.get("fullparse_avg_content_length") or avg_len
    if cf_len:
        s = (95 if cf_len >= 3000 else 85 if cf_len >= 2000 else 75 if cf_len >= 1500 else
             65 if cf_len >= 1000 else 50 if cf_len >= 500 else 35)
        parts.append((s, cf_sub.get('content_length', 0.32)))
        detail['content_length'] = {'score': s, 'raw': round(cf_len)}
    if a.get("fullparse_avg_headings") is not None:
        h = a["fullparse_avg_headings"]; s = min(95, 30 + h * 15)
        parts.append((s, cf_sub.get('heading_count', 0.05)))
        detail['heading_count'] = {'score': round(s, 1), 'raw': round(h, 1)}
    if a.get("fullparse_avg_paragraphs") is not None:
        p = a["fullparse_avg_paragraphs"]; s = min(95, 25 + p * 7)
        parts.append((s, cf_sub.get('paragraph_count', 0.05)))
        detail['paragraph_count'] = {'score': round(s, 1), 'raw': round(p, 1)}
    ci = a.get("fullparse_avg_images")
    if ci is None: ci = a.get("avg_image_count")
    if ci is not None:
        s = min(95, 30 + ci * 8)
        parts.append((s, cf_sub.get('image_count', 0.05)))
        detail['image_count'] = {'score': round(s, 1), 'raw': round(ci, 1)}
    if a.get("recent_activity") is not None:
        # freshness — recency와 같은 신호지만 다른 차원
        d = a["recent_activity"]
        s = 95 if d <= 3 else 85 if d <= 7 else 70 if d <= 14 else 55 if d <= 30 else 35 if d <= 90 else 15
        parts.append((s, cf_sub.get('freshness', 0.16)))
        detail['freshness'] = {'score': s, 'raw': d}

    if parts:
        wsum = sum(w for _, w in parts)
        cf_score = (sum(s*w for s, w in parts)/wsum) if wsum > 0 else (sum(s for s, _ in parts)/len(parts))
    else:
        cf_score = None  # 하나도 못 재면 None → 총점 정규화에서 아예 제외 (0점으로 깔지 않는다)

    # ── 결합 ──────────────────────────────────────────────────
    # 기본 주가중치: c_rank 0.30 / dia 0.20 / content_factors 0.50
    #   근거: c_rank ρ=+0.032, dia ρ=+0.015, content_factors(외부 실측 raw)가 둘보다 큼.
    c_w  = (W.get('c_rank') or {}).get('weight', 0.30)
    d_w  = (W.get('dia') or {}).get('weight', 0.20)
    ct_w = (W.get('content_factors') or {}).get('weight', 0.50)
    ef   = W.get('extra_factors') or {'post_count':0.05,'neighbor_count':0.03,'visitor_count':0.02}

    dims = [(c_rank_score, c_w), (dia_score, d_w)]
    unmeasured_dims = []
    if cf_score is not None:
        dims.append((cf_score, ct_w))
    else:
        unmeasured_dims.append("content_factors")

    # ⚠️ 재정규화는 "0점 처리"보다 나을 뿐, 같은 자가 되지는 않는다.
    #    3개 차원으로 잰 점수와 2개 차원으로 잰 점수는 다른 측정이다.
    #    → measurement_complete 플래그를 보고 시계열에서 불완전 측정을 걸러야 한다.
    weight_sum = sum(w for _, w in dims) or 1.0
    base = sum(s*w for s, w in dims) / weight_sum

    # 2-5. extra_bonus (가산점) — 코드 폴백 기본은 0.15/0.10/0.05 (원본 그대로)
    extra = 0.0
    if stats.get("total_posts"):
        extra += min(stats["total_posts"]/1000, 1.0) * ef.get('post_count', 0.15) * 20
    if stats.get("neighbor_count"):
        extra += min(stats["neighbor_count"]/1000, 1.0) * ef.get('neighbor_count', 0.10) * 20
    if stats.get("visitor_measured") and stats.get("daily_visitors") is not None:
        dv = stats.get("recent_avg_visitors") or stats["daily_visitors"]
        extra += min(dv/1000, 1.0) * ef.get('visitor_count', 0.05) * 20
    elif stats.get("total_visitors") and "scrape" in data_sources:
        extra += min(stats["total_visitors"]/1_000_000, 1.0) * ef.get('visitor_count', 0.05) * 20

    total = base + extra
    # 2-6. 데이터 소스 신뢰도 보정
    if not data_sources:
        total = 25                 # 소스 없음 → 25 고정
    elif "scrape" in data_sources:
        pass                       # 패널티 없음
    elif len(data_sources) == 1:
        total = total * 0.9        # 소스가 정확히 1개(=rss만) → 10% 패널티

    # ── vitality (곱셈) ───────────────────────────────────────
    # 2-7. 방치된 블로그는 "점수가 조금 낮은 좋은 블로그"가 아니라 범주가 다르다.
    #   ⚠️ 이 구간표는 업계 표준이 아니라 자체 휴리스틱이다.
    days_idle = a.get("recent_activity")
    if days_idle is None:      vit, state = 1.0, "unknown"      # RSS를 못 읽음. 감점하지 않고 중립.
    elif days_idle <= 7:       vit, state = 1.0, "active"
    elif days_idle <= 30:      vit, state = 0.95, "active"
    elif days_idle <= 60:      vit, state = 0.82, "slowing"
    elif days_idle <= 90:      vit, state = 0.65, "dormant_entering"
    elif days_idle <= 180:     vit, state = 0.42, "dormant"
    elif days_idle <= 365:     vit, state = 0.25, "stopped"
    else:                      vit, state = 0.15, "abandoned"

    # 발행량 보정 — ※ RSS 50개 캡에 걸린(=고빈도 발행) 블로그는 과소측정이므로 면제.
    if (state in ("active", "slowing") and not a.get("rss_truncated")
            and a.get("posts_last_90d") is not None):
        p90 = a["posts_last_90d"]
        if p90 <= 1:   vit *= 0.75
        elif p90 <= 3: vit *= 0.88
    # 덤프 발행 감쇠
    b = a.get("posting_burstiness")
    if b is not None and b >= 1.5 and state != "active":
        vit *= 0.9
    vit = round(max(vit, 0.10), 3)

    total = total * vit

    # 2-10. 검산용 부가 정보 (weights_used / keyword_category / raw_signals)
    weights_used = {
        "c_rank": round(c_w, 3),
        "dia": round(d_w, 3),
        "content": round(ct_w, 3),
        "is_learned": bool(W.get("_learned", False)),
        "learned_meta": W.get("_learned_meta") or {},
        "scoring_version": SCORING_VERSION,
    }
    raw_signals = {
        "total_posts": stats.get("total_posts"),
        "neighbor_count": stats.get("neighbor_count"),
        "total_visitors": stats.get("total_visitors"),
        "daily_visitors": stats.get("daily_visitors"),
        "recent_avg_visitors": stats.get("recent_avg_visitors"),
        "visitor_measured": bool(stats.get("visitor_measured")),
        "avg_post_length": a.get("avg_post_length"),
        "avg_post_length_adjusted": avg_len,
        "avg_image_count": a.get("avg_image_count"),
        "avg_word_count": a.get("avg_word_count"),
        "category_count": a.get("category_count"),
        "category_entropy": a.get("category_entropy"),
        "recent_activity": a.get("recent_activity"),
        "posting_interval_days": a.get("posting_interval_days"),
        "posting_burstiness": a.get("posting_burstiness"),
        "posts_last_90d": a.get("posts_last_90d"),
        "rss_window_days": a.get("rss_window_days"),
        "rss_truncated": a.get("rss_truncated"),
        "fullparse_avg_content_length": a.get("fullparse_avg_content_length"),
        "fullparse_avg_images": a.get("fullparse_avg_images"),
        "fullparse_avg_headings": a.get("fullparse_avg_headings"),
        "fullparse_avg_paragraphs": a.get("fullparse_avg_paragraphs"),
        "fullparse_avg_likes": a.get("fullparse_avg_likes"),
        "fullparse_avg_comments": a.get("fullparse_avg_comments"),
        "fullparse_sample_size": a.get("fullparse_sample_size"),
        "data_sources": data_sources,
    }

    return {
        "total_score": min(round(total, 1), 100),
        "vitality": vit, "vitality_state": state,
        "days_since_last_post": days_idle,
        "posts_last_90d": a.get("posts_last_90d"),
        "rss_truncated": bool(a.get("rss_truncated")),
        "unmeasured_dimensions": unmeasured_dims,
        "measurement_complete": not unmeasured_dims,
        "extra_bonus": round(extra, 1),
        "breakdown": {
            "c_rank": round(c_rank_score * c_w / weight_sum, 1),
            "dia": round(dia_score * d_w / weight_sum, 1),
            "content_factors": (round(cf_score * ct_w / weight_sum, 1)
                                if cf_score is not None else None),
            "c_rank_detail": {"context": round(context_score,1),
                              "content": round(content_score,1),
                              "chain": round(chain_score,1)},
            "dia_detail": {"depth": round(depth_score,1),
                           "information": round(info_score,1),
                           "accuracy": round(accuracy_score,1)},
            "content_detail": detail,
            "weights_used": weights_used,
            "keyword_category": W.get("_category") or "default",
            "raw_signals": raw_signals,
            "extra_bonus": round(extra, 1),
            "vitality": vit,
            "vitality_state": state,
            "days_since_last_post": days_idle,
            "posts_last_90d": a.get("posts_last_90d"),
            "rss_truncated": bool(a.get("rss_truncated")),
            "unmeasured_dimensions": unmeasured_dims,
            "measurement_complete": not unmeasured_dims,
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# 4. 레벨 판정 체계 — 15단계: 일반(1) / 준최1~7(2~8) / 최적1~3(9~11) / 최적1+~4+(12~15)
# ══════════════════════════════════════════════════════════════════════════════
# 4-1. 백분위는 '같은 자로 잰' 실측 모집단이 충분할 때만 쓴다.
#   ★ 예전에는 가상 블로그 10만 개를 심어 백분위를 냈다 → 어떤 블로그를 넣어도 하위 5%
#     "준최1". 시드 재생성은 폐기. 실측만으로 모집단을 만든다.
MIN_POPULATION_FOR_PERCENTILE = 300

# 4-3. 절대 기준표 (모집단 부족 시) ★ 실측 분포에서 뽑은 값
#   근거: 2026-08-03, 네이버 블로그 검색(32개 주제 × 상위글) 실제 블로그 420개를
#   SCORING_VERSION=5 로 채점한 분포의 분위수. min 6.4 / 중앙값 76.2 / max 90.2
#   ⚠️ 모집단은 "검색에 노출되는 블로그"다(방치 블로그 22% 포함). 전체 평균이 아니다.
#   ⚠️ 상단 구간이 좁다: 최적1(83.6)~최적4+(89.9) 6.3점에 7개 레벨 — 1점 차이가 2~3레벨.
_LEVEL_CUTS: List[Tuple[float, int, str]] = [
    (89.9, 15, "최적4+"),
    (89.3, 14, "최적3+"),
    (87.9, 13, "최적2+"),
    (86.3, 12, "최적1+"),
    (85.3, 11, "최적3"),
    (84.4, 10, "최적2"),
    (83.6,  9, "최적1"),
    (82.2,  8, "준최7"),
    (80.4,  7, "준최6"),
    (76.2,  6, "준최5"),
    (72.7,  5, "준최4"),
    (46.3,  4, "준최3"),
    (13.9,  3, "준최2"),
    ( 7.6,  2, "준최1"),
]


def get_blog_level_from_score(score: float) -> Tuple[int, str]:
    """4-3. 절대 기준표 → (level, grade)."""
    for cut, level, grade in _LEVEL_CUTS:
        if score >= cut:
            return level, grade
    return 1, "일반"


def get_level_from_percentile(percentile: float) -> Tuple[int, str]:
    """4-2. 백분위 → 레벨 (모집단 충분할 때)."""
    if percentile >= 99.5: return (15, "최적4+")   # 상위 0.5%
    if percentile >= 98.5: return (14, "최적3+")   # 상위 1.5%
    if percentile >= 97.0: return (13, "최적2+")   # 상위 3%
    if percentile >= 95.0: return (12, "최적1+")   # 상위 5%
    if percentile >= 92.0: return (11, "최적3")    # 상위 8%
    if percentile >= 88.0: return (10, "최적2")    # 상위 12%
    if percentile >= 83.0: return ( 9, "최적1")    # 상위 17%  ← 네이버 Lv.4 시작
    if percentile >= 75.0: return ( 8, "준최7")    # 상위 25%
    if percentile >= 65.0: return ( 7, "준최6")    # 상위 35%
    if percentile >= 50.0: return ( 6, "준최5")    # 상위 50%  ← 네이버 Lv.3 중심
    if percentile >= 40.0: return ( 5, "준최4")    # 상위 60%
    if percentile >= 25.0: return ( 4, "준최3")    # 상위 75%
    if percentile >= 10.0: return ( 3, "준최2")    # 상위 90%
    if percentile >=  3.0: return ( 2, "준최1")    # 상위 97%
    return (1, "일반")                              # 하위 3%   ← 네이버 Lv.1 영역


def level_category(level: Optional[int]) -> str:
    if level is None:
        return "측정 불가"
    if level >= 12: return "최적+"
    if level >= 9:  return "최적"
    if level >= 2:  return "준최"
    return "일반"


async def add_score_sample(db, blog_id: str, score: float) -> None:
    """4-1 (1) 모집단에 기여. 같은 SCORING_VERSION 으로 스탬프. (자기 세션으로 짧게 커밋)"""
    from app.models.blog_index import BlogScoreSample
    from app.blogindex.dbwrite import isolated_write
    if score is None:
        return

    async def _do(s):
        s.add(BlogScoreSample(blog_id=blog_id, score=float(score), scoring_version=SCORING_VERSION, is_seed=False))

    await isolated_write(_do, what=f"score sample {blog_id}")


async def get_percentile(db, score: float) -> Optional[float]:
    """4-1 (2) 백분위.
    - 같은 SCORING_VERSION, is_seed=False 인 행만 모집단
    - 모집단 < 300 이면 None 을 돌려준다 (지어낸 50.0 금지)
    - percentile = (해당 점수 미만 개수 / 전체) * 100
    """
    from app.models.blog_index import BlogScoreSample
    if score is None:
        return None
    base = (select(func.count(BlogScoreSample.id))
            .where(BlogScoreSample.scoring_version == SCORING_VERSION)
            .where(BlogScoreSample.is_seed == False))  # noqa: E712
    total = (await db.execute(base)).scalar() or 0
    if total < MIN_POPULATION_FOR_PERCENTILE:
        return None
    below = (await db.execute(base.where(BlogScoreSample.score < float(score)))).scalar() or 0
    return round(below / total * 100, 2)


# ══════════════════════════════════════════════════════════════════════════════
# 6. 포스트 단위 점수 (calculate_post_score) — D.I.A.+ 모방 6신호
#   블로그 평균 점수가 SERP 순위와 거의 무관(ρ≈0.04)하다는 검증 결과에 따라
#   문서 단위 평가로 전환한 것. 각 신호 0~100, 종합은 단순 평균(1/6씩).
# ══════════════════════════════════════════════════════════════════════════════
def calculate_post_score(p: Dict[str, Any]) -> Dict[str, Any]:
    p = p or {}
    # 1. title_match — 제목 키워드 포함 + 위치
    if p.get("title_has_keyword"):
        pos = p.get("title_keyword_position", -1)
        title_score = 95 if pos == 0 else 75 if pos == 1 else 60 if pos == 2 else 50
    else:
        title_score = 20

    # 2. keyword_density — 1.5~3% 적정(네이버 권장). density는 1000자당 횟수
    density_pct = (p.get("keyword_density", 0) or 0) / 10
    if 1.5 <= density_pct <= 3.0:                              density_score = 95
    elif 1.0 <= density_pct < 1.5 or 3.0 < density_pct <= 4.0: density_score = 80
    elif 0.5 <= density_pct < 1.0 or 4.0 < density_pct <= 6.0: density_score = 60
    elif density_pct > 0:                                      density_score = 40
    else:                                                      density_score = 20

    # 3. content_richness — 길이 + 이미지 + 동영상
    length = p.get("content_length", 0) or 0
    len_part = (50 if length >= 3000 else 40 if length >= 2000 else
                30 if length >= 1000 else 20 if length >= 500 else 10)
    img_part = min(30, (p.get("image_count", 0) or 0) * 3)     # 장당 +3, 최대 30
    vid_part = min(20, (p.get("video_count", 0) or 0) * 10)    # 개당 +10, 최대 20
    richness_score = min(100, len_part + img_part + vid_part)

    # 4. structural — 문단*2 + 소제목*5
    structure_raw = (p.get("paragraph_count",0) or 0)*2 + (p.get("heading_count",0) or 0)*5
    structural_score = (95 if structure_raw >= 50 else 80 if structure_raw >= 30 else
                        65 if structure_raw >= 15 else 45 if structure_raw >= 5 else 25)

    # 5. engagement — 공감 + 댓글*2
    e = (p.get("like_count",0) or 0) + (p.get("comment_count",0) or 0) * 2
    engagement_score = (95 if e >= 100 else 85 if e >= 50 else 75 if e >= 25 else
                        60 if e >= 10 else 45 if e >= 3 else 35 if e >= 1 else 25)

    # 6. freshness
    age = p.get("post_age_days")
    if age is None:      freshness_score = 50
    elif age <= 7:       freshness_score = 95
    elif age <= 30:      freshness_score = 85
    elif age <= 90:      freshness_score = 70
    elif age <= 180:     freshness_score = 55
    elif age <= 365:     freshness_score = 40
    else:                freshness_score = 25

    total = round((title_score + density_score + richness_score
                   + structural_score + engagement_score + freshness_score) / 6, 1)
    return {"total": total, "title_match": title_score, "keyword_density": density_score,
            "content_richness": richness_score, "structural": structural_score,
            "engagement": engagement_score, "freshness": freshness_score}
