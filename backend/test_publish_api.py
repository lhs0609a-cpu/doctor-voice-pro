"""ASGI contract tests against isolated DB sessions; no application lifespan."""
from datetime import datetime, timedelta
import unittest
import httpx
from fastapi import FastAPI
from test_publish_protocol import DatabaseCase
from app.api import campaign as api
from app.models.campaign import Blog, Draft, Campaign, AutopilotPolicy, AutomationRun, Client, PublishJob
from app.models.background_job import BackgroundJob
from app.models.publish_queue import ScheduleMark
from app.models.user import User


class ApiTests(DatabaseCase):
    async def test_a_paused_campaign_says_so_instead_of_going_quiet(self):
        """내주지 않을 거면 이유를 적어 둔다(2026-09-29 실측).

        예전에는 조용히 건너뛰기만 해서, 실행기는 글쓰기 화면만 새로고침하고 웹에는 '대기'라고만
        떴다. 사용자가 무엇을 해야 하는지 알 길이 없었다."""
        async with self.sessions() as db:
            db.add(AutopilotPolicy(campaign_id='c', user_id='u', enabled=False, config={}))
            await db.commit()
        claimed = await self.client.post('/agent/claim', json={'blog_ref_id': 'b', 'protocol_version': 2})
        self.assertEqual(claimed.status_code, 200, claimed.text)
        self.assertEqual(claimed.json(), [])

        jobs = (await self.client.get('/campaigns/c/jobs')).json()
        self.assertIn('자동 운영', jobs[0]['error'])
        self.assertIn('→', jobs[0]['error'], "왜인지만 적으면 '그래서 뭘 하라고?'가 된다")
        self.assertEqual(jobs[0]['status'], 'queued', "보류는 실패가 아니다 — 여전히 대기다")

        summary = next(r for r in (await self.client.get('/agent/summary')).json() if r['blog_ref_id'] == 'b')
        self.assertIn('자동 운영', summary['hold_reason'])

    async def test_a_hold_note_is_cleared_when_the_job_finally_goes_out(self):
        from unittest.mock import patch
        async with self.sessions() as db:
            db.add(AutopilotPolicy(campaign_id='c', user_id='u', enabled=False, config={}))
            await db.commit()
        await self.client.post('/agent/claim', json={'blog_ref_id': 'b', 'protocol_version': 2})
        async with self.sessions() as db:
            policy = await db.get(AutopilotPolicy, 'c')
            policy.enabled = True
            await db.commit()
        with patch('app.services.editorial_quality.approved', return_value=True):
            claimed = await self.client.post('/agent/claim', json={'blog_ref_id': 'b', 'protocol_version': 2})
        self.assertEqual(len(claimed.json()), 1, claimed.text)
        jobs = (await self.client.get('/campaigns/c/jobs')).json()
        self.assertIsNone(jobs[0]['error'], "내준 뒤에도 옛 보류 사유가 남으면 안 된다")

    async def test_turning_automation_back_on_clears_the_hold_right_away(self):
        """보류를 지워 주지 않으면 실행기가 영영 다시 시도하지 않는다.

        실행기는 보류 사유가 적혀 있으면 브라우저를 열지 않고 기다린다(막힌 줄 알면서 주기마다
        글쓰기 화면을 여는 것은 사용자 화면만 어지럽힌다 — 2026-09-29 신고). 그래서 사람이
        원인을 고친 순간 서버가 지워 줘야 한다."""
        from unittest.mock import patch, AsyncMock
        async with self.sessions() as db:
            db.add(AutopilotPolicy(campaign_id='c', user_id='u', enabled=False, config={}))
            await db.commit()
        await self.client.post('/agent/claim', json={'blog_ref_id': 'b', 'protocol_version': 2})
        self.assertIsNotNone((await self.client.get('/campaigns/c/jobs')).json()[0]['error'])

        with patch('app.services.autopilot.preflight', AsyncMock(return_value=[])), \
             patch('app.services.autopilot.tick', AsyncMock(return_value=None)):
            turned_on = await self.client.put('/campaigns/c/autopilot', json={'enabled': True, 'image_count': 0})
        self.assertEqual(turned_on.status_code, 200, turned_on.text)
        self.assertIsNone((await self.client.get('/campaigns/c/jobs')).json()[0]['error'],
                          '켠 순간 보류가 풀려야 실행기가 다시 가져간다')

    async def test_fixing_the_blog_clears_the_hold_right_away(self):
        async with self.sessions() as db:
            blog = await db.get(Blog, 'b')
            blog.status = 'login_required'
            await db.commit()
        await self.client.post('/agent/claim', json={'blog_ref_id': 'b', 'protocol_version': 2})
        self.assertIn('로그인', (await self.client.get('/campaigns/c/jobs')).json()[0]['error'])
        restored = await self.client.post('/blogs/b/status', json={'status': 'active', 'reason': '로그인 확인'})
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertIsNone((await self.client.get('/campaigns/c/jobs')).json()[0]['error'])

    async def test_what_a_person_scheduled_is_what_gets_published(self):
        """5단계에서 "'확인 필요' 원고도 포함"으로 예약한 건은 발행까지 간다.

        2026-09-29 실측한 모순: 예약은 받아 주면서 발행할 때 "검수가 끝난 원고만 발행할 수
        있습니다"로 거부했다. 그 건은 영영 올라가지 않는데 화면에는 '대기'로만 남았다.
        **예약을 받았으면 발행한다** — 이 시험이 그 약속을 붙잡아 둔다."""
        async with self.sessions() as db:
            draft = await db.get(Draft, 'd')
            draft.status = 'needs_review'
            draft.checks = {'scheduled_unreviewed': True}   # schedule_commit 이 찍는 표식
            await db.commit()
        claimed = await self.client.post('/agent/claim', json={'blog_ref_id': 'b', 'protocol_version': 2})
        self.assertEqual(claimed.status_code, 200, claimed.text)
        self.assertEqual(len(claimed.json()), 1, '사람이 고른 원고는 내줘야 한다')

    async def test_an_unreviewed_draft_nobody_chose_is_refused_with_a_way_out(self):
        async with self.sessions() as db:
            draft = await db.get(Draft, 'd')
            draft.status = 'needs_review'
            await db.commit()
        await self.client.post('/agent/claim', json={'blog_ref_id': 'b', 'protocol_version': 2})
        jobs = (await self.client.get('/campaigns/c/jobs')).json()
        self.assertIn('확인 필요', jobs[0]['error'])
        self.assertIn('→', jobs[0]['error'], '무엇을 하면 되는지까지 적혀야 한다')

    async def test_bulk_claim_works_with_paused_recurring_but_still_requires_review(self):
        from unittest.mock import patch
        async with self.sessions() as db:
            db.add(AutopilotPolicy(campaign_id='c', user_id='u', enabled=False, config={}))
            draft = await db.get(Draft, 'd')
            draft.checks = {'bulk_publication': {'task_id': 'bulk', 'image_count': 0}}
            await db.commit()
        with patch('app.services.editorial_quality.approved', return_value=True) as approved:
            response = await self.client.post('/agent/claim', json={'blog_ref_id': 'b', 'protocol_version': 2})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()), 1)
        approved.assert_called_once()

    async def test_bulk_discovers_without_selected_keywords_and_reuses_active_task(self):
        from unittest.mock import patch, AsyncMock
        async with self.sessions() as db:
            db.add(Client(id='client', user_id='u', name='clinic', diseases=['eczema']))
            await db.commit()
        body = {'max_keywords': 30, 'discover_keywords': True, 'start_date': '2026-10-01',
                'days': 90, 'quality': {'image_count': 0, 'landing_url': 'https://example.com/guide'}}
        with patch('app.services.autopilot.preflight', AsyncMock(return_value=[])):
            first = await self.client.post('/campaigns/c/automation', json=body)
            second = await self.client.post('/campaigns/c/automation', json=body)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()['id'], second.json()['id'])
        async with self.sessions() as db:
            job = await db.get(BackgroundJob, first.json()['id'])
            self.assertEqual(job.payload['max_keywords'], 30)
            self.assertEqual(job.payload['keyword_ids'], [])
            self.assertTrue(job.payload['strict_quality'])
            self.assertTrue(job.payload['auto_schedule'])
            self.assertEqual(job.payload['landing_url'], body['quality']['landing_url'])
            campaign = await db.get(Campaign, 'c')
            self.assertEqual(campaign.settings['landing']['landing_url'], body['quality']['landing_url'])

    async def test_bulk_blocks_recurring_and_preflight_failure(self):
        from unittest.mock import patch, AsyncMock
        body = {'max_keywords': 50, 'discover_keywords': True, 'start_date': '2026-10-01'}
        with patch('app.services.autopilot.preflight', AsyncMock(return_value=['photos missing'])):
            response = await self.client.post('/campaigns/c/automation', json=body)
        self.assertEqual(response.status_code, 400, response.text)
        async with self.sessions() as db:
            self.assertIsNone(await db.get(AutomationRun, 'c'))
            db.add(AutopilotPolicy(campaign_id='c', user_id='u', enabled=True, config={}))
            await db.commit()
        response = await self.client.post('/campaigns/c/automation', json=body)
        self.assertEqual(response.status_code, 409, response.text)

    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with self.engine.begin() as conn:
            for t in (Blog.__table__, Draft.__table__, Campaign.__table__, AutopilotPolicy.__table__, AutomationRun.__table__, BackgroundJob.__table__, Client.__table__,
                      ScheduleMark.__table__):
                await conn.run_sync(lambda c, table=t: table.create(c))
        async with self.sessions() as db:
            db.add(Campaign(id='c', user_id='u', client_id='client', name='test', blog_ids=['b']))
            db.add(Blog(id='b', user_id='u', client_id='client', blog_id='testblog', status='active'))
            db.add(Draft(id='d', user_id='u', client_id='client', campaign_id='c', title='title', body='body', status='ready'))
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

    async def test_old_claim_contract_requires_upgrade(self):
        response = await self.client.post('/agent/claim', json={'blog_ref_id': 'b'})
        self.assertEqual(response.status_code, 426)

    async def test_scoped_grant_payload_checkpoint_and_replay(self):
        response = await self.client.post('/agent/claim', json={'blog_ref_id': 'b', 'protocol_version': 2})
        self.assertEqual(response.status_code, 200, response.text)
        job = response.json()[0]
        headers = {'Authorization': 'Bearer ' + job['lock_token']}
        payload = await self.client.get(f"/execution/{job['id']}/payload", headers=headers)
        self.assertEqual(payload.status_code, 200, payload.text)
        self.assertEqual(payload.json()['title'], 'title')
        wrong = await self.client.get('/execution/wrong/payload', headers=headers)
        self.assertEqual(wrong.status_code, 401)
        checkpoint = await self.client.post(f"/execution/{job['id']}/checkpoint", headers=headers,
                                           json={'lock_token': job['lock_token'], 'stage': 'finalizing'})
        self.assertEqual(checkpoint.status_code, 200, checkpoint.text)
        body = {'lock_token': job['lock_token'], 'ok': False, 'uncertain': True}
        first = await self.client.post(f"/execution/{job['id']}/result", headers=headers, json=body)
        second = await self.client.post(f"/execution/{job['id']}/result", headers=headers, json=body)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(first.json()['status'], 'uncertain')

    async def test_missing_result_token_and_uncertain_retry_rejected(self):
        token = await self.claim()
        response = await self.client.post('/agent/jobs/j0/result', json={'ok': True})
        self.assertEqual(response.status_code, 409)
        await self.client.post('/agent/jobs/j0/result', json={'ok': False, 'uncertain': True, 'lock_token': token})
        response = await self.client.post('/jobs/j0/retry')
        self.assertEqual(response.status_code, 400)

    async def test_claim_and_cancel_cannot_both_own_same_job(self):
        import asyncio
        cancelled, claimed = await asyncio.gather(
            self.client.post('/jobs/j0/cancel'),
            self.client.post('/agent/claim', json={'blog_ref_id': 'b', 'protocol_version': 2}),
        )
        self.assertEqual(claimed.status_code, 200, claimed.text)
        if any(j['id'] == 'j0' for j in claimed.json()):
            self.assertNotEqual(cancelled.status_code, 200)

    async def test_landing_setting_is_owned_and_preserves_campaign_settings(self):
        async with self.sessions() as db:
            campaign = await db.get(Campaign, 'c')
            campaign.settings = {'other_setting': 42}
            await db.commit()
        body = {'landing_url': 'https://example.com/booking', 'landing_tracking': True}
        response = await self.client.put('/campaigns/c/landing', json=body)
        self.assertEqual(response.status_code, 200, response.text)
        async with self.sessions() as db:
            campaign = await db.get(Campaign, 'c')
            self.assertEqual(campaign.settings['other_setting'], 42)
            self.assertEqual(campaign.settings['landing']['landing_url'], body['landing_url'])
            self.assertIsNone(await db.get(AutopilotPolicy, 'c'))
        response = await self.client.put('/campaigns/not-owned/landing', json=body)
        self.assertEqual(response.status_code, 404)

    async def test_landing_requires_capable_runner_and_is_in_frozen_payload(self):
        async with self.sessions() as db:
            draft = await db.get(Draft, 'd')
            draft.body = '본문\nhttps://example.com/info'
            draft.checks = {'landing': {'url': 'https://example.com/info'}}
            await db.commit()
        response = await self.client.post('/agent/claim', json={'blog_ref_id': 'b', 'protocol_version': 2})
        self.assertEqual(response.status_code, 426)
        response = await self.client.post('/agent/claim', json={'blog_ref_id': 'b', 'protocol_version': 2, 'capabilities': ['landing_links_v1']})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()[0]['options']['requiredLinks'], ['https://example.com/info'])

    async def test_start_and_pause_persist_policy_and_stop_claims(self):
        from unittest.mock import patch, AsyncMock
        with patch('app.services.autopilot.preflight', AsyncMock(return_value=[])):
            response = await self.client.put('/campaigns/c/autopilot', json={'enabled': True, 'image_count': 0})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()['enabled'])
        job_id = response.json()['task']['id']
        response = await self.client.put('/campaigns/c/autopilot', json={'enabled': False, 'image_count': 0})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()['enabled'])
        async with self.sessions() as db:
            self.assertEqual((await db.get(BackgroundJob, job_id)).status, 'cancelled')
        response = await self.client.post('/agent/claim', json={'blog_ref_id': 'b', 'protocol_version': 2})
        self.assertEqual(response.json(), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)


