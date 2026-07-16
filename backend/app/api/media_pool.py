"""
사진 풀 & 자동 유니크화 API
- 사진 40~50장 미리 업로드 → 글마다 자동 배정 + 유니크화(중복 회피 + 품질 유지)
- 변형 pHash 로그로 글 간 중복까지 회피
"""
import io
import base64
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import select, func, delete as sa_delete
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from PIL import Image, ImageOps

from app.api.deps import get_current_user, get_db
from app.models import User
from app.models.media_pool import (
    PoolImage, ImageVariant, PoolCollection, PoolCollectionMember,
)
from app.services import image_uniquifier as uniq

router = APIRouter()

MAX_POOL_SIZE = 200            # 사용자당 풀 상한
THUMB_WIDTH = 200

# 업로드 시 원본을 그대로 두지 않고 표시 최대폭(1280) JPEG 로 정규화해서 보관한다.
# 배정(assign) 단계에서 어차피 MAX_WIDTH 로 축소하므로 원본 해상도는 저장할 이유가 없고,
# 6MB PNG 70장(=420MB)이 볼륨을 채워 SQLite 가 disk-full 로 죽는 것을 막는다.
UPLOAD_JPEG_QUALITY = 88
COMMIT_BATCH = 10              # 이만큼씩 커밋 — 중간 실패해도 앞부분은 살린다
DISK_FULL_MESSAGE = (
    "서버 저장 공간이 부족해 업로드를 중단했습니다. "
    "풀에서 쓰지 않는 사진을 정리한 뒤 다시 시도해주세요."
)


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
    message: Optional[str] = None      # 중단 사유(디스크 부족 등) — 있으면 프론트에 그대로 노출


class CollectionItem(BaseModel):
    id: str
    name: str
    count: int
    created_at: datetime
    cover_thumbnail: Optional[str] = None   # 대표 썸네일(첫 사진)


class CollectionListResponse(BaseModel):
    total: int
    collections: List[CollectionItem]


class CreateCollectionRequest(BaseModel):
    name: str
    image_ids: List[str] = []               # 생성과 동시에 담을 기존 풀 사진(옵션)


class RenameCollectionRequest(BaseModel):
    name: str


class CollectionMembersRequest(BaseModel):
    image_ids: List[str]


class AssignRequest(BaseModel):
    count: int = 5
    post_id: Optional[str] = None
    max_width: int = uniq.MAX_WIDTH
    collection_id: Optional[str] = None     # 지정 시 이 목록에서만 배정


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
def _thumb_from_image(im: Image.Image) -> Optional[str]:
    try:
        t = im.copy()
        t.thumbnail((THUMB_WIDTH, THUMB_WIDTH))
        buf = io.BytesIO()
        t.convert("RGB").save(buf, "JPEG", quality=70)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def _normalize_upload(data: bytes) -> tuple:
    """업로드 원본 → 표시 최대폭 JPEG 로 축소. (bytes, width, height, phash, thumbnail) 반환.

    CPU 작업이므로 반드시 threadpool 에서 호출할 것.
    """
    im = Image.open(io.BytesIO(data))
    im = ImageOps.exif_transpose(im)     # 회전 정보를 픽셀에 반영(EXIF 는 버려짐)
    im = im.convert("RGB")
    if im.width > uniq.MAX_WIDTH:
        h = max(1, round(im.height * uniq.MAX_WIDTH / im.width))
        im = im.resize((uniq.MAX_WIDTH, h), Image.Resampling.LANCZOS)
    ph = uniq.to_hex(uniq.phash(im))
    thumb = _thumb_from_image(im)        # 목록 조회용으로 미리 생성해 둔다
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=UPLOAD_JPEG_QUALITY, optimize=True)
    return buf.getvalue(), im.width, im.height, ph, thumb


def _to_item(p: PoolImage, with_thumb: bool = False) -> PoolItem:
    return PoolItem(
        id=p.id, filename=p.filename, width=p.width, height=p.height,
        size_bytes=p.size_bytes, use_count=p.use_count or 0, created_at=p.created_at,
        thumbnail=p.thumbnail if with_thumb else None,
    )


