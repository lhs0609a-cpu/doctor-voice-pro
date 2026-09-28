"""볼륨을 갉아먹는 것들을 주기적으로 덜어낸다.

/data 는 볼륨 한 장이고 SQLite 파일 하나에 원고·사진·캐시가 모두 들어 있다. 게다가
auto_vacuum 이 꺼진 채로 커져 왔기 때문에 행을 지워도 파일은 줄지 않았다
(2026-09-28 실측: 974MB 중 406MB 사용, DB 405MB = 글 분석 캐시 182MB + posts 107MB
 + 사진 46MB + 발행 payload). 워드 100건을 두 번 넣으면 볼륨이 차고, 차는 순간
SQLite 가 'database or disk is full' 을 내며 예약만이 아니라 API 전체가 멈춘다.

그래서 두 가지를 한다.
  1) 다시 만들 수 있는 것(글 분석 캐시·검색 캐시·끝난 발행 영수증)은 보관 기간을 두고 지운다.
  2) 빈 페이지를 운영체제에 돌려준다(incremental_vacuum). auto_vacuum 이 incremental 로
     바뀌어 있어야 동작하므로, 전환은 scripts/db_maintenance.py 가 한 번 해 준다.

지우는 것은 전부 '없으면 다시 만들면 되는 것'뿐이다. 원고·사진·예약은 건드리지 않는다.
"""
from __future__ import annotations

import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

logger = logging.getLogger(__name__)

# 보관 기간 — 모두 '지워도 다시 만들어지는' 것들이다.
POST_CACHE_DAYS = 45      # 글 1개 풀파싱 결과. 발행된 글은 안 변하지만 다시 읽으면 된다.
SERP_CACHE_DAYS = 3       # 검색 결과 캐시. TTL 이 6시간이라 그 뒤로는 쓰이지 않는다.
SNAPSHOT_DAYS = 60        # 블로그 지수 스냅샷 이력.
ATTEMPT_DAYS = 14         # 끝난 발행 시도의 영수증. 중복 보고 방지용이라 2주면 충분하다.

# 글 분석 캐시는 보관 기간만으로는 안 묶인다 — 2026-09-28 실측으로 18일에 13,730행 182MB
# (행당 13KB, 하루 10MB)였다. 그래서 '오래된 것'이 아니라 '가장 오래된 것부터' 잘라
# 항상 이 행 수 안에 둔다(≈130MB). 지워도 다시 읽으면 되는 캐시다.
POST_CACHE_MAX_ROWS = 10_000

BATCH = 2000              # 한 번에 지울 행 수. 쓰기 잠금을 길게 잡지 않는다.
INTERVAL_SECONDS = 3600   # 유지보수 루프가 이 주기로만 실제 정리를 한다.
VACUUM_PAGES = 2000       # 한 주기에 운영체제로 돌려줄 페이지 수(4KB × 2000 = 8MB)

_last_run: Optional[datetime] = None


def db_path() -> Optional[Path]:
    """SQLite 파일 경로. 다른 DB 를 쓰면 None."""
    url = settings.DATABASE_URL_SYNC or settings.DATABASE_URL
    if "sqlite" not in url:
        return None
    _, _, tail = url.partition("///")
    return Path(tail.replace("+aiosqlite", "")) if tail else None


def report() -> Dict[str, Any]:
    """지금 볼륨과 DB 파일이 얼마나 찼는지. 사람이 보고 판단할 숫자만."""
    out: Dict[str, Any] = {}
    path = db_path()
    if path and path.exists():
        out["db_mb"] = round(path.stat().st_size / 1048576, 1)
    target = path.parent if path else Path(settings.MEDIA_DIR)
    try:
        usage = shutil.disk_usage(target if target.exists() else Path("."))
        out.update(disk_total_mb=round(usage.total / 1048576),
                   disk_used_mb=round(usage.used / 1048576),
                   disk_free_mb=round(usage.free / 1048576),
                   disk_used_pct=round(usage.used * 100 / usage.total))
    except OSError as error:
        out["disk_error"] = str(error)
    return out


async def _prune(db: AsyncSession, model, pk, when, cutoff: datetime, extra=None) -> int:
    """오래된 행을 BATCH 개까지 지운다. 지운 개수."""
    q = select(pk).where(when < cutoff)
    if extra is not None:
        q = q.where(extra)
    ids = (await db.execute(q.limit(BATCH))).scalars().all()
    if not ids:
        return 0
    await db.execute(delete(model).where(pk.in_(ids)))
    await db.commit()
    return len(ids)


async def _drop_stale_payloads(db: AsyncSession) -> int:
    """이미 끝났는데 원고·사진(base64)을 안고 있는 시도의 payload 를 비운다.

    지금은 결과를 적는 순간 비우지만(publish_protocol), 그 전에 쌓인 것들이 남아 있다."""
    from app.models.campaign import PublishAttempt

    tokens = (await db.execute(select(PublishAttempt.token).where(
        PublishAttempt.payload.isnot(None), PublishAttempt.result.isnot(None)).limit(BATCH))).scalars().all()
    if not tokens:
        return 0
    await db.execute(update(PublishAttempt).where(PublishAttempt.token.in_(tokens)).values(payload=None))
    await db.commit()
    return len(tokens)


