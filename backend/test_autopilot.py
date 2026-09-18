import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from sqlalchemy import select, update
from test_automation_pipeline import PipelineDatabaseCase
from app.models.campaign import AutopilotPolicy, AutomationRun, Client, BriefPreset, CampaignKeyword, Draft, PublishJob
from app.models.background_job import BackgroundJob
from app.services import autopilot, editorial_quality as quality, topic_discovery


class AutopilotTests(PipelineDatabaseCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with self.engine.begin() as conn:
            for table in (AutopilotPolicy.__table__, AutomationRun.__table__, Client.__table__, BriefPreset.__table__):
                await conn.run_sync(lambda c, t=table: t.create(c))
        self.now = datetime(2026, 9, 8, 6, 0)
        self.db.add(Client(id='client', user_id='u', name='clinic', diseases=['습진'], regions=['서울']))
        self.db.add(AutopilotPolicy(campaign_id='c', user_id='u', enabled=True,
            config={**autopilot.PolicyConfig().model_dump(), 'image_count': 0}, next_run_at=self.now))
        await self.db.commit()

    async def test_parallel_refill_reserves_quota_once(self):
        async def tick():
            async with self.sessions() as db:
                return await autopilot.tick(db, now=self.now)
        results = await asyncio.gather(*(tick() for _ in range(8)))
        self.assertEqual(sum(map(len, results)), 1)
        p = await self.db.get(AutopilotPolicy, 'c', populate_existing=True)
        self.assertEqual(p.reserved_today, 6)

    async def test_long_handler_refreshes_heartbeat_and_stops_after_return(self):
        from app.services import job_worker
        self.job.updated_at = datetime(2000, 1, 1)
        await self.db.commit()
        async def handler(ctx):
            await asyncio.sleep(.15)
            return {'done': True}
        with patch.object(job_worker, 'AsyncSessionLocal', self.sessions):
            result = await job_worker._run_with_heartbeat(job_worker.JobContext(self.db, self.job), handler, interval=.01)
        self.assertEqual(result, {'done': True})
        row = await self.db.get(BackgroundJob, self.job.id, populate_existing=True)
        first = row.updated_at
        self.assertGreater(first, datetime(2000, 1, 1))
        await asyncio.sleep(.05)
        row = await self.db.get(BackgroundJob, self.job.id, populate_existing=True)
        self.assertEqual(row.updated_at, first)

    async def test_restart_and_reenable_do_not_reset_daily_quota(self):
        await autopilot.tick(self.db, now=self.now)
        p = await self.db.get(AutopilotPolicy, 'c')
        job = await self.db.get(BackgroundJob, p.last_job_id)
        job.status = 'failed'
        p.enabled = False
        await self.db.commit()
        p.enabled = True
        await self.db.commit()
        self.assertEqual(await autopilot.tick(self.db, now=self.now + timedelta(hours=1)), [])
        self.assertEqual(p.reserved_today, 6)
        self.assertEqual(len(await autopilot.tick(self.db, now=self.now + timedelta(days=1))), 1)

    async def test_paused_or_uncertain_campaign_does_not_generate(self):
        p = await self.db.get(AutopilotPolicy, 'c')
        p.enabled = False
        await self.db.commit()
        self.assertEqual(await autopilot.tick(self.db, now=self.now), [])
        p.enabled = True
        self.db.add(PublishJob(user_id='u', campaign_id='c', draft_id='d', blog_ref_id='b',
                               scheduled_at=self.now, status='uncertain'))
        await self.db.commit()
        self.assertEqual(await autopilot.tick(self.db, now=self.now), [])
        self.assertEqual(p.reserved_today, 0)

    async def test_inventory_suppresses_generation(self):
        for i in range(6):
            self.db.add(PublishJob(user_id='u', campaign_id='c', draft_id='d', blog_ref_id='b',
                scheduled_at=self.now + timedelta(days=1), status='submitted'))
        await self.db.commit()
        self.assertEqual(await autopilot.tick(self.db, now=self.now), [])

    async def test_missed_unattempted_job_reschedules_but_uncertain_stays(self):
        draft = await self.db.get(Draft, 'd')
        draft.checks = {'editorial': {'version': 1, 'approved': True,
            'content_hash': quality.fingerprint(draft.title, draft.body)}}
        for jid, status in [('missed', 'queued'), ('unknown', 'uncertain')]:
            self.db.add(PublishJob(id=jid, user_id='u', campaign_id='c', draft_id='d', blog_ref_id='b',
                scheduled_at=self.now, status=status, attempts=0))
        await self.db.commit()
        await autopilot.tick(self.db, now=self.now)
        missed = await self.db.get(PublishJob, 'missed', populate_existing=True)
        unknown = await self.db.get(PublishJob, 'unknown', populate_existing=True)
        self.assertGreater(missed.scheduled_at, self.now + timedelta(hours=9, minutes=30))
        self.assertEqual(unknown.scheduled_at, self.now)
        self.assertEqual(unknown.status, 'uncertain')

    async def test_topic_selection_excludes_previous_and_unrelated(self):
        d = await self.db.get(Draft, 'd')
        d.keyword = '습진 원인'
        for i, keyword in enumerate(['습진원인', '자동차 보험', '습진 관리']):
            self.db.add(CampaignKeyword(id=f'kw{i}', user_id='u', client_id='client', campaign_id='c',
                keyword=keyword, passes_filter=True, in_sheet=False))
        self.job.payload = {**self.job.payload, 'max_keywords': 1}
        self.job.result = {'topic_candidates': [{'keyword': '습진 관리', 'subject': '습진', 'intent': '관리 방법'}]}
        await self.db.commit()
        from app.services.job_worker import JobContext
        from app.models.campaign import Campaign
        with patch.object(topic_discovery.jobs, 'keyword_expand', AsyncMock()), patch.object(topic_discovery.jobs, 'serp_analyze', AsyncMock()):
            ids = await topic_discovery.discover(JobContext(self.db, self.job), await self.db.get(Campaign, 'c'))
        self.assertEqual(ids, ['kw2'])
        self.assertEqual(self.job.payload['keyword_ids'], ['kw2'])

    async def test_strict_generation_to_schedule_and_replay(self):
        from app.services.job_worker import JobContext
        from app.services import automation_pipeline, content_evidence, campaign_writer
        self.db.add(CampaignKeyword(id='fresh', user_id='u', campaign_id='c', client_id='client', keyword='습진 관리'))
        self.job.payload = {**self.job.payload, 'keyword_ids': ['fresh'], 'strict_quality': True,
                            'image_count': 0, 'target_chars': 1200, 'max_rewrites': 0}
        await self.db.commit()
        body = '\n\n'.join(f'{i}번째 설명입니다. ' + ('피부 상태에 따라 필요한 관리를 안내하며 독자의 질문을 차근차근 설명합니다. ' * 7) for i in range(6))
        data = {'title': '습진 관리 알아두어야 할 내용', 'body': body, 'char_count': len(body), 'tags': ['습진']}
        check = {'version': 1, 'approved': True, 'content_hash': quality.fingerprint(data['title'], body),
                 'review': {'used_source_ids': ['s']}}
        with patch.object(content_evidence, 'collect', AsyncMock(return_value=[{'id': 's', 'title': 'source', 'url': 'https://nhs.uk/conditions/eczema'}])), \
             patch.object(campaign_writer, 'write_from_keyword', AsyncMock(return_value=data)), \
             patch.object(quality, 'assess', AsyncMock(return_value=check)):
            await automation_pipeline.run(JobContext(self.db, self.job))
            await automation_pipeline.run(JobContext(self.db, self.job))
        rows = list((await self.db.execute(select(PublishJob))).scalars())
        self.assertEqual(len(rows), 1)
        draft = await self.db.get(Draft, rows[0].draft_id)
        self.assertTrue(quality.approved(draft))
        self.assertIn('참고 자료', draft.body)


if __name__ == '__main__':
    import unittest
    unittest.main()
