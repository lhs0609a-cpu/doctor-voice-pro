"""한 계정을 PC 여러 대가 나눠 쓸 때 서로의 발행을 끊지 않는다(2026-10-01 사고).

증상: "저 소잠원고 올리는중인데 실행기 연결이 끊겼다고 알림이 떠서요."
원인: 잠금 만료 복구(recover_expired)가 **계정 전체**를 쓸었다. 다른 PC의 실행기가
일거리를 물으러 오기만 해도, 리스(120초)가 잠깐 지난 남의 진행 중인 글이
'확인 필요'로 떨어졌다. '확인 필요'는 그 블로그를 쥐고 있어 뒤 예약이 전부 멈춘다.
"""
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


class DeviceScopeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_async_engine('sqlite+aiosqlite:///' + str(Path(self.tmp.name) / 'test.db'))
        async with self.engine.begin() as conn:
            for table in (PublishJob.__table__, PublishAttempt.__table__):
                await conn.run_sync(lambda sync, t=table: t.create(sync))
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.sessions() as db:
            for i in range(3):
                db.add(PublishJob(id=f'j{i}', user_id='u', campaign_id='c', draft_id='d',
                                  blog_ref_id=f'b{i}', scheduled_at=datetime.utcnow() + timedelta(days=1),
                                  status='queued'))
            await db.commit()

    async def asyncTearDown(self):
        await self.engine.dispose()
        self.tmp.cleanup()

    async def hold(self, job, blog, device):
        """그 PC가 글을 쥐게 하고, 잠금은 이미 만료된 상태로 만든다."""
        async with self.sessions() as db:
            token = await p.claim(db, job, 'u', blog, device_id=device)
            self.assertIsNotNone(token)
            row = await db.get(PublishJob, job)
            row.lock_expires_at = datetime.utcnow() - timedelta(seconds=1)
            await db.commit()
            return token

    async def status(self, job):
        async with self.sessions() as db:
            return (await db.get(PublishJob, job)).status

    async def recover(self, device=None):
        async with self.sessions() as db:
            await p.recover_expired(db, 'u', device_id=device)

    async def test_another_pc_keeps_its_own_job(self):
        await self.hold('j0', 'b0', 'pc-A')
        await self.recover(device='pc-B')          # B 가 일거리를 물으러 왔다
        self.assertEqual(await self.status('j0'), 'assigned')

    async def test_my_own_expired_job_is_still_recovered(self):
        await self.hold('j0', 'b0', 'pc-A')
        await self.recover(device='pc-A')
        self.assertEqual(await self.status('j0'), 'uncertain')

    async def test_old_launcher_without_a_device_is_recovered_as_before(self):
        """기기를 알려 주지 않는 옛 실행기가 쥔 글은 예전처럼 복구한다."""
        await self.hold('j0', 'b0', None)
        await self.recover(device='pc-B')
        self.assertEqual(await self.status('j0'), 'uncertain')

    async def held_blogs(self):
        async with self.sessions() as db:
            from sqlalchemy import select
            return set((await db.execute(select(PublishAttempt.active_blog_id).where(
                PublishAttempt.active_blog_id.isnot(None)))).scalars().all())

    async def test_a_cancelled_job_lets_go_of_its_blog(self):
        """취소된 글이 블로그를 쥐고 있으면 그 블로그는 영영 다음 글을 받지 못한다.

        active_blog_id 는 유니크라, 쥔 줄이 하나 남으면 claim 이 전부 조용히 실패한다 —
        사유조차 안 남아서 화면에는 '대기 N건'만 뜬다. 실행기는 "서버가 내주지 않았습니다"만
        외친다. 놓아 주는 자리가 result()·mark_published()·reconcile() 뿐이었는데, 발행건은
        release_job·자리 비우기·일괄 취소로도 끝난다 — 그 길들은 상태를 가리지 않으므로
        실행기가 글을 쓰는 중(assigned)이어도 취소되고, 그때 쥔 손이 펴지지 않았다.
        2026-10-06 실측: 'juhdbg58' 이 10/05 00:46 부터, 'rimq8164' 는 09/28 부터 막혀 있었다."""
        await self.hold('j0', 'b0', 'pc-A')
        self.assertEqual(await self.held_blogs(), {'b0'})
        async with self.sessions() as db:                 # release_job / 자리 비우기가 하는 일
            (await db.get(PublishJob, 'j0')).status = 'cancelled'
            await db.commit()
        await self.recover(device='pc-A')
        self.assertEqual(await self.held_blogs(), set())
        async with self.sessions() as db:                 # 그리고 다시 내준다
            self.assertIsNotNone(await p.claim(db, 'j1', 'u', 'b0', device_id='pc-A'))

    async def test_an_uncertain_job_keeps_holding_its_blog(self):
        """'확인 필요'는 결과를 모르는 상태다. 쥔 채로 둬야 같은 글이 두 번 올라가지 않는다."""
        await self.hold('j0', 'b0', 'pc-A')
        await self.recover(device='pc-A')                 # 잠금 만료 → uncertain
        self.assertEqual(await self.status('j0'), 'uncertain')
        self.assertEqual(await self.held_blogs(), {'b0'})
        await self.recover(device='pc-A')                 # 몇 번을 쓸어도 놓지 않는다
        self.assertEqual(await self.held_blogs(), {'b0'})

    async def test_a_job_that_vanished_does_not_keep_the_blog(self):
        """발행건이 통째로 사라져도(캠페인 삭제) 그 손은 펴진다."""
        await self.hold('j0', 'b0', 'pc-A')
        async with self.sessions() as db:
            await db.delete(await db.get(PublishJob, 'j0'))
            await db.commit()
        await self.recover(device='pc-A')
        self.assertEqual(await self.held_blogs(), set())

    async def test_the_website_reading_the_list_does_not_cut_anyone_off(self):
        """사람이 발행 목록 화면을 열어 두기만 해도 남의 PC 작업이 끊기면 안 된다."""
        await self.hold('j0', 'b0', 'pc-A')
        await self.hold('j1', 'b1', None)
        await self.recover()                        # 화면은 어느 PC도 아니다
        self.assertEqual(await self.status('j0'), 'assigned')
        self.assertEqual(await self.status('j1'), 'uncertain')

    async def test_each_pc_recovers_only_its_share(self):
        await self.hold('j0', 'b0', 'pc-A')
        await self.hold('j1', 'b1', 'pc-B')
        await self.recover(device='pc-B')
        self.assertEqual(await self.status('j0'), 'assigned')
        self.assertEqual(await self.status('j1'), 'uncertain')


if __name__ == '__main__':
    unittest.main()
