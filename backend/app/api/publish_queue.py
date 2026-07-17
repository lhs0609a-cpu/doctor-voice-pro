"""
대량 자동발행 큐 API.
- /queue/preview : 붙여넣기 글을 자동 포맷해 미리보기(저장 X)
- /queue/bulk    : 여러 글을 포맷 + 예약시각 배정 + 사진 배정하여 큐 저장
- /queue         : 큐 목록
- /queue/{id}, /queue/batch/{id} : 삭제
- /queue/jobs    : (확장용) 대기 글을 조립+유니크화 이미지 포함해 반환, registered 표시
- /queue/{id}/result : (확장용) 네이버 예약등록 결과 보고
"""
import base64
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import select, func, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import User
from app.models.publish_queue import PublishBatch, QueuedPost, NaverCategoryCache
from app.models.media_pool import PoolImage, ImageVariant
from app.services import post_formatter as fmt
from app.services import image_uniquifier as uniq

router = APIRouter()

MAX_QUEUE = 2000  # 사용자당 큐 상한(안전장치)


# ==================== Schemas ====================
class PreviewRequest(BaseModel):
    text: str
    delimiter: str = ""          # 여러 글 구분자(빈 값이면 빈 줄 2개로 분리)
    top_keywords: int = 6


class BlockOut(BaseModel):
    type: str
    content: Optional[str] = None
    keyword: Optional[str] = None


class FormattedOut(BaseModel):
    title: str
    keywords: List[str]
    hashtags: List[str]
    image_slots: int
    blocks: List[BlockOut]


class PreviewResponse(BaseModel):
    count: int
    posts: List[FormattedOut]


class BulkRequest(BaseModel):
    text: str
    delimiter: str = ""
    top_keywords: int = 6
    start_at: datetime                 # 첫 글 예약시각
    interval_minutes: int = 120        # 글 사이 간격
    open_type: str = "public"
    # 네이버 카테고리 번호(예: "24"). None 이면 네이버 기본 카테고리로 발행.
    category: Optional[str] = None
    assign_images: bool = True         # 사진 풀에서 자동 배정
    name: Optional[str] = None


class QueuedItem(BaseModel):
    id: str
    title: str
    keywords: List[str]
    image_slots: int
    scheduled_at: datetime
    status: str
    order_index: int


class BulkResponse(BaseModel):
    batch_id: str
    created: int
    first_at: datetime
    last_at: datetime
    items: List[QueuedItem]
    warnings: List[str] = []


def _fmt_to_out(p: fmt.FormattedPost) -> FormattedOut:
    return FormattedOut(
        title=p.title, keywords=p.keywords, hashtags=p.hashtags,
        image_slots=p.image_slots,
        blocks=[BlockOut(type=b.type, content=b.content or None, keyword=b.keyword) for b in p.blocks],
    )


# ==================== Preview ====================
@router.post("/queue/preview", response_model=PreviewResponse)
async def preview(req: PreviewRequest, current_user: User = Depends(get_current_user)):
    chunks = fmt.split_bulk(req.text, req.delimiter)
    posts = [fmt.format_post(c, top_keywords=req.top_keywords) for c in chunks]
    return PreviewResponse(count=len(posts), posts=[_fmt_to_out(p) for p in posts])


