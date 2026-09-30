"""카페 바이럴 스레드 API — 만들고, 고치고, 검수한다. 올리는 것은 사람이 한다.

사람이 본문이나 댓글을 고치면 **그 자리에서 다시 검수한다**. 고친 뒤에도 '통과'라고
적혀 있으면 그 표시는 거짓말이 된다.
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.cafe_job import CAFE_JOB_ACTIVE, CafeJob
from app.models.cafe_thread import CafeThread
from app.models.campaign import Client
from app.models.user import User
from app.models.viral_common import NaverAccount
from app.services import cafe_protocol as protocol
from app.services import cafe_thread as service
from app.services.schedule_engine import kst_now

router = APIRouter(prefix="/cafe", tags=["cafe-thread"])


def _client_dict(c: Client) -> Dict[str, Any]:
    return {"name": c.name, "short_name": c.short_name, "brand_keyword": c.brand_keyword,
            "forbidden_words": c.forbidden_words or [], "facts": c.facts, "tone": c.tone}


class CommentOut(BaseModel):
    seq: int
    persona: str = ""
    body: str = ""


class ThreadOut(BaseModel):
    id: str
    client_id: str
    topic: str
    cafe_name: Optional[str] = None
    title: str
    body: str
    comments: List[CommentOut] = []
    promo_index: int
    checks: Dict[str, Any] = {}
    approved: bool = False
    created_at: Optional[datetime] = None


def _out(t: CafeThread) -> ThreadOut:
    return ThreadOut(
        id=t.id, client_id=t.client_id, topic=t.topic, cafe_name=t.cafe_name,
        title=t.title or "", body=t.body or "",
        comments=[CommentOut(**c) for c in (t.comments or [])],
        promo_index=t.promo_index or service.DEFAULT_PROMO_INDEX,
        checks=t.checks or {}, approved=bool(t.approved), created_at=t.created_at,
    )


async def _owned_client(db: AsyncSession, client_id: str, user: User) -> Client:
    c = await db.get(Client, client_id)
    if not c or c.user_id != str(user.id):
        raise HTTPException(status_code=404, detail="병원을 찾을 수 없습니다")
    return c


async def _owned_thread(db: AsyncSession, thread_id: str, user: User) -> CafeThread:
    t = await db.get(CafeThread, thread_id)
    if not t or t.user_id != str(user.id):
        raise HTTPException(status_code=404, detail="스레드를 찾을 수 없습니다")
    return t


class GenerateIn(BaseModel):
    client_id: str
    topic: str = Field(min_length=2, max_length=300)
    cafe_name: Optional[str] = Field(None, max_length=200)
    comment_count: int = Field(service.DEFAULT_COMMENT_COUNT,
                               ge=service.MIN_COMMENTS, le=service.MAX_COMMENTS)
    promo_index: int = Field(service.DEFAULT_PROMO_INDEX, ge=1, le=service.MAX_COMMENTS)


@router.post("/threads/generate", response_model=ThreadOut)
async def generate(body: GenerateIn, current_user: User = Depends(get_current_user),
                   db: AsyncSession = Depends(get_db)):
    client = await _owned_client(db, body.client_id, current_user)
    name = (client.brand_keyword or "").strip() or (client.short_name or "").strip() or client.name
    try:
        made = await service.generate_thread(
            clinic_name=name, topic=body.topic, cafe_name=body.cafe_name or "",
            tone=client.tone or "", comment_count=body.comment_count,
            promo_index=body.promo_index, forbidden_words=client.forbidden_words or [],
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"스레드를 만들지 못했습니다: {exc}")
    checks = service.check_thread(made, _client_dict(client))
    thread = CafeThread(
        user_id=str(current_user.id), client_id=client.id, topic=body.topic,
        cafe_name=body.cafe_name, title=made["title"], body=made["body"],
        comments=made["comments"], promo_index=made["promo_index"], checks=checks,
    )
    db.add(thread)
    await db.commit()
    return _out(thread)


@router.get("/threads", response_model=List[ThreadOut])
async def list_threads(client_id: Optional[str] = None, limit: int = 50,
                       current_user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db)):
    q = select(CafeThread).where(CafeThread.user_id == str(current_user.id))
    if client_id:
        q = q.where(CafeThread.client_id == client_id)
    rows = (await db.execute(q.order_by(CafeThread.created_at.desc()).limit(max(1, min(200, limit))))).scalars().all()
    return [_out(t) for t in rows]


@router.get("/threads/{thread_id}", response_model=ThreadOut)
async def get_thread(thread_id: str, current_user: User = Depends(get_current_user),
                     db: AsyncSession = Depends(get_db)):
    return _out(await _owned_thread(db, thread_id, current_user))


class ThreadPatch(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    comments: Optional[List[CommentOut]] = None
    promo_index: Optional[int] = Field(None, ge=1, le=service.MAX_COMMENTS)
    approved: Optional[bool] = None


@router.put("/threads/{thread_id}", response_model=ThreadOut)
async def update_thread(thread_id: str, body: ThreadPatch,
                        current_user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)):
    thread = await _owned_thread(db, thread_id, current_user)
    client = await _owned_client(db, thread.client_id, current_user)
    if body.title is not None:
        thread.title = body.title
    if body.body is not None:
        thread.body = body.body
    if body.comments is not None:
        thread.comments = [c.model_dump() for c in body.comments]
    if body.promo_index is not None:
        thread.promo_index = body.promo_index
    # 고친 내용으로 **다시** 검수한다. 예전 결과를 그대로 두면 그 표시가 거짓말이 된다.
    checks = service.check_thread({
        "title": thread.title, "body": thread.body, "comments": thread.comments or [],
        "promo_index": thread.promo_index, "comment_count": len(thread.comments or []),
    }, _client_dict(client))
    thread.checks = checks
    if body.approved is not None:
        if body.approved and not checks["ok"]:
            raise HTTPException(status_code=400, detail={
                "message": "검수를 통과하지 못한 스레드는 승인할 수 없습니다", "issues": checks["issues"]})
        thread.approved = body.approved
    elif not checks["ok"]:
        thread.approved = False        # 고쳐서 문제가 생겼으면 승인은 풀린다
    await db.commit()
    return _out(thread)


@router.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str, current_user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)):
    thread = await _owned_thread(db, thread_id, current_user)
    await db.delete(thread)
    await db.commit()
    return {"success": True}


# ─────────────── 2-a: 질문글만 실행기가 올린다(댓글은 사람이) ───────────────
# 계정이 1~2개뿐인 동안에는 댓글 6개를 다른 사람처럼 달 수 없다. 같은 계정이 두 번 달면
# 그게 바로 광고 티라서, 지금은 글 하나만 올린다(2026-09-30 결정).

class ScheduleIn(BaseModel):
    cafe_url: str = Field(min_length=8, max_length=500)
    account_id: str
    board_name: Optional[str] = Field(None, max_length=200)
    scheduled_at: datetime          # KST naive


class JobOut(BaseModel):
    id: str
    thread_id: str
    account_id: str
    cafe_url: str
    board_name: Optional[str] = None
    scheduled_at: str
    status: str
    attempts: int = 0
    result_url: Optional[str] = None
    error: Optional[str] = None


def _job_out(j: CafeJob) -> JobOut:
    return JobOut(id=j.id, thread_id=j.thread_id, account_id=j.account_id, cafe_url=j.cafe_url,
                  board_name=j.board_name, scheduled_at=j.scheduled_at.isoformat(timespec="minutes"),
                  status=j.status, attempts=j.attempts or 0, result_url=j.result_url, error=j.error)


@router.post("/threads/{thread_id}/schedule", response_model=JobOut)
async def schedule_thread(thread_id: str, body: ScheduleIn,
                          current_user: User = Depends(get_current_user),
                          db: AsyncSession = Depends(get_db)):
    """이 스레드의 질문글을 카페에 올릴 예약을 건다."""
    thread = await _owned_thread(db, thread_id, current_user)
    if not thread.approved:
        raise HTTPException(status_code=400, detail="검수를 통과하고 '쓸 수 있음'으로 표시한 뒤에 예약하세요")
    account = await db.get(NaverAccount, body.account_id)
    if not account or str(account.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="네이버 계정을 찾을 수 없습니다")
    if not account.use_for_cafe:
        raise HTTPException(status_code=400, detail="이 계정은 카페용으로 설정되어 있지 않습니다")
    when = body.scheduled_at.replace(tzinfo=None)
    if when <= kst_now() + timedelta(minutes=5):
        raise HTTPException(status_code=400, detail="예약 시각은 지금부터 5분 뒤 이후로 잡아 주세요")
    existing = (await db.execute(select(CafeJob).where(
        CafeJob.thread_id == thread.id, CafeJob.status.in_(list(CAFE_JOB_ACTIVE))))).scalars().first()
    if existing:
        raise HTTPException(status_code=409, detail="이 스레드는 이미 예약되어 있습니다")
    job = CafeJob(user_id=str(current_user.id), thread_id=thread.id, account_id=account.id,
                  cafe_url=body.cafe_url.strip(), board_name=body.board_name, scheduled_at=when)
    db.add(job)
    await db.commit()
    return _job_out(job)


@router.get("/threads/{thread_id}/jobs", response_model=List[JobOut])
async def list_jobs(thread_id: str, current_user: User = Depends(get_current_user),
                    db: AsyncSession = Depends(get_db)):
    await _owned_thread(db, thread_id, current_user)
    rows = (await db.execute(select(CafeJob).where(
        CafeJob.thread_id == thread_id, CafeJob.user_id == str(current_user.id),
    ).order_by(CafeJob.scheduled_at))).scalars().all()
    return [_job_out(j) for j in rows]


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
async def cancel_job(job_id: str, current_user: User = Depends(get_current_user),
                     db: AsyncSession = Depends(get_db)):
    job = await db.get(CafeJob, job_id)
    if not job or job.user_id != str(current_user.id):
        raise HTTPException(status_code=404, detail="예약을 찾을 수 없습니다")
    if job.status not in ("queued", "failed"):
        raise HTTPException(status_code=400, detail="이미 올라갔거나 진행 중인 예약은 취소할 수 없습니다")
    job.status, job.busy_account_id = "cancelled", None
    await db.commit()
    return _job_out(job)


class ReconcileIn(BaseModel):
    posted: bool                     # 카페에 올라가 있던가?
    url: Optional[str] = Field(None, max_length=500)


@router.post("/jobs/{job_id}/reconcile", response_model=JobOut)
async def reconcile_job(job_id: str, body: ReconcileIn,
                        current_user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)):
    """'확인 필요'를 사람이 눈으로 보고 풀어 준다. 그래야 그 계정이 다시 일한다."""
    job = await db.get(CafeJob, job_id)
    if not job or job.user_id != str(current_user.id):
        raise HTTPException(status_code=404, detail="예약을 찾을 수 없습니다")
    if job.status != "uncertain":
        raise HTTPException(status_code=409, detail="확인 필요 상태만 대조할 수 있습니다")
    job.status = "submitted" if body.posted else "cancelled"
    job.result_url = body.url or job.result_url
    job.error = "사용자 확인: " + ("올라가 있었습니다" if body.posted else "올라가지 않았습니다")
    job.busy_account_id = None       # 계정을 풀어 준다
    await db.commit()
    return _job_out(job)


# ───────────────────────────── 실행기 창구 ─────────────────────────────
class ClaimIn(BaseModel):
    account_ids: List[str] = Field(default_factory=list, max_length=20)
    capabilities: List[str] = Field(default_factory=list, max_length=20)


class ClaimedCafeJob(BaseModel):
    id: str
    lock_token: str
    account_id: str
    cafe_url: str
    board_name: Optional[str] = None
    title: str
    body: str


@router.post("/agent/claim", response_model=List[ClaimedCafeJob])
async def agent_claim(body: ClaimIn, current_user: User = Depends(get_current_user),
                      db: AsyncSession = Depends(get_db)):
    """실행기가 올릴 글을 하나 가져간다. 이 PC에 로그인해 둔 계정의 것만 준다."""
    if "cafe_post_v1" not in body.capabilities:
        raise HTTPException(status_code=426, detail="카페 게시를 지원하는 최신 실행기로 업데이트하세요")
    uid = str(current_user.id)
    await protocol.recover_expired(db, uid)
    q = select(CafeJob).where(CafeJob.user_id == uid, protocol.eligible(kst_now()))
    if body.account_ids:
        q = q.where(CafeJob.account_id.in_(body.account_ids))
    for job in (await db.execute(q.order_by(CafeJob.scheduled_at).limit(20))).scalars().all():
        thread = await db.get(CafeThread, job.thread_id)
        if not thread or not thread.approved:
            continue
        token = await protocol.claim(db, job.id, uid, job.account_id)
        if not token:
            continue                 # 남이 가져갔거나 그 계정이 바쁘다
        return [ClaimedCafeJob(id=job.id, lock_token=token, account_id=job.account_id,
                               cafe_url=job.cafe_url, board_name=job.board_name,
                               title=thread.title, body=thread.body)]
    return []


class CheckpointIn(BaseModel):
    lock_token: str = Field(min_length=1, max_length=64)
    stage: str = Field(default="heartbeat", pattern="^(heartbeat|posting)$")


@router.post("/agent/jobs/{job_id}/checkpoint")
async def agent_checkpoint(job_id: str, body: CheckpointIn,
                           current_user: User = Depends(get_current_user),
                           db: AsyncSession = Depends(get_db)):
    try:
        return await protocol.checkpoint(db, job_id, str(current_user.id), body.lock_token, body.stage)
    except protocol.Conflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))


class ResultIn(BaseModel):
    lock_token: str = Field(min_length=1, max_length=64)
    ok: bool
    uncertain: bool = False
    release: bool = False
    url: Optional[str] = Field(None, max_length=500)
    message: Optional[str] = Field(None, max_length=500)


@router.post("/agent/jobs/{job_id}/result")
async def agent_result(job_id: str, body: ResultIn,
                       current_user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db)):
    try:
        return await protocol.result(db, job_id, str(current_user.id), body.lock_token,
                                     body.model_dump(exclude={"lock_token"}))
    except protocol.Conflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
