"""원클릭 자동화 — 주소 하나를 넣으면 **원고**가 된다.

예전에는 여기서 네이버 오픈 API 로 임시저장까지 하려 했는데, 그 길은 누구도 성공할 수
없었다(2026-09-28 실측: 연동 기록 0건, 콜백 주소가 localhost 로 박혀 있고 그 API 자체가
열리지 않는다). 누르면 '네이버 블로그 연동이 필요합니다'만 떴다.

지금은 원고까지만 만들고 발행은 예약발행(실행기)이 이어받는다. 여기서 지키는 약속 셋.
1) 네이버 연동 없이 된다 — 실제로 글을 올리는 길과 같은 길을 쓴다.
2) 다른 문으로 들어왔다고 검수를 건너뛰지 않는다(의료광고 표현·금칙어).
3) 원고를 넣을 캠페인이 없으면 무엇을 해야 하는지 말해 준다.
"""
import unittest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import crawl as api
from app.models.campaign import Campaign, Client, Draft
from app.models.user import User

CRAWLED = {"success": True, "title": "원본 제목", "content": "원본 본문입니다. " * 20, "images": []}


class OneClickTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_async_engine('sqlite+aiosqlite:///' + str(Path(self.tmp.name) / 'oneclick.db'))
        async with self.engine.begin() as conn:
            for table in (Client.__table__, Campaign.__table__, Draft.__table__):
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

    async def seed(self, *, forbidden=None):
        async with self.sessions() as db:
            db.add(Client(id='c1', user_id='u', name='소잠한의원', forbidden_words=forbidden or []))
            db.add(Campaign(id='cam-old', user_id='u', client_id='c1', name='옛 캠페인',
                            updated_at=datetime.utcnow() - timedelta(days=3)))
            db.add(Campaign(id='cam', user_id='u', client_id='c1', name='이번 캠페인',
                            updated_at=datetime.utcnow()))
            await db.commit()

    async def one_click(self, rewritten='제목: 새 제목\n---\n' + '새 본문입니다. ' * 20, **body):
        with patch.object(api.blog_crawler, 'crawl', AsyncMock(return_value=CRAWLED)), \
                patch.object(api.AIService, 'generate_text', AsyncMock(return_value=rewritten)):
            return await self.client.post('/one-click', json={'url': 'blog.naver.com/someone/123', **body})

    async def test_a_url_becomes_a_draft_without_any_naver_connection(self):
        await self.seed()
        out = (await self.one_click()).json()
        self.assertTrue(out['success'], out)
        self.assertEqual(out['campaign_id'], 'cam')          # 가장 최근에 손댄 캠페인
        self.assertEqual(out['draft_status'], 'ready')
        self.assertIn('예약발행', out['message'])
        async with self.sessions() as db:
            draft = (await db.execute(select(Draft).where(Draft.id == out['draft_id']))).scalars().first()
            self.assertEqual(draft.title, '새 제목')
            self.assertEqual(draft.source, 'crawl')
            self.assertEqual(draft.checks['source_url'], 'https://blog.naver.com/someone/123')

    async def test_the_chosen_campaign_wins_over_the_latest_one(self):
        await self.seed()
        out = (await self.one_click(campaign_id='cam-old')).json()
        self.assertEqual(out['campaign_id'], 'cam-old')

    async def test_someone_elses_campaign_is_refused(self):
        await self.seed()
        async with self.sessions() as db:
            db.add(Campaign(id='theirs', user_id='other', client_id='c1', name='남의 캠페인'))
            await db.commit()
        self.assertEqual((await self.one_click(campaign_id='theirs')).status_code, 404)

    async def test_the_forbidden_words_of_this_clinic_still_hold_the_draft(self):
        """다른 문으로 들어왔다고 검수를 건너뛰지 않는다."""
        await self.seed(forbidden=['본문입니다'])
        out = (await self.one_click()).json()
        self.assertTrue(out['success'])
        self.assertEqual(out['draft_status'], 'needs_review')
        self.assertIn('확인이 필요', out['message'])

    async def test_with_no_campaign_it_says_what_to_do(self):
        out = (await self.one_click()).json()
        self.assertFalse(out['success'])
        self.assertIn('원스톱', out['error'])

    async def test_a_page_that_gives_nothing_is_not_saved_as_a_draft(self):
        await self.seed()
        with patch.object(api.blog_crawler, 'crawl', AsyncMock(return_value={'success': True, 'title': 't', 'content': '짧다', 'images': []})):
            out = (await self.client.post('/one-click', json={'url': 'x.com/1'})).json()
        self.assertFalse(out['success'])
        async with self.sessions() as db:
            self.assertEqual(len((await db.execute(select(Draft))).scalars().all()), 0)


if __name__ == '__main__':
    unittest.main()
