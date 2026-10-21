"""지운 병원은 실행기 눈에서도 사라져야 한다.

2026-10-20 신고: "여기 병원들을 삭제할 수 있는 방법이 있나요? 닥터보이스 시작 시 창이
여러개가 떠서 조금 느려지네요. 아마 현석님께 2단계 알림도 계속 가는듯합니다."

병원 삭제는 active=False 로만 표시한다(delete_client). 그런데 실행기에게 블로그 목록을
내주는 agent_summary 는 그 표시를 보지 않고 **사용자의 모든 블로그**를 내줬다. 화면에는
병원도 블로그도 안 보이는데, 실행기는 매 바퀴 그 블로그까지 들러 크롬 창을 하나 더 열고
네이버에 로그인한다 → 창이 늘고, 블로그 주인에게 2단계 인증 알림이 계속 간다.
"""
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import campaign as api
from app.models.campaign import Blog, BriefPreset, Client, PublishJob
from app.models.publish_queue import QueuedPost
from app.models.user import User


class DeletedClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_async_engine('sqlite+aiosqlite:///' + str(Path(self.tmp.name) / 'clients.db'))
        async with self.engine.begin() as conn:
            for table in (Client.__table__, Blog.__table__, BriefPreset.__table__, PublishJob.__table__,
                          QueuedPost.__table__):
                await conn.run_sync(lambda sync, t=table: t.create(sync))
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.sessions() as db:
            for key, name in (('keep', '위례한의원'), ('gone', '안 쓰는 병원')):
                db.add(Client(id=key, user_id='u', name=name, active=True))
                db.add(Blog(id=f'b-{key}', user_id='u', client_id=key, blog_id=f'blog-{key}'))
                db.add(PublishJob(id=f'j-{key}', user_id='u', campaign_id='c', draft_id='d',
                                  blog_ref_id=f'b-{key}', scheduled_at=datetime.utcnow() + timedelta(days=1),
                                  status='queued'))
            await db.commit()

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

    async def blogs_the_launcher_sees(self):
        response = await self.client.get('/agent/summary')
        self.assertEqual(response.status_code, 200, response.text)
        return sorted(row['naver_blog_id'] for row in response.json())

    async def test_a_deleted_hospitals_blog_is_no_longer_handed_to_the_launcher(self):
        self.assertEqual(await self.blogs_the_launcher_sees(), ['blog-gone', 'blog-keep'])

        removed = await self.client.delete('/clients/gone')
        self.assertEqual(removed.status_code, 200, removed.text)

        # 크롬 창도, 네이버 로그인도 더는 일어나지 않는다.
        self.assertEqual(await self.blogs_the_launcher_sees(), ['blog-keep'])

    async def test_the_leftover_reservations_are_collected_not_left_waiting_forever(self):
        """올릴 자리가 없어진 예약을 그대로 두면 '대기'로 영영 쌓이고,
        웹 신호등은 "실행기가 한참째 안 가져갑니다"로 켜진 채 남는다."""
        removed = await self.client.delete('/clients/gone')
        self.assertEqual(removed.json().get('cancelled'), 1, removed.text)

        async with self.sessions() as db:
            self.assertEqual((await db.get(PublishJob, 'j-gone')).status, 'cancelled')
            self.assertEqual((await db.get(PublishJob, 'j-keep')).status, 'queued')  # 남은 병원은 그대로

    async def test_registering_the_same_blog_again_brings_back_its_login(self):
        """2026-10-21: 병원을 지운 뒤 블로그만 다시 쓰려면 로그인·카테고리·링크를 처음부터 넣어야 했다 —
        "작업을 하려면 무조건 이렇게 등록을 해야 하는 시스템". 같은 블로그이므로 예전 값을 되살린다."""
        async with self.sessions() as db:
            old = await db.get(Blog, 'b-gone')
            old.login_id, old.login_pw_enc = 'gone-login', 'encrypted-secret'
            old.categories = [{'id': '7', 'name': '위례'}]
            old.footer_link_url = 'https://example.com/booking'
            await db.commit()
        await self.client.delete('/clients/gone')

        added = await self.client.post('/clients/keep/blogs', json={'blog_id': 'blog-gone'})
        self.assertEqual(added.status_code, 200, added.text)
        body = added.json()
        self.assertEqual(body['login_id'], 'gone-login')
        self.assertTrue(body['has_password'])
        self.assertEqual(body['categories'], [{'id': '7', 'name': '위례'}])
        self.assertEqual(body['footer_link_url'], 'https://example.com/booking')

    async def test_a_failed_post_waiting_for_its_retry_is_told_apart_from_a_refusal(self):
        """2026-10-21 kibundang: 재시도 시각을 기다리는 실패 건을 pending 으로만 세서, 실행기가
        "[조치 필요] 대기 1건을 서버가 내주지 않았습니다"라고 잘못 알렸다."""
        async with self.sessions() as db:
            job = await db.get(PublishJob, 'j-keep')
            job.status, job.attempts, job.max_attempts = 'failed', 1, 3
            job.next_retry_at = datetime.utcnow() + timedelta(minutes=10)
            job.error = '기울임을(를) 빼 달라고 했는데'
            await db.commit()
        row = next(r for r in (await self.client.get('/agent/summary')).json() if r['naver_blog_id'] == 'blog-keep')
        self.assertEqual((row['pending'], row['retrying'], row['working']), (1, 1, 0))
        self.assertIn('기울임', row['retry_reason'])
        self.assertTrue(row['retry_at'])

    async def test_a_restored_hospital_is_handed_back_and_visited_on_the_next_round(self):
        """2026-10-21 신고: 지운 병원의 캠페인이 웹에서는 '정상'으로 보이는데 실행기는 그 블로그를
        받지 못해 크롬 창이 안 열렸다. 되살리면 실행기가 다시 받고, 대기 글이 없어도 다음 바퀴에
        들러야 한다(wants_scan) — 안 그러면 실행기를 껐다 켤 때까지 크롬이 안 열린다."""
        await self.client.delete('/clients/gone')
        self.assertEqual(await self.blogs_the_launcher_sees(), ['blog-keep'])

        restored = await self.client.post('/clients/gone/restore')
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertTrue(restored.json()['active'])

        rows = {row['naver_blog_id']: row for row in (await self.client.get('/agent/summary')).json()}
        self.assertEqual(sorted(rows), ['blog-gone', 'blog-keep'])
        self.assertTrue(rows['blog-gone']['wants_scan'])


if __name__ == '__main__':
    unittest.main()
