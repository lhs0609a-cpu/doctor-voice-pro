"""카페 일감 잠금 — 같은 글이 두 번 올라가지 않는다.

카페에 같은 글이 두 번 올라가면 그 계정은 바로 광고로 찍힌다. 블로그의 중복 발행보다
되돌리기 어렵다(남의 공간이고, 지워도 기록이 남는다). 그래서 '모르면 다시 올리지 않는다'가
블로그보다 더 강하게 지켜져야 한다.
"""
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.cafe_job import CafeJob
from app.services import cafe_protocol as p


class CafeProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_async_engine('sqlite+aiosqlite:///' + str(Path(self.tmp.name) / 'cafe.db'))
        async with self.engine.begin() as conn:
            await conn.run_sync(lambda sync: CafeJob.__table__.create(sync))
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.sessions() as db:
            for i in range(2):
                db.add(CafeJob(id=f'j{i}', user_id='u', thread_id=f't{i}', account_id='acc-1',
                               cafe_url='https://cafe.naver.com/x',
                               scheduled_at=datetime.utcnow() - timedelta(minutes=5)))
            await db.commit()

    async def asyncTearDown(self):
        await self.engine.dispose()
        self.tmp.cleanup()

    async def claim(self, job='j0', account='acc-1'):
        async with self.sessions() as db:
            return await p.claim(db, job, 'u', account)

    async def test_only_one_launcher_wins_a_job(self):
        tokens = await asyncio.gather(*(self.claim() for _ in range(10)))
        self.assertEqual(sum(t is not None for t in tokens), 1)

    async def test_one_account_cannot_hold_two_jobs(self):
        """계정 하나가 동시에 두 곳에 글을 쓸 수는 없다."""
        tokens = await asyncio.gather(self.claim('j0'), self.claim('j1'))
        self.assertEqual(sum(t is not None for t in tokens), 1)

    async def test_a_job_scheduled_for_later_is_not_handed_out(self):
        async with self.sessions() as db:
            job = await db.get(CafeJob, 'j0')
            job.scheduled_at = datetime.utcnow() + timedelta(hours=2)
            await db.commit()
        self.assertIsNone(await self.claim('j0'))

    async def test_posting_then_losing_the_launcher_is_uncertain_not_retried(self):
        """등록을 누른 뒤 끊긴 것은 '모른다'이다. 다시 올리면 같은 글이 두 번 올라간다."""
        token = await self.claim()
        async with self.sessions() as db:
            await p.checkpoint(db, 'j0', 'u', token, 'posting')
        async with self.sessions() as db:
            job = await db.get(CafeJob, 'j0')
            job.lock_expires_at = datetime.utcnow() - timedelta(seconds=1)
            await db.commit()
        async with self.sessions() as db:
            await p.recover_expired(db, 'u')
            job = await db.get(CafeJob, 'j0')
            self.assertEqual(job.status, 'uncertain')
        self.assertIsNone(await self.claim('j0'), 'uncertain 은 다시 가져가면 안 된다')

    async def test_an_uncertain_job_keeps_holding_its_account(self):
        """확인되지 않은 글이 남아 있는 계정으로 또 올리면 중복 위험이 그대로다."""
        token = await self.claim()
        async with self.sessions() as db:
            await p.checkpoint(db, 'j0', 'u', token, 'posting')
            await p.result(db, 'j0', 'u', token, {'ok': False})
        async with self.sessions() as db:
            self.assertEqual((await db.get(CafeJob, 'j0')).status, 'uncertain')
        self.assertIsNone(await self.claim('j1'), '그 계정은 묶여 있어야 한다')

    async def test_a_clean_success_frees_the_account(self):
        token = await self.claim()
        async with self.sessions() as db:
            await p.checkpoint(db, 'j0', 'u', token, 'posting')
            ack = await p.result(db, 'j0', 'u', token,
                                 {'ok': True, 'url': 'https://cafe.naver.com/x/1'})
        self.assertEqual(ack['status'], 'submitted')
        self.assertIsNotNone(await self.claim('j1'), '끝났으면 그 계정은 다음 일을 받는다')

    async def test_reporting_the_same_result_twice_is_harmless(self):
        token = await self.claim()
        async with self.sessions() as db:
            await p.checkpoint(db, 'j0', 'u', token, 'posting')
            first = await p.result(db, 'j0', 'u', token, {'ok': True, 'url': 'https://cafe.naver.com/x/1'})
            second = await p.result(db, 'j0', 'u', token, {'ok': True, 'url': 'https://cafe.naver.com/x/1'})
        self.assertEqual(first['status'], second['status'])
        async with self.sessions() as db:
            self.assertEqual((await db.get(CafeJob, 'j0')).attempts, 1, '두 번 세면 안 된다')

    async def test_a_launcher_that_never_started_does_not_burn_an_attempt(self):
        token = await self.claim()
        async with self.sessions() as db:
            await p.result(db, 'j0', 'u', token, {'ok': False, 'release': True})
            job = await db.get(CafeJob, 'j0')
        self.assertEqual((job.status, job.attempts), ('queued', 0))

    async def test_a_plain_failure_retries_later(self):
        token = await self.claim()
        async with self.sessions() as db:
            await p.result(db, 'j0', 'u', token, {'ok': False, 'message': '게시판을 찾지 못했습니다'})
            job = await db.get(CafeJob, 'j0')
        self.assertEqual(job.status, 'failed')
        self.assertIsNotNone(job.next_retry_at)
        self.assertIn('게시판', job.error)


if __name__ == '__main__':
    unittest.main()
