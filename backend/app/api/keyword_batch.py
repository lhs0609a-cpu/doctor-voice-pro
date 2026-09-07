"""
Keyword Batch API
키워드 대량 생성 - 프롬프트 템플릿 서버 동기화(계정별).

프론트는 템플릿 목록 전체를 통째로 저장한다(추가/수정/삭제 후 배열 저장).
그 방식에 맞춰 GET(목록)·PUT(전체 교체) 두 개만 둔다.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List
from datetime import datetime
from pydantic import BaseModel

from app.db.database import get_db
from app.models import User
from app.models.keyword_template import KeywordPromptTemplate
from app.api.deps import get_current_user
from app.services import search_volume_service

router = APIRouter()


class TemplateItem(BaseModel):
    id: str
    name: str
    body: str
    updatedAt: int = 0


class VolumeRequest(BaseModel):
    keywords: List[str]
    include_related: bool = True       # 검색광고가 함께 주는 연관검색어도 돌려준다
    related_limit: int = 80            # 연관어 상한(모바일 검색량 순)
    related_min_volume: int = 0        # 이 값 미만의 연관어는 버린다(월 모바일 검색량 기준)


class VolumeItem(BaseModel):
    keyword: str
    monthly_pc: int
    monthly_mobile: int
    total_volume: int
    competition: str          # low | mid | high
    comp_idx_raw: str = ""
    est_cpc: int = 0
    is_related: bool = False           # True 면 입력한 키워드가 아니라 연관검색어
    related_of: str = ""               # 어떤 입력 키워드의 연관어인지(대표 1개)


@router.post("/volumes", response_model=List[VolumeItem])
async def get_keyword_volumes(
    req: VolumeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    키워드 실검색량/경쟁도 조회 (네이버 검색광고 API, 하루 단위 캐시).
    include_related 면 검색광고 응답에 함께 오는 연관검색어(예: 임플란트 → 임플란트가격, 강남임플란트 …)도
    검색량과 함께 돌려준다. 연관어는 요청한 키워드 다음에, 모바일 검색량 순으로 붙는다.
    자격증명 미설정 시 전 항목 0으로 반환(프론트가 '미설정' 안내 가능).
    """
    keywords = [k.strip() for k in req.keywords if k and k.strip()][:100]
    if not keywords:
        return []

    def _item(m: dict, is_related: bool = False, related_of: str = "") -> VolumeItem:
        return VolumeItem(
            keyword=m["keyword"], monthly_pc=m["monthly_pc"], monthly_mobile=m["monthly_mobile"],
            total_volume=m["total_volume"], competition=m["competition"],
            comp_idx_raw=m.get("comp_idx_raw", "") or "", est_cpc=m.get("est_cpc", 0) or 0,
            is_related=is_related, related_of=related_of,
        )

    if not (req.include_related and search_volume_service.is_configured()):
        metrics = await search_volume_service.get_keyword_metrics(db, keywords)
        return [_item(m) for m in metrics]

    # 연관어까지 받으려면 API 를 직접 불러야 한다(캐시에는 연관어가 없다).
    # 입력 키워드는 5개씩 나눠 호출하되, 어느 입력의 연관어인지 알 수 있게 묶음별로 호출한다.
    today = datetime.utcnow().date()
    wanted_all: dict = {}
    related_all: dict = {}
    for i in range(0, len(keywords), search_volume_service.MAX_HINTS_PER_CALL):
        chunk = keywords[i : i + search_volume_service.MAX_HINTS_PER_CALL]
        wanted, related = await search_volume_service.fetch_with_related(chunk)
        for nk, m in wanted.items():
            wanted_all[nk] = m
            await search_volume_service._upsert_cache(db, nk, m, today)
        for nk, m in related.items():
            if nk not in related_all and nk not in wanted_all:
                related_all[nk] = (m, chunk[0] if len(chunk) == 1 else ", ".join(chunk))
                await search_volume_service._upsert_cache(db, nk, m, today)
    try:
        await db.commit()
    except Exception:  # noqa: BLE001
        await db.rollback()

    out: List[VolumeItem] = []
    for k in keywords:
        nk = search_volume_service._normalize(k)
        m = wanted_all.get(nk)
        if m:
            out.append(_item(m))
        else:
            out.append(VolumeItem(keyword=k, monthly_pc=0, monthly_mobile=0, total_volume=0, competition="mid"))
    rel = [(m, of) for (m, of) in related_all.values() if m["monthly_mobile"] >= req.related_min_volume]
    rel.sort(key=lambda x: -x[0]["monthly_mobile"])
    out.extend(_item(m, True, of) for (m, of) in rel[: max(0, req.related_limit)])
    return out


@router.get("/volumes/status")
async def get_volume_api_status(
    current_user: User = Depends(get_current_user),
):
    """검색광고 API 자격증명 설정 여부(프론트 안내용)."""
    return {"configured": search_volume_service.is_configured()}


def _to_ms(dt) -> int:
    try:
        return int(dt.timestamp() * 1000)
    except Exception:
        return 0


@router.get("/templates", response_model=List[TemplateItem])
async def get_templates(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """계정에 저장된 프롬프트 템플릿 목록 (생성순)."""
    result = await db.execute(
        select(KeywordPromptTemplate)
        .where(KeywordPromptTemplate.user_id == current_user.id)
        .order_by(KeywordPromptTemplate.created_at)
    )
    rows = result.scalars().all()
    return [
        TemplateItem(id=r.client_id, name=r.name, body=r.body, updatedAt=_to_ms(r.updated_at))
        for r in rows
    ]


@router.put("/templates", response_model=List[TemplateItem])
async def replace_templates(
    items: List[TemplateItem],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    사용자의 템플릿 전체를 교체한다.
    프론트가 목록 전체를 보내므로, 기존 것을 지우고 받은 것으로 새로 채운다.
    """
    await db.execute(
        delete(KeywordPromptTemplate).where(
            KeywordPromptTemplate.user_id == current_user.id
        )
    )
    for it in items:
        db.add(
            KeywordPromptTemplate(
                user_id=current_user.id,
                client_id=(it.id or "")[:64],
                name=(it.name or "")[:200],
                body=it.body or "",
            )
        )
    await db.commit()
    return items
