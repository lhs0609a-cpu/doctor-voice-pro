"""
네이버 블로그 API Router
네이버 블로그 연동 및 자동 발행
"""

from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import secrets

from app.db.database import get_db
from app.schemas.naver import (
    NaverAuthCallbackRequest,
    NaverConnectionResponse,
    NaverCategoryResponse,
    NaverPublishRequest,
    NaverPublishResponse,
)
from app.models import User, NaverConnection, Post
from app.api.deps import get_current_user
from app.services.naver_blog_service import naver_blog_service

router = APIRouter()


@router.get("/auth/url")
async def get_naver_auth_url(
    current_user: User = Depends(get_current_user),
):
    """
    네이버 로그인 URL 생성

    OAuth 인증을 시작하기 위한 네이버 로그인 페이지 URL을 반환합니다.
    """
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # TODO: Store state in session or cache for validation
    # For now, we'll just generate it

    redirect_uri = "http://localhost:3000/dashboard/settings/naver/callback"
    auth_url = naver_blog_service.get_authorization_url(redirect_uri, state)

    return {"auth_url": auth_url, "state": state}


@router.post("/auth/callback", response_model=NaverConnectionResponse)
async def naver_auth_callback(
    callback_data: NaverAuthCallbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    네이버 OAuth 콜백 처리

    네이버 로그인 후 리다이렉트된 callback을 처리하고 액세스 토큰을 발급받습니다.
    """
    redirect_uri = "http://localhost:3000/dashboard/settings/naver/callback"

    # TODO: Validate state to prevent CSRF

    # Get access token
    token_response = await naver_blog_service.get_access_token(
        callback_data.code, callback_data.state, redirect_uri
    )

    if not token_response:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="네이버 인증에 실패했습니다.",
        )

    access_token = token_response.get("access_token")
    refresh_token = token_response.get("refresh_token")
    expires_in = token_response.get("expires_in", 3600)

    # Get user profile from Naver
    profile_response = await naver_blog_service.get_user_profile(access_token)

    if not profile_response or profile_response.get("resultcode") != "00":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="네이버 프로필 조회에 실패했습니다.",
        )

    naver_user = profile_response.get("response", {})

    # Get blog info
    blog_info = await naver_blog_service.get_blog_info(access_token)

    # Check if connection already exists
    result = await db.execute(
        select(NaverConnection).where(NaverConnection.user_id == current_user.id)
    )
    connection = result.scalar_one_or_none()

    token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    if connection:
        # Update existing connection
        connection.access_token = access_token
        connection.refresh_token = refresh_token
        connection.token_expires_at = token_expires_at
        connection.naver_user_id = naver_user.get("id")
        connection.naver_email = naver_user.get("email")
        connection.naver_name = naver_user.get("name")

        if blog_info:
            connection.blog_id = blog_info.get("blogId")
            connection.blog_name = blog_info.get("blogName")
            connection.blog_url = blog_info.get("blogUrl")
    else:
        # Create new connection
        connection = NaverConnection(
            user_id=current_user.id,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            naver_user_id=naver_user.get("id"),
            naver_email=naver_user.get("email"),
            naver_name=naver_user.get("name"),
            blog_id=blog_info.get("blogId") if blog_info else None,
            blog_name=blog_info.get("blogName") if blog_info else None,
            blog_url=blog_info.get("blogUrl") if blog_info else None,
        )
        db.add(connection)

    await db.commit()
    await db.refresh(connection)

    return connection


@router.get("/connection", response_model=NaverConnectionResponse)
async def get_naver_connection(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    네이버 연동 정보 조회

    현재 사용자의 네이버 블로그 연동 정보를 반환합니다.
    """
    result = await db.execute(
        select(NaverConnection).where(NaverConnection.user_id == current_user.id)
    )
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="네이버 블로그 연동이 필요합니다.",
        )

    return connection


