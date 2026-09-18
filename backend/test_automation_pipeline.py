import os
os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///./test-unused.db')
os.environ.setdefault('DATABASE_URL_SYNC', 'sqlite:///./test-unused.db')
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models.campaign import Campaign, Blog, Draft, PublishJob, CampaignKeyword
from app.models.background_job import BackgroundJob
from app.models.publish_queue import ScheduleMark, QueuedPost
from app.services import automation_pipeline as pipeline
from app.services.job_worker import JobContext


class PipelineDatabaseCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_async_engine('sqlite+aiosqlite:///' + str(Path(self.tmp.name) / 'pipeline.db'))
        async with self.engine.begin() as conn:
            for table in (Campaign.__table__, Blog.__table__, Draft.__table__, PublishJob.__table__, CampaignKeyword.__table__, BackgroundJob.__table__, ScheduleMark.__table__, QueuedPost.__table__):
                await conn.run_sync(lambda c, t=table: t.create(c))
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.db = self.sessions()
        self.db.add(Campaign(id='c', user_id='u', client_id='client', name='test', blog_ids=['b']))
        self.db.add(Blog(id='b', user_id='u', client_id='client', blog_id='blog', status='active', daily_limit=3))
        self.db.add(Draft(id='d', user_id='u', client_id='client', campaign_id='c', keyword_id='k', keyword='topic', title='title', body='body', status='ready'))
        self.job = BackgroundJob(id='task', user_id='u', type='automation_pipeline', status='running', payload={
            'campaign_id': 'c', 'keyword_ids': ['k'], 'auto_schedule': True, 'image_count': 0,
            'start_date': (datetime.now() + timedelta(days=2)).date().isoformat(), 'days': 14,
        })
        self.db.add(self.job)
        await self.db.commit()

    async def asyncTearDown(self):
        await self.db.close()
        await self.engine.dispose()
        self.tmp.cleanup()

    async def run_pipeline(self):
        with patch.object(pipeline.jobs, 'draft_generate', AsyncMock(return_value={'generated': 1, 'failed': 0})), patch.object(pipeline.jobs, 'prepare_images', AsyncMock(return_value={'prepared': 0})), patch.object(pipeline.jobs, '_bump_stats', AsyncMock()):
            return await pipeline.run(JobContext(db=self.db, job=self.job))


class PipelineTests(PipelineDatabaseCase):
    async def test_replay_does_not_duplicate_scheduled_job(self):
        await self.run_pipeline()
        replay = await self.run_pipeline()
        self.assertEqual(replay['scheduled'], 1)
        self.assertEqual(len((await self.db.execute(select(PublishJob))).scalars().all()), 1)
        self.assertEqual(len((await self.db.execute(select(ScheduleMark))).scalars().all()), 1)

    async def test_review_mode_does_not_schedule(self):
        self.job.payload = {**self.job.payload, 'auto_schedule': False}
        await self.db.commit()
        result = await self.run_pipeline()
        self.assertTrue(result['needs_review'])
        self.assertEqual((await self.db.execute(select(PublishJob))).scalars().all(), [])

    async def test_failed_validation_draft_is_not_scheduled(self):
        draft = await self.db.get(Draft, 'd')
        draft.status = 'needs_review'
        await self.db.commit()
        result = await self.run_pipeline()
        self.assertTrue(result['needs_review'])
        self.assertEqual((await self.db.execute(select(PublishJob))).scalars().all(), [])

    async def test_cancelled_pipeline_does_not_schedule(self):
        self.job.status = 'cancelled'
        await self.db.commit()
        with self.assertRaises(ValueError):
            await self.run_pipeline()
        self.assertEqual((await self.db.execute(select(PublishJob))).scalars().all(), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
