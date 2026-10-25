"""네이버 비밀번호 없이 등록한 블로그는 **등록하는 그 자리에서** 말해 준다.

2026-10-25 실측: 한 계정의 블로그 6개 중 4개가 비밀번호 없이 등록돼 있었다
(compete3651·egpebee947·juhdbg58·kibundang). 화면에는 '정상'으로 보였고 예약은 그대로
쌓였는데, 실행기만 "네이버 로그인이 풀렸습니다"에서 멈췄다. 같은 블로그가 비밀번호를
넣어 둔 다른 계정에서는 잘 올라갔기 때문에, 사람 눈에는 **"저 컴퓨터에서는 안 된다"**로
보였다. 그 계정에 붙은 PC 두 대의 발행 시도는 각각 0건과, 블로그 1개분뿐이었다.

막지는 않는다 — PC 에서 직접 로그인해 쓰는 길도 실제로 쓰인다. 다만 등록 즉시
'로그인 필요'로 보여 주어, 예약을 잔뜩 걸어 둔 뒤에 알게 되는 일이 없게 한다.
"""
import unittest

import httpx
from fastapi import FastAPI

from test_publish_protocol import DatabaseCase

from app.api import campaign as api
from app.models.campaign import Blog, Campaign, Client, Draft, PublishJob
from app.models.publish_queue import QueuedPost, ScheduleMark
from app.models.user import User


class BlogWithoutPasswordTest(DatabaseCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with self.engine.begin() as conn:
            for table in (Blog.__table__, Draft.__table__, Campaign.__table__, Client.__table__,
                          ScheduleMark.__table__, QueuedPost.__table__):
                await conn.run_sync(lambda sync, t=table: t.create(sync))
        async with self.sessions() as db:
            db.add(Client(id='client', user_id='u', name='clinic'))
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

    async def add(self, blog_id, **extra):
        body = {'blog_id': blog_id}
        body.update(extra)
        return await self.client.post('/clients/client/blogs', json=body)

    async def test_a_blog_without_a_password_says_so_at_once(self):
        response = await self.add('nopw8164')
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body['status'], 'login_required')
        self.assertIn('비밀번호', body['status_reason'])

    async def test_a_blog_with_a_password_is_normal(self):
        response = await self.add('haspw8164', login_id='clinic01', login_pw='secret-value')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['status'], 'active')

    async def test_the_second_hospital_inherits_the_password_and_stays_normal(self):
        """같은 블로그를 둘째 병원에 붙일 때는 먼저 등록한 줄에서 로그인을 물려받는다."""
        first = await self.add('shared8164', login_id='clinic01', login_pw='secret-value')
        self.assertEqual(first.json()['status'], 'active')
        async with self.sessions() as db:
            db.add(Client(id='client2', user_id='u', name='clinic2'))
            await db.commit()
        again = await self.client.post('/clients/client2/blogs', json={'blog_id': 'shared8164'})
        self.assertEqual(again.status_code, 200, again.text)
        self.assertEqual(again.json()['status'], 'active')


if __name__ == '__main__':
    unittest.main()
