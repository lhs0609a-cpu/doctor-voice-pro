"""
DB 기반 작업 워커.

- enqueue(): 작업 적재(같은 dedupe_key 가 pending/running 이면 그 작업을 돌려줌)
- register(type): 핸들러 등록 데코레이터. 핸들러 시그니처: async (ctx: JobContext) -> dict | None
- run_forever(): 앱 시작 시 asyncio.create_task 로 띄우거나, `python -m app.worker` 로 별도 프로세스 실행

핸들러는 자기 세션(ctx.db)을 받는다. 긴 루프 안에서는 ctx.progress() 로 진행률을 남긴다.
예외가 나면 attempts 를 올리고 max_attempts 미만이면 30초 뒤 재시도, 넘으면 failed.
running 인 채 30분 지난 작업(워커 사망)은 pending 으로 되돌린다.
"""
from __future__ import annotations

import asyncio
import logging
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Dict, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.models.background_job import BackgroundJob

logger = logging.getLogger(__name__)

STALE_AFTER = timedelta(minutes=30)
RETRY_DELAY = timedelta(seconds=30)
POLL_INTERVAL = 2.0


@dataclass
class JobContext:
    db: AsyncSession
    job: BackgroundJob

    @property
    def payload(self) -> Dict[str, Any]:
        return self.job.payload or {}

    @property
    def user_id(self) -> Optional[str]:
        return self.job.user_id

    async def progress(self, done: int, total: Optional[int] = None, message: Optional[str] = None) -> None:
        """진행률 기록. 화면이 폴링으로 읽는다. 자주 불러도 되도록 commit 은 가볍게."""
        self.job.progress = int(done)
        if total is not None:
            self.job.total = int(total)
        if message is not None:
            self.job.message = message[:300]
        self.job.updated_at = datetime.utcnow()
        try:
            await self.db.commit()
        except Exception:  # noqa: BLE001
            await self.db.rollback()

    async def cancelled(self) -> bool:
        """사용자가 취소했는지(행을 다시 읽어 확인)."""
        res = await self.db.execute(select(BackgroundJob.status).where(BackgroundJob.id == self.job.id))
        st = res.scalar_one_or_none()
        return st == "cancelled"


Handler = Callable[[JobContext], Awaitable[Optional[dict]]]
HANDLERS: Dict[str, Handler] = {}
_runner_task: Optional[asyncio.Task] = None
_wake = asyncio.Event()


def register(job_type: str) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        HANDLERS[job_type] = fn
        return fn
    return deco


