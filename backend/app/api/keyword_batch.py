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


class VolumeItem(BaseModel):
    keyword: str
    monthly_pc: int
    monthly_mobile: int
    total_volume: int
    competition: str          # low | mid | high
    comp_idx_raw: str = ""
    est_cpc: int = 0


@router.post("/volumes", response_model=List[VolumeItem])
async def get_keyword_volumes(
    req: VolumeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    키워드 실검색량/경쟁도 조회 (네이버 검색광고 API, 하루 단위 캐시).
    자격증명 미설정 시 전 항목 0으로 반환(프론트가 '미설정' 안내 가능).
    """
    metrics = await search_volume_service.get_keyword_metrics(
        db, req.keywords[:100]
    )
    return [VolumeItem(**m) for m in metrics]


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
