"""
SNS 멀티 포스팅 API
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.sns_connection import SNSPlatform, SNSPostStatus, SNSContentType
from app.services.sns_service import sns_service

router = APIRouter()


# ==================== Schemas ====================

class SNSAuthCallbackRequest(BaseModel):
    code: str
    state: str
    redirect_uri: str


class SNSConvertRequest(BaseModel):
    post_id: str
    platform: SNSPlatform
    content_type: SNSContentType = SNSContentType.POST


class ShortformScriptRequest(BaseModel):
    post_id: str
    duration: int = Field(30, ge=15, le=60, description="초 단위 (15-60)")


class SNSPostCreateRequest(BaseModel):
    platform: SNSPlatform
    caption: str
    content_type: SNSContentType = SNSContentType.POST
    hashtags: Optional[List[str]] = None
    media_urls: Optional[List[str]] = None
    original_post_id: Optional[str] = None
    script: Optional[str] = None
    script_duration: Optional[int] = None


class SNSPostUpdateRequest(BaseModel):
    caption: Optional[str] = None
    hashtags: Optional[List[str]] = None
    media_urls: Optional[List[str]] = None
    script: Optional[str] = None


class SNSConnectionResponse(BaseModel):
    id: str
    platform: str
    platform_username: Optional[str]
    profile_image_url: Optional[str]
    page_name: Optional[str]
    is_active: bool
    connection_status: str
    created_at: str


class SNSPostResponse(BaseModel):
    id: str
    platform: str
    content_type: str
    caption: Optional[str]
    hashtags: Optional[List[str]]
    media_urls: Optional[List[str]]
    script: Optional[str]
    script_duration: Optional[int]
    status: str
    scheduled_at: Optional[str]
    published_at: Optional[str]
    platform_post_url: Optional[str]
    error_message: Optional[str]
    original_post_id: Optional[str]
    created_at: str


class ConvertResponse(BaseModel):
    caption: str
    hashtags: List[str]
    original_post_id: str
    original_title: str
    platform: str
    content_type: str


class ShortformScriptResponse(BaseModel):
    script: str
    duration: int
    sections: List[dict]
    hooks: List[str]
    cta: List[str]
    original_post_id: str


# ==================== Helper Functions ====================

def connection_to_response(conn) -> dict:
    """SNSConnection을 응답 딕셔너리로 변환"""
    return {
        "id": str(conn.id),
        "platform": conn.platform.value,
        "platform_username": conn.platform_username,
        "profile_image_url": conn.profile_image_url,
        "page_name": conn.page_name,
        "is_active": conn.is_active,
        "connection_status": conn.connection_status,
        "created_at": conn.created_at.isoformat(),
    }


def sns_post_to_response(post) -> dict:
    """SNSPost를 응답 딕셔너리로 변환"""
    return {
        "id": str(post.id),
        "platform": post.platform.value,
        "content_type": post.content_type.value,
        "caption": post.caption,
        "hashtags": post.hashtags,
        "media_urls": post.media_urls,
        "script": post.script,
        "script_duration": post.script_duration,
        "status": post.status.value,
        "scheduled_at": post.scheduled_at.isoformat() if post.scheduled_at else None,
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "platform_post_url": post.platform_post_url,
        "error_message": post.error_message,
        "original_post_id": str(post.original_post_id) if post.original_post_id else None,
        "created_at": post.created_at.isoformat(),
    }


# ==================== OAuth Endpoints ====================

@router.get("/{platform}/auth/url")
async def get_auth_url(
    platform: SNSPlatform,
    redirect_uri: str = Query(...),
    current_user: User = Depends(get_current_user),
):
    """
    SNS OAuth 인증 URL 생성
    """
    import secrets
    state = secrets.token_urlsafe(16)

    if platform == SNSPlatform.INSTAGRAM:
        auth_url = sns_service.get_instagram_auth_url(redirect_uri, state)
    elif platform == SNSPlatform.FACEBOOK:
        auth_url = sns_service.get_facebook_auth_url(redirect_uri, state)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform.value}")

    return {
        "auth_url": auth_url,
        "state": state,
    }


@router.post("/{platform}/auth/callback")
async def auth_callback(
    platform: SNSPlatform,
    request: SNSAuthCallbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    SNS OAuth 콜백 처리
    """
    # 토큰 교환
    token_data = await sns_service.exchange_code_for_token(
        platform=platform,
        code=request.code,
        redirect_uri=request.redirect_uri,
    )

    if not token_data:
        raise HTTPException(status_code=400, detail="Failed to exchange code for token")

    access_token = token_data.get("access_token")

    # 사용자 정보 조회
    user_info = await sns_service.get_user_info(
        platform=platform,
        access_token=access_token,
    )

    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to get user info")

    # 연동 정보 저장
    connection = await sns_service.save_connection(
        db=db,
        user_id=str(current_user.id),
        platform=platform,
        access_token=access_token,
        token_data=token_data,
        user_info=user_info,
    )

    return connection_to_response(connection)


# ==================== Connection Endpoints ====================

