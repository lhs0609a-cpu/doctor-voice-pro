"""
사진 풀 & 자동 유니크화 API
- 사진 40~50장 미리 업로드 → 글마다 자동 배정 + 유니크화(중복 회피 + 품질 유지)
- 변형 pHash 로그로 글 간 중복까지 회피
"""
import io
import base64
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from PIL import Image

from app.api.deps import get_current_user, get_db
from app.models import User
from app.models.media_pool import PoolImage, ImageVariant
from app.services import image_uniquifier as uniq

router = APIRouter()

MAX_POOL_SIZE = 200            # 사용자당 풀 상한
THUMB_WIDTH = 200


# ==================== Schemas ====================
class PoolItem(BaseModel):
    id: str
    filename: Optional[str]
    width: Optional[int]
    height: Optional[int]
    size_bytes: Optional[int]
    use_count: int
    created_at: datetime
    thumbnail: Optional[str] = None   # data URL (base64)


class PoolListResponse(BaseModel):
    total: int
    images: List[PoolItem]


class UploadResponse(BaseModel):
    uploaded: int
    failed: int
    images: List[PoolItem]


class AssignRequest(BaseModel):
    count: int = 5
    post_id: Optional[str] = None
    max_width: int = uniq.MAX_WIDTH


class AssignedImage(BaseModel):
    pool_image_id: str
    filename: Optional[str]
    image: str                 # data URL (유니크화된 JPEG base64)
    phash: str
    frame_style: str
    ssim: float
    min_distance: int
    passed: bool


class AssignResponse(BaseModel):
    requested: int
    returned: int
    all_passed: bool
    images: List[AssignedImage]
    warnings: List[str] = []


# ==================== Helpers ====================
def _thumb_data_url(data: bytes) -> Optional[str]:
    try:
        im = Image.open(io.BytesIO(data))
        im.thumbnail((THUMB_WIDTH, THUMB_WIDTH))
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "JPEG", quality=70)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def _to_item(p: PoolImage, with_thumb: bool = False) -> PoolItem:
    return PoolItem(
        id=p.id, filename=p.filename, width=p.width, height=p.height,
        size_bytes=p.size_bytes, use_count=p.use_count or 0, created_at=p.created_at,
        thumbnail=_thumb_data_url(p.data) if with_thumb else None,
    )


# ==================== Endpoints ====================
@router.post("/pool/upload", response_model=UploadResponse)
async def upload_pool_images(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """사진을 풀에 업로드 (여러 장). 원본 pHash/크기 기록."""
    count_res = await db.execute(
        select(func.count()).select_from(PoolImage).where(
            PoolImage.user_id == current_user.id, PoolImage.active == True  # noqa: E712
        )
    )
    current = count_res.scalar() or 0

    uploaded, failed, items = 0, 0, []
    for f in files:
        if current + uploaded >= MAX_POOL_SIZE:
            failed += 1
            continue
        try:
            data = await f.read()
            im = Image.open(io.BytesIO(data))
            im.load()
            w, h = im.size
            ph = uniq.to_hex(uniq.phash(im))
            row = PoolImage(
                user_id=current_user.id, filename=f.filename,
                content_type=f.content_type or "image/jpeg", data=data,
                original_phash=ph, width=w, height=h, size_bytes=len(data),
            )
            db.add(row)
            await db.flush()
            items.append(_to_item(row, with_thumb=True))
            uploaded += 1
        except Exception:
            failed += 1
    await db.commit()
    return UploadResponse(uploaded=uploaded, failed=failed, images=items)


@router.get("/pool", response_model=PoolListResponse)
async def list_pool(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """풀 목록 (썸네일 포함)"""
    res = await db.execute(
        select(PoolImage).where(
            PoolImage.user_id == current_user.id, PoolImage.active == True  # noqa: E712
        ).order_by(PoolImage.use_count.asc(), PoolImage.created_at.desc())
    )
    rows = res.scalars().all()
    return PoolListResponse(total=len(rows), images=[_to_item(r, with_thumb=True) for r in rows])


@router.delete("/pool/{image_id}")
async def delete_pool_image(
    image_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(PoolImage).where(PoolImage.id == image_id, PoolImage.user_id == current_user.id)
    )
    row = res.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="사진을 찾을 수 없습니다")
    row.active = False
    await db.commit()
    return {"success": True}


@router.post("/assign", response_model=AssignResponse)
async def assign_and_uniquify(
    req: AssignRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """풀에서 '가장 적게 쓴' 사진을 count 만큼 자동 배정하고 각각 유니크화.

    - 같은 원본의 과거 변형 pHash 를 회피셋으로 넣어 글 간 중복까지 방지.
    - 통과 못한 사진은 건너뛰고 다음 후보로 대체(풀이 크면 자연 해결).
    """
    if req.count < 1:
        raise HTTPException(status_code=400, detail="count는 1 이상이어야 합니다")

    # 후보: 적게 쓴 순으로 넉넉히 확보(대체 여지)
    res = await db.execute(
        select(PoolImage).where(
            PoolImage.user_id == current_user.id, PoolImage.active == True  # noqa: E712
        ).order_by(PoolImage.use_count.asc(), PoolImage.last_used_at.asc(),
                   PoolImage.created_at.asc())
        .limit(req.count * 3)
    )
    candidates = res.scalars().all()
    if not candidates:
        raise HTTPException(status_code=400, detail="풀에 사진이 없습니다. 먼저 업로드하세요.")

    out: List[AssignedImage] = []
    warnings: List[str] = []

    for p in candidates:
        if len(out) >= req.count:
            break
        # 이 원본의 과거 변형 해시(형제) 수집
        sib_res = await db.execute(
            select(ImageVariant.phash).where(ImageVariant.pool_image_id == p.id)
        )
        siblings = [s for (s,) in sib_res.all() if s]

        result = await run_in_threadpool(
            uniq.uniquify, p.data,
            sibling_hashes=siblings, max_width=req.max_width,
        )
        if result is None:
            continue

        # 변형 이력 기록 + 사용 카운트 증가
        db.add(ImageVariant(
            pool_image_id=p.id, user_id=current_user.id,
            phash=result.phash, dhash=result.dhash, frame_style=result.frame_style,
            ssim=result.ssim, min_distance=result.min_distance, passed=result.passed,
            post_id=req.post_id,
        ))
        p.use_count = (p.use_count or 0) + 1
        p.last_used_at = datetime.utcnow()

        if not result.passed:
            warnings.append(f"{p.filename or p.id}: 유니크화 임계 미달(거리 {result.min_distance}) — 재사용 과다 가능")

        out.append(AssignedImage(
            pool_image_id=p.id, filename=p.filename,
            image="data:image/jpeg;base64," + base64.b64encode(result.image_bytes).decode(),
            phash=result.phash, frame_style=result.frame_style, ssim=result.ssim,
            min_distance=result.min_distance, passed=result.passed,
        ))

    await db.commit()

    if len(out) < req.count:
        warnings.append(f"요청 {req.count}장 중 {len(out)}장만 배정됨(풀 사진 부족).")

    return AssignResponse(
        requested=req.count, returned=len(out),
        all_passed=all(a.passed for a in out) if out else False,
        images=out, warnings=warnings,
    )