@router.delete("/connection", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_naver(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    네이버 연동 해제

    네이버 블로그 연동을 해제합니다.
    """
    result = await db.execute(
        select(NaverConnection).where(NaverConnection.user_id == current_user.id)
    )
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="네이버 블로그 연동이 없습니다.",
        )

    await db.delete(connection)
    await db.commit()

    return None


@router.get("/categories", response_model=List[NaverCategoryResponse])
async def get_naver_categories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    네이버 블로그 카테고리 목록 조회

    연동된 네이버 블로그의 카테고리 목록을 반환합니다.
    """
    result = await db.execute(
        select(NaverConnection).where(NaverConnection.user_id == current_user.id)
    )
    connection = result.scalar_one_or_none()

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="네이버 블로그 연동이 필요합니다.",
        )

    # Check token expiration
    if datetime.utcnow() >= connection.token_expires_at:
        # Refresh token
        token_response = await naver_blog_service.refresh_access_token(
            connection.refresh_token
        )

        if not token_response:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="토큰 갱신에 실패했습니다. 다시 연동해주세요.",
            )

        connection.access_token = token_response.get("access_token")
        expires_in = token_response.get("expires_in", 3600)
        connection.token_expires_at = datetime.utcnow() + timedelta(
            seconds=expires_in
        )
        await db.commit()

    # Get categories
    categories = await naver_blog_service.get_categories(
        connection.access_token, connection.blog_id
    )

    return [
        NaverCategoryResponse(
            category_no=str(cat.get("categoryNo")),
            category_name=cat.get("categoryName"),
            post_count=cat.get("postCnt", 0),
        )
        for cat in categories
    ]


@router.post("/publish", response_model=NaverPublishResponse)
async def publish_to_naver(
    publish_request: NaverPublishRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    네이버 블로그에 포스트 발행

    Doctor Voice Pro의 포스트를 네이버 블로그에 자동으로 발행합니다.

    **Parameters:**
    - **post_id**: 발행할 포스트 ID
    - **category_no**: 네이버 블로그 카테고리 번호 (선택)
    - **open_type**: 공개 설정 (0: 전체공개, 1: 이웃공개, 2: 비공개)
    - **tags**: 태그 목록 (선택)
    """
    # Get Naver connection
    conn_result = await db.execute(
        select(NaverConnection).where(NaverConnection.user_id == current_user.id)
    )
    connection = conn_result.scalar_one_or_none()

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="네이버 블로그 연동이 필요합니다.",
        )

    # Get post
    post_result = await db.execute(
        select(Post).where(
            Post.id == publish_request.post_id, Post.user_id == current_user.id
        )
    )
    post = post_result.scalar_one_or_none()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="포스트를 찾을 수 없습니다."
        )

    # Check token expiration and refresh if needed
    if datetime.utcnow() >= connection.token_expires_at:
        token_response = await naver_blog_service.refresh_access_token(
            connection.refresh_token
        )

        if not token_response:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="토큰 갱신에 실패했습니다. 다시 연동해주세요.",
            )

        connection.access_token = token_response.get("access_token")
        expires_in = token_response.get("expires_in", 3600)
        connection.token_expires_at = datetime.utcnow() + timedelta(
            seconds=expires_in
        )
        await db.commit()

    # Prepare tags (use SEO keywords if tags not provided)
    tags = publish_request.tags
    if not tags and post.seo_keywords:
        tags = post.seo_keywords[:10]  # Limit to 10 tags

    # Publish to Naver Blog
    category_no = (
        int(publish_request.category_no)
        if publish_request.category_no
        else (
            int(connection.default_category_no)
            if connection.default_category_no
            else None
        )
    )

    result = await naver_blog_service.create_post(
        access_token=connection.access_token,
        title=post.title or "제목 없음",
        content=post.generated_content,
        category_no=category_no,
        open_type=publish_request.open_type,
        tag=tags,
    )

    if not result:
        return NaverPublishResponse(
            success=False, message="네이버 블로그 발행에 실패했습니다."
        )

    # Update post with Naver blog URL
    naver_post_id = result.get("logNo")
    naver_post_url = f"{connection.blog_url}/{naver_post_id}"

    post.naver_blog_url = naver_post_url
    post.status = "published"
    post.published_at = datetime.utcnow()

    await db.commit()

    return NaverPublishResponse(
        success=True,
        naver_post_id=naver_post_id,
        naver_post_url=naver_post_url,
        message="네이버 블로그에 성공적으로 발행되었습니다.",
    )
