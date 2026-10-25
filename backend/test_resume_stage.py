"""재개 지점은 '다음에 또 할 때'만 남는다.

2026-10-25: 10월 400편에 시도 811회(평균 2.0회)가 들었고, 재시도는 매번 본문과 사진을
처음부터 다시 올렸다. 실행기가 다 쓴 글을 임시저장해 두고 'body_saved' 로 알리면,
다음 claim 이 그걸 실어 보내 발행 단계부터 잇는다.

남겨 두면 안 되는 때가 있다 — 다시 할 일이 없는데 남기면, 한참 뒤 같은 글을 새로
예약했을 때 네이버에 남은 옛 '작성 중인 글'을 이어받으려 들 수 있다.
"""
import unittest
from datetime import datetime, timedelta

from test_publish_protocol import DatabaseCase

from app.models.campaign import PublishJob
from app.services import publish_protocol as p


class ResumeStageTests(DatabaseCase):
    async def stage_of(self, job='j0'):
        async with self.sessions() as db:
            return (await db.get(PublishJob, job)).resume_stage

    async def test_body_saved_is_remembered_on_the_job(self):
        token = await self.claim()
        async with self.sessions() as db:
            await p.checkpoint(db, 'j0', 'u', token, 'body_saved')
        self.assertEqual(await self.stage_of(), 'body_saved')

    async def test_a_plain_heartbeat_does_not_set_it(self):
        token = await self.claim()
        async with self.sessions() as db:
            await p.checkpoint(db, 'j0', 'u', token, 'heartbeat')
        self.assertIsNone(await self.stage_of())

    async def test_an_unknown_stage_is_refused(self):
        token = await self.claim()
        async with self.sessions() as db:
            with self.assertRaises(p.Conflict):
                await p.checkpoint(db, 'j0', 'u', token, 'halfway')

    async def test_it_survives_a_failure_that_will_be_retried(self):
        token = await self.claim()
        async with self.sessions() as db:
            await p.checkpoint(db, 'j0', 'u', token, 'body_saved')
        async with self.sessions() as db:
            await p.result(db, 'j0', 'u', token, {'ok': False, 'message': '카테고리를 고르지 못했습니다'})
        async with self.sessions() as db:
            job = await db.get(PublishJob, 'j0')
            self.assertEqual(job.status, 'failed')
            self.assertIsNotNone(job.next_retry_at)      # 다시 할 일이 있다
        self.assertEqual(await self.stage_of(), 'body_saved')

    async def test_it_is_cleared_once_the_post_is_in(self):
        token = await self.claim()
        async with self.sessions() as db:
            await p.checkpoint(db, 'j0', 'u', token, 'body_saved')
            await p.checkpoint(db, 'j0', 'u', token, 'finalizing')
        async with self.sessions() as db:
            await p.result(db, 'j0', 'u', token, {'ok': True})
        async with self.sessions() as db:
            self.assertEqual((await db.get(PublishJob, 'j0')).status, 'submitted')
        self.assertIsNone(await self.stage_of())

    async def test_it_is_cleared_when_no_retry_is_left(self):
        async with self.sessions() as db:
            job = await db.get(PublishJob, 'j0')
            job.attempts, job.max_attempts = 2, 3
            await db.commit()
        token = await self.claim()
        async with self.sessions() as db:
            await p.checkpoint(db, 'j0', 'u', token, 'body_saved')
        async with self.sessions() as db:
            await p.result(db, 'j0', 'u', token, {'ok': False, 'message': '끝내 실패'})
        async with self.sessions() as db:
            job = await db.get(PublishJob, 'j0')
            self.assertIsNone(job.next_retry_at)         # 더 할 일이 없다
        self.assertIsNone(await self.stage_of())

    async def test_a_released_job_keeps_it_for_the_next_run(self):
        """로그인·캡차로 되돌린 글은 네이버에 임시저장이 그대로 남아 있다."""
        token = await self.claim()
        async with self.sessions() as db:
            await p.checkpoint(db, 'j0', 'u', token, 'body_saved')
        async with self.sessions() as db:
            await p.result(db, 'j0', 'u', token, {'ok': False, 'need_login': True, 'message': '로그인이 풀렸습니다'})
        async with self.sessions() as db:
            self.assertEqual((await db.get(PublishJob, 'j0')).status, 'queued')
        self.assertEqual(await self.stage_of(), 'body_saved')


if __name__ == '__main__':
    unittest.main()
