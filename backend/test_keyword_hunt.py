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
        self.candidate_disease = None      # _expand 대역이 행에 붙일 질환

    async def asyncTearDown(self):
        await self.db.close()
        await self.engine.dispose()
        self.tmp.cleanup()

    async def _expand(self, ctx):
        """keyword_expand 대역 — 후보 행을 검색량과 함께 심는다."""
        for kw, volume in self.candidates:
            self.db.add(CampaignKeyword(user_id='u', campaign_id='c', client_id='client', keyword=kw,
                                        source='related', total_volume=volume, monthly_mobile=volume,
                                        disease=self.candidate_disease,
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

    async def test_new_hunt_clears_the_previous_keywords(self):
        """새로 찾으면 지난 목록은 사라진다 — 쌓이면 이번에 판정된 것이 무엇인지 알 수 없다."""
        self.db.add(CampaignKeyword(user_id='u', campaign_id='c', client_id='client',
                                    keyword='지난번 키워드', source='related', total_volume=100,
                                    passes_filter=True, verdict='possible', my_verdict='likely'))
        await self.db.commit()
        await self.run_hunt()
        rows = await self._rows()
        self.assertNotIn('지난번 키워드', rows)
        self.assertTrue(rows)                      # 새로 찾은 것들은 남아 있다

    async def test_keeping_the_previous_keywords_is_possible(self):
        """replace=false 면 이어 붙인다(자동 이어하기·복구용)."""
        self.db.add(CampaignKeyword(user_id='u', campaign_id='c', client_id='client',
                                    keyword='지난번 키워드', source='related', total_volume=100,
                                    passes_filter=True, verdict='possible'))
        await self.db.commit()
        self.job.payload = {**self.job.payload, 'replace': False}
        await self.run_hunt()
        self.assertIn('지난번 키워드', await self._rows())

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


class QuotaHuntTests(HuntCase):
    """발굴 잡 전체가 씨앗 입력과 비율 설정을 실제로 반영하는지."""

    async def _run(self, payload):
        self.job.payload = {**self.job.payload, **payload}
        await self.db.commit()
        self.judged_waves = []
        seeds = AsyncMock(return_value=['아토피 증상'])
        with patch.object(hunt, '_claude_topics', AsyncMock(return_value=[])),              patch.object(hunt, '_naver_seeds', seeds),              patch.object(hunt.jobs, 'keyword_expand', AsyncMock(side_effect=self._expand)) as expand,              patch('app.services.serp_analyzer.analyze_keyword', AsyncMock(side_effect=_fake_serp)),              patch('app.services.blog_index_jobs.blog_verdict_batch', AsyncMock(side_effect=self._verdict_batch)):
            result = await hunt.keyword_hunt(self.ctx)
        return result, expand.await_args.args[0].payload, seeds.await_args

    async def test_asked_seeds_replace_the_clinic_subjects(self):
        _, expand_payload, seed_call = await self._run({'seeds': ['탈모', '원형탈모']})
        # 연관어 필터가 쓰는 diseases 가 직접 입력한 키워드여야 한다.
        # 여기에 안 넣으면 '탈모' 연관어가 통째로 버려진다.
        self.assertEqual(expand_payload['diseases'], ['탈모', '원형탈모'])
        self.assertIn('탈모', seed_call.args[0])
        self.assertIn('탈모 치료', seed_call.args[0])

    async def test_without_seeds_the_clinic_subjects_are_used(self):
        _, expand_payload, _ = await self._run({})
        self.assertEqual(expand_payload['diseases'], ['아토피'])

    async def test_blank_seeds_are_ignored(self):
        _, expand_payload, _ = await self._run({'seeds': ['  ', '']})
        self.assertEqual(expand_payload['diseases'], ['아토피'])

    async def test_every_selected_row_gets_a_category(self):
        await self._run({})
        rows = await self._rows()
        self.assertTrue(all(r.category for r in rows.values()),
                        '성격이 안 붙으면 비율 추출이 불가능하다')

    async def test_quota_axis_follows_the_asked_seeds(self):
        """직접 입력이 있으면 질환 할당도 그 키워드 기준이어야 한다.

        병원 진료 항목(아토피)으로 나누면 행이 하나도 없는 칸에 자리를 배정하고,
        그만큼이 '메우기'로 흘러가 비율 지정이 무의미해진다.
        """
        self.candidates = [(f'탈모 possible {i}', 900 - i) for i in range(14)]
        self.verdicts = {kw: ('likely', 0.8) for kw, _ in self.candidates}
        self.candidate_disease = '탈모'
        result, _, _ = await self._run({'seeds': ['탈모'], 'target': 10,
                                        'disease_quota': {'탈모': 10}})
        self.assertEqual(result['selected'], 10)
        # 질환 축이 '탈모' 였다는 증거 — 아토피는 후보가 없어 키 자체가 안 생긴다.
        self.assertEqual(result['disease_mix'], {'탈모': 10})

    async def test_asked_seed_axis_keeps_the_category_ratio_intact(self):
        """질환 축이 틀리면 비율이 조용히 무너진다 — 그걸 잡는 시험.

        축을 병원 진료 항목(탈모+아토피)으로 잡으면 목표의 절반이 '아토피' 칸에 배정되는데
        그 칸에는 행이 없다. 그 절반은 비율을 안 거치고 '메우기'로 채워져,
        '치료만 뽑아 줘'라고 했는데 증상이 섞여 나온다.
        """
        self.candidates = ([(f'탈모치료 possible {i}', 900 - i) for i in range(10)]
                           + [(f'탈모증상 possible {i}', 800 - i) for i in range(10)])
        # 증상 쪽 확률을 높게 둬서, 비율을 안 거치면 증상이 먼저 끌려오게 만든다.
        self.verdicts = {kw: ('likely', 0.9 if '증상' in kw else 0.7)
                         for kw, _ in self.candidates}
        self.candidate_disease = '탈모'
        result, _, _ = await self._run({'seeds': ['탈모'], 'target': 10, 'verdict_limit': 20,
                                        'category_ratio': {'치료': 100}})
        self.assertEqual(result['selected'], 10)
        self.assertEqual(result['category_mix'], {'치료': 10},
                         "비율을 100% 치료로 줬으면 치료만 나와야 한다")

    async def test_target_floor_is_ten(self):
        """target 은 10 미만으로 못 내려간다(_clamp). 화면 입력도 min=10 이다."""
        self.candidates = [(f'아토피 possible {i}', 900 - i) for i in range(14)]
        self.verdicts = {kw: ('likely', 0.8) for kw, _ in self.candidates}
        result, _, _ = await self._run({'target': 3})
        self.assertEqual(result['target'], 10)

    async def test_result_reports_the_category_mix(self):
        result, _, _ = await self._run({})
        self.assertIn('category_mix', result)
        self.assertEqual(sum(result['category_mix'].values()), result['selected'])


class SeedTests(HuntCase):
    """씨앗 단계 — 외부 원천이 죽어도 진료 항목만으로 깔때기가 돌아야 한다."""

    async def _run_with_seeds(self, topics, naver):
        self.judged_waves = []
        with patch.object(hunt, '_claude_topics', AsyncMock(return_value=topics)), \
             patch.object(hunt, '_naver_seeds', AsyncMock(return_value=naver)) as seeds, \
             patch.object(hunt.jobs, 'keyword_expand', AsyncMock(side_effect=self._expand)) as expand, \
             patch('app.services.serp_analyzer.analyze_keyword', AsyncMock(side_effect=_fake_serp)), \
             patch('app.services.blog_index_jobs.blog_verdict_batch', AsyncMock(side_effect=self._verdict_batch)):
            result = await hunt.keyword_hunt(self.ctx)
            return result, expand.await_args.args[0].payload['seeds'], seeds.await_args

    async def test_subject_survives_when_every_external_source_is_empty(self):
        # Claude 키 없음 + 네이버 빈손이어도 '씨앗을 만들지 못했습니다'로 죽으면 안 된다.
        result, seeds, _ = await self._run_with_seeds([], [])
        self.assertEqual(seeds, ['아토피'])
        self.assertEqual(result['seeded'], 1)

    async def test_subject_is_always_included_alongside_found_seeds(self):
        _, seeds, _ = await self._run_with_seeds(['아토피 밤에 가려움'], ['아토피 증상'])
        self.assertEqual(seeds[0], '아토피')                 # 진료 항목이 맨 앞
        self.assertIn('아토피 밤에 가려움', seeds)
        self.assertIn('아토피 증상', seeds)

    async def test_autocomplete_probes_cover_subject_and_suffixes(self):
        _, _, seed_call = await self._run_with_seeds([], [])
        probes = seed_call.args[0]
        self.assertIn('아토피', probes)
        for suffix in hunt.SEED_SUFFIXES:
            if suffix:
                self.assertIn(f'아토피 {suffix}', probes)
        # 1.8MB 짜리 통검 스크래핑은 진료 항목에만 건다
        self.assertEqual(list(seed_call.kwargs['related_terms']), ['아토피'])


if __name__ == '__main__':
    unittest.main()
