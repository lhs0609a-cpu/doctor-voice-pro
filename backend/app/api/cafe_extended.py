"""
카페 확장 기능 API
- 대댓글 자동화
- 게시판 타겟팅
- 인기글 분석
- 팔로우/좋아요 활동
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from app.db.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.cafe_extended import PopularPostCategory, EngagementType
from app.services.cafe_extended_service import (
    board_targeting, reply_automation,
    popular_post_analysis, engagement_service
)

router = APIRouter()


# ==================== Schemas ====================

class BoardCreate(BaseModel):
    cafe_id: str
    board_id: str
    board_name: str
    board_url: Optional[str] = None
    priority: int = 1
    allow_comment: bool = True
    allow_post: bool = False
    allow_reply: bool = True
    daily_comment_limit: int = 10
    daily_post_limit: int = 2


class BoardKeywords(BaseModel):
    include_keywords: Optional[List[str]] = None
    exclude_keywords: Optional[List[str]] = None


class ReplyTemplateCreate(BaseModel):
    name: str
    category: str
    template_content: str
    trigger_keywords: Optional[List[str]] = None
    trigger_sentiment: Optional[str] = None
    tone: str = "friendly"
    include_promotion: bool = False


class PopularPostData(BaseModel):
    post_id: str
    article_id: Optional[str] = None
    board_id: Optional[str] = None
    title: str
    content: str
    url: Optional[str] = None
    author_name: Optional[str] = None
    author_id: Optional[str] = None
    view_count: int = 0
    comment_count: int = 0
    like_count: int = 0
    image_count: int = 0
    posted_at: Optional[datetime] = None


class EngagementScheduleCreate(BaseModel):
    name: str
    activity_types: List[str]  # like, save, follow
    target_cafes: Optional[List[str]] = None
    target_boards: Optional[List[str]] = None
    target_keywords: Optional[List[str]] = None
    daily_like_limit: int = 30
    daily_save_limit: int = 10
    daily_follow_limit: int = 5
    min_interval: int = 60
    max_interval: int = 300
    working_hours: Optional[Dict[str, str]] = None
    working_days: Optional[List[int]] = None


# ==================== 게시판 타겟팅 ====================

@router.post("/boards")
async def add_board(
    data: BoardCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """게시판 추가"""
    board = await board_targeting.add_board(
        db=db,
        user_id=str(current_user.id),
        cafe_id=data.cafe_id,
        board_id=data.board_id,
        board_name=data.board_name,
        board_url=data.board_url,
        priority=data.priority,
        allow_comment=data.allow_comment,
        allow_post=data.allow_post,
        allow_reply=data.allow_reply,
        daily_comment_limit=data.daily_comment_limit,
        daily_post_limit=data.daily_post_limit
    )
    return {"id": board.id, "board_name": board.board_name}


@router.get("/boards")
async def get_boards(
    cafe_id: Optional[str] = None,
    is_target: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """게시판 목록"""
    boards = await board_targeting.get_boards(
        db, str(current_user.id), cafe_id, is_target
    )
    return [
        {
            "id": b.id,
            "cafe_id": b.cafe_id,
            "board_id": b.board_id,
            "board_name": b.board_name,
            "priority": b.priority,
            "is_target": b.is_target,
            "allow_comment": b.allow_comment,
            "allow_post": b.allow_post,
            "total_comments": b.total_comments,
            "total_posts": b.total_posts,
            "total_likes": b.total_likes
        }
        for b in boards
    ]


@router.put("/boards/{board_id}/keywords")
async def set_board_keywords(
    board_id: str,
    data: BoardKeywords,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """게시판 키워드 필터 설정"""
    await board_targeting.set_board_keywords(
        db, board_id, data.include_keywords, data.exclude_keywords
    )
    return {"success": True}


@router.delete("/boards/{board_id}")
async def delete_board(
    board_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """게시판 삭제"""
    from sqlalchemy import select, and_
    from app.models.cafe_extended import CafeBoard

    result = await db.execute(
        select(CafeBoard).where(
            and_(
                CafeBoard.id == board_id,
                CafeBoard.user_id == str(current_user.id)
            )
        )
    )
    board = result.scalar_one_or_none()

    if not board:
        raise HTTPException(status_code=404, detail="Board not found")

    await db.delete(board)
    await db.commit()
    return {"success": True}


# ==================== 대댓글 자동화 ====================

@router.get("/replies/pending")
async def get_pending_replies(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """응답 대기 대댓글"""
    replies = await reply_automation.get_pending_replies(
        db, str(current_user.id), limit
    )
    return [
        {
            "id": r.id,
            "reply_author": r.reply_author,
            "reply_content": r.reply_content,
            "reply_at": r.reply_at,
            "sentiment": r.sentiment,
            "urgency": r.urgency,
            "original_post_url": r.original_post_url
        }
        for r in replies
    ]


@router.post("/replies/templates")
async def create_reply_template(
    data: ReplyTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """대댓글 템플릿 생성"""
    template = await reply_automation.create_reply_template(
        db=db,
        user_id=str(current_user.id),
        name=data.name,
        category=data.category,
        template_content=data.template_content,
        trigger_keywords=data.trigger_keywords,
        trigger_sentiment=data.trigger_sentiment,
        tone=data.tone,
        include_promotion=data.include_promotion
    )
    return {"id": template.id, "name": template.name}


@router.get("/replies/templates")
async def get_reply_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """대댓글 템플릿 목록"""
    from sqlalchemy import select
    from app.models.cafe_extended import ReplyTemplate

    result = await db.execute(
        select(ReplyTemplate).where(
            ReplyTemplate.user_id == str(current_user.id)
        )
    )
    templates = list(result.scalars().all())

    return [
        {
            "id": t.id,
            "name": t.name,
            "category": t.category,
            "template_content": t.template_content,
            "trigger_keywords": t.trigger_keywords,
            "tone": t.tone,
            "usage_count": t.usage_count,
            "is_active": t.is_active
        }
        for t in templates
    ]


@router.put("/replies/{reply_id}/sent")
async def mark_reply_sent(
    reply_id: str,
    auto_reply_content: str,
    reply_url: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """응답 완료 표시"""
    await reply_automation.mark_reply_sent(
        db, reply_id, auto_reply_content, reply_url
    )
    return {"success": True}


# ==================== 인기글 분석 ====================

@router.post("/popular-posts")
async def save_popular_post(
    cafe_id: str,
    data: PopularPostData,
    category: str = "hot",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """인기글 저장"""
    post = await popular_post_analysis.save_popular_post(
        db=db,
        user_id=str(current_user.id),
        cafe_id=cafe_id,
        post_data=data.dict(),
        category=category
    )
    return {
        "id": post.id,
        "title": post.title,
        "topic": post.topic,
        "reference_score": post.reference_score,
        "success_factors": post.success_factors
    }


@router.get("/popular-posts")
async def get_popular_posts(
    cafe_id: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """인기글 목록"""
    from sqlalchemy import select, and_
    from app.models.cafe_extended import PopularPost

    query = select(PopularPost).where(
        PopularPost.user_id == str(current_user.id)
    )

    if cafe_id:
        query = query.where(PopularPost.cafe_id == cafe_id)
    if category:
        query = query.where(PopularPost.category == category)

    query = query.order_by(PopularPost.reference_score.desc()).limit(limit)

    result = await db.execute(query)
    posts = list(result.scalars().all())

    return [
        {
            "id": p.id,
            "title": p.title,
            "url": p.url,
            "category": p.category,
            "view_count": p.view_count,
            "comment_count": p.comment_count,
            "like_count": p.like_count,
            "topic": p.topic,
            "keywords": p.keywords,
            "success_factors": p.success_factors,
            "reference_score": p.reference_score,
            "posted_at": p.posted_at
        }
        for p in posts
    ]


@router.post("/popular-posts/analyze-patterns")
async def analyze_popular_patterns(
    cafe_id: Optional[str] = None,
    period: str = "week",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """인기글 패턴 분석"""
    pattern = await popular_post_analysis.analyze_patterns(
        db, str(current_user.id), cafe_id, period
    )

    if not pattern:
        return {"message": "No posts to analyze"}

    return {
        "id": pattern.id,
        "analysis_period": pattern.analysis_period,
        "sample_count": pattern.sample_count,
        "title_patterns": pattern.title_patterns,
        "content_patterns": pattern.content_patterns,
        "time_patterns": pattern.time_patterns,
        "success_factors": pattern.success_factors
    }


# ==================== 팔로우/좋아요 활동 ====================

@router.post("/engagement/schedules")
async def create_engagement_schedule(
    data: EngagementScheduleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """활동 스케줄 생성"""
    schedule = await engagement_service.create_schedule(
        db=db,
        user_id=str(current_user.id),
        name=data.name,
        activity_types=data.activity_types,
        target_cafes=data.target_cafes,
        target_boards=data.target_boards,
        target_keywords=data.target_keywords,
        daily_like_limit=data.daily_like_limit,
        daily_save_limit=data.daily_save_limit,
        daily_follow_limit=data.daily_follow_limit,
        min_interval=data.min_interval,
        max_interval=data.max_interval,
        working_hours=data.working_hours,
        working_days=data.working_days
    )
    return {"id": schedule.id, "name": schedule.name}


@router.get("/engagement/schedules")
async def get_engagement_schedules(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """활동 스케줄 목록"""
    from sqlalchemy import select
    from app.models.cafe_extended import EngagementSchedule

    result = await db.execute(
        select(EngagementSchedule).where(
            EngagementSchedule.user_id == str(current_user.id)
        )
    )
    schedules = list(result.scalars().all())

    return [
        {
            "id": s.id,
            "name": s.name,
            "is_active": s.is_active,
            "activity_types": s.activity_types,
            "daily_like_limit": s.daily_like_limit,
            "daily_save_limit": s.daily_save_limit,
            "daily_follow_limit": s.daily_follow_limit,
            "total_likes": s.total_likes,
            "total_saves": s.total_saves,
            "total_follows": s.total_follows,
            "working_hours": s.working_hours
        }
        for s in schedules
    ]


@router.put("/engagement/schedules/{schedule_id}")
async def update_engagement_schedule(
    schedule_id: str,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """스케줄 활성화/비활성화"""
    from sqlalchemy import select, and_
    from app.models.cafe_extended import EngagementSchedule

    result = await db.execute(
        select(EngagementSchedule).where(
            and_(
                EngagementSchedule.id == schedule_id,
                EngagementSchedule.user_id == str(current_user.id)
            )
        )
    )
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if is_active is not None:
        schedule.is_active = is_active

    await db.commit()
    return {"success": True}


@router.post("/engagement/record")
async def record_engagement(
    activity_type: str,
    target_type: str,
    target_id: str,
    target_url: Optional[str] = None,
    target_author: Optional[str] = None,
    is_success: bool = True,
    error_message: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """활동 기록"""
    activity = await engagement_service.record_activity(
        db=db,
        user_id=str(current_user.id),
        activity_type=activity_type,
        target_type=target_type,
        target_id=target_id,
        target_url=target_url,
        target_author=target_author,
        is_success=is_success,
        error_message=error_message
    )
    return {"id": activity.id, "activity_type": activity.activity_type}


@router.get("/engagement/stats")
async def get_engagement_stats(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """활동 통계"""
    return await engagement_service.get_activity_stats(
        db, str(current_user.id), days
    )


@router.get("/engagement/today-count")
async def get_today_count(
    activity_type: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """오늘 활동 수"""
    count = await engagement_service.get_today_activity_count(
        db, str(current_user.id), activity_type
    )
    return {"activity_type": activity_type, "count": count}
