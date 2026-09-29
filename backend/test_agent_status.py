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

    async def test_summary_says_how_many_uncertain_jobs_hold_the_blog(self):
        """'확인 필요' 한 건은 그 블로그의 나머지 예약을 전부 멈춘다 — 그 숫자를 실행기에 알린다.

        한 블로그에 미해결 발행은 하나뿐이다(PublishAttempt.active_blog_id 유니크). 서버가 말해
        주지 않으면 실행기는 글쓰기 화면만 새로고침하며 멈춘 것처럼 보인다(2026-09-28 신고)."""
        async with self.sessions() as db:
            db.add(Blog(id='b9', user_id='u', client_id='c', blog_id='myblog', status='active'))
            db.add(PublishJob(id='j-stuck', user_id='u', campaign_id='c', draft_id='d', blog_ref_id='b9',
                              scheduled_at=datetime.utcnow() + timedelta(hours=1), status='uncertain'))
            db.add(PublishJob(id='j-waiting', user_id='u', campaign_id='c', draft_id='d2', blog_ref_id='b9',
                              scheduled_at=datetime.utcnow() + timedelta(hours=3), status='queued'))
            await db.commit()
        row = next(r for r in (await self.client.get('/agent/summary')).json() if r['blog_ref_id'] == 'b9')
        self.assertEqual(row['blocked'], 1)
        self.assertEqual(row['pending'], 1)      # 막힌 건은 대기 수에 섞지 않는다

    async def test_a_job_that_ran_out_of_retries_is_not_counted_as_waiting(self):
        """재시도가 끝난 건을 '대기'로 세면 실행기가 "대기 1건인데 안 내준다"고 말하게 된다.

        2026-09-29 실측: 사용자 화면에 '대기 1건 · 다음 10-03 15:30' 이라고 떠 있는데 서버는
        한 건도 내주지 않았다. 그 건은 이미 여러 번 실패해 멈춰 있었다 — 기다리는 게 아니라
        사람이 손대야 하는 상태였다."""
        async with self.sessions() as db:
            db.add(Blog(id='b7', user_id='u', client_id='c', blog_id='myblog', status='active'))
            db.add(PublishJob(id='j-dead', user_id='u', campaign_id='c', draft_id='d', blog_ref_id='b7',
                              scheduled_at=datetime.utcnow() + timedelta(days=4), status='failed',
                              attempts=3, max_attempts=3, error='검수가 끝난 원고만 발행할 수 있습니다'))
            db.add(PublishJob(id='j-retry', user_id='u', campaign_id='c', draft_id='d2', blog_ref_id='b7',
                              scheduled_at=datetime.utcnow() + timedelta(days=5), status='failed',
                              attempts=1, max_attempts=3))
            await db.commit()
        row = next(r for r in (await self.client.get('/agent/summary')).json() if r['blog_ref_id'] == 'b7')
        self.assertEqual(row['stalled'], 1, '재시도가 끝난 건')
        self.assertEqual(row['pending'], 1, '아직 재시도가 남은 건만 대기다')

    async def test_categories_are_fetched_on_request_and_shown_to_the_app(self):
        """[카테고리 새로 읽기]를 누르면 실행기가 다음 차례에 읽어 오고, 그 목록이 화면에 뜬다.

        카테고리는 네이버 글쓰기 화면 안에만 있다. 블로그에서 카테고리를 새로 만들었을 때
        일주일을 기다리지 않고 바로 가져오려면 사람이 눌러 줄 수 있어야 한다."""
        async with self.sessions() as db:
            db.add(Blog(id='b1', user_id='u', client_id='c', blog_id='dojtp647', status='active',
                        categories=[{'id': '1', 'name': '옛 목록'}], categories_synced_at=datetime.utcnow()))
            await db.commit()
        summary = (await self.client.get('/agent/summary')).json()
        self.assertFalse(summary[0]['wants_categories'])          # 방금 읽었으면 또 읽지 않는다

        blog = (await self.client.post('/blogs/b1/categories/rescan')).json()
        self.assertTrue(blog['categories_pending'])
        summary = (await self.client.get('/agent/summary')).json()
        self.assertTrue(summary[0]['wants_categories'])           # 실행기가 다음 차례에 읽는다

        saved = await self.client.post('/agent/blogs/b1/categories', json={'categories': [
            {'id': '24', 'name': 'PLT 컨설팅 칼럼'}, {'id': '25', 'name': 'PLT 심리학 연구'}]})
        self.assertEqual(saved.json()['saved'], 2)
        summary = (await self.client.get('/agent/summary')).json()
        self.assertFalse(summary[0]['wants_categories'])          # 받았으면 요청은 끝난다

    async def test_an_empty_category_report_never_wipes_the_list(self):
        async with self.sessions() as db:
            db.add(Blog(id='b2', user_id='u', client_id='c', blog_id='x', status='active',
                        categories=[{'id': '1', 'name': '살아 있어야 할 목록'}]))
            await db.commit()
        refused = await self.client.post('/agent/blogs/b2/categories', json={'categories': []})
        self.assertEqual(refused.status_code, 400)

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
