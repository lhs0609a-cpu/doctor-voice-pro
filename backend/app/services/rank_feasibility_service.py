"""
상위노출 가능성 판정 서비스 (작성 '전' 키워드 난이도).

dia_crank_analyzer(작성완료 글 SEO 자가진단, LLM 주관 채점)와는 목적이 다르다.
여기서는 아직 '내 글'이 없는 상태에서, 키워드별로:
  - 상위글 실측 지표(top_post_analyzer.analyze_top_posts 의 summary)
  - 검색광고 경쟁도/검색량(search_volume_service)
를 결합해 결정론적(LLM 미사용) 난이도 점수와 목표 프로필을 낸다.

difficulty_score: 0~100, 낮을수록 노려볼 만함(유망).
"""
import asyncio
import logging
import math
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import search_volume_service
from app.services.top_post_analyzer import (
    analyze_top_posts,
    calculate_keyword_density,
)

logger = logging.getLogger(__name__)

# 동시 크롤 제한(네이버 차단/부하 완충)
_SEM = asyncio.Semaphore(3)

_COMP_WEIGHT = {"low": 20.0, "mid": 55.0, "high": 90.0}


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _content_bar_score(summary: Optional[Dict]) -> float:
    """상위글이 세워놓은 '콘텐츠 벽'의 높이(0~100). 높을수록 넘기 어렵다."""
    if not summary:
        return 50.0  # 데이터 없음 → 중립
    content = summary.get("content", {})
    media = summary.get("media", {})
    avg_len = content.get("avg_length", 0) or 0
    avg_img = media.get("avg_images", 0) or 0
    avg_head = content.get("avg_headings", 0) or 0

    # 각 지표를 경험적 상한으로 정규화(0~100)
    len_score = _clamp(avg_len / 2500 * 100)     # 2500자 이상이면 만점
    img_score = _clamp(avg_img / 15 * 100)       # 이미지 15장 이상이면 만점
    head_score = _clamp(avg_head / 8 * 100)      # 소제목 8개 이상이면 만점
    return 0.5 * len_score + 0.3 * img_score + 0.2 * head_score


def _build_target(summary: Optional[Dict]) -> Dict:
    """상위글을 살짝 상회하는 목표 프로필."""
    if not summary:
        # 데이터 없으면 무난한 기본치
        return {
            "content_length": 1500,
            "image_count": 8,
            "heading_count": 4,
            "keyword_density": 1.0,
        }
    content = summary.get("content", {})
    media = summary.get("media", {})
    avg_len = content.get("avg_length", 0) or 0
    avg_img = media.get("avg_images", 0) or 0
    avg_head = content.get("avg_headings", 0) or 0
    avg_density = content.get("avg_keyword_density", 0) or 0
    return {
        # 상위 평균보다 10% 길게(최소 1200자)
        "content_length": max(1200, round(avg_len * 1.1)),
        # 이미지/소제목은 평균보다 1 더
        "image_count": max(5, math.ceil(avg_img) + 1),
        "heading_count": max(3, math.ceil(avg_head)),
        # 밀도는 과하지 않게 상위 평균 수준 유지(0.8~2.0 클램프)
        "keyword_density": round(min(2.0, max(0.8, avg_density or 1.0)), 2),
    }


def _verdict(difficulty: float, total_volume: int) -> tuple[str, str]:
    """난이도 + 검색량 → 판정/사유."""
    if difficulty < 40:
        if total_volume >= 500:
            return "유망", "검색량이 있고 경쟁 벽이 낮아 상위노출을 노려볼 만합니다."
        if total_volume > 0:
            return "유망", "경쟁이 낮은 롱테일 키워드입니다. 꾸준히 쌓으면 유리합니다."
        return "유망", "경쟁 벽은 낮으나 검색량 데이터가 부족합니다."
    if difficulty < 70:
        return "보통", "경쟁이 중간 수준입니다. 상위글 기준을 확실히 넘기면 가능합니다."
    return "레드오션", "상위글 품질과 경쟁도가 높아 진입 난이도가 큽니다."


