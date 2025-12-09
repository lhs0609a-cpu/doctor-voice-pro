"""
Posts API Router
포스팅 생성 및 관리
"""

from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.db.database import get_db
from app.schemas.post import (
    PostCreate,
    PostResponse,
    PostListResponse,
    PostUpdate,
    RewriteRequest,
)
from app.models import User, Post, PostVersion
from app.api.deps import get_current_user
from app.services.post_service import post_service
from app.api.websocket import get_connection_manager

router = APIRouter()


@router.post("/", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    post_data: PostCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    새로운 포스팅 생성

    전체 AI 각색 파이프라인을 실행합니다:
    1. Claude API로 콘텐츠 각색
    2. 의료법 준수 검증 및 자동 수정
    3. 설득력 점수 계산
    4. SEO 최적화 (키워드, 해시태그)
    5. 제목 및 메타 설명 자동 생성

    **Parameters:**
    - **original_content**: 원본 의료 정보 (최소 50자)
    - **persuasion_level**: 각색 레벨 1-5 (기본값: 3)
      - 1: 객관적 정보 전달
      - 2: 설명 강화
      - 3: 공감 유도
      - 4: 행동 촉구
      - 5: 스토리 극대화
    - **framework**: 설득 프레임워크 (기본값: AIDA)
      - AIDA: Attention - Interest - Desire - Action
      - PAS: Problem - Agitate - Solution
      - STORY: 스토리텔링 구조
      - QA: Q&A 형식
    - **target_length**: 목표 글자 수 500-5000 (기본값: 1500)
    """
    try:
        # Get WebSocket manager
        ws_manager = get_connection_manager()

        post = await post_service.create_post(
            db=db,
            user_id=current_user.id,
            original_content=post_data.original_content,
            persuasion_level=post_data.persuasion_level,
            framework=post_data.framework,
            target_length=post_data.target_length,
            websocket_manager=ws_manager,
        )

        return post

    except Exception as e:
        # Send error via WebSocket if available
        try:
            ws_manager = get_connection_manager()
            await ws_manager.send_error(
                str(current_user.id),
                "post_creation",
                str(e)
            )
        except:
            pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"포스팅 생성 중 오류가 발생했습니다: {str(e)}",
        )


@router.get("/", response_model=PostListResponse)
async def get_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    포스팅 목록 조회 (페이지네이션)

    **Parameters:**
    - **page**: 페이지 번호 (기본값: 1)
    - **page_size**: 페이지당 항목 수 (기본값: 10, 최대: 50)
    """
    # 전체 개수 조회
    count_result = await db.execute(
        select(Post).where(Post.user_id == current_user.id)
    )
    total = len(count_result.scalars().all())

    # 페이지네이션 적용
    offset = (page - 1) * page_size

    result = await db.execute(
        select(Post)
        .where(Post.user_id == current_user.id)
        .order_by(desc(Post.created_at))
        .offset(offset)
        .limit(page_size)
    )

    posts = result.scalars().all()

    total_pages = (total + page_size - 1) // page_size

    return PostListResponse(
        posts=posts, total=total, page=page, page_size=page_size, total_pages=total_pages
    )


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    포스팅 상세 조회
    """
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.user_id == current_user.id)
    )

    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="포스팅을 찾을 수 없습니다"
        )

    return post


@router.put("/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: UUID,
    post_update: PostUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    포스팅 수정 (수동)

    제목, 내용, 상태 등을 직접 수정합니다.
    """
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.user_id == current_user.id)
    )

    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="포스팅을 찾을 수 없습니다"
        )

    # 업데이트
    if post_update.title is not None:
        post.title = post_update.title
    if post_update.generated_content is not None:
        post.generated_content = post_update.generated_content
    if post_update.status is not None:
        post.status = post_update.status

    await db.commit()
    await db.refresh(post)

    return post


@router.post("/{post_id}/rewrite", response_model=PostResponse)
async def rewrite_post(
    post_id: UUID,
    rewrite_data: RewriteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    포스팅 재작성 (다른 스타일로)

    기존 포스팅을 다른 설정으로 재작성하여 새 버전을 생성합니다.
    이전 버전들은 모두 보존됩니다.

    **Parameters:**
    - **persuasion_level**: 새로운 각색 레벨 (선택)
    - **framework**: 새로운 프레임워크 (선택)
    - **target_length**: 새로운 목표 길이 (선택)
    """
    try:
        post = await post_service.rewrite_post(
            db=db,
            post_id=post_id,
            user_id=current_user.id,
            persuasion_level=rewrite_data.persuasion_level,
            framework=rewrite_data.framework,
            target_length=rewrite_data.target_length,
        )

        return post

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"재작성 중 오류가 발생했습니다: {str(e)}",
        )


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    포스팅 삭제
    """
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.user_id == current_user.id)
    )

    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="포스팅을 찾을 수 없습니다"
        )

    await db.delete(post)
    await db.commit()

    return None


