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

router = APIRouter()


class TemplateItem(BaseModel):
    id: str
    name: str
    body: str
    updatedAt: int = 0


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
