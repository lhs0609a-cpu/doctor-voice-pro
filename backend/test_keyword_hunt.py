"""키워드 발굴 3단 깔때기 검사.

외부 호출(Claude 주제, 네이버 연관검색어, 통합검색, 경쟁자 채점)은 전부 대역으로 바꾸고
깔때기의 판단만 검사한다: avoid 를 비싼 판정에 넣지 않는가, 재개가 단계를 건너뛰는가,
최종 선택이 내 블로그 판정과 목표 수를 지키는가.
"""
import os
os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///./test-unused.db')
os.environ.setdefault('DATABASE_URL_SYNC', 'sqlite:///./test-unused.db')

import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.background_job import BackgroundJob
from app.models.campaign import Blog, Campaign, CampaignKeyword, Client, Draft
from app.services import keyword_hunt as hunt
from app.services.job_worker import JobContext

# 통검 대역: 키워드 이름으로 판정을 정한다
SERP_VERDICT = {
    'possible': ('possible', '병원 블로그 진입 여지가 있습니다'),
    'contested': ('contested', '경쟁 중입니다'),
    'avoid': ('avoid', '병원 블로그가 전혀 노출되지 않습니다'),
}


def _fake_serp(keyword, fetch_post_metrics=True):
    for mark, (verdict, reason) in SERP_VERDICT.items():
        if mark in keyword:
            return {'keyword': keyword, 'verdict': verdict, 'verdict_reason': reason,
                    'summary': {'exposed': 5, 'hospital': 2}, 'posts': [], 'error': None}
    return {'keyword': keyword, 'verdict': 'unknown', 'verdict_reason': None, 'summary': {}, 'posts': [], 'error': None}


class HuntCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_async_engine('sqlite+aiosqlite:///' + str(Path(self.tmp.name) / 'hunt.db'))
        async with self.engine.begin() as conn:
            for table in (Client.__table__, Campaign.__table__, Blog.__table__, Draft.__table__,
                          CampaignKeyword.__table__, BackgroundJob.__table__):
                await conn.run_sync(lambda c, t=table: t.create(c))
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.db = self.sessions()
        self.db.add(Client(id='client', user_id='u', name='서울봄의원', diseases=['아토피'],
                           treatments=[], regions=['강남'], forbidden_words=['최고']))
        self.db.add(Campaign(id='c', user_id='u', client_id='client', name='운영', blog_ids=['b']))
        self.db.add(Blog(id='b', user_id='u', client_id='client', blog_id='myblog', status='active', daily_limit=2))
        self.job = BackgroundJob(id='task', user_id='u', type='keyword_hunt', status='running',
                                 payload={'campaign_id': 'c', 'target': 10})
        self.db.add(self.job)
        await self.db.commit()
        self.ctx = JobContext(db=self.db, job=self.job)
        # keyword_expand 대역이 심을 후보들
        self.candidates = [
            ('아토피 possible 1', 900), ('아토피 possible 2', 800), ('아토피 contested 1', 700),
            ('아토피 avoid 1', 6000), ('아토피 avoid 2', 5000), ('아토피 최고 possible', 4000),
        ]
        self.verdicts = {'아토피 possible 1': ('likely', 0.81), '아토피 possible 2': ('unlikely', 0.12),
                         '아토피 contested 1': ('contested', 0.44)}

    async def asyncTearDown(self):
        await self.db.close()
        await self.engine.dispose()
        self.tmp.cleanup()

    async def _expand(self, ctx):
        """keyword_expand 대역 — 후보 행을 검색량과 함께 심는다."""
        for kw, volume in self.candidates:
            self.db.add(CampaignKeyword(user_id='u', campaign_id='c', client_id='client', keyword=kw,
                                        source='related', total_volume=volume, monthly_mobile=volume,
                                        passes_filter=True, verdict='unknown'))
        await self.db.commit()
        return {'added': len(self.candidates)}

    async def _verdict_batch(self, ctx):
        """blog_verdict_batch 대역 — 요청한 키워드 행에 내 블로그 판정을 적는다."""
        asked = ctx.payload['keywords']
        self.judged_waves.append(list(asked))
        rows = (await self.db.execute(select(CampaignKeyword).where(
            CampaignKeyword.campaign_id == 'c', CampaignKeyword.keyword.in_(asked)))).scalars().all()
        for row in rows:
            verdict, probability = self.verdicts.get(row.keyword, ('unknown', None))
            row.my_blog_id = ctx.payload['blog_id']
            row.my_verdict = verdict
            row.my_probability = probability
        await self.db.commit()
        return {'items': []}

    async def run_hunt(self):
        self.judged_waves = []
        self.topics = AsyncMock(return_value=['아토피 possible 1'])
        with patch.object(hunt, '_claude_topics', self.topics), \
             patch.object(hunt, '_naver_seeds', AsyncMock(return_value=['아토피 증상'])), \
             patch.object(hunt.jobs, 'keyword_expand', AsyncMock(side_effect=self._expand)) as expand, \
             patch('app.services.serp_analyzer.analyze_keyword', AsyncMock(side_effect=_fake_serp)), \
             patch('app.services.blog_index_jobs.blog_verdict_batch', AsyncMock(side_effect=self._verdict_batch)):
            self.expand = expand
            return await hunt.keyword_hunt(self.ctx)

    async def _rows(self):
        return {r.keyword: r for r in (await self.db.execute(
            select(CampaignKeyword).where(CampaignKeyword.campaign_id == 'c'))).scalars().all()}


