"""Real database transactions, no provider or live account required."""
import asyncio
from datetime import datetime, timedelta
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///./test-unused.db')
os.environ.setdefault('DATABASE_URL_SYNC', 'sqlite:///./test-unused.db')

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models.campaign import PublishJob, PublishAttempt
from app.services import publish_protocol as p


class DatabaseCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_async_engine('sqlite+aiosqlite:///' + str(Path(self.tmp.name) / 'test.db'))
        async with self.engine.begin() as conn:
            for table in (PublishJob.__table__, PublishAttempt.__table__):
                await conn.run_sync(lambda sync, t=table: t.create(sync))
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.sessions() as db:
            for i in range(2):
                db.add(PublishJob(id=f'j{i}', user_id='u', campaign_id='c', draft_id='d', blog_ref_id='b',
                                  scheduled_at=datetime.utcnow() + timedelta(days=1), status='queued'))
            await db.commit()

    async def asyncTearDown(self):
        await self.engine.dispose()
        self.tmp.cleanup()

    async def claim(self, job='j0'):
        async with self.sessions() as db:
            return await p.claim(db, job, 'u', 'b')


class ProtocolTests(DatabaseCase):
    async def test_concurrent_claims_have_one_owner(self):
        tokens = await asyncio.gather(*(self.claim() for _ in range(20)))
        self.assertEqual(sum(t is not None for t in tokens), 1)

    async def test_different_jobs_same_blog_have_one_writer(self):
        tokens = await asyncio.gather(self.claim('j0'), self.claim('j1'))
        self.assertEqual(sum(t is not None for t in tokens), 1)

    async def test_result_replay_and_token_validation(self):
        token = await self.claim()
        async with self.sessions() as db:
            for invalid in (None, 'wrong'):
                with self.assertRaises(p.Conflict):
                    await p.result(db, 'j0', 'u', invalid, {'ok': False})
            a = await p.result(db, 'j0', 'u', token, {'ok': False})
            b = await p.result(db, 'j0', 'u', token, {'ok': False})
            self.assertEqual(a, b)
            self.assertEqual((await db.get(PublishJob, 'j0')).attempts, 1)
            with self.assertRaises(p.Conflict):
                await p.result(db, 'j0', 'u', token, {'ok': True})

    async def test_finalizing_loss_never_requeues(self):
        token = await self.claim()
        async with self.sessions() as db:
            await p.checkpoint(db, 'j0', 'u', token, 'finalizing')
            ack = await p.result(db, 'j0', 'u', token, {'ok': False, 'release': True})
            self.assertEqual(ack['status'], 'uncertain')
        self.assertIsNone(await self.claim('j1'))

    async def test_expired_lease_blocks_final_click(self):
        token = await self.claim()
        async with self.sessions() as db:
            with self.assertRaises(p.Conflict):
                await p.checkpoint(db, 'j0', 'u', token, 'finalizing', datetime.utcnow() + timedelta(hours=1))

    async def test_dry_run_never_finalizes_or_retries(self):
        async with self.sessions() as db:
            token = await p.claim(db, 'j0', 'u', 'b', mode='dry_run')
            with self.assertRaises(p.Conflict):
                await p.checkpoint(db, 'j0', 'u', token, 'finalizing')
            ack = await p.result(db, 'j0', 'u', token, {'ok': False})
            self.assertEqual(ack['status'], 'dry_run')
            self.assertEqual((await db.get(PublishJob, 'j0')).attempts, 0)

    async def test_unproven_success_is_uncertain(self):
        token = await self.claim()
        async with self.sessions() as db:
            ack = await p.result(db, 'j0', 'u', token, {'ok': True})
            self.assertEqual(ack['status'], 'uncertain')

    async def test_concurrent_identical_reports_count_once(self):
        token = await self.claim()
        async def report():
            async with self.sessions() as db:
                return await p.result(db, 'j0', 'u', token, {'ok': False, 'message': 'same'})
        results = await asyncio.gather(*(report() for _ in range(10)))
        self.assertTrue(all(r == results[0] for r in results))
        async with self.sessions() as db:
            self.assertEqual((await db.get(PublishJob, 'j0')).attempts, 1)

    async def test_identified_receipt_is_submitted_not_published(self):
        token = await self.claim()
        async with self.sessions() as db:
            job = await db.get(PublishJob, 'j0')
            job.naver_blog_id = 'testblog'
            await db.commit()
            await p.checkpoint(db, 'j0', 'u', token, 'finalizing')
            ack = await p.result(db, 'j0', 'u', token, {'ok': True, 'url': 'https://blog.naver.com/testblog/123', 'receipt_id': '123'})
            self.assertEqual(ack['status'], 'submitted')
            self.assertIsNone((await db.get(PublishJob, 'j0')).published_at)

    async def test_success_signal_without_receipt_is_submitted_and_frees_blog(self):
        # 최종 발행 단계에서 성공 신호만 봤을 때(글 번호 없음): 네이버 예약됨, 다음 글을 막지 않는다
        token = await self.claim()
        async with self.sessions() as db:
            await p.checkpoint(db, 'j0', 'u', token, 'finalizing')
            ack = await p.result(db, 'j0', 'u', token, {'ok': True, 'url': 'https://blog.naver.com/elsewhere/1', 'message': '발행 레이어 닫힘'})
            self.assertEqual(ack['status'], 'submitted')
            job = await db.get(PublishJob, 'j0')
            self.assertIsNone(job.result_url)      # 다른 블로그 주소는 증거로 남기지 않는다
            self.assertIsNone(job.published_at)    # 공개 확인은 예약 시각 뒤에 따로 한다
            self.assertEqual(job.attempts, 1)
        self.assertIsNotNone(await self.claim('j1'))

    async def test_other_user_cannot_change_checkpoint_or_result(self):
        token = await self.claim()
        async with self.sessions() as db:
            with self.assertRaises(p.Conflict):
                await p.checkpoint(db, 'j0', 'other', token, 'finalizing')
            with self.assertRaises(p.Conflict):
                await p.result(db, 'j0', 'other', token, {'ok': False})


if __name__ == '__main__':
    unittest.main(verbosity=2)
