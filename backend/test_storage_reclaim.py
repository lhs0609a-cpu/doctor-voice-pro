"""볼륨이 차서 전체가 멈추는 일을 막는 두 가지 — 영수증에서 사진을 버리고, 낡은 캐시를 지운다.

배경(2026-09-28 fly 실측): /data 974MB 중 406MB 사용, 그 대부분이 SQLite 한 파일.
발행 1건의 payload(사진 base64)가 1~2MB 인데 끝난 뒤에도 남아 있어서, 워드 100건을
예약하면 그것만으로 150MB 가 박혔다. 지워도 파일이 줄지 않으니 두 배치면 볼륨이 찬다.
"""
import unittest
from datetime import datetime, timedelta

from test_publish_protocol import DatabaseCase

from app.models.blog_index import BlogIndexSnapshot, PostAnalysisCache, SerpCache
from app.models.campaign import PublishAttempt, PublishJob
from app.services import publish_protocol as p
from app.services import storage_reclaim as sr


class PayloadTests(DatabaseCase):
    """끝난 발행 시도는 원고·사진을 안고 있지 않는다."""

    async def _claim_with_payload(self, job='j0'):
        token = await self.claim(job)
        async with self.sessions() as db:
            attempt = await db.get(PublishAttempt, token)
            attempt.payload = {'blocks': [{'type': 'image', 'image': 'data:image/jpeg;base64,' + 'A' * 4096}]}
            await db.commit()
        return token

    async def test_result_drops_the_payload(self):
        token = await self._claim_with_payload()
        async with self.sessions() as db:
            await p.result(db, 'j0', 'u', token, {'ok': True})
            attempt = await db.get(PublishAttempt, token)
            self.assertIsNone(attempt.payload)
            self.assertIsNotNone(attempt.result)          # 영수증(중복 보고 방지)은 남는다

    async def test_failed_result_also_drops_the_payload(self):
        token = await self._claim_with_payload()
        async with self.sessions() as db:
            await p.result(db, 'j0', 'u', token, {'ok': False, 'message': '실패'})
            self.assertIsNone((await db.get(PublishAttempt, token)).payload)

    async def test_expired_lease_drops_the_payload(self):
        """결과도 없이 잠금이 만료된 시도 — 그 권한으로는 더 받아 갈 수 없으니 버린다."""
        token = await self._claim_with_payload()
        async with self.sessions() as db:
            attempt = await db.get(PublishAttempt, token)
            attempt.updated_at = datetime.utcnow() - timedelta(hours=1)
            job = await db.get(PublishJob, 'j0')
            job.lock_expires_at = datetime.utcnow() - timedelta(minutes=1)
            await db.commit()
            await p.recover_expired(db, 'u')
            self.assertIsNone((await db.get(PublishAttempt, token)).payload)

    async def test_a_live_lease_keeps_its_payload(self):
        """아직 일하고 있는 실행기의 원고는 건드리지 않는다 — 다시 받아 가야 한다."""
        token = await self._claim_with_payload()
        async with self.sessions() as db:
            await p.recover_expired(db, 'u')
            self.assertIsNotNone((await db.get(PublishAttempt, token)).payload)


class ReclaimTests(DatabaseCase):
    """다시 만들 수 있는 것만 보관 기간대로 지운다."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with self.engine.begin() as conn:
            for table in (PostAnalysisCache.__table__, SerpCache.__table__, BlogIndexSnapshot.__table__):
                await conn.run_sync(lambda sync, t=table: t.create(sync))
        now = datetime.utcnow()
        self.old = now - timedelta(days=400)
        async with self.sessions() as db:
            db.add(PostAnalysisCache(post_url='old', blog_id='b', data={'success': True}, created_at=self.old))
            db.add(PostAnalysisCache(post_url='new', blog_id='b', data={'success': True}, created_at=now))
            db.add(SerpCache(keyword_norm='k', keyword='k', rows=[], fetched_at=self.old))
            db.add(SerpCache(keyword_norm='k2', keyword='k2', rows=[], fetched_at=now))
            db.add(BlogIndexSnapshot(blog_id='b', created_at=self.old))
            db.add(BlogIndexSnapshot(blog_id='b', created_at=now))
            await db.commit()
        sr._last_run = None

    async def test_old_caches_go_and_fresh_ones_stay(self):
        async with self.sessions() as db:
            freed = await sr.reclaim(db, force=True)
            self.assertEqual(freed.get('post_cache'), 1)
            self.assertEqual(freed.get('serp_cache'), 1)
            self.assertEqual(freed.get('snapshots'), 1)
            self.assertIsNotNone(await db.get(PostAnalysisCache, 'new'))
            self.assertIsNone(await db.get(PostAnalysisCache, 'old'))

    async def test_finished_receipts_expire_but_open_ones_never_do(self):
        token = await self.claim()
        async with self.sessions() as db:
            # 실패로 끝낸다 — 성공/uncertain 은 그 블로그를 붙잡아 두어 다음 claim 이 막힌다.
            await p.result(db, 'j0', 'u', token, {'ok': False, 'message': '실패'})
            attempt = await db.get(PublishAttempt, token)
            attempt.updated_at = self.old
            await db.commit()
        open_token = await self.claim('j1')
        async with self.sessions() as db:
            attempt = await db.get(PublishAttempt, open_token)
            attempt.updated_at = self.old            # 오래됐지만 결과가 없다 — 아직 살아 있는 시도다
            await db.commit()
            self.assertEqual((await sr.reclaim(db, force=True)).get('attempts'), 1)
            self.assertIsNone(await db.get(PublishAttempt, token))
            self.assertIsNotNone(await db.get(PublishAttempt, open_token))

    async def test_it_only_works_once_an_hour_unless_forced(self):
        async with self.sessions() as db:
            self.assertTrue(await sr.reclaim(db, force=True))
            db.add(PostAnalysisCache(post_url='old2', blog_id='b', data={'success': True}, created_at=self.old))
            await db.commit()
            self.assertEqual(await sr.reclaim(db), {})                  # 주기 안이라 아무것도 하지 않는다
            self.assertIsNotNone(await db.get(PostAnalysisCache, 'old2'))

    async def test_report_reads_the_disk_without_blowing_up(self):
        out = sr.report()
        self.assertIn('disk_total_mb', out)


if __name__ == '__main__':
    unittest.main()
