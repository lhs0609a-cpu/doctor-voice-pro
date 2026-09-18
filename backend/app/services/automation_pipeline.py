"""Resumable server pipeline using existing generation, photo and schedule logic."""
from datetime import date, datetime
from sqlalchemy import select, update
from app.models.campaign import Blog, Campaign, Draft, PublishJob
from app.models.publish_queue import ScheduleMark
from app.services import campaign_jobs as jobs, schedule_engine as schedule
from app.services.job_worker import JobContext, register


class StageContext(JobContext):
    def __init__(self, parent, payload):
        super().__init__(db=parent.db, job=parent.job)
        self.stage_payload = payload

    @property
    def payload(self):
        return self.stage_payload


@register('automation_pipeline')
async def run(ctx):
    p = ctx.payload
    campaign = await ctx.db.get(Campaign, p['campaign_id'])
    if not campaign or campaign.user_id != ctx.user_id:
        raise ValueError('캠페인 권한을 확인할 수 없습니다')
    from app.services.autopilot import still_enabled
    if not await still_enabled(ctx):
        raise ValueError('자동화가 중단되었습니다')
    if p.get('discover_keywords') and not p.get('keyword_ids'):
        from app.services.topic_discovery import discover
        await discover(ctx, campaign)
        p = ctx.payload
    completed = list((ctx.job.result or {}).get('completed', []))

    async def stage(name, handler, payload):
        if not await still_enabled(ctx):
            raise ValueError('자동화가 취소되었습니다')
        if name in completed:
            return
        await ctx.progress(len(completed), 4, name)
        result = await handler(StageContext(ctx, {**p, **payload}))
        if result and result.get('failed') and not (p.get('strict_quality') and handler is jobs.draft_generate):
            raise ValueError(f"{name}: {result['failed']}건 실패. 오류를 확인한 뒤 재시도하세요")
        completed.append(name)
        ctx.job.result = {**(ctx.job.result or {}), 'completed': completed, name: result}
        await ctx.db.commit()

    await stage('원고 생성', jobs.draft_generate, {'force': False})
    drafts = (await ctx.db.execute(select(Draft).where(
        Draft.campaign_id == campaign.id, Draft.keyword_id.in_(p['keyword_ids']),
        Draft.status == 'ready',
    ))).scalars().all()
    if p.get('strict_quality'):
        from app.services.editorial_quality import approved
        drafts = [d for d in drafts if approved(d)]
    if p.get('discover_keywords') and not p.get('autopilot') and p.get('strict_quality'):
        for draft in drafts:
            draft.checks = {**(draft.checks or {}), 'bulk_publication': {
                'task_id': ctx.job.id, 'image_count': p.get('image_count', 0)}}
    ready_count = len(drafts)
    if p.get('image_count', 0):
        draft_ids = [d.id for d in drafts if not d.image_plan]
        if draft_ids:
            await stage('사진 배치', jobs.image_plan, {'draft_ids': draft_ids})
    if not p.get('auto_schedule'):
        return {**(ctx.job.result or {}), 'needs_review': True, 'ready': len(drafts)}
    if not await still_enabled(ctx):
        return {'cancelled': True}

    # Only approved/validated drafts; a previously created job prevents replay
    # from generating a second publication even after the job was published.
    await ctx.db.execute(update(Campaign).where(Campaign.id == campaign.id).values(updated_at=datetime.utcnow()))
    existing = set((await ctx.db.execute(select(PublishJob.draft_id).where(
        PublishJob.campaign_id == campaign.id, PublishJob.status != 'cancelled',
    ))).scalars().all())
    previously_scheduled = sum(d.id in existing for d in drafts)
    drafts = [d for d in drafts if d.id not in existing]
    blogs = (await ctx.db.execute(select(Blog).where(
        Blog.user_id == ctx.user_id, Blog.client_id == campaign.client_id,
        Blog.id.in_(campaign.blog_ids or []), Blog.status == 'active',
    ))).scalars().all()
    if not blogs:
        raise ValueError('캠페인에 정상 블로그를 연결하세요')
    for blog in sorted(blogs, key=lambda b: b.id):
        await ctx.db.execute(update(Blog).where(Blog.id == blog.id).values(status=Blog.status))
    if p.get('image_count', 0) and any(not d.image_plan for d in drafts):
        raise ValueError('필수 사진 계획이 누락되었습니다')
    plans = [schedule.blog_plan_from_model(b) for b in blogs]
    if p.get('autopilot'):
        # Distribute the campaign daily quota across its blogs, including existing slots below.
        quota = p['daily_posts']
        plans = sorted(plans, key=lambda b: b.ref_id)
        for index, plan in enumerate(plans):
            plan.daily_limit = min(plan.daily_limit, quota // len(plans) + (index < quota % len(plans)))
        plans = [plan for plan in plans if plan.daily_limit > 0]
    await schedule.load_taken_slots(ctx.db, ctx.user_id, plans)
    assigned, remaining = schedule.allocate(len(drafts), plans, date.fromisoformat(p['start_date']), p['days'], seed=0)
    by_ref = {b.id: b for b in blogs}
    for draft, (ref, at) in zip(drafts, assigned):
        blog = by_ref[ref]
        ctx.db.add(PublishJob(user_id=ctx.user_id, campaign_id=campaign.id, draft_id=draft.id,
                              blog_ref_id=ref, naver_blog_id=blog.blog_id, scheduled_at=at,
                              status='queued', category=blog.default_category, open_type=blog.open_type))
        ctx.db.add(ScheduleMark(user_id=ctx.user_id, blog_id=blog.blog_id, scheduled_at=at,
                               title=draft.title[:200], source='automation'))
    campaign.step = 6
    campaign.status = 'scheduled'
    await ctx.db.commit()
    await stage('사진 준비', jobs.prepare_images, {})
    await jobs._bump_stats(ctx, campaign.id)
    return {**(ctx.job.result or {}), 'scheduled': len(assigned) + previously_scheduled, 'unassigned': remaining,
            'selected': len(p['keyword_ids']), 'ready': ready_count,
            'needs_review': ready_count < len(p['keyword_ids'])}