@router.get("/{post_id}/versions")
async def get_post_versions(
    post_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    포스팅의 모든 버전 이력 조회

    포스팅의 모든 버전을 최신순으로 반환합니다.
    """
    # 포스팅 소유권 확인
    post_result = await db.execute(
        select(Post).where(Post.id == post_id, Post.user_id == current_user.id)
    )
    post = post_result.scalar_one_or_none()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="포스팅을 찾을 수 없습니다"
        )

    # 버전 조회
    result = await db.execute(
        select(PostVersion)
        .where(PostVersion.post_id == post_id)
        .order_by(desc(PostVersion.version_number))
    )
    versions = result.scalars().all()

    return {
        "post_id": post_id,
        "total_versions": len(versions),
        "versions": [
            {
                "id": str(v.id),
                "version_number": v.version_number,
                "content": v.content,
                "persuasion_score": v.persuasion_score,
                "generation_config": v.generation_config,
                "created_at": v.created_at.isoformat(),
            }
            for v in versions
        ],
    }


@router.post("/{post_id}/versions/{version_id}/restore", response_model=PostResponse)
async def restore_post_version(
    post_id: UUID,
    version_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    특정 버전으로 포스팅 복원

    이전 버전의 내용을 현재 포스팅 내용으로 복원합니다.
    복원 시 현재 버전은 자동으로 버전 이력에 저장됩니다.
    """
    # 포스팅 소유권 확인
    post_result = await db.execute(
        select(Post).where(Post.id == post_id, Post.user_id == current_user.id)
    )
    post = post_result.scalar_one_or_none()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="포스팅을 찾을 수 없습니다"
        )

    # 버전 조회
    version_result = await db.execute(
        select(PostVersion).where(
            PostVersion.id == version_id, PostVersion.post_id == post_id
        )
    )
    version = version_result.scalar_one_or_none()

    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="버전을 찾을 수 없습니다"
        )

    # 현재 내용을 버전으로 저장
    current_versions_result = await db.execute(
        select(PostVersion)
        .where(PostVersion.post_id == post_id)
        .order_by(desc(PostVersion.version_number))
    )
    current_versions = current_versions_result.scalars().all()
    next_version_number = (
        max(v.version_number for v in current_versions) + 1
        if current_versions
        else 1
    )

    new_version = PostVersion(
        post_id=post_id,
        version_number=next_version_number,
        content=post.generated_content,
        persuasion_score=post.persuasion_score,
        generation_config={
            "restored_from_version": version.version_number,
            "restored_at": datetime.utcnow().isoformat(),
        },
    )
    db.add(new_version)

    # 복원할 버전의 내용으로 포스팅 업데이트
    post.generated_content = version.content
    post.persuasion_score = version.persuasion_score

    await db.commit()
    await db.refresh(post)

    return post


@router.post("/{post_id}/favorite")
async def toggle_favorite(
    post_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """포스팅 즐겨찾기 토글"""
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.user_id == current_user.id)
    )
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="포스팅을 찾을 수 없습니다"
        )

    post.is_favorited = not post.is_favorited
    await db.commit()

    return {
        "success": True,
        "is_favorited": post.is_favorited,
        "message": "즐겨찾기에 추가되었습니다" if post.is_favorited else "즐겨찾기에서 제거되었습니다",
    }


@router.post("/{post_id}/duplicate", response_model=PostResponse)
async def duplicate_post(
    post_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """포스팅 복제"""
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.user_id == current_user.id)
    )
    original_post = result.scalar_one_or_none()

    if not original_post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="포스팅을 찾을 수 없습니다"
        )

    # Create duplicate
    duplicated_post = Post(
        user_id=current_user.id,
        title=f"{original_post.title} (복사본)",
        original_content=original_post.original_content,
        generated_content=original_post.generated_content,
        persuasion_score=original_post.persuasion_score,
        medical_law_check=original_post.medical_law_check,
        seo_keywords=original_post.seo_keywords,
        hashtags=original_post.hashtags,
        meta_description=original_post.meta_description,
        status="draft",
        is_favorited=False,
    )

    db.add(duplicated_post)
    await db.commit()
    await db.refresh(duplicated_post)

    # Copy first version
    if original_post.versions:
        first_version = PostVersion(
            post_id=duplicated_post.id,
            version_number=1,
            content=original_post.generated_content,
            persuasion_score=original_post.persuasion_score,
            generation_config={"duplicated_from": str(original_post.id)},
        )
        db.add(first_version)
        await db.commit()

    return duplicated_post


@router.get("/{post_id}/suggestions")
async def get_post_suggestions(
    post_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """포스팅 AI 개선 제안"""
    from app.services.ai_suggestions import ai_suggestions_service

    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.user_id == current_user.id)
    )
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="포스팅을 찾을 수 없습니다"
        )

    suggestions = await ai_suggestions_service.generate_suggestions(
        post.generated_content,
        post.persuasion_score,
        current_user.specialty or "의료",
    )

    return suggestions


@router.get("/{post_id}/seo-analysis")
async def get_seo_analysis(
    post_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """포스팅 SEO 분석"""
    from app.services.seo_analyzer import seo_analyzer

    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.user_id == current_user.id)
    )
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="포스팅을 찾을 수 없습니다"
        )

    analysis = seo_analyzer.analyze(
        post.title or "",
        post.generated_content or "",
        post.seo_keywords or [],
    )

    return analysis
