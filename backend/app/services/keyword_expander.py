"""
키워드 확장: 지역 × 질환 조합 + 검색광고 연관키워드 + 검색량 필터.

마케터의 실제 규칙(인터뷰):
  - 네이버 검색광고 모바일 검색량 기준, 지역 키워드 20 이상 / 전국 키워드 100 이상
  - 지역+질환 조합을 찾는 데 가장 시간이 오래 걸린다 → 여기서 자동으로 만든다

흐름
  seeds(원장 제안·직접 입력) + combine(regions×diseases×suffix)
  → 검색광고 API(5개씩, 캐시 우선) → 연관키워드까지 수집
  → 지역/전국 판정 → 하한 필터 → 중복 제거 → CampaignKeyword 후보 목록
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import search_volume_service as svs

logger = logging.getLogger(__name__)

try:
    from app.services import region_dictionary as rd
except Exception:  # noqa: BLE001  (모듈이 아직 없을 때도 앱은 떠야 한다)
    rd = None  # type: ignore


DEFAULT_SUFFIXES = ["", "한의원", "병원", "치료", "잘하는곳"]


def _norm(k: str) -> str:
    return svs._normalize(k)


def expand_regions(regions: Sequence[str], level: int = 1, limit_per_region: int = 30) -> List[str]:
    """입력 지역들을 사전으로 확장. 사전이 없으면 입력 그대로."""
    out: List[str] = []
    seen = set()
    for r in regions:
        r = (r or "").strip()
        if not r:
            continue
        names = [r]
        if rd is not None:
            try:
                names = rd.expand_region(r, level=level, limit=limit_per_region)
            except Exception as e:  # noqa: BLE001
                logger.warning("[확장] 지역 사전 오류(%s): %s", r, e)
        for n in names:
            key = _norm(n)
            if key and key not in seen:
                seen.add(key)
                out.append(n)
    return out


def combine(regions: Sequence[str], diseases: Sequence[str], suffixes: Optional[Sequence[str]] = None, max_items: int = 600) -> List[Dict]:
    """지역×질환×접미어 조합. [{keyword, region, disease, suffix}]

    순서가 중요하다: 상한(max_items)에 걸려 잘릴 때 '접미어 없는 기본형'이 모든 지역·질환에
    대해 먼저 들어가야 한다. 지역 우선으로 돌리면 앞쪽 지역의 '치료/잘하는곳' 변형이
    뒤쪽 지역의 기본형을 밀어낸다. 그래서 접미어 → 지역 → 질환 순으로 채운다.
    """
    sfx = list(suffixes) if suffixes else DEFAULT_SUFFIXES
    out: List[Dict] = []
    seen = set()
    for s in sfx:
        for r in regions:
            for d in diseases:
                kw = f"{r}{d}{s}".replace(" ", "")
                key = _norm(kw)
                if not key or key in seen:
                    continue
                seen.add(key)
                out.append({"keyword": kw, "region": r, "disease": d, "suffix": s})
                if len(out) >= max_items:
                    return out
    return out


def guess_scope(keyword: str, regions: Iterable[str]) -> str:
    """키워드 안에 지역명이 들어 있으면 region, 아니면 national."""
    k = _norm(keyword)
    for r in regions:
        if r and _norm(r) and _norm(r) in k:
            return "region"
    if rd is not None:
        try:
            for name in rd.known_regions():
                if len(name) >= 2 and _norm(name) in k:
                    return "region"
        except Exception:  # noqa: BLE001
            pass
    return "national"


def _match_region_disease(keyword: str, regions: Sequence[str], diseases: Sequence[str]) -> tuple[Optional[str], Optional[str]]:
    k = _norm(keyword)
    region = next((r for r in sorted(regions, key=len, reverse=True) if _norm(r) and _norm(r) in k), None)
    disease = next((d for d in sorted(diseases, key=len, reverse=True) if _norm(d) and _norm(d) in k), None)
    return region, disease


async def expand_keywords(
    db: AsyncSession,
    *,
    seeds: Sequence[str],
    regions: Sequence[str],
    diseases: Sequence[str],
    suffixes: Optional[Sequence[str]] = None,
    region_level: int = 1,
    min_volume_region: int = 20,
    min_volume_national: int = 100,
    include_related: bool = True,
    max_candidates: int = 300,
    progress=None,
) -> List[Dict]:
    """
    후보 키워드 목록을 만든다. 각 항목:
      {keyword, region, disease, source(seed|combo|related), scope, monthly_mobile, monthly_pc,
       total_volume, competition, passes_filter}
    검색량은 캐시(하루)를 먼저 보고, 없는 것만 API 를 부른다. 연관키워드는 API 응답에서 그대로 챙긴다.
    """
    all_regions = expand_regions(regions, level=region_level)
    combos = combine(all_regions, diseases, suffixes, max_items=max_candidates) if diseases else []

    base: Dict[str, Dict] = {}
    for s in seeds:
        s = (s or "").strip()
        if s and _norm(s) not in base:
            r, d = _match_region_disease(s, all_regions, diseases)
            base[_norm(s)] = {"keyword": s, "region": r, "disease": d, "source": "seed"}
    for c in combos:
        key = _norm(c["keyword"])
        if key not in base:
            base[key] = {"keyword": c["keyword"], "region": c["region"], "disease": c["disease"], "source": "combo"}

    ordered_keys = list(base.keys())
    total_calls = max(1, (len(ordered_keys) + svs.MAX_HINTS_PER_CALL - 1) // svs.MAX_HINTS_PER_CALL)
    if progress:
        await progress(0, total_calls, f"검색량 조회 준비: 후보 {len(ordered_keys)}개")

    # 1) 캐시 우선 조회(요청 키워드) — 하루 안이면 API 를 안 부른다
    today = datetime.utcnow().date()
    metrics_by_norm: Dict[str, Dict] = {}
    missing: List[str] = []
    if ordered_keys:
        from sqlalchemy import select
        from app.models.keyword_volume import KeywordVolumeCache
        rows = (await db.execute(select(KeywordVolumeCache).where(KeywordVolumeCache.keyword.in_(ordered_keys)))).scalars().all()
        cached = {r.keyword: r for r in rows}
        for nk in ordered_keys:
            row = cached.get(nk)
            if row is not None and row.fetched_date == today:
                metrics_by_norm[nk] = svs._row_to_dict(row)
            else:
                missing.append(base[nk]["keyword"])

    # 2) 미스분 API 호출(연관어 포함) — 5개씩, 진행률 보고
    related_all: Dict[str, Dict] = {}
    if missing and svs.is_configured():
        chunks = [missing[i : i + svs.MAX_HINTS_PER_CALL] for i in range(0, len(missing), svs.MAX_HINTS_PER_CALL)]
        for i, chunk in enumerate(chunks):
            wanted, related = await svs.fetch_with_related(chunk)
            for nk, m in wanted.items():
                metrics_by_norm[nk] = m
                await svs._upsert_cache(db, nk, m, today)
            if include_related:
                for nk, m in related.items():
                    if nk not in metrics_by_norm and nk not in related_all:
                        related_all[nk] = m
            if progress:
                await progress(i + 1, len(chunks), f"검색량 조회 {i + 1}/{len(chunks)}")
        try:
            await db.commit()
        except Exception as e:  # noqa: BLE001
            logger.error("[확장] 캐시 커밋 실패: %s", e)
            await db.rollback()
    elif missing and not svs.is_configured():
        logger.warning("[확장] 검색광고 API 미설정 — 검색량 없이 후보만 반환")

    # 3) 연관키워드를 후보에 합류(지역/질환 매칭되는 것만: 무관한 연관어는 소음)
    for nk, m in related_all.items():
        kw = m["keyword"]
        r, d = _match_region_disease(kw, all_regions, diseases)
        if not d and diseases:
            continue  # 질환이 안 들어간 연관어는 버린다
        base[nk] = {"keyword": kw, "region": r, "disease": d, "source": "related"}
        metrics_by_norm[nk] = m

    # 4) 판정/필터
    out: List[Dict] = []
    for nk, info in base.items():
        m = metrics_by_norm.get(nk) or {}
        mobile = int(m.get("monthly_mobile", 0) or 0)
        pc = int(m.get("monthly_pc", 0) or 0)
        scope = "region" if info.get("region") else guess_scope(info["keyword"], all_regions)
        threshold = min_volume_region if scope == "region" else min_volume_national
        # 검색량이 없으면(API 미설정) 원장 제안·직접 입력 키워드만 통과시킨다 — 초보자가 키 없이도 진행할 수 있게
        passes = (mobile >= threshold) if m else (info.get("source") == "seed")
        out.append({
            "keyword": info["keyword"],
            "region": info.get("region"),
            "disease": info.get("disease"),
            "source": info.get("source", "combo"),
            "scope": scope,
            "monthly_mobile": mobile,
            "monthly_pc": pc,
            "total_volume": mobile + pc,
            "competition": m.get("competition", "mid") if m else "mid",
            "passes_filter": passes,
            "has_volume": bool(m),
        })

    # 통과한 것 → 검색량 순, 그 다음 미통과(검색량 있는 것) → 검색량 없는 것
    out.sort(key=lambda x: (not x["passes_filter"], not x["has_volume"], -x["monthly_mobile"], x["keyword"]))
    return out
