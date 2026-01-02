"""
카페 바이럴 자동화 API 엔드포인트
"""

from datetime import datetime, date
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.cafe import (
    CafeCommunity, CafeKeyword, CafePost, CafeContent,
    CafeAutoSetting, CafeStats, CafeTemplate,
    CafePostStatus, ContentType, ContentStatus, CafeTone, CafeCategory
)
from app.services.cafe_crawler import cafe_crawler
from app.services.cafe_content_generator import cafe_content_generator
from app.services.cafe_scheduler import get_cafe_scheduler
from app.services.cafe_poster import cafe_poster_manager, CafePosterService
from app.services.account_manager import account_manager
from app.models.viral_common import NaverAccount, AccountStatus

router = APIRouter(prefix="/cafe", tags=["cafe"])


# ============= Schemas =============

class CafeCreate(BaseModel):
    cafe_id: str = Field(..., description="카페 ID (URL의 카페명)")
    cafe_name: str
    category: CafeCategory = CafeCategory.OTHER
    description: Optional[str] = None
    posting_enabled: bool = False
    commenting_enabled: bool = True
    daily_post_limit: int = 2
    daily_comment_limit: int = 10
    priority: int = 1


class CafeUpdate(BaseModel):
    cafe_name: Optional[str] = None
    category: Optional[CafeCategory] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    posting_enabled: Optional[bool] = None
    commenting_enabled: Optional[bool] = None
    daily_post_limit: Optional[int] = None
    daily_comment_limit: Optional[int] = None
    priority: Optional[int] = None
    target_boards: Optional[List[dict]] = None


class KeywordCreate(BaseModel):
    keyword: str
    category: Optional[str] = None
    cafe_id: Optional[str] = None
    priority: int = 1


class ContentGenerate(BaseModel):
    post_id: str
    tone: CafeTone = CafeTone.FRIENDLY
    include_promotion: bool = False
    max_length: int = 200
    include_emoji: bool = True


class PostGenerate(BaseModel):
    cafe_id: str
    topic: str
    style: str = "review"
    tone: CafeTone = CafeTone.FRIENDLY
    include_promotion: bool = True
    min_length: int = 500
    max_length: int = 1500


class SettingsUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    auto_collect: Optional[bool] = None
    auto_generate: Optional[bool] = None
    auto_post: Optional[bool] = None
    collect_interval_minutes: Optional[int] = None
    posts_per_collect: Optional[int] = None
    min_relevance_score: Optional[float] = None
    default_tone: Optional[CafeTone] = None
    max_content_length: Optional[int] = None
    include_emoji: Optional[bool] = None
    auto_approve_threshold: Optional[float] = None
    posting_delay_seconds: Optional[int] = None
    daily_post_limit: Optional[int] = None
    daily_comment_limit: Optional[int] = None
    working_hours: Optional[dict] = None
    working_days: Optional[List[int]] = None
    default_blog_link: Optional[str] = None
    default_place_link: Optional[str] = None
    promotion_frequency: Optional[float] = None


class LoginRequest(BaseModel):
    username: str
    password: str


# ============= 카페 관리 =============

