"""Recurring bounded campaigns. Database row locks serialize start, stop and refill."""
from datetime import datetime, timedelta
from sqlalchemy import select, update, func
from pydantic import BaseModel, Field, field_validator
from app.models.campaign import AutopilotPolicy, AutomationRun, Campaign, Blog, Client, Draft, PublishJob
from app.models.background_job import BackgroundJob
from app.services.schedule_engine import kst_now


class PolicyConfig(BaseModel):
    daily_posts: int = Field(default=2, ge=1, le=10)
    buffer_days: int = Field(default=3, ge=1, le=7)
    image_count: int = Field(default=3, ge=0, le=10)
    target_chars: int = Field(default=2000, ge=1200, le=4000)
    min_score: int = Field(default=85, ge=80, le=95)
    max_rewrites: int = Field(default=2, ge=0, le=2)
    daily_generation_limit: int = Field(default=6, ge=1, le=30)
    landing_url: str = Field(default='', max_length=1500)
    landing_label: str = Field(default='자세한 안내 확인하기', min_length=1, max_length=60)
    landing_purpose: str = Field(default='', max_length=300)
    landing_tracking: bool = False

    @field_validator('landing_url')
    @classmethod
    def valid_landing(cls, value):
        from app.services.landing_links import validate_url
        return validate_url(value.strip())


async def preflight(db, campaign, config):
    from app.services.claude_client import resolve_api_key
    from app.core.config import settings
    issues = []
    client = await db.get(Client, campaign.client_id)
    if not client or client.user_id != campaign.user_id or not client.active:
        issues.append('사용 가능한 병원 정보가 없습니다')
    elif not (client.diseases or client.treatments):
        issues.append('병원 정보에 진료 질환 또는 치료 항목을 입력하세요')
    if not await resolve_api_key():
        issues.append('Claude API 키를 설정하세요')
    from app.services.naver_search_credentials import resolve as resolve_search_keys
    if not await resolve_search_keys(db, campaign.user_id):
        issues.append('블로그 아웃리치 > 설정 > 네이버 검색 API에서 키를 저장하세요')
    blogs = (await db.execute(select(Blog).where(Blog.id.in_(campaign.blog_ids or []),
        Blog.user_id == campaign.user_id, Blog.client_id == campaign.client_id,
        Blog.status == 'active'))).scalars().all()
    if not blogs:
        issues.append('정상 상태의 블로그를 캠페인에 연결하세요')
    if config.image_count:
        from app.services.campaign_jobs import _collection_photos
        collection = campaign.collection_id or (client.default_collection_id if client else None)
        photos = await _collection_photos(db, campaign.user_id, collection) if collection else []
        if len(photos) < config.image_count:
            issues.append(f'사진 세트에 사용할 사진 {config.image_count}장 이상을 연결하세요')
    return issues