class DraftModeTests(ApiTests):
    """블로그를 '임시저장만'으로 두면 실행기에게 그렇게 알린다(2026-09-30 키네스 요청)."""

    async def test_the_launcher_is_told_to_save_a_draft(self):
        async with self.sessions() as db:
            blog = await db.get(Blog, 'b')
            blog.publish_mode = 'draft'
            await db.commit()
        from unittest.mock import patch
        with patch('app.services.editorial_quality.approved', return_value=True):
            claimed = await self.client.post('/agent/claim', json={'blog_ref_id': 'b', 'protocol_version': 2})
        self.assertEqual(claimed.status_code, 200, claimed.text)
        self.assertEqual(claimed.json()[0]['finalAction'], 'draft')

    async def test_a_normal_blog_still_schedules(self):
        from unittest.mock import patch
        with patch('app.services.editorial_quality.approved', return_value=True):
            claimed = await self.client.post('/agent/claim', json={'blog_ref_id': 'b', 'protocol_version': 2})
        self.assertEqual(claimed.json()[0]['finalAction'], 'schedule')

    async def test_the_choice_made_while_scheduling_beats_the_blog_setting(self):
        """예약을 걸 때 고른 방식이 블로그 상시 설정을 이긴다(2026-10-02 요청).

        블로그는 '예약 발행'인데 이번 건만 임시저장으로 걸 수 있어야 한다."""
        async with self.sessions() as db:
            job = await db.get(PublishJob, 'j0')
            job.publish_mode = 'draft'
            await db.commit()
        from unittest.mock import patch
        with patch('app.services.editorial_quality.approved', return_value=True):
            claimed = await self.client.post('/agent/claim', json={'blog_ref_id': 'b', 'protocol_version': 2})
        self.assertEqual(claimed.json()[0]['finalAction'], 'draft')

    async def test_a_scheduled_batch_still_schedules_on_a_draft_only_blog(self):
        """반대도 된다 — 블로그가 '임시저장만'이어도 이번 건은 예약으로 걸 수 있다."""
        async with self.sessions() as db:
            (await db.get(Blog, 'b')).publish_mode = 'draft'
            (await db.get(PublishJob, 'j0')).publish_mode = 'schedule'
            await db.commit()
        from unittest.mock import patch
        with patch('app.services.editorial_quality.approved', return_value=True):
            claimed = await self.client.post('/agent/claim', json={'blog_ref_id': 'b', 'protocol_version': 2})
        self.assertEqual(claimed.json()[0]['finalAction'], 'schedule')

    async def test_an_imminent_time_does_not_block_a_draft(self):
        """임시저장은 네이버가 '즉시 발행'으로 바꿀 위험이 없다 — 그 검사는 예약에만 쓴다."""
        async with self.sessions() as db:
            blog = await db.get(Blog, 'b')
            blog.publish_mode = 'draft'
            job = await db.get(PublishJob, 'j0')
            job.scheduled_at = datetime.utcnow() + timedelta(minutes=2)
            await db.commit()
        from unittest.mock import patch
        with patch('app.services.editorial_quality.approved', return_value=True):
            claimed = await self.client.post('/agent/claim', json={'blog_ref_id': 'b', 'protocol_version': 2})
        self.assertEqual(len(claimed.json()), 1, claimed.text)
