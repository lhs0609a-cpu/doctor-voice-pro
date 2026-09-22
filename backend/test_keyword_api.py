"""키워드 목록을 손으로 정리하는 길 — 한 개 지우기와 전부 비우기.

전부 비우기는 '새로 찾기'가 하는 일(replace)을 사용자가 직접 하는 것이다.
지난 판정은 블로그 지수·경쟁이 바뀌면 맞지 않으므로 쌓아 두지 않는다.
"""
import unittest

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from test_publish_protocol import DatabaseCase

from app.api import campaign as api
from app.models.campaign import Campaign, CampaignKeyword, Client
from app.models.user import User


class KeywordCleanupTests(DatabaseCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with self.engine.begin() as conn:
            for table in (Campaign.__table__, Client.__table__, CampaignKeyword.__table__):
                await conn.run_sync(lambda sync, t=table: t.create(sync))
        async with self.sessions() as db:
            db.add(Client(id='client', user_id='u', name='clinic'))
            db.add(Campaign(id='c', user_id='u', client_id='client', name='이번 캠페인'))
            db.add(Campaign(id='other', user_id='u', client_id='client', name='다른 캠페인'))
            for i in range(3):
                db.add(CampaignKeyword(id=f'k{i}', user_id='u', campaign_id='c', keyword=f'아토피{i}'))
            db.add(CampaignKeyword(id='keep', user_id='u', campaign_id='other', keyword='남의 키워드'))
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

    async def ids(self, campaign='c'):
        async with self.sessions() as db:
            return sorted((await db.execute(select(CampaignKeyword.id).where(
                CampaignKeyword.campaign_id == campaign))).scalars())

    async def test_clear_empties_this_campaign_only(self):
        response = await self.client.delete('/campaigns/c/keywords')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['removed'], 3)
        self.assertEqual(await self.ids(), [])
        self.assertEqual(await self.ids('other'), ['keep'])     # 다른 캠페인은 건드리지 않는다

    async def test_clear_twice_is_harmless(self):
        await self.client.delete('/campaigns/c/keywords')
        again = await self.client.delete('/campaigns/c/keywords')
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.json()['removed'], 0)

    async def test_single_delete_still_removes_just_one(self):
        response = await self.client.delete('/campaigns/c/keywords/k1')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(await self.ids(), ['k0', 'k2'])

    async def test_other_users_campaign_is_not_reachable(self):
        async with self.sessions() as db:
            db.add(Campaign(id='theirs', user_id='someone-else', client_id='client', name='남의 것'))
            db.add(CampaignKeyword(id='t1', user_id='someone-else', campaign_id='theirs', keyword='남의 키워드'))
            await db.commit()
        response = await self.client.delete('/campaigns/theirs/keywords')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(await self.ids('theirs'), ['t1'])


if __name__ == '__main__':
    unittest.main()
