"""발행 큐 API 계약 — 확장 대신 PC 실행기가 블로그별로 가져가는 경로."""
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import publish_queue as api
from app.services.schedule_engine import kst_now
from app.models.publish_queue import NaverCategoryCache, PublishBatch, QueuedPost, ScheduleMark
from app.models.user import User

PIXEL = 'data:image/jpeg;base64,' + 'A' * 64


class QueueApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_async_engine('sqlite+aiosqlite:///' + str(Path(self.tmp.name) / 'queue.db'))
        async with self.engine.begin() as conn:
            for table in (PublishBatch.__table__, QueuedPost.__table__, NaverCategoryCache.__table__, ScheduleMark.__table__):
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

    async def add_post(self, **overrides):
        row = dict(user_id='u', title='글', blocks=[{'type': 'text', 'content': '본문'}],
                   keywords=[], hashtags=[], image_pool_ids=[], image_slots=0,
                   scheduled_at=datetime.utcnow() + timedelta(days=1), status='queued')
        row.update(overrides)
        async with self.sessions() as db:
            post = QueuedPost(**row)
            db.add(post)
            await db.commit()
            return post.id

    def job_body(self, **overrides):
        body = {'title': '제목', 'blocks': [{'type': 'text', 'content': '본문'}, {'type': 'image', 'image': PIXEL}],
                'tags': ['태그'], 'emphasize': ['핵심'],
                'scheduled_at': (kst_now() + timedelta(hours=3)).isoformat(),
                'blog_ref_id': 'blog-1'}
        body.update(overrides)
        return body

    # ---------------------------------------------------------------- 블로그별 수령
    async def test_agent_only_takes_jobs_for_its_own_blog(self):
        mine = await self.add_post(blog_ref_id='blog-1')
        await self.add_post(blog_ref_id='blog-2')
        await self.add_post(blog_ref_id=None)
        response = await self.client.get('/queue/jobs', params={'blog_ref_id': 'blog-1'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([j['id'] for j in response.json()], [mine])

    async def test_unassigned_jobs_need_an_explicit_opt_in(self):
        mine = await self.add_post(blog_ref_id='blog-1')
        legacy = await self.add_post(blog_ref_id=None)
        response = await self.client.get('/queue/jobs', params={'blog_ref_id': 'blog-1', 'claim_unassigned': True})
        self.assertEqual(sorted(j['id'] for j in response.json()), sorted([mine, legacy]))

    async def test_fetched_jobs_are_not_handed_out_twice(self):
        await self.add_post(blog_ref_id='blog-1')
        first = await self.client.get('/queue/jobs', params={'blog_ref_id': 'blog-1'})
        second = await self.client.get('/queue/jobs', params={'blog_ref_id': 'blog-1'})
        self.assertEqual(len(first.json()), 1)
        self.assertEqual(second.json(), [])

    async def test_stored_images_reach_the_agent_untouched(self):
        await self.add_post(blog_ref_id='blog-1', blocks=[{'type': 'text', 'content': '본문'}, {'type': 'image', 'image': PIXEL}])
        job = (await self.client.get('/queue/jobs', params={'blog_ref_id': 'blog-1'})).json()[0]
        self.assertEqual([b['type'] for b in job['blocks']], ['text', 'image'])
        self.assertEqual(job['blocks'][1]['image'], PIXEL)

    async def test_final_action_travels_with_the_job(self):
        await self.add_post(blog_ref_id='blog-1', final_action='draft')
        job = (await self.client.get('/queue/jobs', params={'blog_ref_id': 'blog-1'})).json()[0]
        self.assertEqual(job['finalAction'], 'draft')

    # ---------------------------------------------------------------- 글 1건 담기
    async def test_enqueued_post_comes_back_as_an_agent_job(self):
        created = await self.client.post('/queue/job', json=self.job_body())
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(created.json()['blog_ref_id'], 'blog-1')
        job = (await self.client.get('/queue/jobs', params={'blog_ref_id': 'blog-1'})).json()[0]
        self.assertEqual(job['title'], '제목')
        self.assertEqual(job['tags'], ['태그'])
        self.assertEqual(job['emphasize'], ['핵심'])
        self.assertEqual(job['blocks'][1]['image'], PIXEL)

    async def test_schedule_must_leave_room_for_the_agent_to_open_the_editor(self):
        # 큐의 예약 시각은 네이버 화면에 넣는 KST naive 값이다 — UTC 로 비교하면 9시간 지난
        # 예약도 통과해 실행기가 '이미 지난 시각' 을 네이버에 넣으려다 실패한다.
        for when in (kst_now() - timedelta(hours=1), kst_now() + timedelta(minutes=1),
                     kst_now() - timedelta(hours=8)):
            response = await self.client.post('/queue/job', json=self.job_body(scheduled_at=when.isoformat()))
            self.assertEqual(response.status_code, 400, response.text)

    async def test_immediate_and_draft_need_no_schedule(self):
        for action in ('publish', 'draft'):
            response = await self.client.post('/queue/job', json=self.job_body(final_action=action, scheduled_at=None))
            self.assertEqual(response.status_code, 200, response.text)

    async def test_rejects_junk_payloads(self):
        cases = [self.job_body(blocks=[]), self.job_body(final_action='sideways'),
                 self.job_body(blocks=[{'type': 'image', 'image': 'https://evil.example.com/x.jpg'}]),
                 self.job_body(blocks=[{'type': 'text', 'content': 'x'}] * (api.MAX_JOB_BLOCKS + 1))]
        for body in cases:
            response = await self.client.post('/queue/job', json=body)
            self.assertEqual(response.status_code, 400, response.text)

    # ---------------------------------------------------------------- 카테고리
    async def test_agent_can_fill_the_category_dropdown(self):
        empty = await self.client.get('/categories')
        self.assertEqual(empty.json()['categories'], [])
        saved = await self.client.post('/categories', json={'categories': [{'id': '24', 'name': '칼럼'}]})
        self.assertEqual(saved.status_code, 200, saved.text)
        again = await self.client.get('/categories')
        self.assertEqual(again.json()['categories'], [{'id': '24', 'name': '칼럼'}])

    # ---------------------------------------------------------------- 결과 보고
    async def test_result_marks_the_row_and_keeps_the_message(self):
        post_id = await self.add_post(blog_ref_id='blog-1')
        await self.client.get('/queue/jobs', params={'blog_ref_id': 'blog-1'})
        done = await self.client.post(f'/queue/{post_id}/result', json={'ok': True, 'message': '예약 등록'})
        self.assertEqual(done.status_code, 200, done.text)
        async with self.sessions() as db:
            row = await db.get(QueuedPost, post_id)
            self.assertEqual(row.status, 'published')
            self.assertEqual(row.naver_result, '예약 등록')


if __name__ == '__main__':
    unittest.main()
