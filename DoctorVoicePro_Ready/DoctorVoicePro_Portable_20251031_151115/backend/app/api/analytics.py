"""
Analytics API Router
포스트 분석 및 통계
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import List, Dict
from datetime import datetime, timedelta
from uuid import UUID

from app.db.database import get_db
from app.models import User, Post
from app.api.deps import get_current_user

router = APIRouter()


@router.get("/overview")
async def get_analytics_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    전체 분석 개요

    사용자의 모든 포스팅에 대한 통계를 반환합니다.
    """
    # 전체 포스트 조회
    result = await db.execute(
        select(Post).where(Post.user_id == current_user.id)
    )
    posts = result.scalars().all()

    if not posts:
        return {
            "total_posts": 0,
            "average_persuasion_score": 0,
            "posts_this_month": 0,
            "posts_this_week": 0,
            "time_saved_minutes": 0,
            "status_breakdown": {"draft": 0, "published": 0},
            "top_keywords": [],
            "persuasion_trend": [],
        }

    # 기본 통계
    total_posts = len(posts)
    avg_persuasion = sum(p.persuasion_score for p in posts) / total_posts if posts else 0

    # 이번 달/주 포스트 수
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    week_start = now - timedelta(days=7)

    posts_this_month = sum(1 for p in posts if p.created_at >= month_start)
    posts_this_week = sum(1 for p in posts if p.created_at >= week_start)

    # 시간 절약 계산 (포스트당 60분 가정)
    time_saved = total_posts * 60

    # 상태별 분류
    status_breakdown = {
        "draft": sum(1 for p in posts if p.status == "draft"),
        "published": sum(1 for p in posts if p.status == "published"),
        "archived": sum(1 for p in posts if p.status == "archived"),
    }

    # 상위 키워드 추출
    keyword_counts = {}
    for post in posts:
        if post.seo_keywords:
            for keyword in post.seo_keywords[:5]:  # 각 포스트의 상위 5개 키워드
                keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1

    top_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    # 설득력 트렌드 (최근 30일)
    thirty_days_ago = now - timedelta(days=30)
    recent_posts = [p for p in posts if p.created_at >= thirty_days_ago]

    # 날짜별 평균 설득력
    daily_scores = {}
    for post in recent_posts:
        date_key = post.created_at.strftime("%Y-%m-%d")
        if date_key not in daily_scores:
            daily_scores[date_key] = []
        daily_scores[date_key].append(post.persuasion_score)

    persuasion_trend = [
        {
            "date": date,
            "score": sum(scores) / len(scores),
            "count": len(scores)
        }
        for date, scores in sorted(daily_scores.items())
    ]

    return {
        "total_posts": total_posts,
        "average_persuasion_score": round(avg_persuasion, 2),
        "posts_this_month": posts_this_month,
        "posts_this_week": posts_this_week,
        "time_saved_minutes": time_saved,
        "status_breakdown": status_breakdown,
        "top_keywords": [{"keyword": k, "count": c} for k, c in top_keywords],
        "persuasion_trend": persuasion_trend,
    }


