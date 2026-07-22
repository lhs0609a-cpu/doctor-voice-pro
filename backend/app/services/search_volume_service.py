"""
네이버 검색광고 API(keywordstool) 연동 - 키워드 실검색량/경쟁도.

- 인증: CUSTOMER_ID + API_KEY + SECRET_KEY 기반 HMAC-SHA256 서명.
- 데이터: 월간 PC/모바일 검색수(monthlyPcQcCnt/monthlyMobileQcCnt), 경쟁도(compIdx).
- 캐싱: 하루 단위(KeywordVolumeCache). 일일 호출 제한 + 데이터가 하루 단위 갱신이라 필수.

keyword_collector.py 의 httpx 비동기 패턴을 따른다.
"""
import base64
import hashlib
import hmac
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.keyword_volume import KeywordVolumeCache

logger = logging.getLogger(__name__)

# 검색광고 API는 요청당 hintKeywords 최대 5개.
MAX_HINTS_PER_CALL = 5

# compIdx(한글) → 표준 등급
_COMP_MAP = {"낮음": "low", "중간": "mid", "높음": "high"}


def is_configured() -> bool:
    """검색광고 API 자격증명이 모두 설정되었는지."""
    return bool(
        settings.NAVER_AD_CUSTOMER_ID
        and settings.NAVER_AD_API_KEY
        and settings.NAVER_AD_SECRET_KEY
    )


