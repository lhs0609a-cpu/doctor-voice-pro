"""카페 바이럴 스레드 API — 만들고, 고치고, 검수한다. 올리는 것은 사람이 한다.

사람이 본문이나 댓글을 고치면 **그 자리에서 다시 검수한다**. 고친 뒤에도 '통과'라고
적혀 있으면 그 표시는 거짓말이 된다.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.cafe_thread import CafeThread
from app.models.campaign import Client
from app.models.user import User
from app.services import cafe_thread as service

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
