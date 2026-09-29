import os
os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite:///./test-unused.db')
os.environ.setdefault('DATABASE_URL_SYNC', 'sqlite:///./test-unused.db')
import unittest
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
import httpx
from app.services import editorial_quality as q, content_evidence as evidence


class QualityTests(unittest.IsolatedAsyncioTestCase):
    def review(self, **kw):
        return dict(relevant=True, facts_supported=True, no_invented_experience=True,
            search_intent=90, usefulness=90, readability=90, originality=90,
            unsupported_claims=[], issues=[], used_source_ids=['s'], **kw)

    async def test_malformed_review_never_approves(self):
        with patch.object(q.cc, 'complete_json', AsyncMock(return_value={'approved': True})):
            with self.assertRaises(ValueError):
                await q.assess('title', 'body', 'keyword', {}, [], [], 2000, 85)

    async def test_unknown_source_and_lowest_dimension_block(self):
        with patch.object(q, 'structural_checks', return_value={'ok': True, 'issues': []}):
            for overrides in ({'used_source_ids': ['invented']}, {'facts_supported': False},
                              {'usefulness': 79}, {'no_invented_experience': False}):
                review = {**self.review(), **overrides}
                with patch.object(q.cc, 'complete_json', AsyncMock(return_value=review)):
                    result = await q.assess('title', 'body', 'keyword', {}, [{'id': 's'}], [], 2000, 85)
                    self.assertFalse(result['approved'])

    async def test_rewrite_limit_and_revision_records(self):
        generation = AsyncMock(return_value={'title': 'title', 'body': 'body', 'tags': []})
        with patch.object(q.writer, 'write_from_keyword', generation), \
             patch.object(q, 'assess', AsyncMock(return_value={'approved': False, 'issues': ['bad']})):
            _, check = await q.write_reviewed(keyword='topic', client={}, brief=None, evidence=[], previous=[], max_rewrites=2)
        self.assertEqual(generation.await_count, 3)
        self.assertEqual(len(check['history']), 3)
        self.assertFalse(check['approved'])

    def test_edit_invalidates_approval(self):
        draft = SimpleNamespace(title='title', body='body', checks={'editorial': {
            'version': q.VERSION, 'approved': True, 'content_hash': q.fingerprint('title', 'body')}})
        self.assertTrue(q.approved(draft))
        draft.body += ' changed'
        self.assertFalse(q.approved(draft))

    def test_repetition_and_previous_copy_block(self):
        text = ('정확한 설명이 필요합니다. ' * 200)
        self.assertFalse(q.structural_checks('주제 설명을 위한 제목', text, '주제', [text])['ok'])

    def test_evidence_url_boundary(self):
        self.assertTrue(evidence.allowed_url('https://www.nhs.uk/conditions/eczema/'))
        for url in ('http://nhs.uk/x', 'https://nhs.uk.evil.com/x', 'https://nhs.uk@evil.com/x',
                    'https://127.0.0.1/x', 'https://nhs.uk:8080/x', 'file:///secret'):
            self.assertFalse(evidence.allowed_url(url), url)

    async def test_redirect_to_private_host_is_rejected(self):
        requested = []
        def handler(request):
            requested.append(str(request.url))
            return httpx.Response(302, headers={'location': 'https://127.0.0.1/secret'})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(ValueError):
                await evidence.read_source(client, 'https://nhs.uk/conditions/eczema')
        self.assertEqual(len(requested), 1)


if __name__ == '__main__':
    unittest.main()


class DoubleKeywordTitleTests(unittest.TestCase):
    """제목에 질환 키워드와 병원 키워드가 **둘 다** 들어간다(2026-09-30 소잠한의원 요청).

    "더블 키워드 중, 제목에 포함 안 됨 (ex. 지루성피부염, 선릉역한의원이라면
    선릉역한의원이 제목에 포함 안 됨)". 지시만으로는 모델이 하나를 흘린다.
    """

    def test_both_keywords_pass_even_when_separated(self):
        """'지루성피부염, 선릉역한의원에서…' 처럼 떨어져 있어도 통과해야 한다.
        붙어 있어야 통과로 보면 자연스러운 제목이 전부 떨어진다."""
        self.assertEqual(
            q.title_misses('지루성피부염, 선릉역한의원에서 이렇게 봅니다', '지루성피부염', '선릉역한의원'), [])

    def test_a_missing_clinic_keyword_is_named(self):
        self.assertEqual(
            q.title_misses('지루성피부염 원인과 관리법', '지루성피부염', '선릉역한의원'), ['선릉역한의원'])

    def test_without_a_clinic_keyword_nothing_changes(self):
        self.assertEqual(q.title_misses('지루성피부염 원인과 관리법', '지루성피부염', None), [])

    def test_the_structural_check_reports_it(self):
        issues = q.structural_checks(
            '지루성피부염 원인과 관리법', '문단\n\n' * 8, '지루성피부염', [],
            target_chars=10, brand_keyword='선릉역한의원')['issues']
        self.assertTrue(any('선릉역한의원' in i for i in issues), issues)


class ClinicNumberTests(unittest.TestCase):
    """병원 실적 숫자는 병원이 적어 준 것만 쓴다(2026-09-30 소잠한의원 실측).

    본문에 "23541건 이상"이라고 나갔는데 실제 실적은 27000건 이상이었다.
    환자는 이 숫자를 곧이곧대로 믿는다.
    """

    FACTS = '소잠한의원, 2008년 개원. 누적 진료 27000건 이상.'

    def test_a_number_the_clinic_never_gave_is_caught(self):
        self.assertEqual(q.clinic_number_misses('누적 23541건 이상 진료했습니다.', self.FACTS), ['누적 23541건'])

    def test_the_clinics_own_number_passes_however_it_is_written(self):
        """27,000 과 27000 은 같은 숫자다. 표기 때문에 막으면 쓸 수 있는 말이 없어진다."""
        self.assertEqual(q.clinic_number_misses('27,000건 이상 진료했습니다.', self.FACTS), [])

    def test_ordinary_medical_numbers_are_left_alone(self):
        self.assertEqual(q.clinic_number_misses('하루 10분씩 3주간 해 보세요. 3건의 사례가 있습니다.', self.FACTS), [])

    def test_years_of_experience_is_a_clinic_claim_too(self):
        self.assertEqual(q.clinic_number_misses('12년째 진료하고 있습니다.', self.FACTS), ['12년째'])

    def test_the_structural_check_tells_the_writer_where_to_fix_it(self):
        issues = q.structural_checks(
            '지루성피부염 관리법', '누적 23541건 이상 진료했습니다.\n\n' + '문단\n\n' * 8,
            '지루성피부염', [], target_chars=10, facts=self.FACTS)['issues']
        self.assertTrue(any('23541' in i and '고정 사실' in i for i in issues), issues)
