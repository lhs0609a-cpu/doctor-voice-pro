"""실행기 하트비트 계약 — 웹 신호등이 읽는 값."""
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import campaign as api
from app.models.campaign import AgentSession, Blog, PublishAttempt, PublishJob
from app.models.user import User


class AgentStatusTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_async_engine('sqlite+aiosqlite:///' + str(Path(self.tmp.name) / 'agent.db'))
        async with self.engine.begin() as conn:
            await conn.run_sync(lambda sync: AgentSession.__table__.create(sync))
            for table in (PublishJob.__table__, PublishAttempt.__table__, Blog.__table__):
                await conn.run_sync(lambda sync, t=table: t.create(sync))
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        app = FastAPI()
        app.include_router(api.router)

        async def db_override():
            async with self.sessions() as db:
                yield db
        app.dependency_overrides[api.get_db] = db_override
        app.dependency_overrides[api.get_current_user] = lambda: User(id='u')
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test')

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.engine.dispose()
        self.tmp.cleanup()

    def beat(self, **overrides):
        body = {'device_id': 'pc-1', 'version': '1.2.0', 'running': True, 'label': '원장님 PC', 'note': '대기 3건'}
        body.update(overrides)
        return body

    async def test_a_launcher_that_never_takes_the_work_is_called_out(self):
        """켜져 있다는 신호만 보내고 글은 한 번도 가져가지 않는 상태를 짚어 준다.

        실행기 안에서 신호를 보내는 쪽과 글을 올리는 쪽이 따로 돈다. 올리는 쪽의 인증이
        끊기면 초록불은 켜진 채 발행만 영영 시작되지 않는다(2026-09-23 실측)."""
        await self.client.post('/agent/heartbeat', json=self.beat())
        status = (await self.client.get('/agent/status')).json()
        self.assertFalse(status['stalled'])            # 올릴 글이 없으면 멀쩡한 것이다

        async with self.sessions() as db:
            db.add(PublishJob(id='stuck', user_id='u', campaign_id='c', draft_id='d', blog_ref_id='b',
                              scheduled_at=datetime.utcnow() + timedelta(days=1), status='queued',
                              created_at=datetime.utcnow() - timedelta(minutes=30)))
            await db.commit()
        status = (await self.client.get('/agent/status')).json()
        self.assertTrue(status['stalled'])
        self.assertIn('실행 중단', status['stalled_hint'])

    async def test_a_blocked_blog_is_named_instead_of_blaming_the_launcher(self):
        """블로그가 막혀 있으면 실행기를 다시 켜 봐야 소용없다 — 진짜 이유를 그대로 전한다."""
        await self.client.post('/agent/heartbeat', json=self.beat())
        async with self.sessions() as db:
            db.add(PublishJob(id='blocked', user_id='u', campaign_id='c', draft_id='d', blog_ref_id='b',
                              scheduled_at=datetime.utcnow() + timedelta(days=1), status='queued',
                              created_at=datetime.utcnow() - timedelta(minutes=30)))
            db.add(Blog(id='b', user_id='u', client_id='client', blog_id='myblog', status='login_required',
                        status_reason="로그인된 블로그가 다릅니다(예상 'myblog', 현재 'otherblog')."))
            await db.commit()
        status = (await self.client.get('/agent/status')).json()
        self.assertTrue(status['stalled'])
        self.assertIn("현재 'otherblog'", status['stalled_hint'])

    async def test_a_launcher_that_just_took_a_job_is_not_called_out(self):
        await self.client.post('/agent/heartbeat', json=self.beat())
        async with self.sessions() as db:
            db.add(PublishJob(id='stuck2', user_id='u', campaign_id='c', draft_id='d', blog_ref_id='b',
                              scheduled_at=datetime.utcnow() + timedelta(days=1), status='queued',
                              created_at=datetime.utcnow() - timedelta(minutes=30)))
            db.add(PublishAttempt(token='t1', job_id='stuck2', user_id='u', stage='claimed'))
            await db.commit()
        self.assertFalse((await self.client.get('/agent/status')).json()['stalled'])

    async def test_light_turns_on_with_the_first_heartbeat(self):
        before = await self.client.get('/agent/status')
        self.assertEqual(before.json()['online'], False)
        beat = await self.client.post('/agent/heartbeat', json=self.beat())
        self.assertEqual(beat.status_code, 200, beat.text)
        status = (await self.client.get('/agent/status')).json()
        self.assertTrue(status['online'])
        self.assertTrue(status['running'])
        self.assertEqual(status['version'], '1.2.0')
        self.assertEqual(status['devices'][0]['label'], '원장님 PC')
        self.assertEqual(status['devices'][0]['note'], '대기 3건')

    async def test_same_device_updates_one_row(self):
        await self.client.post('/agent/heartbeat', json=self.beat())
        await self.client.post('/agent/heartbeat', json=self.beat(running=False, note='중단됨'))
        status = (await self.client.get('/agent/status')).json()
        self.assertEqual(len(status['devices']), 1)
        self.assertFalse(status['running'])
        self.assertTrue(status['online'])  # 켜져 있지만 발행은 멈춘 상태
        self.assertEqual(status['devices'][0]['note'], '중단됨')

    async def test_silence_turns_the_light_off(self):
        await self.client.post('/agent/heartbeat', json=self.beat())
        async with self.sessions() as db:
            row = await db.get(AgentSession, 'pc-1')
            row.last_seen_at = datetime.utcnow() - timedelta(seconds=api.ONLINE_SECONDS + 30)
            await db.commit()
        status = (await self.client.get('/agent/status')).json()
        self.assertFalse(status['online'])
        self.assertFalse(status['running'])
        self.assertIsNone(status['version'])
        self.assertGreater(status['devices'][0]['seconds_ago'], api.ONLINE_SECONDS)

    async def test_two_computers_are_listed_and_either_one_keeps_it_online(self):
        await self.client.post('/agent/heartbeat', json=self.beat(device_id='pc-1', running=False))
        await self.client.post('/agent/heartbeat', json=self.beat(device_id='pc-2', running=True))
        status = (await self.client.get('/agent/status')).json()
        self.assertEqual(len(status['devices']), 2)
        self.assertTrue(status['online'])
        self.assertTrue(status['running'])

    async def test_another_users_device_is_refused(self):
        async with self.sessions() as db:
            db.add(AgentSession(device_id='pc-1', user_id='someone-else', last_seen_at=datetime.utcnow()))
            await db.commit()
        response = await self.client.post('/agent/heartbeat', json=self.beat())
        self.assertEqual(response.status_code, 403, response.text)

    async def test_device_id_is_required(self):
        response = await self.client.post('/agent/heartbeat', json=self.beat(device_id='  '))
        self.assertEqual(response.status_code, 400, response.text)


if __name__ == '__main__':
    unittest.main()
