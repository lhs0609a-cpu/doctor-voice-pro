"""
Tags API Router
사용자 태그 관리
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List
from uuid import UUID
from pydantic import BaseModel

from app.db.database import get_db
from app.models import User, Tag, Post
from app.api.deps import get_current_user

router = APIRouter()


class TagCreate(BaseModel):
    name: str
    color: str = "#3B82F6"


class TagUpdate(BaseModel):
    name: str | None = None
    color: str | None = None


class TagResponse(BaseModel):
    id: str
    name: str
    color: str
    post_count: int = 0

    class Config:
        from_attributes = True


@router.get("/", response_model=List[TagResponse])
async def get_tags(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """사용자의 모든 태그 조회"""
    result = await db.execute(
        select(Tag).where(Tag.user_id == current_user.id).order_by(Tag.name)
    )
    tags = result.scalars().all()

    # Count posts for each tag
    tag_responses = []
    for tag in tags:
        post_count = len(tag.posts)
        tag_responses.append(
            TagResponse(
                id=str(tag.id),
                name=tag.name,
                color=tag.color,
                post_count=post_count,
            )
        )

    return tag_responses


@router.post("/", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(
    tag_data: TagCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """새로운 태그 생성"""
    # Check if tag already exists
    result = await db.execute(
        select(Tag).where(
            Tag.user_id == current_user.id, Tag.name == tag_data.name
        )
    )
    existing_tag = result.scalar_one_or_none()

    if existing_tag:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 같은 이름의 태그가 있습니다",
        )

    tag = Tag(
        user_id=current_user.id,
        name=tag_data.name,
        color=tag_data.color,
    )

    db.add(tag)
    await db.commit()
    await db.refresh(tag)

    return TagResponse(
        id=str(tag.id),
        name=tag.name,
        color=tag.color,
        post_count=0,
    )


@router.put("/{tag_id}", response_model=TagResponse)
async def update_tag(
    tag_id: UUID,
    tag_data: TagUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """태그 수정"""
    result = await db.execute(
        select(Tag).where(Tag.id == tag_id, Tag.user_id == current_user.id)
    )
    tag = result.scalar_one_or_none()

    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="태그를 찾을 수 없습니다"
        )

    if tag_data.name is not None:
        tag.name = tag_data.name
    if tag_data.color is not None:
        tag.color = tag_data.color

    await db.commit()
    await db.refresh(tag)

    return TagResponse(
        id=str(tag.id),
        name=tag.name,
        color=tag.color,
        post_count=len(tag.posts),
    )


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """태그 삭제"""
    result = await db.execute(
        select(Tag).where(Tag.id == tag_id, Tag.user_id == current_user.id)
    )
    tag = result.scalar_one_or_none()

    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="태그를 찾을 수 없습니다"
        )

    await db.delete(tag)
    await db.commit()

    return None


@router.post("/{tag_id}/posts/{post_id}")
async def add_tag_to_post(
    tag_id: UUID,
    post_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """포스트에 태그 추가"""
    # Fetch tag
    tag_result = await db.execute(
        select(Tag).where(Tag.id == tag_id, Tag.user_id == current_user.id)
    )
    tag = tag_result.scalar_one_or_none()

    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="태그를 찾을 수 없습니다"
        )

    # Fetch post
    post_result = await db.execute(
        select(Post).where(Post.id == post_id, Post.user_id == current_user.id)
    )
    post = post_result.scalar_one_or_none()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="포스팅을 찾을 수 없습니다"
        )

    # Add tag to post
    if tag not in post.tags:
        post.tags.append(tag)
        await db.commit()

    return {"success": True, "message": "태그가 추가되었습니다"}


@router.delete("/{tag_id}/posts/{post_id}")
async def remove_tag_from_post(
    tag_id: UUID,
    post_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """포스트에서 태그 제거"""
    # Fetch tag
    tag_result = await db.execute(
        select(Tag).where(Tag.id == tag_id, Tag.user_id == current_user.id)
    )
    tag = tag_result.scalar_one_or_none()

    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="태그를 찾을 수 없습니다"
        )

    # Fetch post
    post_result = await db.execute(
        select(Post).where(Post.id == post_id, Post.user_id == current_user.id)
    )
    post = post_result.scalar_one_or_none()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="포스팅을 찾을 수 없습니다"
        )

    # Remove tag from post
    if tag in post.tags:
        post.tags.remove(tag)
        await db.commit()

    return {"success": True, "message": "태그가 제거되었습니다"}