def _make_signature(timestamp: str, method: str, path: str, secret: str) -> str:
    """검색광고 API 서명: base64(HMAC-SHA256(secret, "{ts}.{METHOD}.{path}"))."""
    message = f"{timestamp}.{method}.{path}"
    digest = hmac.new(
        secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def _headers(method: str, path: str) -> Dict[str, str]:
    """서명 헤더 조립."""
    timestamp = str(int(time.time() * 1000))
    signature = _make_signature(
        timestamp, method, path, settings.NAVER_AD_SECRET_KEY
    )
    return {
        "X-Timestamp": timestamp,
        "X-API-KEY": settings.NAVER_AD_API_KEY,
        "X-Customer": str(settings.NAVER_AD_CUSTOMER_ID),
        "X-Signature": signature,
        "Content-Type": "application/json; charset=UTF-8",
    }


def _normalize(keyword: str) -> str:
    """네이버는 키워드를 공백 제거 + 대문자로 정규화해 돌려준다. 매칭용 키로 통일."""
    return (keyword or "").replace(" ", "").upper()


def _to_int(value) -> int:
    """'< 10' 같은 문자열/None을 정수로 정규화."""
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip()
    if not s:
        return 0
    if s.startswith("<"):
        # '< 10' → 보수적으로 5로 취급
        return 5
    digits = "".join(ch for ch in s if ch.isdigit())
    return int(digits) if digits else 0


def _row_to_dict(row: KeywordVolumeCache) -> Dict:
    return {
        "keyword": row.keyword,
        "monthly_pc": row.monthly_pc,
        "monthly_mobile": row.monthly_mobile,
        "total_volume": row.total_volume,
        "competition": row.competition,
        "comp_idx_raw": row.comp_idx_raw,
        "est_cpc": row.est_cpc,
    }


async def fetch_keyword_volumes(keywords: List[str]) -> Dict[str, Dict]:
    """
    검색광고 API 직접 호출(캐시 미경유). 정규화 키 → 지표 dict.
    hintKeywords는 최대 5개씩 나눠 호출한다.
    """
    if not is_configured():
        logger.warning("[검색량] 검색광고 API 자격증명 미설정 — 빈 결과 반환")
        return {}

    path = "/keywordstool"
    url = f"{settings.NAVER_AD_BASE_URL}{path}"
    result: Dict[str, Dict] = {}

    # 요청 대상 정규화 집합(응답엔 연관어까지 섞여 오므로 이걸로 필터)
    wanted = {_normalize(k) for k in keywords if k and k.strip()}

    unique = list({k.strip() for k in keywords if k and k.strip()})
    chunks = [
        unique[i : i + MAX_HINTS_PER_CALL]
        for i in range(0, len(unique), MAX_HINTS_PER_CALL)
    ]

    async with httpx.AsyncClient(timeout=15.0) as client:
        for chunk in chunks:
            params = {
                # 검색광고 API는 콤마 없이 공백 없는 키워드 리스트를 콤마로 join
                "hintKeywords": ",".join(chunk),
                "showDetail": "1",
            }
            try:
                resp = await client.get(
                    url, params=params, headers=_headers("GET", path)
                )
                if resp.status_code != 200:
                    logger.error(
                        "[검색량] API 오류 %s: %s", resp.status_code, resp.text[:200]
                    )
                    continue
                data = resp.json()
                for item in data.get("keywordList", []):
                    rel = item.get("relKeyword", "")
                    norm = _normalize(rel)
                    if norm not in wanted:
                        continue  # 연관어(요청 안 한 키워드)는 버림
                    pc = _to_int(item.get("monthlyPcQcCnt"))
                    mobile = _to_int(item.get("monthlyMobileQcCnt"))
                    comp_raw = item.get("compIdx") or ""
                    result[norm] = {
                        "keyword": rel,
                        "monthly_pc": pc,
                        "monthly_mobile": mobile,
                        "total_volume": pc + mobile,
                        "competition": _COMP_MAP.get(comp_raw, "mid"),
                        "comp_idx_raw": comp_raw,
                        "est_cpc": _to_int(item.get("plAvgDepth"))
                        or _to_int(item.get("monthlyAvePcClkCnt")),
                        "raw": item,
                    }
            except Exception as e:  # noqa: BLE001
                logger.error("[검색량] 요청 실패 (%s): %s", chunk, e)

    return result


async def get_keyword_metrics(
    db: AsyncSession, keywords: List[str], use_cache: bool = True
) -> List[Dict]:
    """
    캐시 우선 조회 → 미스분만 API 호출 → 캐시 저장. 입력 순서를 보존해 반환.

    반환: [{keyword, monthly_pc, monthly_mobile, total_volume,
            competition, comp_idx_raw, est_cpc}, ...]
    """
    clean = [k.strip() for k in keywords if k and k.strip()]
    if not clean:
        return []

    today = datetime.utcnow().date()
    by_norm: Dict[str, Dict] = {}
    missing: List[str] = []

    # 1) 캐시 조회
    if use_cache:
        norm_keys = list({_normalize(k) for k in clean})
        rows = (
            await db.execute(
                select(KeywordVolumeCache).where(
                    KeywordVolumeCache.keyword.in_(norm_keys)
                )
            )
        ).scalars().all()
        cached = {r.keyword: r for r in rows}
        for k in clean:
            nk = _normalize(k)
            row = cached.get(nk)
            if row is not None and row.fetched_date == today:
                by_norm[nk] = _row_to_dict(row)
            elif nk not in {_normalize(m) for m in missing}:
                missing.append(k)
    else:
        missing = clean

    # 2) 미스분 API 호출 + 캐시 저장
    if missing:
        fetched = await fetch_keyword_volumes(missing)
        for nk, metrics in fetched.items():
            by_norm[nk] = {
                "keyword": metrics["keyword"],
                "monthly_pc": metrics["monthly_pc"],
                "monthly_mobile": metrics["monthly_mobile"],
                "total_volume": metrics["total_volume"],
                "competition": metrics["competition"],
                "comp_idx_raw": metrics["comp_idx_raw"],
                "est_cpc": metrics["est_cpc"],
            }
            await _upsert_cache(db, nk, metrics, today)
        try:
            await db.commit()
        except Exception as e:  # noqa: BLE001
            logger.error("[검색량] 캐시 커밋 실패: %s", e)
            await db.rollback()

    # 3) 입력 순서대로 결과 조립(미조회분은 0으로 채움)
    out: List[Dict] = []
    for k in clean:
        nk = _normalize(k)
        if nk in by_norm:
            out.append(by_norm[nk])
        else:
            out.append(
                {
                    "keyword": k,
                    "monthly_pc": 0,
                    "monthly_mobile": 0,
                    "total_volume": 0,
                    "competition": "mid",
                    "comp_idx_raw": "",
                    "est_cpc": 0,
                }
            )
    return out


async def _upsert_cache(
    db: AsyncSession, norm_key: str, metrics: Dict, today
) -> None:
    """캐시 행 갱신 또는 삽입."""
    row = await db.get(KeywordVolumeCache, norm_key)
    if row is None:
        row = KeywordVolumeCache(keyword=norm_key)
        db.add(row)
    row.monthly_pc = metrics["monthly_pc"]
    row.monthly_mobile = metrics["monthly_mobile"]
    row.total_volume = metrics["total_volume"]
    row.competition = metrics["competition"]
    row.comp_idx_raw = metrics["comp_idx_raw"]
    row.est_cpc = metrics["est_cpc"]
    row.raw = metrics.get("raw")
    row.fetched_date = today
