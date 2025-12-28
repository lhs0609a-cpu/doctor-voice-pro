"""
지식인 확장 기능 API
- 채택률 추적
- 경쟁 답변 분석
- 질문자 분석
- 내공 우선순위
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from app.db.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.knowledge_extended_service import (
    adoption_tracker, competitor_analysis,
    questioner_analysis, reward_priority
)

router = APIRouter()


# ==================== Schemas ====================

class CompetitorAnswerData(BaseModel):
    answer_id: str
    author_name: Optional[str] = None
    author_id: Optional[str] = None
    author_level: Optional[str] = None
    content: str
    has_image: bool = False
    has_link: bool = False
    image_count: int = 0
    is_adopted: bool = False
    like_count: int = 0


class QuestionerData(BaseModel):
    questioner_id: str
    questioner_name: str
    category: Optional[str] = None
    content: Optional[str] = None
    reward_points: int = 0


class RewardRuleCreate(BaseModel):
    name: str
    min_reward_points: int = 0
    max_reward_points: Optional[int] = None
    priority_boost: float = 1.0
    categories: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    exclude_keywords: Optional[List[str]] = None
    max_question_age_hours: Optional[int] = None
    max_existing_answers: Optional[int] = None


# ==================== 채택 추적 ====================

@router.post("/adoption/track")
async def create_adoption_tracking(
    answer_id: str,
    question_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """채택 추적 시작"""
    record = await adoption_tracker.create_adoption_record(
        db, str(current_user.id), answer_id, question_id
    )
    return {"id": record.id, "status": record.status}


@router.put("/adoption/{adoption_id}/check")
async def check_adoption_status(
    adoption_id: str,
    is_adopted: bool,
    total_answers: int = 0,
    adoption_rank: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """채택 상태 확인"""
    record = await adoption_tracker.check_adoption(
        db, adoption_id, is_adopted, total_answers, adoption_rank
    )
    if not record:
        raise HTTPException(status_code=404, detail="Adoption record not found")
    return {"id": record.id, "status": record.status, "is_adopted": record.is_adopted}


@router.get("/adoption/stats")
async def get_adoption_stats(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """채택 통계"""
    return await adoption_tracker.get_adoption_stats(
        db, str(current_user.id), days
    )


# ==================== 경쟁 분석 ====================

@router.post("/competitor/{question_id}/analyze")
async def analyze_competitors(
    question_id: str,
    answers: List[CompetitorAnswerData],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """경쟁 답변 분석"""
    results = await competitor_analysis.analyze_competitor_answers(
        db, str(current_user.id), question_id,
        [a.dict() for a in answers]
    )
    return {
        "question_id": question_id,
        "analyzed_count": len(results),
        "competitors": [
            {
                "id": r.id,
                "author_name": r.author_name,
                "quality_score": r.quality_score,
                "tone": r.tone,
                "strengths": r.strengths,
                "weaknesses": r.weaknesses
            }
            for r in results
        ]
    }


@router.post("/competitor/{question_id}/strategy")
async def create_answer_strategy(
    question_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """답변 전략 생성"""
    strategy = await competitor_analysis.create_strategy(
        db, str(current_user.id), question_id
    )
    return {
        "id": strategy.id,
        "competitor_count": strategy.competitor_count,
        "recommended_length": strategy.recommended_length,
        "recommended_tone": strategy.recommended_tone,
        "recommended_structure": strategy.recommended_structure,
        "include_image": strategy.include_image,
        "differentiation_points": strategy.differentiation_points,
        "adoption_probability": strategy.adoption_probability
    }


# ==================== 질문자 분석 ====================

@router.post("/questioner/analyze")
async def analyze_questioner(
    data: QuestionerData,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """질문자 분석"""
    profile = await questioner_analysis.analyze_questioner(
        db, str(current_user.id),
        data.questioner_id,
        data.questioner_name,
        {
            "category": data.category,
            "content": data.content,
            "reward_points": data.reward_points
        }
    )
    return {
        "id": profile.id,
        "questioner_type": profile.questioner_type,
        "is_potential_customer": profile.is_potential_customer,
        "customer_score": profile.customer_score,
        "total_questions": profile.total_questions,
        "interests": profile.interests,
        "concerns": profile.concerns,
        "avg_reward_points": profile.avg_reward_points
    }


@router.get("/questioner/{questioner_id}")
async def get_questioner_profile(
    questioner_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """질문자 프로필 조회"""
    from sqlalchemy import select, and_
    from app.models.knowledge_extended import QuestionerProfile

    result = await db.execute(
        select(QuestionerProfile).where(
            and_(
                QuestionerProfile.user_id == str(current_user.id),
                QuestionerProfile.questioner_id == questioner_id
            )
        )
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return {
        "id": profile.id,
        "questioner_id": profile.questioner_id,
        "questioner_name": profile.questioner_name,
        "questioner_type": profile.questioner_type,
        "is_potential_customer": profile.is_potential_customer,
        "customer_score": profile.customer_score,
        "total_questions": profile.total_questions,
        "question_categories": profile.question_categories,
        "interests": profile.interests,
        "concerns": profile.concerns,
        "avg_reward_points": profile.avg_reward_points,
        "first_seen_at": profile.first_seen_at,
        "last_seen_at": profile.last_seen_at
    }


# ==================== 내공 우선순위 ====================

@router.post("/priority/rules")
async def create_priority_rule(
    data: RewardRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """우선순위 규칙 생성"""
    rule = await reward_priority.create_rule(
        db=db,
        user_id=str(current_user.id),
        name=data.name,
        min_reward=data.min_reward_points,
        max_reward=data.max_reward_points,
        priority_boost=data.priority_boost,
        categories=data.categories,
        keywords=data.keywords,
        exclude_keywords=data.exclude_keywords,
        max_question_age_hours=data.max_question_age_hours,
        max_existing_answers=data.max_existing_answers
    )
    return {"id": rule.id, "name": rule.name}


@router.get("/priority/rules")
async def get_priority_rules(
    is_active: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """우선순위 규칙 목록"""
    rules = await reward_priority.get_rules(
        db, str(current_user.id), is_active
    )
    return [
        {
            "id": r.id,
            "name": r.name,
            "min_reward_points": r.min_reward_points,
            "max_reward_points": r.max_reward_points,
            "priority_boost": r.priority_boost,
            "categories": r.categories,
            "keywords": r.keywords,
            "is_active": r.is_active
        }
        for r in rules
    ]


@router.put("/priority/rules/{rule_id}")
async def update_priority_rule(
    rule_id: str,
    is_active: Optional[bool] = None,
    priority_boost: Optional[float] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """규칙 업데이트"""
    from sqlalchemy import select, and_
    from app.models.knowledge_extended import RewardPriorityRule

    result = await db.execute(
        select(RewardPriorityRule).where(
            and_(
                RewardPriorityRule.id == rule_id,
                RewardPriorityRule.user_id == str(current_user.id)
            )
        )
    )
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if is_active is not None:
        rule.is_active = is_active
    if priority_boost is not None:
        rule.priority_boost = priority_boost

    await db.commit()
    return {"success": True}


@router.delete("/priority/rules/{rule_id}")
async def delete_priority_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """규칙 삭제"""
    from sqlalchemy import select, and_
    from app.models.knowledge_extended import RewardPriorityRule

    result = await db.execute(
        select(RewardPriorityRule).where(
            and_(
                RewardPriorityRule.id == rule_id,
                RewardPriorityRule.user_id == str(current_user.id)
            )
        )
    )
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    await db.delete(rule)
    await db.commit()
    return {"success": True}