async def _assess_one(
    keyword: str, volume: int, competition: str, top_n: int = 3
) -> Dict:
    """
    검색량/경쟁도가 이미 주어진 상태에서 상위글만 크롤해 판정.
    DB를 건드리지 않으므로 동시 실행에 안전하다(크롤 동시성은 _SEM으로 제한).
    """
    # 상위글 실측(크롤). db=None으로 호출해 저장 부작용 회피(가능성 판정은 읽기 목적).
    summary = None
    analyzed_count = 0
    async with _SEM:
        try:
            top = await analyze_top_posts(keyword, top_n=top_n, db=None)
            summary = top.get("summary")
            analyzed_count = top.get("analyzed_count", 0)
        except Exception as e:  # noqa: BLE001
            logger.warning("[가능성] 상위글 분석 실패(%s): %s", keyword, e)

    # 난이도 = 경쟁도(0.55) + 콘텐츠 벽(0.45)
    comp_score = _COMP_WEIGHT.get(competition, 55.0)
    bar_score = _content_bar_score(summary)
    difficulty = round(_clamp(0.55 * comp_score + 0.45 * bar_score), 1)

    verdict, reason = _verdict(difficulty, volume)
    if analyzed_count == 0:
        reason = "상위글을 읽지 못해(네이버 차단 가능) 경쟁도만으로 추정한 값입니다. " + reason

    return {
        "keyword": keyword,
        "search_volume": volume,
        "competition": competition,
        "difficulty_score": difficulty,
        "verdict": verdict,
        "reason": reason,
        "target": _build_target(summary),
        "analyzed_count": analyzed_count,
        "top_summary": summary,
    }


async def assess_keyword_feasibility(
    db: Optional[AsyncSession], keyword: str, top_n: int = 3
) -> Dict:
    """키워드 1개 판정(검색량 조회 포함). 단건 호출용."""
    keyword = (keyword or "").strip()
    if not keyword:
        return {}
    volume, competition = 0, "mid"
    try:
        if db is not None:
            metrics = await search_volume_service.get_keyword_metrics(db, [keyword])
            if metrics:
                volume = metrics[0]["total_volume"]
                competition = metrics[0]["competition"]
    except Exception as e:  # noqa: BLE001
        logger.warning("[가능성] 검색량 조회 실패(%s): %s", keyword, e)
    return await _assess_one(keyword, volume, competition, top_n=top_n)


async def assess_keywords(
    db: Optional[AsyncSession], keywords: List[str], top_n: int = 3
) -> List[Dict]:
    """
    여러 키워드 판정.
    - 검색량은 DB 세션으로 '한 번에' 배치 조회(세션 동시 사용 금지 준수).
    - 상위글 크롤만 동시 실행(_SEM으로 동시성 제한, DB 미접근).
    """
    clean = [k.strip() for k in keywords if k and k.strip()][:30]
    if not clean:
        return []

    # 1) 검색량/경쟁도 배치 조회 (세션은 여기서만, 순차)
    vol_map: Dict[str, Dict] = {}
    try:
        if db is not None:
            metrics = await search_volume_service.get_keyword_metrics(db, clean)
            for m in metrics:
                vol_map[search_volume_service._normalize(m["keyword"])] = m
    except Exception as e:  # noqa: BLE001
        logger.warning("[가능성] 검색량 배치 조회 실패: %s", e)

    # 2) 크롤 판정 동시 실행 (DB 미접근이라 안전)
    def _vc(k: str) -> tuple[int, str]:
        m = vol_map.get(search_volume_service._normalize(k))
        return (m["total_volume"], m["competition"]) if m else (0, "mid")

    tasks = [_assess_one(k, *_vc(k), top_n=top_n) for k in clean]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out: List[Dict] = []
    for k, r in zip(clean, results):
        if isinstance(r, Exception):
            logger.error("[가능성] %s 판정 예외: %s", k, r)
            continue
        if r:
            out.append(r)
    return out


def score_my_post_against_top(
    my_title: str, my_content: str, keyword: str, summary: Optional[Dict]
) -> Dict:
    """
    (선택) 작성 완료 글이 상위권 기준을 얼마나 충족하는지 로컬 측정(크롤 불필요).
    반환: {feasibility_pct(0~100), gaps: [...], my: {...}}
    """
    my_len = len(my_content or "")
    kw_count, kw_density = calculate_keyword_density(my_content or "", keyword)
    my_headings = (my_content or "").count("\n#") + (my_content or "").count("<h")

    if not summary:
        return {
            "feasibility_pct": 60,
            "gaps": ["상위글 데이터가 없어 절대 기준으로만 평가했습니다."],
            "my": {"content_length": my_len, "keyword_density": kw_density},
        }

    content = summary.get("content", {})
    target_len = content.get("avg_length", 1500) or 1500
    target_density = content.get("avg_keyword_density", 1.0) or 1.0

    gaps: List[str] = []
    score = 100.0
    if my_len < target_len * 0.9:
        deficit = 1 - my_len / max(1, target_len)
        score -= min(35, deficit * 60)
        gaps.append(f"본문이 상위 평균({round(target_len)}자)보다 짧습니다.")
    if kw_density < target_density * 0.5:
        score -= 15
        gaps.append("키워드 밀도가 낮습니다.")
    elif kw_density > target_density * 2:
        score -= 10
        gaps.append("키워드가 과다 반복(스팸 위험)입니다.")

    return {
        "feasibility_pct": round(_clamp(score)),
        "gaps": gaps,
        "my": {
            "content_length": my_len,
            "keyword_count": kw_count,
            "keyword_density": kw_density,
            "heading_count": my_headings,
        },
    }
