"""로그인 아이디와 블로그 주소가 다를 때.

네이버는 lhs0609c 로 로그인해도 블로그가 blog.naver.com/platonmarketing 일 수 있다.
등록 칸에 아이디를 적어 둔 사람은 아무 잘못이 없는데 발행이 영영 막혔다(2026-09-23 실측).
저장된 값이 '로그인 아이디 그대로'일 때만 주소로 맞춰 준다 — 남의 블로그에 쏘는 것이 제일 나쁘다.
"""
import unittest
from datetime import datetime, timedelta

import httpx
from fastapi import FastAPI

from test_publish_protocol import DatabaseCase

from app.api import campaign as api
from app.models.campaign import Blog, Campaign, Client, Draft, PublishJob
from app.models.publish_queue import QueuedPost, ScheduleMark
from app.models.user import User


class BlogIdentityTest(DatabaseCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with self.engine.begin() as conn:
            for table in (Blog.__table__, Draft.__table__, Campaign.__table__, Client.__table__,
                          ScheduleMark.__table__, QueuedPost.__table__):
                await conn.run_sync(lambda sync, t=table: t.create(sync))
        async with self.sessions() as db:
            db.add(Client(id='client', user_id='u', name='clinic'))
            db.add(Campaign(id='c', user_id='u', client_id='client', name='test', blog_ids=['b']))
            db.add(Blog(id='b', user_id='u', client_id='client', blog_id='lhs0609c',
                        login_id='lhs0609c', status='login_required'))
            job = await db.get(PublishJob, 'j0')
            job.naver_blog_id = 'lhs0609c'
            db.add(ScheduleMark(user_id='u', blog_id='lhs0609c', scheduled_at=job.scheduled_at, source='campaign'))
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
        await super().asyncTearDown()

    async def post(self, blog_id: str):
        return await self.client.post('/agent/blogs/b/identity', json={'blog_id': blog_id})

    async def test_an_id_written_where_the_address_belongs_is_corrected(self):
        response = await self.post('platonmarketing')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()['adopted'])
        async with self.sessions() as db:
            blog = await db.get(Blog, 'b')
            self.assertEqual(blog.blog_id, 'platonmarketing')
            self.assertEqual(blog.status, 'active')
            self.assertEqual((await db.get(PublishJob, 'j0')).naver_blog_id, 'platonmarketing')
            marks = (await db.execute(ScheduleMark.__table__.select())).all()
            self.assertEqual([m.blog_id for m in marks], ['platonmarketing'])

    async def test_a_real_address_is_never_swapped_under_the_user(self):
        """주소를 제대로 적어 둔 블로그는 건드리지 않는다 — 다른 계정으로 로그인했을 뿐일 수 있다."""
        async with self.sessions() as db:
            (await db.get(Blog, 'b')).blog_id = 'myclinicblog'
            await db.commit()
        response = await self.post('someoneelse')
        self.assertFalse(response.json()['adopted'])
        async with self.sessions() as db:
            self.assertEqual((await db.get(Blog, 'b')).blog_id, 'myclinicblog')

    async def test_an_address_another_blog_already_uses_is_refused(self):
        async with self.sessions() as db:
            db.add(Blog(id='b2', user_id='u', client_id='client', blog_id='platonmarketing', status='active'))
            await db.commit()
        response = await self.post('platonmarketing')
        self.assertFalse(response.json()['adopted'])
        self.assertIn('이미 등록', response.json()['reason'])

    async def test_the_same_address_is_a_no_op(self):
        response = await self.post('lhs0609c')
        self.assertFalse(response.json()['adopted'])


if __name__ == '__main__':
    unittest.main()