@router.get("/connections", response_model=List[SNSConnectionResponse])
async def get_connections(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    SNS 연동 목록 조회
    """
    connections = await sns_service.get_connections(
        db=db,
        user_id=str(current_user.id),
    )

    return [connection_to_response(c) for c in connections]


@router.delete("/connections/{platform}")
async def disconnect(
    platform: SNSPlatform,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    SNS 연동 해제
    """
    success = await sns_service.disconnect(
        db=db,
        user_id=str(current_user.id),
        platform=platform,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Connection not found")

    return {"message": f"{platform.value} disconnected successfully"}


# ==================== Content Conversion Endpoints ====================

@router.post("/convert", response_model=ConvertResponse)
async def convert_to_sns(
    request: SNSConvertRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    블로그 글을 SNS 포맷으로 변환
    """
    try:
        result = await sns_service.convert_to_sns(
            db=db,
            post_id=request.post_id,
            user_id=str(current_user.id),
            platform=request.platform,
            content_type=request.content_type,
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-script", response_model=ShortformScriptResponse)
async def generate_shortform_script(
    request: ShortformScriptRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    숏폼(릴스/숏츠) 스크립트 생성
    """
    try:
        result = await sns_service.generate_shortform_script(
            db=db,
            post_id=request.post_id,
            user_id=str(current_user.id),
            duration=request.duration,
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hashtag-recommendations")
async def get_hashtag_recommendations(
    category: str = Query(...),
    platform: Optional[SNSPlatform] = None,
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    해시태그 추천 조회
    """
    recommendations = await sns_service.get_hashtag_recommendations(
        db=db,
        category=category,
        platform=platform,
        limit=limit,
    )

    return [
        {
            "hashtag": r.hashtag,
            "category": r.category,
            "popularity_score": r.popularity_score,
            "engagement_rate": r.engagement_rate,
            "priority": r.priority,
        }
        for r in recommendations
    ]


# ==================== SNS Post Endpoints ====================

@router.post("/posts", response_model=SNSPostResponse)
async def create_sns_post(
    request: SNSPostCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    SNS 포스트 생성
    """
    sns_post = await sns_service.create_sns_post(
        db=db,
        user_id=str(current_user.id),
        platform=request.platform,
        caption=request.caption,
        content_type=request.content_type,
        hashtags=request.hashtags,
        media_urls=request.media_urls,
        original_post_id=request.original_post_id,
        script=request.script,
        script_duration=request.script_duration,
    )

    return sns_post_to_response(sns_post)


@router.get("/posts", response_model=List[SNSPostResponse])
async def get_sns_posts(
    platform: Optional[SNSPlatform] = None,
    status: Optional[SNSPostStatus] = None,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    SNS 포스트 목록 조회
    """
    posts = await sns_service.get_sns_posts(
        db=db,
        user_id=str(current_user.id),
        platform=platform,
        status=status,
        limit=limit,
        offset=offset,
    )

    return [sns_post_to_response(p) for p in posts]


@router.get("/posts/{sns_post_id}", response_model=SNSPostResponse)
async def get_sns_post(
    sns_post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    SNS 포스트 상세 조회
    """
    sns_post = await sns_service.get_sns_post(
        db=db,
        sns_post_id=sns_post_id,
        user_id=str(current_user.id),
    )

    if not sns_post:
        raise HTTPException(status_code=404, detail="SNS post not found")

    return sns_post_to_response(sns_post)


@router.put("/posts/{sns_post_id}", response_model=SNSPostResponse)
async def update_sns_post(
    sns_post_id: str,
    request: SNSPostUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    SNS 포스트 수정
    """
    update_data = {}
    if request.caption is not None:
        update_data["caption"] = request.caption
    if request.hashtags is not None:
        update_data["hashtags"] = request.hashtags
    if request.media_urls is not None:
        update_data["media_urls"] = request.media_urls
    if request.script is not None:
        update_data["script"] = request.script

    sns_post = await sns_service.update_sns_post(
        db=db,
        sns_post_id=sns_post_id,
        user_id=str(current_user.id),
        **update_data,
    )

    if not sns_post:
        raise HTTPException(status_code=404, detail="SNS post not found")

    return sns_post_to_response(sns_post)


@router.delete("/posts/{sns_post_id}")
async def delete_sns_post(
    sns_post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    SNS 포스트 삭제
    """
    success = await sns_service.delete_sns_post(
        db=db,
        sns_post_id=sns_post_id,
        user_id=str(current_user.id),
    )

    if not success:
        raise HTTPException(status_code=404, detail="SNS post not found")

    return {"message": "SNS post deleted successfully"}


@router.post("/posts/{sns_post_id}/publish")
async def publish_sns_post(
    sns_post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    SNS 포스트 즉시 발행
    """
    sns_post = await sns_service.get_sns_post(
        db=db,
        sns_post_id=sns_post_id,
        user_id=str(current_user.id),
    )

    if not sns_post:
        raise HTTPException(status_code=404, detail="SNS post not found")

    if sns_post.platform == SNSPlatform.INSTAGRAM:
        result = await sns_service.publish_to_instagram(
            db=db,
            sns_post_id=sns_post_id,
            user_id=str(current_user.id),
        )
    else:
        raise HTTPException(status_code=400, detail=f"Publishing to {sns_post.platform.value} is not supported yet")

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to publish"))

    return result