class HuntTests(HuntCase):
    async def test_avoid_keywords_never_reach_my_blog_judging(self):
        await self.run_hunt()
        judged = [kw for wave in self.judged_waves for kw in wave]
        self.assertIn('아토피 possible 1', judged)
        self.assertIn('아토피 contested 1', judged)
        self.assertNotIn('아토피 avoid 1', judged)
        self.assertNotIn('아토피 avoid 2', judged)

    async def test_forbidden_word_keyword_is_not_screened(self):
        await self.run_hunt()
        rows = await self._rows()
        self.assertEqual(rows['아토피 최고 possible'].verdict, 'unknown')

    async def test_possible_is_judged_before_contested(self):
        result = await self.run_hunt()
        judged = [kw for wave in self.judged_waves for kw in wave]
        self.assertEqual(judged[:2], ['아토피 possible 1', '아토피 possible 2'])
        self.assertEqual(result['judged'], 3)

    async def test_only_writable_verdicts_are_selected(self):
        result = await self.run_hunt()
        rows = await self._rows()
        self.assertTrue(rows['아토피 possible 1'].selected)      # likely
        self.assertTrue(rows['아토피 contested 1'].selected)     # contested
        self.assertFalse(rows['아토피 possible 2'].selected)     # unlikely
        self.assertFalse(rows['아토피 avoid 1'].selected)
        self.assertEqual(result['selected'], 2)
        self.assertEqual(result['likely'], 1)

    async def test_target_caps_selection(self):
        self.job.payload = {**self.job.payload, 'target': 10}
        self.verdicts = {kw: ('likely', 0.9) for kw, _ in self.candidates}
        result = await self.run_hunt()
        # 통검 possible/contested 인 3개만 판정 대상 → 목표 10개여도 3개가 상한
        self.assertEqual(result['selected'], 3)

    async def test_resume_skips_completed_stages(self):
        await self.run_hunt()
        seeded_once = self.topics.await_count
        await self.run_hunt()
        self.assertEqual(self.topics.await_count, 0)   # 재실행에서는 씨앗 단계를 건너뛴다
        self.assertEqual(seeded_once, 1)
        self.assertEqual(self.expand.await_count, 0)
        rows = await self._rows()
        self.assertEqual(len(rows), len(self.candidates))   # 후보가 두 배로 늘지 않는다

    async def test_verdict_limit_zero_skips_expensive_stage(self):
        self.job.payload = {**self.job.payload, 'verdict_limit': 0}
        result = await self.run_hunt()
        self.assertEqual(self.judged_waves, [])
        self.assertEqual(result['selected'], 0)
        self.assertEqual(result['possible'], 2)
        self.assertEqual(result['avoid'], 2)

    async def test_blog_id_comes_from_linked_active_blog(self):
        result = await self.run_hunt()
        self.assertEqual(result['blog_id'], 'myblog')

    async def test_missing_blog_is_reported(self):
        await self.db.execute(CampaignKeyword.__table__.delete())
        blog = await self.db.get(Blog, 'b')
        await self.db.delete(blog)
        await self.db.commit()
        with self.assertRaises(ValueError) as caught:
            await self.run_hunt()
        self.assertIn('블로그', str(caught.exception))


class WaveTests(HuntCase):
    async def test_judging_is_split_into_waves_of_sixty(self):
        self.candidates = [(f'아토피 possible {i}', 1000 - i) for i in range(130)]
        self.verdicts = {kw: ('likely', 0.7) for kw, _ in self.candidates}
        self.job.payload = {**self.job.payload, 'target': 300, 'verdict_limit': 130}
        await self.db.commit()
        await self.run_hunt()
        self.assertEqual([len(w) for w in self.judged_waves], [60, 60, 10])


if __name__ == '__main__':
    unittest.main()
