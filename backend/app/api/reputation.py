"""
평판 모니터링 API
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import uuid

from app.db.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.reputation import (
    MonitorProfile, Mention, GeneratedMentionResponse,
    ReputationAlertRule, ReputationAlertLog,
    SpreadIncident, ReputationSnapshot,
    ReputationCompetitor, ReputationCompetitorSnapshot,
    ReputationCrawlJob, PlatformGuide,
    MentionPlatform, MentionSentiment, RiskLevel, MentionStatus,
    ResponseStyle, CrawlJobStatus, AlertSeverity, SpreadStatus, GuideCategory
)

router = APIRouter()


# ==================== Pydantic Schemas ====================

class MonitorProfileCreate(BaseModel):
    business_name: str
    business_type: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    naver_place_id: Optional[str] = None
    google_place_id: Optional[str] = None
    kakao_place_id: Optional[str] = None
    baemin_store_id: Optional[str] = None
    yogiyo_store_id: Optional[str] = None
    keywords: Optional[List[str]] = None
    negative_keywords: Optional[List[str]] = None
    crawl_interval_minutes: int = 60
    enabled_platforms: Optional[List[str]] = None
    alert_email: Optional[str] = None
    alert_phone: Optional[str] = None
    alert_kakao: Optional[str] = None


class MonitorProfileUpdate(BaseModel):
    business_name: Optional[str] = None
    business_type: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    naver_place_id: Optional[str] = None
    google_place_id: Optional[str] = None
    kakao_place_id: Optional[str] = None
    baemin_store_id: Optional[str] = None
    yogiyo_store_id: Optional[str] = None
    keywords: Optional[List[str]] = None
    negative_keywords: Optional[List[str]] = None
    crawl_interval_minutes: Optional[int] = None
    enabled_platforms: Optional[List[str]] = None
    is_active: Optional[bool] = None
    alert_email: Optional[str] = None
    alert_phone: Optional[str] = None
    alert_kakao: Optional[str] = None


class MentionUpdate(BaseModel):
    status: Optional[str] = None
    is_bookmarked: Optional[bool] = None
    note: Optional[str] = None


class GenerateResponseRequest(BaseModel):
    business_context: Optional[str] = None  # 사업장 맥락 정보
    tone: Optional[str] = "professional"  # professional, friendly, formal


class AlertRuleCreate(BaseModel):
    name: str
    severity: str  # critical, warning, info
    platforms: Optional[List[str]] = None
    keyword_contains: Optional[List[str]] = None
    min_risk_score: Optional[int] = None
    sentiment_filter: Optional[List[str]] = None
    min_rating: Optional[float] = None
    max_rating: Optional[float] = None
    notify_email: bool = True
    notify_sms: bool = False
    notify_kakao: bool = False
    notify_webhook_url: Optional[str] = None
    cooldown_minutes: int = 30


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    severity: Optional[str] = None
    platforms: Optional[List[str]] = None
    keyword_contains: Optional[List[str]] = None
    min_risk_score: Optional[int] = None
    sentiment_filter: Optional[List[str]] = None
    min_rating: Optional[float] = None
    max_rating: Optional[float] = None
    notify_email: Optional[bool] = None
    notify_sms: Optional[bool] = None
    notify_kakao: Optional[bool] = None
    notify_webhook_url: Optional[str] = None
    cooldown_minutes: Optional[int] = None
    is_active: Optional[bool] = None


class CompetitorCreate(BaseModel):
    business_name: str
    naver_place_id: Optional[str] = None
    google_place_id: Optional[str] = None
    address: Optional[str] = None


class CrawlTriggerRequest(BaseModel):
    profile_id: str
    platforms: Optional[List[str]] = None  # null이면 모든 활성 플랫폼


# ==================== Profile APIs ====================

@router.post("/profiles")
async def create_profile(
    request: MonitorProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """모니터링 프로필 생성"""
    profile = MonitorProfile(
        id=str(uuid.uuid4()),
        user_id=str(current_user.id),
        business_name=request.business_name,
        business_type=request.business_type,
        address=request.address,
        phone=request.phone,
        naver_place_id=request.naver_place_id,
        google_place_id=request.google_place_id,
        kakao_place_id=request.kakao_place_id,
        baemin_store_id=request.baemin_store_id,
        yogiyo_store_id=request.yogiyo_store_id,
        keywords=request.keywords or [request.business_name],
        negative_keywords=request.negative_keywords,
        crawl_interval_minutes=request.crawl_interval_minutes,
        enabled_platforms=request.enabled_platforms or ["naver_place"],
        alert_email=request.alert_email,
        alert_phone=request.alert_phone,
        alert_kakao=request.alert_kakao,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return _serialize_profile(profile)


@router.get("/profiles")
async def get_profiles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """모니터링 프로필 목록"""
    result = await db.execute(
        select(MonitorProfile)
        .where(MonitorProfile.user_id == str(current_user.id))
        .order_by(desc(MonitorProfile.created_at))
    )
    profiles = result.scalars().all()
    return [_serialize_profile(p) for p in profiles]


@router.get("/profiles/{profile_id}")
async def get_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """모니터링 프로필 상세"""
    profile = await _get_user_profile(db, profile_id, str(current_user.id))
    return _serialize_profile(profile)


@router.put("/profiles/{profile_id}")
async def update_profile(
    profile_id: str,
    request: MonitorProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """모니터링 프로필 수정"""
    profile = await _get_user_profile(db, profile_id, str(current_user.id))
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(profile, key, value)
    await db.commit()
    await db.refresh(profile)
    return _serialize_profile(profile)


@router.delete("/profiles/{profile_id}")
async def delete_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """모니터링 프로필 삭제"""
    profile = await _get_user_profile(db, profile_id, str(current_user.id))
    await db.delete(profile)
    await db.commit()
    return {"message": "프로필이 삭제되었습니다."}


# ==================== Dashboard API ====================

@router.get("/dashboard")
async def get_dashboard(
    profile_id: str = Query(..., description="모니터링 프로필 ID"),
    days: int = Query(30, description="조회 기간 (일)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """대시보드 데이터 조회"""
    uid = str(current_user.id)
    since = datetime.utcnow() - timedelta(days=days)

    # 프로필 확인
    profile = await _get_user_profile(db, profile_id, uid)

    # 기간 내 멘션 통계
    mention_stats = await db.execute(
        select(
            func.count(Mention.id).label("total"),
            func.count().filter(Mention.sentiment == MentionSentiment.POSITIVE).label("positive"),
            func.count().filter(Mention.sentiment == MentionSentiment.NEUTRAL).label("neutral"),
            func.count().filter(Mention.sentiment == MentionSentiment.NEGATIVE).label("negative"),
            func.count().filter(Mention.sentiment == MentionSentiment.MIXED).label("mixed"),
            func.count().filter(Mention.risk_level == RiskLevel.CRITICAL).label("critical"),
            func.count().filter(Mention.status == MentionStatus.NEW).label("unread"),
            func.avg(Mention.rating).label("avg_rating"),
        ).where(and_(
            Mention.profile_id == profile_id,
            Mention.user_id == uid,
            Mention.created_at >= since,
        ))
    )
    stats = mention_stats.one()

    # 최신 스냅샷
    latest_snapshot = await db.execute(
        select(ReputationSnapshot)
        .where(and_(
            ReputationSnapshot.profile_id == profile_id,
            ReputationSnapshot.user_id == uid,
        ))
        .order_by(desc(ReputationSnapshot.snapshot_date))
        .limit(1)
    )
    snapshot = latest_snapshot.scalar_one_or_none()

    # 점수 추이
    score_history = await db.execute(
        select(ReputationSnapshot)
        .where(and_(
            ReputationSnapshot.profile_id == profile_id,
            ReputationSnapshot.user_id == uid,
            ReputationSnapshot.snapshot_date >= since,
        ))
        .order_by(ReputationSnapshot.snapshot_date)
    )
    score_data = score_history.scalars().all()

    # 최근 위험 멘션
    critical_mentions = await db.execute(
        select(Mention)
        .where(and_(
            Mention.profile_id == profile_id,
            Mention.user_id == uid,
            Mention.risk_level.in_([RiskLevel.CRITICAL, RiskLevel.WARNING]),
            Mention.status == MentionStatus.NEW,
        ))
        .order_by(desc(Mention.created_at))
        .limit(5)
    )
    criticals = critical_mentions.scalars().all()

    # 플랫폼별 멘션 분포
    platform_dist = await db.execute(
        select(
            Mention.platform,
            func.count(Mention.id)
        ).where(and_(
            Mention.profile_id == profile_id,
            Mention.user_id == uid,
            Mention.created_at >= since,
        ))
        .group_by(Mention.platform)
    )

    return {
        "profile": _serialize_profile(profile),
        "stats": {
            "total_mentions": stats.total or 0,
            "positive": stats.positive or 0,
            "neutral": stats.neutral or 0,
            "negative": stats.negative or 0,
            "mixed": stats.mixed or 0,
            "critical_count": stats.critical or 0,
            "unread_count": stats.unread or 0,
            "avg_rating": round(float(stats.avg_rating or 0), 1),
        },
        "reputation_score": snapshot.reputation_score if snapshot else None,
        "score_history": [
            {
                "date": s.snapshot_date.isoformat(),
                "score": s.reputation_score,
                "avg_rating": s.avg_rating,
                "positive": s.positive_count,
                "negative": s.negative_count,
            }
            for s in score_data
        ],
        "critical_mentions": [_serialize_mention(m) for m in criticals],
        "platform_distribution": {
            row[0].value: row[1] for row in platform_dist.all()
        },
    }


# ==================== Mentions APIs ====================

@router.get("/mentions")
async def get_mentions(
    profile_id: str = Query(...),
    platform: Optional[str] = None,
    sentiment: Optional[str] = None,
    risk_level: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    is_bookmarked: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """멘션 목록 조회 (필터링)"""
    uid = str(current_user.id)
    conditions = [
        Mention.profile_id == profile_id,
        Mention.user_id == uid,
    ]

    if platform:
        conditions.append(Mention.platform == MentionPlatform(platform))
    if sentiment:
        conditions.append(Mention.sentiment == MentionSentiment(sentiment))
    if risk_level:
        conditions.append(Mention.risk_level == RiskLevel(risk_level))
    if status:
        conditions.append(Mention.status == MentionStatus(status))
    if is_bookmarked is not None:
        conditions.append(Mention.is_bookmarked == is_bookmarked)
    if search:
        conditions.append(or_(
            Mention.content.ilike(f"%{search}%"),
            Mention.title.ilike(f"%{search}%"),
            Mention.author_name.ilike(f"%{search}%"),
        ))

    # Count
    total = (await db.execute(
        select(func.count()).select_from(Mention).where(and_(*conditions))
    )).scalar() or 0

    # Data
    result = await db.execute(
        select(Mention)
        .where(and_(*conditions))
        .order_by(desc(Mention.created_at))
        .offset(skip)
        .limit(limit)
    )
    mentions = result.scalars().all()

    return {
        "total": total,
        "mentions": [_serialize_mention(m) for m in mentions],
    }


@router.get("/mentions/{mention_id}")
async def get_mention_detail(
    mention_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """멘션 상세 조회"""
    mention = await _get_user_mention(db, mention_id, str(current_user.id))

    # 대응 답변도 함께 조회
    responses = await db.execute(
        select(GeneratedMentionResponse)
        .where(GeneratedMentionResponse.mention_id == mention_id)
        .order_by(GeneratedMentionResponse.created_at)
    )
    resp_list = responses.scalars().all()

    result = _serialize_mention(mention)
    result["responses"] = [
        {
            "id": r.id,
            "style": r.style.value,
            "content": r.content,
            "is_selected": r.is_selected,
            "is_posted": r.is_posted,
            "edited_content": r.edited_content,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in resp_list
    ]
    return result


@router.put("/mentions/{mention_id}")
async def update_mention(
    mention_id: str,
    request: MentionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """멘션 상태 업데이트 (읽음/북마크/메모)"""
    mention = await _get_user_mention(db, mention_id, str(current_user.id))
    update_data = request.model_dump(exclude_unset=True)

    if "status" in update_data and update_data["status"]:
        update_data["status"] = MentionStatus(update_data["status"])

    for key, value in update_data.items():
        setattr(mention, key, value)

    await db.commit()
    await db.refresh(mention)
    return _serialize_mention(mention)


@router.post("/mentions/{mention_id}/generate-response")
async def generate_mention_response(
    mention_id: str,
    request: GenerateResponseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """AI 대응 답변 3종 생성 (사과형/설명형/보상형)"""
    mention = await _get_user_mention(db, mention_id, str(current_user.id))

    # 프로필 정보 가져오기
    profile = await _get_user_profile(db, mention.profile_id, str(current_user.id))

    from app.services.reputation_analyzer import ReputationAnalyzer
    analyzer = ReputationAnalyzer()

    responses = await analyzer.generate_responses(
        mention_content=mention.content,
        mention_platform=mention.platform.value,
        mention_rating=mention.rating,
        business_name=profile.business_name,
        business_type=profile.business_type,
        business_context=request.business_context,
        tone=request.tone,
    )

    # 기존 답변 삭제
    existing = await db.execute(
        select(GeneratedMentionResponse)
        .where(GeneratedMentionResponse.mention_id == mention_id)
    )
    for resp in existing.scalars().all():
        await db.delete(resp)

    # 새 답변 저장
    saved_responses = []
    for style_name, content in responses.items():
        resp = GeneratedMentionResponse(
            id=str(uuid.uuid4()),
            mention_id=mention_id,
            style=ResponseStyle(style_name),
            content=content,
        )
        db.add(resp)
        saved_responses.append(resp)

    # 멘션 상태 업데이트
    mention.status = MentionStatus.RESPONDING
    await db.commit()

    return {
        "mention_id": mention_id,
        "responses": [
            {
                "id": r.id,
                "style": r.style.value,
                "content": r.content,
            }
            for r in saved_responses
        ]
    }


# ==================== Alert Rules APIs ====================

@router.post("/alerts/rules")
async def create_alert_rule(
    request: AlertRuleCreate,
    profile_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """알림 규칙 생성"""
    await _get_user_profile(db, profile_id, str(current_user.id))

    rule = ReputationAlertRule(
        id=str(uuid.uuid4()),
        profile_id=profile_id,
        user_id=str(current_user.id),
        name=request.name,
        severity=AlertSeverity(request.severity),
        platforms=request.platforms,
        keyword_contains=request.keyword_contains,
        min_risk_score=request.min_risk_score,
        sentiment_filter=request.sentiment_filter,
        min_rating=request.min_rating,
        max_rating=request.max_rating,
        notify_email=request.notify_email,
        notify_sms=request.notify_sms,
        notify_kakao=request.notify_kakao,
        notify_webhook_url=request.notify_webhook_url,
        cooldown_minutes=request.cooldown_minutes,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return _serialize_alert_rule(rule)


@router.get("/alerts/rules")
async def get_alert_rules(
    profile_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """알림 규칙 목록"""
    result = await db.execute(
        select(ReputationAlertRule)
        .where(and_(
            ReputationAlertRule.profile_id == profile_id,
            ReputationAlertRule.user_id == str(current_user.id),
        ))
        .order_by(desc(ReputationAlertRule.created_at))
    )
    return [_serialize_alert_rule(r) for r in result.scalars().all()]


@router.put("/alerts/rules/{rule_id}")
async def update_alert_rule(
    rule_id: str,
    request: AlertRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """알림 규칙 수정"""
    result = await db.execute(
        select(ReputationAlertRule).where(and_(
            ReputationAlertRule.id == rule_id,
            ReputationAlertRule.user_id == str(current_user.id),
        ))
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="알림 규칙을 찾을 수 없습니다.")

    update_data = request.model_dump(exclude_unset=True)
    if "severity" in update_data and update_data["severity"]:
        update_data["severity"] = AlertSeverity(update_data["severity"])

    for key, value in update_data.items():
        setattr(rule, key, value)

    await db.commit()
    await db.refresh(rule)
    return _serialize_alert_rule(rule)


@router.delete("/alerts/rules/{rule_id}")
async def delete_alert_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """알림 규칙 삭제"""
    result = await db.execute(
        select(ReputationAlertRule).where(and_(
            ReputationAlertRule.id == rule_id,
            ReputationAlertRule.user_id == str(current_user.id),
        ))
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="알림 규칙을 찾을 수 없습니다.")

    await db.delete(rule)
    await db.commit()
    return {"message": "알림 규칙이 삭제되었습니다."}


@router.get("/alerts/logs")
async def get_alert_logs(
    profile_id: str = Query(...),
    severity: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """알림 발송 기록"""
    uid = str(current_user.id)
    conditions = [ReputationAlertLog.user_id == uid]

    if severity:
        conditions.append(ReputationAlertLog.severity == AlertSeverity(severity))

    # profile_id로 연관된 rule의 로그만 가져오기
    rule_ids_query = select(ReputationAlertRule.id).where(
        ReputationAlertRule.profile_id == profile_id
    )
    conditions.append(ReputationAlertLog.rule_id.in_(rule_ids_query))

    total = (await db.execute(
        select(func.count()).select_from(ReputationAlertLog).where(and_(*conditions))
    )).scalar() or 0

    result = await db.execute(
        select(ReputationAlertLog)
        .where(and_(*conditions))
        .order_by(desc(ReputationAlertLog.created_at))
        .offset(skip)
        .limit(limit)
    )
    logs = result.scalars().all()

    return {
        "total": total,
        "logs": [
            {
                "id": log.id,
                "rule_id": log.rule_id,
                "mention_id": log.mention_id,
                "severity": log.severity.value if log.severity else None,
                "title": log.title,
                "message": log.message,
                "channel": log.channel,
                "is_sent": log.is_sent,
                "sent_at": log.sent_at.isoformat() if log.sent_at else None,
                "error_message": log.error_message,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
    }


# ==================== Spread Incident APIs ====================

@router.get("/spread")
async def get_spread_incidents(
    profile_id: str = Query(...),
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """확산 사건 목록"""
    uid = str(current_user.id)
    conditions = [
        SpreadIncident.user_id == uid,
        SpreadIncident.profile_id == profile_id,
    ]
    if status:
        conditions.append(SpreadIncident.status == SpreadStatus(status))

    total = (await db.execute(
        select(func.count()).select_from(SpreadIncident).where(and_(*conditions))
    )).scalar() or 0

    result = await db.execute(
        select(SpreadIncident)
        .where(and_(*conditions))
        .order_by(desc(SpreadIncident.created_at))
        .offset(skip)
        .limit(limit)
    )
    incidents = result.scalars().all()

    return {
        "total": total,
        "incidents": [_serialize_spread(i) for i in incidents],
    }


@router.get("/spread/{incident_id}")
async def get_spread_detail(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """확산 사건 상세 + 타임라인"""
    result = await db.execute(
        select(SpreadIncident).where(and_(
            SpreadIncident.id == incident_id,
            SpreadIncident.user_id == str(current_user.id),
        ))
    )
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="확산 사건을 찾을 수 없습니다.")

    # 관련 멘션
    related = await db.execute(
        select(Mention)
        .where(Mention.spread_incident_id == incident_id)
        .order_by(Mention.published_at)
    )
    mentions = related.scalars().all()

    data = _serialize_spread(incident)
    data["related_mentions"] = [_serialize_mention(m) for m in mentions]
    return data


# ==================== Score History API ====================

@router.get("/score/history")
async def get_score_history(
    profile_id: str = Query(...),
    days: int = Query(90),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """평판 점수 변화 추이"""
    since = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(ReputationSnapshot)
        .where(and_(
            ReputationSnapshot.profile_id == profile_id,
            ReputationSnapshot.user_id == str(current_user.id),
            ReputationSnapshot.snapshot_date >= since,
        ))
        .order_by(ReputationSnapshot.snapshot_date)
    )
    snapshots = result.scalars().all()

    return {
        "profile_id": profile_id,
        "days": days,
        "snapshots": [
            {
                "date": s.snapshot_date.isoformat(),
                "reputation_score": s.reputation_score,
                "avg_rating": s.avg_rating,
                "positive_count": s.positive_count,
                "neutral_count": s.neutral_count,
                "negative_count": s.negative_count,
                "mixed_count": s.mixed_count,
                "platform_stats": s.platform_stats,
                "top_issues": s.top_issues,
            }
            for s in snapshots
        ],
    }


# ==================== Competitor APIs ====================

@router.post("/competitors")
async def add_competitor(
    request: CompetitorCreate,
    profile_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """경쟁사 추가"""
    await _get_user_profile(db, profile_id, str(current_user.id))

    competitor = ReputationCompetitor(
        id=str(uuid.uuid4()),
        profile_id=profile_id,
        user_id=str(current_user.id),
        business_name=request.business_name,
        naver_place_id=request.naver_place_id,
        google_place_id=request.google_place_id,
        address=request.address,
    )
    db.add(competitor)
    await db.commit()
    await db.refresh(competitor)
    return _serialize_competitor(competitor)


@router.get("/competitors")
async def get_competitors(
    profile_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """경쟁사 목록"""
    result = await db.execute(
        select(ReputationCompetitor)
        .where(and_(
            ReputationCompetitor.profile_id == profile_id,
            ReputationCompetitor.user_id == str(current_user.id),
            ReputationCompetitor.is_active == True,
        ))
        .order_by(ReputationCompetitor.created_at)
    )
    return [_serialize_competitor(c) for c in result.scalars().all()]


@router.delete("/competitors/{competitor_id}")
async def delete_competitor(
    competitor_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """경쟁사 삭제"""
    result = await db.execute(
        select(ReputationCompetitor).where(and_(
            ReputationCompetitor.id == competitor_id,
            ReputationCompetitor.user_id == str(current_user.id),
        ))
    )
    comp = result.scalar_one_or_none()
    if not comp:
        raise HTTPException(status_code=404, detail="경쟁사를 찾을 수 없습니다.")

    await db.delete(comp)
    await db.commit()
    return {"message": "경쟁사가 삭제되었습니다."}


# ==================== Guide APIs ====================

@router.get("/guides")
async def get_guides(
    platform: Optional[str] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """플랫폼별 대응 가이드 목록"""
    conditions = [PlatformGuide.is_active == True]

    if platform:
        conditions.append(PlatformGuide.platform == MentionPlatform(platform))
    if category:
        conditions.append(PlatformGuide.category == GuideCategory(category))

    result = await db.execute(
        select(PlatformGuide)
        .where(and_(*conditions))
        .order_by(PlatformGuide.platform, PlatformGuide.category)
    )
    guides = result.scalars().all()

    return [
        {
            "id": g.id,
            "platform": g.platform.value,
            "category": g.category.value,
            "title": g.title,
            "description": g.description,
            "difficulty": g.difficulty,
            "estimated_days": g.estimated_days,
            "success_rate": g.success_rate,
        }
        for g in guides
    ]


@router.get("/guides/{platform}/{category}")
async def get_guide_detail(
    platform: str,
    category: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """특정 가이드 상세"""
    result = await db.execute(
        select(PlatformGuide).where(and_(
            PlatformGuide.platform == MentionPlatform(platform),
            PlatformGuide.category == GuideCategory(category),
            PlatformGuide.is_active == True,
        ))
    )
    guide = result.scalar_one_or_none()
    if not guide:
        raise HTTPException(status_code=404, detail="가이드를 찾을 수 없습니다.")

    return {
        "id": guide.id,
        "platform": guide.platform.value,
        "category": guide.category.value,
        "title": guide.title,
        "description": guide.description,
        "steps": guide.steps,
        "legal_basis": guide.legal_basis,
        "tips": guide.tips,
        "template_text": guide.template_text,
        "difficulty": guide.difficulty,
        "estimated_days": guide.estimated_days,
        "success_rate": guide.success_rate,
    }


# ==================== Crawl Trigger API ====================

@router.post("/crawl/trigger")
async def trigger_crawl(
    request: CrawlTriggerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """수동 크롤링 실행"""
    uid = str(current_user.id)
    profile = await _get_user_profile(db, request.profile_id, uid)

    platforms = request.platforms or profile.enabled_platforms or ["naver_place"]
    jobs = []

    for platform_str in platforms:
        platform_enum = MentionPlatform(platform_str)
        job = ReputationCrawlJob(
            id=str(uuid.uuid4()),
            profile_id=request.profile_id,
            user_id=uid,
            platform=platform_enum,
            status=CrawlJobStatus.PENDING,
            trigger_type="manual",
        )
        db.add(job)
        jobs.append(job)

    await db.commit()

    # 비동기로 크롤링 시작
    from app.services.reputation_crawler import ReputationCrawlerService
    crawler_service = ReputationCrawlerService(db)

    for job in jobs:
        await db.refresh(job)
        try:
            await crawler_service.run_crawl_job(job.id, profile)
        except Exception as e:
            job.status = CrawlJobStatus.FAILED
            job.error_message = str(e)
            await db.commit()

    return {
        "message": f"{len(jobs)}개 플랫폼 크롤링이 시작되었습니다.",
        "jobs": [
            {
                "id": j.id,
                "platform": j.platform.value,
                "status": j.status.value,
                "mentions_found": j.mentions_found,
                "mentions_new": j.mentions_new,
                "error_message": j.error_message,
            }
            for j in jobs
        ],
    }


# ==================== Helper Functions ====================

async def _get_user_profile(db: AsyncSession, profile_id: str, user_id: str) -> MonitorProfile:
    result = await db.execute(
        select(MonitorProfile).where(and_(
            MonitorProfile.id == profile_id,
            MonitorProfile.user_id == user_id,
        ))
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="모니터링 프로필을 찾을 수 없습니다.")
    return profile


async def _get_user_mention(db: AsyncSession, mention_id: str, user_id: str) -> Mention:
    result = await db.execute(
        select(Mention).where(and_(
            Mention.id == mention_id,
            Mention.user_id == user_id,
        ))
    )
    mention = result.scalar_one_or_none()
    if not mention:
        raise HTTPException(status_code=404, detail="멘션을 찾을 수 없습니다.")
    return mention


def _serialize_profile(p: MonitorProfile) -> dict:
    return {
        "id": p.id,
        "user_id": p.user_id,
        "business_name": p.business_name,
        "business_type": p.business_type,
        "address": p.address,
        "phone": p.phone,
        "naver_place_id": p.naver_place_id,
        "google_place_id": p.google_place_id,
        "kakao_place_id": p.kakao_place_id,
        "baemin_store_id": p.baemin_store_id,
        "yogiyo_store_id": p.yogiyo_store_id,
        "keywords": p.keywords,
        "negative_keywords": p.negative_keywords,
        "crawl_interval_minutes": p.crawl_interval_minutes,
        "enabled_platforms": p.enabled_platforms,
        "is_active": p.is_active,
        "alert_email": p.alert_email,
        "alert_phone": p.alert_phone,
        "alert_kakao": p.alert_kakao,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _serialize_mention(m: Mention) -> dict:
    return {
        "id": m.id,
        "profile_id": m.profile_id,
        "platform": m.platform.value if m.platform else None,
        "platform_post_id": m.platform_post_id,
        "source_url": m.source_url,
        "author_name": m.author_name,
        "author_id": m.author_id,
        "title": m.title,
        "content": m.content,
        "rating": m.rating,
        "images": m.images,
        "sentiment": m.sentiment.value if m.sentiment else None,
        "sentiment_score": m.sentiment_score,
        "risk_level": m.risk_level.value if m.risk_level else None,
        "risk_score": m.risk_score,
        "issues": m.issues,
        "spread_potential": m.spread_potential,
        "is_defamation": m.is_defamation,
        "ai_summary": m.ai_summary,
        "platform_data": m.platform_data,
        "status": m.status.value if m.status else None,
        "is_bookmarked": m.is_bookmarked,
        "note": m.note,
        "published_at": m.published_at.isoformat() if m.published_at else None,
        "collected_at": m.collected_at.isoformat() if m.collected_at else None,
        "analyzed_at": m.analyzed_at.isoformat() if m.analyzed_at else None,
        "responded_at": m.responded_at.isoformat() if m.responded_at else None,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def _serialize_alert_rule(r: ReputationAlertRule) -> dict:
    return {
        "id": r.id,
        "profile_id": r.profile_id,
        "name": r.name,
        "is_active": r.is_active,
        "severity": r.severity.value if r.severity else None,
        "platforms": r.platforms,
        "keyword_contains": r.keyword_contains,
        "min_risk_score": r.min_risk_score,
        "sentiment_filter": r.sentiment_filter,
        "min_rating": r.min_rating,
        "max_rating": r.max_rating,
        "notify_email": r.notify_email,
        "notify_sms": r.notify_sms,
        "notify_kakao": r.notify_kakao,
        "notify_webhook_url": r.notify_webhook_url,
        "cooldown_minutes": r.cooldown_minutes,
        "last_triggered_at": r.last_triggered_at.isoformat() if r.last_triggered_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _serialize_spread(i: SpreadIncident) -> dict:
    return {
        "id": i.id,
        "profile_id": i.profile_id,
        "title": i.title,
        "description": i.description,
        "status": i.status.value if i.status else None,
        "first_detected_at": i.first_detected_at.isoformat() if i.first_detected_at else None,
        "platform_count": i.platform_count,
        "mention_count": i.mention_count,
        "estimated_reach": i.estimated_reach,
        "timeline": i.timeline,
        "response_plan": i.response_plan,
        "resolved_at": i.resolved_at.isoformat() if i.resolved_at else None,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }


def _serialize_competitor(c: ReputationCompetitor) -> dict:
    return {
        "id": c.id,
        "profile_id": c.profile_id,
        "business_name": c.business_name,
        "naver_place_id": c.naver_place_id,
        "google_place_id": c.google_place_id,
        "address": c.address,
        "current_rating": c.current_rating,
        "review_count": c.review_count,
        "reputation_score": c.reputation_score,
        "is_active": c.is_active,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }
