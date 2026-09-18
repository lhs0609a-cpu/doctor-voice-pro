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