@router.post("/cafes")
async def create_cafe(
    data: CafeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """타겟 카페 등록"""
    # 카페 접근 확인
    verify_result = await cafe_crawler.verify_cafe_access(data.cafe_id)

    if not verify_result.get("accessible"):
        raise HTTPException(400, f"카페 접근 불가: {verify_result.get('error')}")

    # 중복 체크
    existing = await db.execute(
        select(CafeCommunity).where(
            and_(
                CafeCommunity.user_id == str(current_user.id),
                CafeCommunity.cafe_id == data.cafe_id
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "이미 등록된 카페입니다")

    cafe = CafeCommunity(
        user_id=str(current_user.id),
        cafe_id=data.cafe_id,
        cafe_name=verify_result.get("cafe_name", data.cafe_name),
        cafe_url=f"https://cafe.naver.com/{data.cafe_id}",
        category=data.category,
        description=data.description,
        member_count=verify_result.get("member_count", 0),
        posting_enabled=data.posting_enabled,
        commenting_enabled=data.commenting_enabled,
        daily_post_limit=data.daily_post_limit,
        daily_comment_limit=data.daily_comment_limit,
        priority=data.priority,
    )

    db.add(cafe)
    await db.commit()
    await db.refresh(cafe)

    return {"success": True, "cafe": cafe}


@router.get("/cafes")
async def list_cafes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """카페 목록"""
    result = await db.execute(
        select(CafeCommunity).where(
            CafeCommunity.user_id == str(current_user.id)
        ).order_by(CafeCommunity.priority.desc())
    )
    return result.scalars().all()


@router.put("/cafes/{cafe_id}")
async def update_cafe(
    cafe_id: str,
    data: CafeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """카페 수정"""
    result = await db.execute(
        select(CafeCommunity).where(
            and_(
                CafeCommunity.id == cafe_id,
                CafeCommunity.user_id == str(current_user.id)
            )
        )
    )
    cafe = result.scalar_one_or_none()

    if not cafe:
        raise HTTPException(404, "카페를 찾을 수 없습니다")

    for key, value in data.dict(exclude_unset=True).items():
        setattr(cafe, key, value)

    await db.commit()
    return {"success": True, "cafe": cafe}


@router.delete("/cafes/{cafe_id}")
async def delete_cafe(
    cafe_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """카페 삭제"""
    result = await db.execute(
        select(CafeCommunity).where(
            and_(
                CafeCommunity.id == cafe_id,
                CafeCommunity.user_id == str(current_user.id)
            )
        )
    )
    cafe = result.scalar_one_or_none()

    if not cafe:
        raise HTTPException(404, "카페를 찾을 수 없습니다")

    await db.delete(cafe)
    await db.commit()
    return {"success": True}


@router.post("/cafes/{cafe_id}/verify")
async def verify_cafe(cafe_id: str):
    """카페 접근 확인"""
    result = await cafe_crawler.verify_cafe_access(cafe_id)
    return result


# ============= 키워드 관리 =============

@router.post("/keywords")
async def create_keyword(
    data: KeywordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """키워드 추가"""
    keyword = CafeKeyword(
        user_id=str(current_user.id),
        cafe_id=data.cafe_id,
        keyword=data.keyword,
        category=data.category,
        priority=data.priority,
    )

    db.add(keyword)
    await db.commit()
    await db.refresh(keyword)

    return {"success": True, "keyword": keyword}


@router.get("/keywords")
async def list_keywords(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """키워드 목록"""
    result = await db.execute(
        select(CafeKeyword).where(
            CafeKeyword.user_id == str(current_user.id)
        ).order_by(CafeKeyword.priority.desc())
    )
    return result.scalars().all()


@router.delete("/keywords/{keyword_id}")
async def delete_keyword(
    keyword_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """키워드 삭제"""
    result = await db.execute(
        select(CafeKeyword).where(
            and_(
                CafeKeyword.id == keyword_id,
                CafeKeyword.user_id == str(current_user.id)
            )
        )
    )
    keyword = result.scalar_one_or_none()

    if not keyword:
        raise HTTPException(404, "키워드를 찾을 수 없습니다")

    await db.delete(keyword)
    await db.commit()
    return {"success": True}


# ============= 게시글 관리 =============

@router.get("/posts")
async def list_posts(
    status: Optional[CafePostStatus] = None,
    cafe_id: Optional[str] = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """수집된 게시글 목록"""
    query = select(CafePost).where(CafePost.user_id == str(current_user.id))

    if status:
        query = query.where(CafePost.status == status)
    if cafe_id:
        query = query.where(CafePost.cafe_id == cafe_id)

    query = query.order_by(desc(CafePost.collected_at)).offset(offset).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/posts/{post_id}")
async def get_post(
    post_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """게시글 상세"""
    result = await db.execute(
        select(CafePost).where(
            and_(
                CafePost.id == post_id,
                CafePost.user_id == str(current_user.id)
            )
        )
    )
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(404, "게시글을 찾을 수 없습니다")

    return post


@router.post("/posts/collect")
async def collect_posts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """게시글 수동 수집"""
    scheduler = await get_cafe_scheduler(db, str(current_user.id))
    result = await scheduler.run_collection_job(str(current_user.id))
    return result


@router.put("/posts/{post_id}/skip")
async def skip_post(
    post_id: str,
    reason: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """게시글 건너뛰기"""
    result = await db.execute(
        select(CafePost).where(
            and_(
                CafePost.id == post_id,
                CafePost.user_id == str(current_user.id)
            )
        )
    )
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(404, "게시글을 찾을 수 없습니다")

    post.status = CafePostStatus.SKIPPED
    post.skip_reason = reason

    await db.commit()
    return {"success": True}


# ============= 콘텐츠 관리 =============

@router.get("/contents")
async def list_contents(
    status: Optional[ContentStatus] = None,
    content_type: Optional[ContentType] = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """생성된 콘텐츠 목록"""
    query = select(CafeContent).where(CafeContent.user_id == str(current_user.id))

    if status:
        query = query.where(CafeContent.status == status)
    if content_type:
        query = query.where(CafeContent.content_type == content_type)

    query = query.order_by(desc(CafeContent.created_at)).offset(offset).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/contents/{content_id}")
async def get_content(
    content_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """콘텐츠 상세"""
    result = await db.execute(
        select(CafeContent).where(
            and_(
                CafeContent.id == content_id,
                CafeContent.user_id == str(current_user.id)
            )
        )
    )
    content = result.scalar_one_or_none()

    if not content:
        raise HTTPException(404, "콘텐츠를 찾을 수 없습니다")

    return content


@router.post("/contents/generate")
async def generate_content(
    data: ContentGenerate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """댓글 수동 생성"""
    # 대상 게시글 조회
    post_result = await db.execute(
        select(CafePost).where(
            and_(
                CafePost.id == data.post_id,
                CafePost.user_id == str(current_user.id)
            )
        )
    )
    post = post_result.scalar_one_or_none()

    if not post:
        raise HTTPException(404, "게시글을 찾을 수 없습니다")

    # 카페 정보 조회
    cafe_result = await db.execute(
        select(CafeCommunity).where(CafeCommunity.id == post.cafe_id)
    )
    cafe = cafe_result.scalar_one_or_none()

    # 댓글 생성
    result = await cafe_content_generator.generate_comment(
        post_title=post.title,
        post_content=post.content or "",
        cafe_category=cafe.category if cafe else CafeCategory.OTHER,
        tone=data.tone,
        include_promotion=data.include_promotion,
        max_length=data.max_length,
        include_emoji=data.include_emoji
    )

    # 저장
    content = CafeContent(
        user_id=str(current_user.id),
        target_post_id=post.id,
        content_type=ContentType.COMMENT,
        content=result.get("content"),
        tone=data.tone,
        quality_score=result.get("quality_score"),
        naturalness_score=result.get("naturalness_score"),
        relevance_score=result.get("relevance_score"),
        include_promotion=data.include_promotion,
        status=ContentStatus.DRAFT,
    )

    db.add(content)
    post.status = CafePostStatus.ANALYZED
    await db.commit()
    await db.refresh(content)

    return {"success": True, "content": content}


@router.post("/contents/generate-post")
async def generate_post_content(
    data: PostGenerate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """게시글 생성"""
    # 카페 조회
    cafe_result = await db.execute(
        select(CafeCommunity).where(
            and_(
                CafeCommunity.id == data.cafe_id,
                CafeCommunity.user_id == str(current_user.id)
            )
        )
    )
    cafe = cafe_result.scalar_one_or_none()

    if not cafe:
        raise HTTPException(404, "카페를 찾을 수 없습니다")

    # 글 생성
    result = await cafe_content_generator.generate_post(
        cafe_name=cafe.cafe_name,
        cafe_category=cafe.category,
        topic=data.topic,
        style=data.style,
        tone=data.tone,
        include_promotion=data.include_promotion,
        min_length=data.min_length,
        max_length=data.max_length
    )

    # 저장
    content = CafeContent(
        user_id=str(current_user.id),
        target_cafe_id=cafe.id,
        content_type=ContentType.POST,
        title=result.get("title"),
        content=result.get("content"),
        tone=data.tone,
        quality_score=result.get("quality_score"),
        naturalness_score=result.get("naturalness_score"),
        relevance_score=result.get("relevance_score"),
        include_promotion=data.include_promotion,
        status=ContentStatus.DRAFT,
    )

    db.add(content)
    await db.commit()
    await db.refresh(content)

    return {"success": True, "content": content}


@router.put("/contents/{content_id}/approve")
async def approve_content(
    content_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """콘텐츠 승인"""
    result = await db.execute(
        select(CafeContent).where(
            and_(
                CafeContent.id == content_id,
                CafeContent.user_id == str(current_user.id)
            )
        )
    )
    content = result.scalar_one_or_none()

    if not content:
        raise HTTPException(404, "콘텐츠를 찾을 수 없습니다")

    content.status = ContentStatus.APPROVED
    await db.commit()
    return {"success": True}


@router.put("/contents/{content_id}/reject")
async def reject_content(
    content_id: str,
    reason: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """콘텐츠 반려"""
    result = await db.execute(
        select(CafeContent).where(
            and_(
                CafeContent.id == content_id,
                CafeContent.user_id == str(current_user.id)
            )
        )
    )
    content = result.scalar_one_or_none()

    if not content:
        raise HTTPException(404, "콘텐츠를 찾을 수 없습니다")

    content.status = ContentStatus.REJECTED
    content.rejection_reason = reason
    await db.commit()
    return {"success": True}


@router.post("/contents/{content_id}/post")
async def post_content(
    content_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """콘텐츠 수동 등록"""
    poster = await cafe_poster_manager.get_poster(db, str(current_user.id))

    if not poster.is_logged_in():
        raise HTTPException(400, "네이버 로그인이 필요합니다")

    # 콘텐츠 조회
    result = await db.execute(
        select(CafeContent).where(
            and_(
                CafeContent.id == content_id,
                CafeContent.user_id == str(current_user.id)
            )
        )
    )
    content = result.scalar_one_or_none()

    if not content:
        raise HTTPException(404, "콘텐츠를 찾을 수 없습니다")

    if content.content_type == ContentType.COMMENT:
        post_result = await poster.post_comment(content_id, str(current_user.id))
    elif content.content_type == ContentType.POST:
        post_result = await poster.create_post(content_id, str(current_user.id))
    else:
        raise HTTPException(400, "지원하지 않는 콘텐츠 유형입니다")

    return post_result


# ============= 자동화 설정 =============

@router.get("/settings")
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """설정 조회"""
    result = await db.execute(
        select(CafeAutoSetting).where(
            CafeAutoSetting.user_id == str(current_user.id)
        )
    )
    settings = result.scalar_one_or_none()

    if not settings:
        # 기본 설정 생성
        settings = CafeAutoSetting(user_id=str(current_user.id))
        db.add(settings)
        await db.commit()
        await db.refresh(settings)

    return settings


@router.put("/settings")
async def update_settings(
    data: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """설정 수정"""
    result = await db.execute(
        select(CafeAutoSetting).where(
            CafeAutoSetting.user_id == str(current_user.id)
        )
    )
    settings = result.scalar_one_or_none()

    if not settings:
        settings = CafeAutoSetting(user_id=str(current_user.id))
        db.add(settings)

    for key, value in data.dict(exclude_unset=True).items():
        setattr(settings, key, value)

    await db.commit()
    return {"success": True, "settings": settings}


# ============= 스케줄러 =============

@router.post("/scheduler/start")
async def start_scheduler(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """스케줄러 시작"""
    scheduler = await get_cafe_scheduler(db, str(current_user.id))
    await scheduler.start(str(current_user.id))
    return {"success": True, "message": "스케줄러가 시작되었습니다"}


@router.post("/scheduler/stop")
async def stop_scheduler(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """스케줄러 중지"""
    scheduler = await get_cafe_scheduler(db, str(current_user.id))
    await scheduler.stop()
    return {"success": True, "message": "스케줄러가 중지되었습니다"}


@router.get("/scheduler/status")
async def scheduler_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """스케줄러 상태"""
    scheduler = await get_cafe_scheduler(db, str(current_user.id))
    return await scheduler.get_status(str(current_user.id))


@router.post("/scheduler/run-collect")
async def run_collect(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """수동 수집 실행"""
    scheduler = await get_cafe_scheduler(db, str(current_user.id))
    return await scheduler.run_collection_job(str(current_user.id))


@router.post("/scheduler/run-generate")
async def run_generate(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """수동 생성 실행"""
    scheduler = await get_cafe_scheduler(db, str(current_user.id))
    return await scheduler.run_generation_job(str(current_user.id))


# ============= 포스터 (로그인) =============

@router.post("/poster/login")
async def poster_login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """네이버 로그인"""
    poster = await cafe_poster_manager.get_poster(db, str(current_user.id))

    try:
        await poster.initialize()
        success = await poster.login(data.username, data.password)
        if success:
            await poster.save_cookies()
        return {"success": success}
    except Exception as e:
        raise HTTPException(400, str(e))


@router.post("/poster/logout")
async def poster_logout(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """로그아웃"""
    poster = await cafe_poster_manager.get_poster(db, str(current_user.id))
    await poster.close()
    return {"success": True}


@router.get("/poster/status")
async def poster_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """포스터 상태"""
    poster = await cafe_poster_manager.get_poster(db, str(current_user.id))
    return {
        "initialized": poster._browser is not None,
        "logged_in": poster.is_logged_in()
    }


@router.post("/poster/post-multiple")
async def post_multiple(
    limit: int = 5,
    delay: int = 300,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """일괄 등록"""
    poster = await cafe_poster_manager.get_poster(db, str(current_user.id))

    if not poster.is_logged_in():
        raise HTTPException(400, "네이버 로그인이 필요합니다")

    return await poster.post_multiple_contents(str(current_user.id), limit, delay)


# ============= 대시보드 =============

@router.get("/dashboard")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """대시보드 통계"""
    user_id = str(current_user.id)
    today = date.today()

    # 오늘 통계
    today_stats = await db.execute(
        select(CafeStats).where(
            and_(
                CafeStats.user_id == user_id,
                func.date(CafeStats.stat_date) == today
            )
        )
    )
    stats = today_stats.scalar_one_or_none()

    # 카페 수
    cafe_count = await db.execute(
        select(func.count(CafeCommunity.id)).where(
            and_(
                CafeCommunity.user_id == user_id,
                CafeCommunity.is_active == True
            )
        )
    )

    # 새 게시글 수
    new_posts = await db.execute(
        select(func.count(CafePost.id)).where(
            and_(
                CafePost.user_id == user_id,
                CafePost.status == CafePostStatus.NEW
            )
        )
    )

    # 승인 대기 콘텐츠 수
    pending_contents = await db.execute(
        select(func.count(CafeContent.id)).where(
            and_(
                CafeContent.user_id == user_id,
                CafeContent.status == ContentStatus.DRAFT
            )
        )
    )

    # 이번 주 통계
    week_start = today - timedelta(days=today.weekday())
    week_stats = await db.execute(
        select(
            func.sum(CafeStats.posts_collected),
            func.sum(CafeStats.contents_generated),
            func.sum(CafeStats.comments_published + CafeStats.posts_published)
        ).where(
            and_(
                CafeStats.user_id == user_id,
                CafeStats.stat_date >= week_start
            )
        )
    )
    week_data = week_stats.first()

    return {
        "today_collected": stats.posts_collected if stats else 0,
        "today_generated": stats.contents_generated if stats else 0,
        "today_posted": (stats.comments_published + stats.posts_published) if stats else 0,
        "active_cafes": cafe_count.scalar() or 0,
        "new_posts": new_posts.scalar() or 0,
        "pending_contents": pending_contents.scalar() or 0,
        "week_collected": week_data[0] or 0 if week_data else 0,
        "week_generated": week_data[1] or 0 if week_data else 0,
        "week_posted": week_data[2] or 0 if week_data else 0,
    }


@router.get("/stats")
async def get_stats(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """일별 통계"""
    start_date = date.today() - timedelta(days=days)

    result = await db.execute(
        select(CafeStats).where(
            and_(
                CafeStats.user_id == str(current_user.id),
                CafeStats.stat_date >= start_date
            )
        ).order_by(CafeStats.stat_date)
    )

    return result.scalars().all()


# ============= 계정 관리 (다중 계정 로테이션) =============

class AccountCreate(BaseModel):
    account_id: str = Field(..., description="네이버 아이디")
    password: str = Field(..., description="네이버 비밀번호")
    account_name: Optional[str] = None
    daily_comment_limit: int = 10
    daily_post_limit: int = 2
    memo: Optional[str] = None


class AccountStatusUpdate(BaseModel):
    status: AccountStatus
    reason: Optional[str] = None


@router.get("/accounts")
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    네이버 계정 목록 조회 (카페용)

    다중 계정 로테이션에 사용할 계정 목록
    """
    result = await db.execute(
        select(NaverAccount).where(
            NaverAccount.user_id == str(current_user.id)
        ).order_by(NaverAccount.created_at.desc())
    )
    accounts = result.scalars().all()

    # 비밀번호 제외하고 반환
    return [
        {
            "id": acc.id,
            "account_id": acc.account_id,
            "account_name": acc.account_name,
            "status": acc.status,
            "is_warming_up": acc.is_warming_up,
            "warming_day": acc.warming_day,
            "daily_comment_limit": acc.daily_comment_limit,
            "daily_post_limit": acc.daily_post_limit,
            "today_comments": acc.today_comments,
            "today_posts": acc.today_posts,
            "total_comments": acc.total_comments,
            "total_posts": acc.total_posts,
            "last_comment_at": acc.last_comment_at,
            "last_post_at": acc.last_post_at,
            "memo": acc.memo,
            "created_at": acc.created_at,
        }
        for acc in accounts
    ]


@router.post("/accounts")
async def create_account(
    data: AccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """네이버 계정 추가"""
    # 중복 체크
    existing = await db.execute(
        select(NaverAccount).where(
            and_(
                NaverAccount.user_id == str(current_user.id),
                NaverAccount.account_id == data.account_id
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "이미 등록된 계정입니다")

    account = await account_manager.add_account(
        db=db,
        user_id=str(current_user.id),
        account_id=data.account_id,
        password=data.password,
        account_name=data.account_name,
        daily_answer_limit=data.daily_comment_limit,  # comment limit으로 사용
        memo=data.memo
    )

    # 카페용 한도 설정
    account.daily_comment_limit = data.daily_comment_limit
    account.daily_post_limit = data.daily_post_limit
    await db.commit()

    return {
        "success": True,
        "account": {
            "id": account.id,
            "account_id": account.account_id,
            "account_name": account.account_name,
            "status": account.status,
        }
    }


@router.delete("/accounts/{account_id}")
async def delete_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """네이버 계정 삭제"""
    result = await db.execute(
        select(NaverAccount).where(
            and_(
                NaverAccount.id == account_id,
                NaverAccount.user_id == str(current_user.id)
            )
        )
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(404, "계정을 찾을 수 없습니다")

    await db.delete(account)
    await db.commit()
    return {"success": True}


@router.put("/accounts/{account_id}/status")
async def update_account_status(
    account_id: str,
    data: AccountStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """계정 상태 변경"""
    result = await db.execute(
        select(NaverAccount).where(
            and_(
                NaverAccount.id == account_id,
                NaverAccount.user_id == str(current_user.id)
            )
        )
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(404, "계정을 찾을 수 없습니다")

    await account_manager.update_account_status(
        db, account_id, data.status, data.reason
    )

    return {"success": True}


@router.post("/accounts/{account_id}/warmup")
async def start_account_warmup(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """계정 워밍업 시작"""
    result = await db.execute(
        select(NaverAccount).where(
            and_(
                NaverAccount.id == account_id,
                NaverAccount.user_id == str(current_user.id)
            )
        )
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(404, "계정을 찾을 수 없습니다")

    await account_manager.start_warmup(db, account_id)
    return {"success": True, "message": "워밍업이 시작되었습니다"}


@router.get("/accounts/stats")
async def get_account_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """계정 통계"""
    result = await db.execute(
        select(NaverAccount).where(
            NaverAccount.user_id == str(current_user.id)
        )
    )
    accounts = result.scalars().all()

    total = len(accounts)
    active = sum(1 for a in accounts if a.status == AccountStatus.ACTIVE)
    warming = sum(1 for a in accounts if a.is_warming_up)
    resting = sum(1 for a in accounts if a.status == AccountStatus.RESTING)
    error = sum(1 for a in accounts if a.status == AccountStatus.ERROR)

    today_comments = sum(a.today_comments or 0 for a in accounts)
    today_posts = sum(a.today_posts or 0 for a in accounts)
    total_comments = sum(a.total_comments or 0 for a in accounts)
    total_posts = sum(a.total_posts or 0 for a in accounts)

    return {
        "total": total,
        "active": active,
        "warming_up": warming,
        "resting": resting,
        "error": error,
        "today_comments": today_comments,
        "today_posts": today_posts,
        "total_comments": total_comments,
        "total_posts": total_posts,
    }


# ============= 다중 계정 로테이션 게시 =============

@router.post("/poster/post-rotated")
async def post_content_rotated(
    content_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """다중 계정 로테이션으로 콘텐츠 게시"""
    poster = CafePosterService(db)

    try:
        await poster.initialize()

        # 콘텐츠 조회
        result = await db.execute(
            select(CafeContent).where(
                and_(
                    CafeContent.id == content_id,
                    CafeContent.user_id == str(current_user.id)
                )
            )
        )
        content = result.scalar_one_or_none()

        if not content:
            raise HTTPException(404, "콘텐츠를 찾을 수 없습니다")

        if content.content_type == ContentType.COMMENT:
            post_result = await poster.post_comment_rotated(content_id, str(current_user.id))
        elif content.content_type == ContentType.POST:
            post_result = await poster.create_post_rotated(content_id, str(current_user.id))
        else:
            raise HTTPException(400, "지원하지 않는 콘텐츠 유형입니다")

        return post_result

    finally:
        await poster.close()


@router.post("/poster/post-multiple-rotated")
async def post_multiple_rotated(
    limit: int = 5,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """다중 계정 로테이션으로 일괄 게시"""
    poster = CafePosterService(db)

    try:
        await poster.initialize()
        result = await poster.post_multiple_contents_rotated(
            str(current_user.id), limit
        )
        return result

    finally:
        await poster.close()


# ============= 풀 자동화 스케줄러 =============

@router.post("/scheduler/full-automation/start")
async def start_full_automation(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """풀 자동화 시작 (수집 + 생성 + 게시)"""
    scheduler = await get_cafe_scheduler(db, str(current_user.id))
    await scheduler.start_full_automation(str(current_user.id))
    return {"success": True, "message": "풀 자동화가 시작되었습니다"}


@router.post("/scheduler/posting/start")
async def start_posting_scheduler(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """자동 게시만 시작"""
    scheduler = await get_cafe_scheduler(db, str(current_user.id))
    await scheduler.start_posting(str(current_user.id))
    return {"success": True, "message": "자동 게시가 시작되었습니다"}


@router.post("/scheduler/posting/stop")
async def stop_posting_scheduler(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """자동 게시 중지"""
    scheduler = await get_cafe_scheduler(db, str(current_user.id))
    await scheduler.stop_posting()
    return {"success": True, "message": "자동 게시가 중지되었습니다"}


@router.post("/scheduler/run-posting")
async def run_posting_job(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """수동 게시 작업 실행"""
    scheduler = await get_cafe_scheduler(db, str(current_user.id))
    return await scheduler.run_posting_job(str(current_user.id))