async def enqueue(
    db: AsyncSession,
    job_type: str,
    payload: Optional[dict] = None,
    user_id: Optional[str] = None,
    dedupe_key: Optional[str] = None,
    run_after: Optional[datetime] = None,
    max_attempts: int = 2,
    total: int = 0,
) -> BackgroundJob:
    """작업 적재. dedupe_key 가 있고 같은 키의 pending/running 이 있으면 그것을 돌려준다."""
    if dedupe_key:
        res = await db.execute(
            select(BackgroundJob).where(
                BackgroundJob.dedupe_key == dedupe_key,
                BackgroundJob.status.in_(["pending", "running"]),
            )
        )
        existing = res.scalar_one_or_none()
        if existing:
            return existing
    job = BackgroundJob(
        user_id=str(user_id) if user_id else None,
        type=job_type,
        payload=payload or {},
        status="pending",
        run_after=run_after or datetime.utcnow(),
        dedupe_key=dedupe_key,
        max_attempts=max_attempts,
        total=total,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    _wake.set()
    return job


async def cancel(db: AsyncSession, job_id: str, user_id: Optional[str] = None) -> bool:
    q = select(BackgroundJob).where(BackgroundJob.id == job_id)
    if user_id:
        q = q.where(BackgroundJob.user_id == str(user_id))
    job = (await db.execute(q)).scalar_one_or_none()
    if not job or job.status in ("done", "failed", "cancelled"):
        return False
    job.status = "cancelled"
    job.finished_at = datetime.utcnow()
    await db.commit()
    return True


async def _reclaim_stale(db: AsyncSession) -> None:
    cutoff = datetime.utcnow() - STALE_AFTER
    await db.execute(
        update(BackgroundJob)
        .where(BackgroundJob.status == "running", BackgroundJob.locked_at < cutoff)
        .values(status="pending", locked_at=None, message="워커가 멈춰 다시 시도합니다")
    )
    await db.commit()


async def _claim_one(db: AsyncSession) -> Optional[BackgroundJob]:
    now = datetime.utcnow()
    res = await db.execute(
        select(BackgroundJob)
        .where(BackgroundJob.status == "pending", BackgroundJob.run_after <= now)
        .order_by(BackgroundJob.run_after.asc(), BackgroundJob.created_at.asc())
        .limit(1)
    )
    job = res.scalar_one_or_none()
    if not job:
        return None
    # 낙관적 잠금: pending 인 행만 running 으로 바꾼다(여러 워커가 있어도 한 곳만 성공)
    upd = await db.execute(
        update(BackgroundJob)
        .where(BackgroundJob.id == job.id, BackgroundJob.status == "pending")
        .values(status="running", locked_at=now, started_at=now, attempts=BackgroundJob.attempts + 1)
    )
    await db.commit()
    if upd.rowcount != 1:
        return None
    await db.refresh(job)
    return job


async def _process(job_id: str) -> None:
    async with AsyncSessionLocal() as db:
        job = (await db.execute(select(BackgroundJob).where(BackgroundJob.id == job_id))).scalar_one()
        job_type = job.type  # 롤백 뒤에는 ORM 속성이 만료되어 접근하면 동기 IO 오류가 난다 → 미리 복사
        handler = HANDLERS.get(job_type)
        ctx = JobContext(db=db, job=job)
        if not handler:
            job.status = "failed"
            job.error = f"등록되지 않은 작업 유형: {job.type}"
            job.finished_at = datetime.utcnow()
            await db.commit()
            return
        try:
            result = await handler(ctx)
            # 핸들러가 취소를 감지해 중단했을 수 있다
            await db.refresh(job)
            if job.status == "cancelled":
                return
            job.status = "done"
            job.result = result if result is not None else job.result
            job.progress = job.total or job.progress
            job.finished_at = datetime.utcnow()
            job.error = None
            await db.commit()
        except Exception as e:  # noqa: BLE001
            await db.rollback()
            tb = traceback.format_exc()
            logger.error("[worker] %s 실패: %s\n%s", job_type, e, tb)
            db.expunge_all()  # 롤백으로 만료된 인스턴스를 버리고 새로 읽는다
            job = (await db.execute(select(BackgroundJob).where(BackgroundJob.id == job_id))).scalar_one()
            job.error = f"{e}"[:2000]
            if job.attempts < job.max_attempts:
                job.status = "pending"
                job.locked_at = None
                job.run_after = datetime.utcnow() + RETRY_DELAY
                job.message = "오류로 잠시 후 다시 시도합니다"
            else:
                job.status = "failed"
                job.finished_at = datetime.utcnow()
            await db.commit()


async def run_forever(poll_interval: float = POLL_INTERVAL) -> None:
    """워커 루프. 앱 lifespan 에서 create_task 로 띄운다."""
    # 핸들러 모듈을 여기서 임포트해 등록(순환 임포트 방지)
    from app.services import campaign_jobs  # noqa: F401
    from app.services import blog_index_jobs  # noqa: F401

    logger.info("[worker] 시작. 핸들러 %d개", len(HANDLERS))
    last_stale_check = datetime.min
    while True:
        try:
            async with AsyncSessionLocal() as db:
                if datetime.utcnow() - last_stale_check > timedelta(minutes=1):
                    await _reclaim_stale(db)
                    last_stale_check = datetime.utcnow()
                job = await _claim_one(db)
            if job:
                await _process(job.id)
                continue  # 남은 작업이 있으면 바로 다음
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.error("[worker] 루프 오류: %s", e)
        _wake.clear()
        try:
            await asyncio.wait_for(_wake.wait(), timeout=poll_interval)
        except asyncio.TimeoutError:
            pass


def start_in_app() -> None:
    """FastAPI lifespan 에서 호출. 이미 떠 있으면 무시."""
    global _runner_task
    if _runner_task and not _runner_task.done():
        return
    _runner_task = asyncio.create_task(run_forever())


async def stop_in_app() -> None:
    global _runner_task
    if _runner_task:
        _runner_task.cancel()
        try:
            await _runner_task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        _runner_task = None