async def _cap_post_cache(db: AsyncSession) -> int:
    """글 분석 캐시를 POST_CACHE_MAX_ROWS 행 안으로 — 오래된 것부터 BATCH 개까지 지운다."""
    from app.models.blog_index import PostAnalysisCache

    total = int((await db.execute(select(func.count()).select_from(PostAnalysisCache))).scalar() or 0)
    over = total - POST_CACHE_MAX_ROWS
    if over <= 0:
        return 0
    urls = (await db.execute(select(PostAnalysisCache.post_url)
                             .order_by(PostAnalysisCache.created_at.asc())
                             .limit(min(BATCH, over)))).scalars().all()
    if not urls:
        return 0
    await db.execute(delete(PostAnalysisCache).where(PostAnalysisCache.post_url.in_(urls)))
    await db.commit()
    return len(urls)


async def reclaim(db: AsyncSession, *, now: Optional[datetime] = None, force: bool = False,
                  passes: int = 1) -> Dict[str, Any]:
    """다시 만들 수 있는 것들을 보관 기간대로 덜어낸다. force=False 면 1시간에 한 번만."""
    global _last_run
    now = now or datetime.utcnow()
    if not force and _last_run and (now - _last_run).total_seconds() < INTERVAL_SECONDS:
        return {}
    _last_run = now

    from app.models.blog_index import BlogIndexSnapshot, PostAnalysisCache, SerpCache
    from app.models.campaign import PublishAttempt

    jobs = (
        ("post_cache", PostAnalysisCache, PostAnalysisCache.post_url,
         PostAnalysisCache.created_at, POST_CACHE_DAYS, None),
        ("serp_cache", SerpCache, SerpCache.id, SerpCache.fetched_at, SERP_CACHE_DAYS, None),
        ("snapshots", BlogIndexSnapshot, BlogIndexSnapshot.id,
         BlogIndexSnapshot.created_at, SNAPSHOT_DAYS, None),
        ("attempts", PublishAttempt, PublishAttempt.token, PublishAttempt.updated_at,
         ATTEMPT_DAYS, PublishAttempt.result.isnot(None)),
    )
    freed: Dict[str, Any] = {}
    for name, model, pk, when, days, extra in jobs:
        cutoff = now - timedelta(days=days)
        total = 0
        for _ in range(max(1, passes)):
            n = await _prune(db, model, pk, when, cutoff, extra)
            total += n
            if n < BATCH:
                break
        if total:
            freed[name] = total
    capped = 0
    for _ in range(max(1, passes)):
        n = await _cap_post_cache(db)
        capped += n
        if n < BATCH:
            break
    if capped:
        freed["post_cache_over_cap"] = capped
    payloads = 0
    for _ in range(max(1, passes)):
        n = await _drop_stale_payloads(db)
        payloads += n
        if n < BATCH:
            break
    if payloads:
        freed["payloads"] = payloads
    reclaimed = await incremental_vacuum(db)
    if reclaimed:
        freed["vacuum_pages"] = reclaimed
    if freed:
        logger.info("[저장공간] 정리: %s / %s", freed, report())
    return freed


async def incremental_vacuum(db: AsyncSession, pages: int = VACUUM_PAGES) -> int:
    """빈 페이지를 운영체제에 돌려준다. auto_vacuum=incremental 일 때만 동작한다."""
    path = db_path()
    if path is None:
        return 0
    try:
        mode = (await db.execute(text("PRAGMA auto_vacuum"))).scalar()
        if int(mode or 0) != 2:      # 0=none, 1=full, 2=incremental
            return 0
        free_before = int((await db.execute(text("PRAGMA freelist_count"))).scalar() or 0)
        if free_before < pages // 4:
            return 0
        await db.execute(text(f"PRAGMA incremental_vacuum({int(pages)})"))
        await db.commit()
        free_after = int((await db.execute(text("PRAGMA freelist_count"))).scalar() or 0)
        return max(0, free_before - free_after)
    except Exception:  # noqa: BLE001 — 정리가 실패해도 서비스는 계속 돌아야 한다
        logger.exception("[저장공간] incremental_vacuum 실패")
        await db.rollback()
        return 0


async def table_sizes(db: AsyncSession, limit: int = 15) -> list:
    """어느 테이블이 파일을 먹고 있는지(dbstat). 없으면 빈 목록."""
    try:
        rows = (await db.execute(text(
            "select name, sum(pgsize) bytes from dbstat group by name order by bytes desc limit :n"
        ), {"n": limit})).all()
    except Exception:  # noqa: BLE001 — dbstat 이 없는 빌드도 있다
        return []
    return [{"name": n, "mb": round((b or 0) / 1048576, 1)} for n, b in rows]


async def count_rows(db: AsyncSession) -> Dict[str, int]:
    """정리 대상 테이블의 현재 행 수 — 스크립트 출력용."""
    from app.models.blog_index import BlogIndexSnapshot, PostAnalysisCache, SerpCache
    from app.models.campaign import PublishAttempt

    out: Dict[str, int] = {}
    for name, model in (("post_cache", PostAnalysisCache), ("serp_cache", SerpCache),
                        ("snapshots", BlogIndexSnapshot), ("attempts", PublishAttempt)):
        try:
            out[name] = int((await db.execute(select(func.count()).select_from(model))).scalar() or 0)
        except Exception:  # noqa: BLE001
            out[name] = -1
    return out