# ==================== Bulk create ====================
@router.post("/queue/bulk", response_model=BulkResponse)
async def bulk_create(
    req: BulkRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chunks = fmt.split_bulk(req.text, req.delimiter)
    if not chunks:
        raise HTTPException(status_code=400, detail="등록할 글이 없습니다")

    # 큐 상한 확인
    cnt_res = await db.execute(
        select(func.count()).select_from(QueuedPost).where(
            QueuedPost.user_id == str(current_user.id), QueuedPost.status == "queued"
        )
    )
    existing = cnt_res.scalar() or 0
    if existing + len(chunks) > MAX_QUEUE:
        raise HTTPException(status_code=400, detail=f"큐 상한({MAX_QUEUE})을 초과합니다. 현재 {existing}건.")

    warnings: List[str] = []

    # 사진 풀(적게 쓴 순) 확보 — 배정용
    pool_ids: List[str] = []
    if req.assign_images:
        pres = await db.execute(
            select(PoolImage.id).where(
                PoolImage.user_id == str(current_user.id), PoolImage.active == True  # noqa: E712
            ).order_by(PoolImage.use_count.asc(), PoolImage.created_at.asc())
        )
        pool_ids = [r for (r,) in pres.all()]
    if req.assign_images and not pool_ids:
        warnings.append("사진 풀이 비어 있어 이미지 없이 저장됩니다. 먼저 사진 풀에 업로드하세요.")

    batch = PublishBatch(
        user_id=str(current_user.id), name=req.name or f"대량발행 {len(chunks)}건",
        start_at=req.start_at, interval_minutes=req.interval_minutes,
        open_type=req.open_type, category=req.category, total=len(chunks),
    )
    db.add(batch)
    await db.flush()

    # round-robin 으로 풀 이미지 배정(고르게)
    ptr = 0
    items: List[QueuedItem] = []
    for i, chunk in enumerate(chunks):
        p = fmt.format_post(chunk, top_keywords=req.top_keywords)
        sched = req.start_at + timedelta(minutes=req.interval_minutes * i)

        assigned: List[str] = []
        if req.assign_images and pool_ids and p.image_slots:
            for _ in range(p.image_slots):
                assigned.append(pool_ids[ptr % len(pool_ids)])
                ptr += 1

        row = QueuedPost(
            user_id=str(current_user.id), batch_id=batch.id,
            title=p.title,
            blocks=[{"type": b.type, "content": b.content, "keyword": b.keyword} for b in p.blocks],
            keywords=p.keywords, hashtags=p.hashtags,
            image_pool_ids=assigned, image_slots=p.image_slots,
            scheduled_at=sched, open_type=req.open_type, search=True,
            category=req.category,
            status="queued", order_index=i,
        )
        db.add(row)
        items.append(QueuedItem(
            id=row.id, title=p.title, keywords=p.keywords, image_slots=p.image_slots,
            scheduled_at=sched, status="queued", order_index=i,
        ))

    await db.commit()
    return BulkResponse(
        batch_id=batch.id, created=len(items),
        first_at=items[0].scheduled_at, last_at=items[-1].scheduled_at,
        items=items, warnings=warnings,
    )


# ==================== List / Delete ====================
@router.get("/queue", response_model=List[QueuedItem])
async def list_queue(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(QueuedPost).where(QueuedPost.user_id == str(current_user.id))
    if status:
        q = q.where(QueuedPost.status == status)
    q = q.order_by(QueuedPost.scheduled_at.asc())
    res = await db.execute(q)
    rows = res.scalars().all()
    return [
        QueuedItem(
            id=r.id, title=r.title, keywords=r.keywords or [], image_slots=r.image_slots or 0,
            scheduled_at=r.scheduled_at, status=r.status, order_index=r.order_index or 0,
        ) for r in rows
    ]


@router.delete("/queue/{post_id}")
async def delete_queued(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(QueuedPost).where(QueuedPost.id == post_id, QueuedPost.user_id == str(current_user.id))
    )
    row = res.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="찾을 수 없습니다")
    await db.delete(row)
    await db.commit()
    return {"success": True}


@router.delete("/queue/batch/{batch_id}")
async def delete_batch(
    batch_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        sa_delete(QueuedPost).where(
            QueuedPost.batch_id == batch_id, QueuedPost.user_id == str(current_user.id)
        )
    )
    await db.execute(
        sa_delete(PublishBatch).where(
            PublishBatch.id == batch_id, PublishBatch.user_id == str(current_user.id)
        )
    )
    await db.commit()
    return {"success": True}


# ==================== 확장용: job fetch ====================
class JobBlock(BaseModel):
    type: str
    content: Optional[str] = None
    image: Optional[str] = None   # data URL(유니크화 JPEG)


class ExtJob(BaseModel):
    id: str
    title: str
    content: str                  # 텍스트 통합(하위호환)
    blocks: List[JobBlock]        # 글-이미지 인터리브(확장이 순서대로 삽입)
    tags: List[str]
    finalAction: str = "schedule"
    schedule: dict
    options: dict


@router.get("/queue/jobs", response_model=List[ExtJob])
async def fetch_jobs(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """확장이 대기 글을 가져감. 배정된 풀 이미지를 즉석 유니크화해 base64로 포함.
    반환된 글은 registered 로 표시(중복 등록 방지)."""
    res = await db.execute(
        select(QueuedPost).where(
            QueuedPost.user_id == str(current_user.id), QueuedPost.status == "queued"
        ).order_by(QueuedPost.scheduled_at.asc()).limit(limit)
    )
    rows = res.scalars().all()

    jobs: List[ExtJob] = []
    for r in rows:
        pool_ids = r.image_pool_ids or []
        # 배정 풀 이미지 로드
        imgs_by_id = {}
        if pool_ids:
            ires = await db.execute(
                select(PoolImage).where(PoolImage.id.in_(list(set(pool_ids))))
            )
            imgs_by_id = {p.id: p for p in ires.scalars().all()}

        blocks_out: List[JobBlock] = []
        img_ptr = 0
        for b in (r.blocks or []):
            if b.get("type") == "text":
                blocks_out.append(JobBlock(type="text", content=b.get("content") or ""))
            else:
                data_url = None
                if img_ptr < len(pool_ids):
                    pid = pool_ids[img_ptr]
                    pimg = imgs_by_id.get(pid)
                    if pimg:
                        # 형제 변형 해시 수집(글 간 중복 회피)
                        sres = await db.execute(
                            select(ImageVariant.phash).where(ImageVariant.pool_image_id == pid)
                        )
                        siblings = [s for (s,) in sres.all() if s]
                        result = await run_in_threadpool(
                            uniq.uniquify, pimg.data, sibling_hashes=siblings
                        )
                        if result:
                            data_url = "data:image/jpeg;base64," + base64.b64encode(result.image_bytes).decode()
                            db.add(ImageVariant(
                                pool_image_id=pid, user_id=str(current_user.id),
                                phash=result.phash, dhash=result.dhash, frame_style=result.frame_style,
                                ssim=result.ssim, min_distance=result.min_distance, passed=result.passed,
                                post_id=r.id,
                            ))
                            pimg.use_count = (pimg.use_count or 0) + 1
                            pimg.last_used_at = datetime.utcnow()
                    img_ptr += 1
                if data_url:
                    blocks_out.append(JobBlock(type="image", image=data_url))

        content = "\n\n".join(b.content for b in blocks_out if b.type == "text" and b.content)
        r.status = "registered"
        r.registered_at = datetime.utcnow()

        jobs.append(ExtJob(
            id=r.id, title=r.title, content=content, blocks=blocks_out,
            tags=r.hashtags or r.keywords or [],
            finalAction="schedule",
            schedule={"datetime": r.scheduled_at.isoformat()},
            options={
                "openType": r.open_type or "public",
                "search": bool(r.search),
                "category": r.category or None,
            },
        ))

    await db.commit()
    return jobs


# ==================== 카테고리 목록 (확장이 읽어와 캐시) ====================
class CategoryItem(BaseModel):
    id: str
    name: str


class CategoriesResponse(BaseModel):
    categories: List[CategoryItem] = []
    updated_at: Optional[datetime] = None


class CategoriesRequest(BaseModel):
    categories: List[CategoryItem]


@router.get("/categories", response_model=CategoriesResponse)
async def get_categories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """앱 드롭다운용 카테고리 목록. 비어 있으면 아직 동기화 전이다."""
    res = await db.execute(
        select(NaverCategoryCache).where(NaverCategoryCache.user_id == str(current_user.id))
    )
    row = res.scalar_one_or_none()
    if not row:
        return CategoriesResponse()
    return CategoriesResponse(categories=row.categories or [], updated_at=row.updated_at)


@router.post("/categories", response_model=CategoriesResponse)
async def put_categories(
    req: CategoriesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """(확장용) 네이버 에디터에서 읽은 카테고리 목록을 저장."""
    if not req.categories:
        raise HTTPException(status_code=400, detail="카테고리 목록이 비어 있습니다")

    items = [{"id": c.id, "name": c.name} for c in req.categories]
    res = await db.execute(
        select(NaverCategoryCache).where(NaverCategoryCache.user_id == str(current_user.id))
    )
    row = res.scalar_one_or_none()
    if row:
        row.categories = items
        row.updated_at = datetime.utcnow()
    else:
        row = NaverCategoryCache(
            user_id=str(current_user.id), categories=items, updated_at=datetime.utcnow()
        )
        db.add(row)
    await db.commit()
    return CategoriesResponse(categories=req.categories, updated_at=row.updated_at)


class ResultRequest(BaseModel):
    ok: bool
    message: Optional[str] = None


@router.post("/queue/{post_id}/result")
async def report_result(
    post_id: str,
    req: ResultRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(QueuedPost).where(QueuedPost.id == post_id, QueuedPost.user_id == str(current_user.id))
    )
    row = res.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="찾을 수 없습니다")
    row.status = "published" if req.ok else "failed"
    row.naver_result = req.message
    await db.commit()
    return {"success": True}