@router.get("/post/{post_id}")
async def get_post_analytics(
    post_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    특정 포스트의 상세 분석

    포스트의 모든 분석 데이터를 반환합니다.
    """
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.user_id == current_user.id)
    )
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="포스팅을 찾을 수 없습니다."
        )

    # 의료법 체크 결과 파싱
    law_check = post.medical_law_check or {}
    is_compliant = law_check.get("is_compliant", True)
    violations = law_check.get("violations", [])
    warnings = law_check.get("warnings", [])

    # 콘텐츠 분석
    content_length = len(post.generated_content) if post.generated_content else 0
    word_count = len(post.generated_content.split()) if post.generated_content else 0

    return {
        "post_id": str(post.id),
        "title": post.title,
        "created_at": post.created_at.isoformat(),
        "status": post.status,

        # 설득력 분석
        "persuasion_score": post.persuasion_score,

        # 의료법 준수
        "law_compliance": {
            "is_compliant": is_compliant,
            "violations_count": len(violations),
            "warnings_count": len(warnings),
            "violations": violations,
            "warnings": warnings,
        },

        # SEO 분석
        "seo": {
            "keywords": post.seo_keywords or [],
            "keywords_count": len(post.seo_keywords) if post.seo_keywords else 0,
            "hashtags": post.hashtags or [],
            "hashtags_count": len(post.hashtags) if post.hashtags else 0,
            "meta_description": post.meta_description,
        },

        # 콘텐츠 통계
        "content_stats": {
            "character_count": content_length,
            "word_count": word_count,
            "estimated_read_time_minutes": round(word_count / 200) if word_count else 0,
        },

        # 발행 정보
        "publishing": {
            "published_at": post.published_at.isoformat() if post.published_at else None,
            "naver_blog_url": post.naver_blog_url,
        }
    }


@router.get("/trends")
async def get_trends(
    days: int = Query(30, ge=7, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    트렌드 분석

    지정된 기간 동안의 트렌드를 분석합니다.
    """
    start_date = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(Post).where(
            Post.user_id == current_user.id,
            Post.created_at >= start_date
        ).order_by(Post.created_at)
    )
    posts = result.scalars().all()

    if not posts:
        return {
            "period_days": days,
            "total_posts": 0,
            "daily_average": 0,
            "score_trend": [],
            "volume_trend": [],
        }

    # 일별 포스트 수
    daily_counts = {}
    daily_scores = {}

    for post in posts:
        date_key = post.created_at.strftime("%Y-%m-%d")

        if date_key not in daily_counts:
            daily_counts[date_key] = 0
            daily_scores[date_key] = []

        daily_counts[date_key] += 1
        daily_scores[date_key].append(post.persuasion_score)

    # 점수 트렌드
    score_trend = [
        {
            "date": date,
            "average_score": round(sum(scores) / len(scores), 2),
            "max_score": round(max(scores), 2),
            "min_score": round(min(scores), 2),
        }
        for date, scores in sorted(daily_scores.items())
    ]

    # 볼륨 트렌드
    volume_trend = [
        {
            "date": date,
            "count": count
        }
        for date, count in sorted(daily_counts.items())
    ]

    return {
        "period_days": days,
        "total_posts": len(posts),
        "daily_average": round(len(posts) / days, 2),
        "score_trend": score_trend,
        "volume_trend": volume_trend,
    }


@router.get("/comparison")
async def get_comparison(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    기간별 비교 분석

    이번 달과 지난 달의 통계를 비교합니다.
    """
    now = datetime.utcnow()

    # 이번 달
    this_month_start = datetime(now.year, now.month, 1)
    result = await db.execute(
        select(Post).where(
            Post.user_id == current_user.id,
            Post.created_at >= this_month_start
        )
    )
    this_month_posts = result.scalars().all()

    # 지난 달
    if now.month == 1:
        last_month_start = datetime(now.year - 1, 12, 1)
        last_month_end = datetime(now.year, 1, 1)
    else:
        last_month_start = datetime(now.year, now.month - 1, 1)
        last_month_end = this_month_start

    result = await db.execute(
        select(Post).where(
            Post.user_id == current_user.id,
            Post.created_at >= last_month_start,
            Post.created_at < last_month_end
        )
    )
    last_month_posts = result.scalars().all()

    def get_stats(posts):
        if not posts:
            return {"count": 0, "avg_score": 0, "published": 0}

        return {
            "count": len(posts),
            "avg_score": round(sum(p.persuasion_score for p in posts) / len(posts), 2),
            "published": sum(1 for p in posts if p.status == "published"),
        }

    this_month = get_stats(this_month_posts)
    last_month = get_stats(last_month_posts)

    # 변화율 계산
    def calc_change(current, previous):
        if previous == 0:
            return 100 if current > 0 else 0
        return round(((current - previous) / previous) * 100, 2)

    return {
        "this_month": this_month,
        "last_month": last_month,
        "changes": {
            "count_change_percent": calc_change(this_month["count"], last_month["count"]),
            "score_change_percent": calc_change(this_month["avg_score"], last_month["avg_score"]),
            "published_change_percent": calc_change(this_month["published"], last_month["published"]),
        }
    }