async def tick(db, campaign_id=None, now=None):
    now = now or datetime.utcnow()
    query = select(AutopilotPolicy.campaign_id).where(AutopilotPolicy.enabled == True,
                                                    AutopilotPolicy.next_run_at <= now)
    if campaign_id:
        query = query.where(AutopilotPolicy.campaign_id == campaign_id)
    ids = list((await db.execute(query.limit(100))).scalars())
    started = []
    for cid in ids:
        # CAS first: transaction owns this policy until quota, run and task commit together.
        won = await db.execute(update(AutopilotPolicy).where(AutopilotPolicy.campaign_id == cid,
            AutopilotPolicy.enabled == True, AutopilotPolicy.next_run_at <= now
        ).values(next_run_at=now + timedelta(minutes=15)))
        if won.rowcount != 1:
            await db.rollback()
            continue
        policy = await db.get(AutopilotPolicy, cid, populate_existing=True)
        campaign = await db.get(Campaign, cid)
        if not campaign or campaign.user_id != policy.user_id or campaign.status == 'cancelled':
            policy.enabled = False
            policy.message = '캠페인이 삭제되었거나 중단되었습니다'
            await db.commit()
            continue
        # Same lock as manual pipeline start / scheduling, consistent lock order policy -> campaign.
        await db.execute(update(Campaign).where(Campaign.id == cid).values(updated_at=now))
        active = await db.get(AutomationRun, cid)
        old = await db.get(BackgroundJob, active.job_id) if active else None
        if old and (old.status in ('pending', 'running') or
                    (old.status == 'cancelled' and old.locked_at and old.updated_at > now - timedelta(minutes=30))):
            policy.message = '진행 중인 작업이 끝나면 자동 보충합니다'
            await db.commit()
            continue
        config = PolicyConfig.model_validate(policy.config)
        await reschedule_missed(db, campaign, config, now)
        day = (now + timedelta(hours=9)).date().isoformat()
        if policy.quota_day != day:
            policy.quota_day, policy.reserved_today = day, 0
        blocked = (await db.execute(select(func.count()).select_from(PublishJob).where(
            PublishJob.campaign_id == cid, PublishJob.status.in_(['uncertain', 'failed'])))).scalar()
        if blocked:
            policy.message = '발행 오류 또는 등록 여부 확인이 필요해 새 원고 생성을 대기합니다'
            await db.commit()
            continue
        inventory = (await db.execute(select(func.count()).select_from(PublishJob).where(
            PublishJob.campaign_id == cid, PublishJob.status.in_(['queued', 'assigned', 'publishing', 'submitted']),
        ))).scalar() or 0
        count = min(config.daily_posts * config.buffer_days - inventory,
                    config.daily_generation_limit - policy.reserved_today, 10)
        if count <= 0:
            policy.message = '예약 재고 또는 오늘의 생성 한도에 도달했습니다'
            await db.commit()
            continue
        client = await db.get(Client, campaign.client_id)
        job = BackgroundJob(user_id=policy.user_id, type='automation_pipeline', status='pending',
            payload={**config.model_dump(), 'campaign_id': cid, 'discover_keywords': True,
                'strict_quality': True, 'autopilot': True, 'max_keywords': count,
                'auto_schedule': True, 'start_date': day, 'days': config.buffer_days + 7,
                'collection_id': campaign.collection_id or (client.default_collection_id if client else None),
                'keyword_ids': []}, run_after=now, max_attempts=2, total=7)
        db.add(job)
        await db.flush()
        if active:
            active.job_id = job.id
        else:
            db.add(AutomationRun(campaign_id=cid, user_id=policy.user_id, job_id=job.id))
        policy.reserved_today += count
        policy.last_job_id = job.id
        policy.message = f'키워드 발굴부터 최대 {count}건 자동 준비 중'
        started.append(job.id)
        await db.commit()
    return started


async def reschedule_missed(db, campaign, config, now):
    """Move only unclaimed queued work; never move an attempted or uncertain publication."""
    from app.services import schedule_engine as schedule
    from app.models.publish_queue import ScheduleMark
    from app.services.editorial_quality import approved
    rows = (await db.execute(select(PublishJob).where(PublishJob.campaign_id == campaign.id,
        PublishJob.status == 'queued', PublishJob.attempts == 0,
        PublishJob.lock_token.is_(None), PublishJob.scheduled_at <= now + timedelta(hours=9, minutes=30),
    ).order_by(PublishJob.blog_ref_id, PublishJob.scheduled_at).limit(30))).scalars().all()
    for job in rows:
        draft = await db.get(Draft, job.draft_id)
        if not draft or not approved(draft):
            continue
        blog = await db.get(Blog, job.blog_ref_id)
        if not blog or blog.status != 'active':
            continue
        await db.execute(update(Blog).where(Blog.id == blog.id).values(status=Blog.status))
        plan = schedule.blog_plan_from_model(blog)
        plan.daily_limit = min(plan.daily_limit, config.daily_posts)
        await schedule.load_taken_slots(db, campaign.user_id, [plan])
        slots, _ = schedule.allocate(1, [plan], (now + timedelta(hours=9)).date(), 14,
            earliest=now + timedelta(hours=9, minutes=90), seed=0)
        if not slots:
            continue
        old_time = job.scheduled_at
        at = slots[0][1]
        changed = await db.execute(update(PublishJob).where(PublishJob.id == job.id,
            PublishJob.status == 'queued', PublishJob.attempts == 0, PublishJob.lock_token.is_(None),
            PublishJob.scheduled_at == old_time).values(scheduled_at=at, error=None))
        if changed.rowcount == 1:
            db.add(ScheduleMark(user_id=campaign.user_id, blog_id=blog.blog_id, scheduled_at=at,
                                title=draft.title[:200], source='automation'))


async def still_enabled(ctx):
    if await ctx.cancelled():
        return False
    if not ctx.payload.get('autopilot'):
        return True
    return (await ctx.db.execute(select(AutopilotPolicy.enabled).where(
        AutopilotPolicy.campaign_id == ctx.payload['campaign_id'],
        AutopilotPolicy.user_id == ctx.user_id))).scalar() is True
