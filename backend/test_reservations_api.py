"""네이버에 이미 걸린 예약을 피해 잡기 — 장부 갱신과 발행 직전 자리 옮기기.

여기서 지키는 약속 셋.
1) 실행기가 읽어 온 목록은 '그 시점의 진실 전체'다 — 미래의 naver 자리를 통째로 갈아 끼운다.
   그래야 네이버에서 지운 예약이 유령 자리로 남아 영영 그 시간대를 막는 일이 없다.
2) 우리가 걸어 둔 자리(campaign)는 스캔이 건드리지 않는다. 아직 실행기가 못 올렸을 뿐이다.
3) 발행 직전 그 칸이 차 있으면 올리지 않고 다음 빈 자리로 옮긴다(시도 횟수는 늘지 않는다).
"""
import unittest
from datetime import datetime, timedelta

import httpx
from fastapi import FastAPI

from test_publish_protocol import DatabaseCase

from app.api import campaign as api
from app.models.background_job import BackgroundJob
from app.models.campaign import Blog, Campaign, CampaignKeyword, Client, Draft, PublishJob
from app.models.publish_queue import QueuedPost, ScheduleMark
from app.models.user import User
from app.services import schedule_engine as se


def kst(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, day, hour, minute)


class ReservationTests(DatabaseCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with self.engine.begin() as conn:
            for table in (Blog.__table__, Draft.__table__, Campaign.__table__, Client.__table__,
                          ScheduleMark.__table__, QueuedPost.__table__, BackgroundJob.__table__,
                          CampaignKeyword.__table__):
                await conn.run_sync(lambda sync, t=table: t.create(sync))
        # 발행 시각은 '지금'과 견주므로 고정 날짜 대신 현재 기준으로 잡는다.
        self.now = se.kst_now()
        self.future = se.floor_slot(self.now + timedelta(days=2))
        async with self.sessions() as db:
            db.add(Client(id='client', user_id='u', name='clinic'))
            db.add(Campaign(id='c', user_id='u', client_id='client', name='test', blog_ids=['b']))
            db.add(Blog(id='b', user_id='u', client_id='client', blog_id='testblog', status='active',
                        window_start='00:00', window_end='23:50', min_gap_minutes=120))
            db.add(Draft(id='d', user_id='u', campaign_id='c', title='아직 예약 안 한 원고', status='ready'))
            db.add(Draft(id='busy', user_id='u', campaign_id='c', title='이미 걸린 원고', status='ready'))
            for name in ('j0', 'j1'):
                job = await db.get(PublishJob, name)
                job.draft_id, job.naver_blog_id = 'busy', 'testblog'
            (await db.get(PublishJob, 'j0')).scheduled_at = self.future
            (await db.get(PublishJob, 'j1')).scheduled_at = self.future - timedelta(days=1)
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

    async def marks(self):
        async with self.sessions() as db:
            rows = (await db.execute(
                ScheduleMark.__table__.select().order_by(ScheduleMark.scheduled_at))).all()
        return [(r.scheduled_at, r.source) for r in rows]

    async def scan(self, *slots, ok=True, note=None):
        body = {'ok': ok, 'note': note, 'items': [{'at': s.isoformat(timespec='minutes'), 'title': '예약 글'} for s in slots]}
        response = await self.client.post('/agent/blogs/b/reservations', json=body)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    # ------------------------------------------------------------ 장부 갱신
    async def test_scan_replaces_the_previous_naver_snapshot(self):
        first, second = self.future + timedelta(hours=3), self.future + timedelta(hours=6)
        await self.scan(first, second)
        self.assertEqual(await self.marks(), [(self.future + timedelta(hours=3), 'naver'),
                                              (self.future + timedelta(hours=6), 'naver')])
        # 네이버에서 한 건을 지우고 다른 시각으로 옮겼다 → 장부도 그 모습이어야 한다
        third = self.future + timedelta(hours=9)
        await self.scan(second, third)
        self.assertEqual(await self.marks(), [(second, 'naver'), (third, 'naver')])

    async def test_scan_keeps_our_own_marks(self):
        ours = self.future + timedelta(hours=1)
        async with self.sessions() as db:
            db.add(ScheduleMark(user_id='u', blog_id='testblog', scheduled_at=ours, source='campaign'))
            await db.commit()
        await self.scan(self.future + timedelta(hours=4))
        self.assertIn((ours, 'campaign'), await self.marks())

    async def test_failed_scan_leaves_the_ledger_alone(self):
        await self.scan(self.future + timedelta(hours=2))
        before = await self.marks()
        async with self.sessions() as db:
            scanned = (await db.get(Blog, 'b')).reservations_scanned_at
        await self.scan(ok=False, note='예약 목록 화면을 찾지 못했습니다')
        self.assertEqual(await self.marks(), before)
        async with self.sessions() as db:
            blog = await db.get(Blog, 'b')
            self.assertEqual(blog.reservations_scanned_at, scanned)   # 확인 시각도 그대로
            self.assertIn('찾지 못했', blog.reservations_note)

    async def test_scan_ignores_past_slots(self):
        await self.scan(se.floor_slot(self.now - timedelta(hours=2)), self.future)
        self.assertEqual([at for at, _ in await self.marks()], [self.future])

    # ------------------------------------------------- 배정이 그 자리를 피하는가
    async def test_preview_starts_after_the_last_known_reservation(self):
        last = self.future + timedelta(hours=5)
        await self.scan(self.future, last)
        body = {'start_date': self.now.date().isoformat(), 'days': 30, 'draft_ids': ['d'],
                'mode': 'interval', 'every_minutes': 120, 'start_mode': 'after_last'}
        response = await self.client.post('/campaigns/c/schedule/preview', json=body)
        self.assertEqual(response.status_code, 200, response.text)
        preview = response.json()
        self.assertEqual(preview['starts_after'], last.isoformat(timespec='minutes'))
        self.assertEqual(preview['assigned'][0]['scheduled_at'],
                         (last + timedelta(hours=2)).isoformat(timespec='minutes'))
        info = preview['reservations'][0]
        self.assertEqual(info['last_at'], last.isoformat(timespec='minutes'))
        self.assertFalse(info['stale'])                     # 방금 읽어 온 목록이다

    async def test_our_own_waiting_job_counts_as_a_taken_slot(self):
        """네이버 목록에 없어도 아직 못 올린 우리 발행건은 이미 잡아 둔 자리다."""
        far = self.future + timedelta(days=5)
        async with self.sessions() as db:
            (await db.get(PublishJob, 'j1')).scheduled_at = far
            await db.commit()
        await self.scan(self.future)
        body = {'start_date': self.now.date().isoformat(), 'days': 60, 'draft_ids': ['d'],
                'mode': 'interval', 'every_minutes': 120, 'start_mode': 'after_last'}
        preview = (await self.client.post('/campaigns/c/schedule/preview', json=body)).json()
        self.assertEqual(preview['starts_after'], far.isoformat(timespec='minutes'))

    async def test_never_scanned_blog_is_reported_stale(self):
        """'목록을 못 읽었다'는 stale 한 값으로만 알린다 — 화면 위 상자가 이미 말하므로
        경고로 또 적으면 같은 말이 두 번 나온다."""
        body = {'start_date': self.now.date().isoformat(), 'days': 30, 'draft_ids': ['d'],
                'mode': 'interval', 'every_minutes': 120}
        preview = (await self.client.post('/campaigns/c/schedule/preview', json=body)).json()
        self.assertTrue(preview['reservations'][0]['stale'])
        self.assertFalse([w for w in preview['warnings'] if '예약 목록' in w], preview['warnings'])

    async def test_going_over_the_daily_limit_says_how_to_fix_it(self):
        """하루 한도를 넘기면 그냥 알리고 끝내지 않는다 — 어떻게 지킬 수 있는지까지 적는다."""
        async with self.sessions() as db:
            (await db.get(Blog, 'b')).daily_limit = 1
            for i in range(3):
                db.add(Draft(id=f'many{i}', user_id='u', campaign_id='c', title=f'원고 {i}', status='ready'))
            await db.commit()
        body = {'start_date': self.now.date().isoformat(), 'days': 30,
                'draft_ids': ['many0', 'many1', 'many2'], 'mode': 'interval', 'every_minutes': 60}
        preview = (await self.client.post('/campaigns/c/schedule/preview', json=body)).json()
        warning = next(w for w in preview['warnings'] if '하루' in w)
        self.assertIn('하루 한도는 1건', warning)
        self.assertIn('2시간', warning)          # 바로 다음으로 넓힐 간격을 짚어 준다
        self.assertIn('하루 한도를 올리세요', warning)

    async def test_the_chosen_gap_is_what_actually_happens(self):
        """'마지막 예약 다음 2시간'이라고 적었으면 정확히 2시간 뒤여야 한다.

        블로그 설정의 최소 간격(여기서는 120분)이나 '목록이 오래됨' 같은 사정으로 더 밀면
        화면에 적힌 시각과 실제가 어긋난다. 30분을 골랐으면 30분 뒤다."""
        last = self.future + timedelta(hours=5)
        await self.scan(last)
        body = {'start_date': self.now.date().isoformat(), 'days': 30, 'draft_ids': ['d'],
                'mode': 'interval', 'every_minutes': 30, 'start_mode': 'after_last'}
        preview = (await self.client.post('/campaigns/c/schedule/preview', json=body)).json()
        self.assertEqual(preview['assigned'][0]['scheduled_at'],
                         (last + timedelta(minutes=30)).isoformat(timespec='minutes'))

    # --------------------------------------- 같은 시각에 두 글이 걸리지 않는가
    async def commit(self, draft_ids, every=120, start_mode='after_last'):
        body = {'start_date': self.now.date().isoformat(), 'days': 60, 'draft_ids': draft_ids,
                'mode': 'interval', 'every_minutes': every, 'start_mode': start_mode}
        response = await self.client.post('/campaigns/c/schedule/commit', json=body)
        self.assertEqual(response.status_code, 200, response.text)
        return [a['scheduled_at'] for a in response.json()['assigned']]

    async def test_two_separate_commits_never_reuse_a_slot(self):
        """따로 두 번 예약해도 시각이 겹치지 않는다 — 같은 시각 두 글은 저품질로 간다.

        두 번째 예약은 첫 번째가 남긴 자리를 보고 그 뒤로 이어 붙어야 한다."""
        async with self.sessions() as db:
            for i in range(6):
                db.add(Draft(id=f'd{i}', user_id='u', campaign_id='c', title=f'원고 {i}', status='ready'))
            await db.commit()
        first = await self.commit(['d0', 'd1', 'd2'])
        second = await self.commit(['d3', 'd4', 'd5'])
        every = first + second
        self.assertEqual(len(set(every)), 6, every)                    # 여섯 시각 모두 다르다
        stamps = sorted(datetime.fromisoformat(t) for t in every)
        gaps = [(b - a).total_seconds() / 60 for a, b in zip(stamps, stamps[1:])]
        self.assertTrue(all(g >= 120 for g in gaps), gaps)             # 그리고 완충만큼 떨어져 있다

    async def test_commit_avoids_slots_naver_already_holds(self):
        """네이버에서 읽어 온 남의 예약 시각도 절대 다시 쓰지 않는다."""
        taken = [self.future + timedelta(hours=h) for h in (0, 2, 4)]
        await self.scan(*taken)
        async with self.sessions() as db:
            for i in range(3):
                db.add(Draft(id=f'n{i}', user_id='u', campaign_id='c', title=f'원고 {i}', status='ready'))
            await db.commit()
        placed = [datetime.fromisoformat(t) for t in await self.commit(['n0', 'n1', 'n2'], start_mode='at')]
        for slot in placed:
            self.assertNotIn(slot, taken)
            self.assertTrue(all(abs((slot - t).total_seconds()) >= 120 * 60 for t in taken),
                            f'{slot} 가 기존 예약 {taken} 에 너무 가깝다')

    # ------------------------------------------------------- 발행 직전 방어
    async def test_reschedule_moves_the_job_and_keeps_the_attempt_count(self):
        async with self.sessions() as db:
            token = await api.protocol.claim(db, 'j0', 'u', 'b')
        clash = self.future
        response = await self.client.post('/agent/jobs/j0/reschedule', json={
            'lock_token': token, 'reason': '이미 예약된 글이 있습니다',
            'taken_at': [clash.isoformat(timespec='minutes')]})
        self.assertEqual(response.status_code, 200, response.text)
        moved = datetime.fromisoformat(response.json()['scheduled_at'])
        self.assertGreaterEqual(moved - clash, timedelta(minutes=120))   # 완충만큼 떨어졌다
        async with self.sessions() as db:
            job = await db.get(PublishJob, 'j0')
            self.assertEqual(job.status, 'queued')          # 다시 줄을 선다
            self.assertEqual(job.attempts or 0, 0)          # 실패로 치지 않는다
            self.assertEqual(job.scheduled_at, moved)
        sources = dict((at, src) for at, src in await self.marks())
        self.assertEqual(sources.get(clash), 'naver')       # 현장에서 본 남의 자리
        self.assertEqual(sources.get(moved), 'campaign')    # 우리가 새로 잡은 자리


if __name__ == '__main__':
    unittest.main()