# ==================== Endpoints ====================
async def _get_owned_collection(db: AsyncSession, user_id: str, collection_id: str) -> PoolCollection:
    res = await db.execute(
        select(PoolCollection).where(
            PoolCollection.id == collection_id, PoolCollection.user_id == user_id
        )
    )
    col = res.scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="목록을 찾을 수 없습니다")
    return col


@router.post("/pool/upload", response_model=UploadResponse)
async def upload_pool_images(
    files: List[UploadFile] = File(...),
    collection_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """사진을 풀에 업로드 (여러 장). collection_id 지정 시 해당 목록에도 담는다."""
    if collection_id:
        await _get_owned_collection(db, str(current_user.id), collection_id)

    count_res = await db.execute(
        select(func.count()).select_from(PoolImage).where(
            PoolImage.user_id == str(current_user.id), PoolImage.active == True  # noqa: E712
        )
    )
    current = count_res.scalar() or 0

    committed: List[PoolItem] = []   # 커밋까지 끝난 것만
    pending: List[PoolItem] = []     # flush 됐지만 아직 커밋 전
    message: Optional[str] = None

    for f in files:
        if current + len(committed) + len(pending) >= MAX_POOL_SIZE:
            continue
        try:
            raw = await f.read()
            data, w, h, ph, thumb = await run_in_threadpool(_normalize_upload, raw)
        except Exception:
            continue                 # 이미지가 아닌 파일 등 — 세션은 멀쩡하므로 다음 장으로

        row = PoolImage(
            user_id=str(current_user.id), filename=f.filename,
            content_type="image/jpeg", data=data, thumbnail=thumb,
            original_phash=ph, width=w, height=h, size_bytes=len(data),
        )
        try:
            db.add(row)
            await db.flush()
            if collection_id:
                db.add(PoolCollectionMember(
                    collection_id=collection_id, pool_image_id=row.id,
                    user_id=str(current_user.id),
                ))
                await db.flush()
            # 썸네일은 커밋 전에 만들어 둔다(커밋 후엔 row 속성이 만료됨)
            pending.append(_to_item(row, with_thumb=True))
            if len(pending) >= COMMIT_BATCH:
                await db.commit()
                committed.extend(pending)
                pending.clear()
        except OperationalError:
            # 디스크 부족 등 — 세션이 롤백 대기 상태가 되므로 계속 돌리면 안 된다.
            # (이 처리를 건너뛰면 이후 전 장이 실패하고 마지막 commit 이 PendingRollbackError 로 터진다)
            await db.rollback()
            pending.clear()
            message = DISK_FULL_MESSAGE
            break

    if pending:
        try:
            await db.commit()
            committed.extend(pending)
        except OperationalError:
            await db.rollback()
            message = DISK_FULL_MESSAGE

    return UploadResponse(
        uploaded=len(committed), failed=len(files) - len(committed),
        images=committed, message=message,
    )


@router.get("/pool", response_model=PoolListResponse)
async def list_pool(
    collection_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """풀 목록 (썸네일 포함). collection_id 지정 시 그 목록의 사진만.

    주의: 원본 BLOB(PoolImage.data)은 절대 SELECT 하지 않는다.
    전체 행을 로드하면 풀 크기에 비례해 메모리가 늘어 1GB 머신에서 OOM 이 난다(실측 95장=484MB).
    미리 만들어둔 thumbnail 컬럼만 읽어 조회 비용을 풀 크기와 무관하게 유지한다.
    """
    stmt = select(
        PoolImage.id, PoolImage.filename, PoolImage.width, PoolImage.height,
        PoolImage.size_bytes, PoolImage.use_count, PoolImage.created_at,
        PoolImage.thumbnail,
    ).where(
        PoolImage.user_id == str(current_user.id), PoolImage.active == True  # noqa: E712
    )
    if collection_id:
        stmt = stmt.join(
            PoolCollectionMember, PoolCollectionMember.pool_image_id == PoolImage.id
        ).where(PoolCollectionMember.collection_id == collection_id)
    stmt = stmt.order_by(PoolImage.use_count.asc(), PoolImage.created_at.desc())
    res = await db.execute(stmt)
    rows = res.all()
    return PoolListResponse(
        total=len(rows),
        images=[
            PoolItem(
                id=r.id, filename=r.filename, width=r.width, height=r.height,
                size_bytes=r.size_bytes, use_count=r.use_count or 0,
                created_at=r.created_at, thumbnail=r.thumbnail,
            )
            for r in rows
        ],
    )


# ==================== 목록(컬렉션) ====================
async def _collection_count(db: AsyncSession, collection_id: str) -> int:
    res = await db.execute(
        select(func.count()).select_from(PoolCollectionMember)
        .join(PoolImage, PoolImage.id == PoolCollectionMember.pool_image_id)
        .where(
            PoolCollectionMember.collection_id == collection_id,
            PoolImage.active == True,  # noqa: E712
        )
    )
    return res.scalar() or 0


async def _collection_cover(db: AsyncSession, collection_id: str) -> Optional[str]:
    # list_pool 과 같은 이유로 data 는 읽지 않고 미리 만들어둔 썸네일만 읽는다.
    res = await db.execute(
        select(PoolImage.thumbnail).join(
            PoolCollectionMember, PoolCollectionMember.pool_image_id == PoolImage.id
        ).where(
            PoolCollectionMember.collection_id == collection_id,
            PoolImage.active == True,  # noqa: E712
        ).order_by(PoolCollectionMember.created_at.asc()).limit(1)
    )
    return res.scalar_one_or_none()


@router.get("/collections", response_model=CollectionListResponse)
async def list_collections(
    with_cover: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내 사진 목록(앨범) 전체."""
    res = await db.execute(
        select(PoolCollection).where(PoolCollection.user_id == str(current_user.id))
        .order_by(PoolCollection.created_at.desc())
    )
    cols = res.scalars().all()
    out: List[CollectionItem] = []
    for c in cols:
        out.append(CollectionItem(
            id=c.id, name=c.name, created_at=c.created_at,
            count=await _collection_count(db, c.id),
            cover_thumbnail=(await _collection_cover(db, c.id)) if with_cover else None,
        ))
    return CollectionListResponse(total=len(out), collections=out)


@router.post("/collections", response_model=CollectionItem)
async def create_collection(
    req: CreateCollectionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="목록 이름을 입력하세요")
    col = PoolCollection(user_id=str(current_user.id), name=name)
    db.add(col)
    await db.flush()
    # 생성과 동시에 기존 사진 담기(옵션)
    for iid in req.image_ids:
        db.add(PoolCollectionMember(
            collection_id=col.id, pool_image_id=iid, user_id=str(current_user.id),
        ))
    await db.commit()
    return CollectionItem(
        id=col.id, name=col.name, created_at=col.created_at,
        count=len(req.image_ids), cover_thumbnail=None,
    )


@router.patch("/collections/{collection_id}", response_model=CollectionItem)
async def rename_collection(
    collection_id: str,
    req: RenameCollectionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    col = await _get_owned_collection(db, str(current_user.id), collection_id)
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="목록 이름을 입력하세요")
    col.name = name
    await db.commit()
    return CollectionItem(
        id=col.id, name=col.name, created_at=col.created_at,
        count=await _collection_count(db, col.id),
        cover_thumbnail=await _collection_cover(db, col.id),
    )


@router.delete("/collections/{collection_id}")
async def delete_collection(
    collection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """목록만 삭제(사진 원본은 풀에 남김)."""
    col = await _get_owned_collection(db, str(current_user.id), collection_id)
    await db.execute(
        sa_delete(PoolCollectionMember).where(
            PoolCollectionMember.collection_id == collection_id
        )
    )
    await db.delete(col)
    await db.commit()
    return {"success": True}


@router.post("/collections/{collection_id}/members")
async def add_collection_members(
    collection_id: str,
    req: CollectionMembersRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """기존 풀 사진을 목록에 추가(중복은 건너뜀)."""
    await _get_owned_collection(db, str(current_user.id), collection_id)
    existing_res = await db.execute(
        select(PoolCollectionMember.pool_image_id).where(
            PoolCollectionMember.collection_id == collection_id
        )
    )
    existing = {pid for (pid,) in existing_res.all()}
    added = 0
    for iid in req.image_ids:
        if iid in existing:
            continue
        db.add(PoolCollectionMember(
            collection_id=collection_id, pool_image_id=iid, user_id=str(current_user.id),
        ))
        added += 1
    await db.commit()
    return {"success": True, "added": added}


@router.delete("/collections/{collection_id}/members/{image_id}")
async def remove_collection_member(
    collection_id: str,
    image_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """목록에서 사진 하나 빼기(원본은 풀에 유지)."""
    await _get_owned_collection(db, str(current_user.id), collection_id)
    await db.execute(
        sa_delete(PoolCollectionMember).where(
            PoolCollectionMember.collection_id == collection_id,
            PoolCollectionMember.pool_image_id == image_id,
        )
    )
    await db.commit()
    return {"success": True}


@router.delete("/pool/{image_id}")
async def delete_pool_image(
    image_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(PoolImage).where(PoolImage.id == image_id, PoolImage.user_id == str(current_user.id))
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

    # 후보: 적게 쓴 순으로 넉넉히 확보(대체 여지). 목록 지정 시 그 목록에서만.
    stmt = select(PoolImage).where(
        PoolImage.user_id == str(current_user.id), PoolImage.active == True  # noqa: E712
    )
    if req.collection_id:
        await _get_owned_collection(db, str(current_user.id), req.collection_id)
        stmt = stmt.join(
            PoolCollectionMember, PoolCollectionMember.pool_image_id == PoolImage.id
        ).where(PoolCollectionMember.collection_id == req.collection_id)
    stmt = stmt.order_by(
        PoolImage.use_count.asc(), PoolImage.last_used_at.asc(), PoolImage.created_at.asc()
    ).limit(req.count * 3)
    res = await db.execute(stmt)
    candidates = res.scalars().all()
    if not candidates:
        detail = (
            "목록에 사진이 없습니다. 먼저 목록에 사진을 담으세요."
            if req.collection_id else "풀에 사진이 없습니다. 먼저 업로드하세요."
        )
        raise HTTPException(status_code=400, detail=detail)

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
            pool_image_id=p.id, user_id=str(current_user.id),
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


# ==================== 고정 이미지 유니크화 (본문 하단 고정 삽입용) ====================
class UniquifyOneRequest(BaseModel):
    image: str                       # data URL 또는 base64
    sibling_hashes: List[str] = []   # 과거 변형 pHash(글마다 다르게)
    max_width: int = uniq.MAX_WIDTH


class UniquifyOneResponse(BaseModel):
    image: str                       # 유니크화된 data URL
    phash: str
    passed: bool
    min_distance: int


@router.post("/uniquify-one", response_model=UniquifyOneResponse)
async def uniquify_one(
    req: UniquifyOneRequest,
    current_user: User = Depends(get_current_user),
):
    """임의 이미지 1장을 유니크화해서 반환(고정 하단 이미지가 글마다 다른 변형으로 들어가도록).
    DB 미사용 — 클라이언트가 sibling_hashes 를 누적 전달해 글 간 중복 회피."""
    raw = req.image or ""
    if "," in raw and raw.strip().startswith("data:"):
        raw = raw.split(",", 1)[1]
    try:
        data = base64.b64decode(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="이미지 디코딩 실패")

    result = await run_in_threadpool(
        uniq.uniquify, data, sibling_hashes=req.sibling_hashes, max_width=req.max_width,
    )
    if result is None:
        raise HTTPException(status_code=400, detail="유니크화 실패(이미지 확인)")

    return UniquifyOneResponse(
        image="data:image/jpeg;base64," + base64.b64encode(result.image_bytes).decode(),
        phash=result.phash, passed=result.passed, min_distance=result.min_distance,
    )
