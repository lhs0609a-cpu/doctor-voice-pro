"""간격 예약 — '몇 시간마다 한 개씩'.

원스톱 화면은 기간을 나눠 흩뿌리는 대신 사용자가 고른 간격을 그대로 지킨다.
지켜야 할 것은 셋: 발행 시간대 밖으로 나가지 않기, 이미 잡힌 자리 비켜 가기, 10분 단위.
"""
import unittest
from datetime import datetime, timedelta

from app.services import schedule_engine as se


def _plan(ref="b1", start="09:00", end="21:00", limit=3):
    return se.BlogPlan(ref_id=ref, naver_blog_id=f"naver-{ref}", daily_limit=limit,
                       window_start=start, window_end=end)


class IntervalAllocationTest(unittest.TestCase):
    def test_keeps_chosen_gap(self):
        start = datetime(2026, 9, 23, 9, 0)
        assigned, remaining = se.allocate_interval(4, [_plan()], start, 120, earliest=start)
        self.assertEqual(remaining, 0)
        self.assertEqual([at for _, at in assigned],
                         [start + timedelta(hours=2 * i) for i in range(4)])

    def test_daily_limit_does_not_cut_the_pace(self):
        """하루 한도 3건이어도 사용자가 고른 간격대로 6건이 들어간다(경고는 화면 몫)."""
        start = datetime(2026, 9, 23, 9, 0)
        assigned, remaining = se.allocate_interval(6, [_plan(limit=3)], start, 120, earliest=start)
        self.assertEqual(remaining, 0)
        first_day = [at for _, at in assigned if at.date() == start.date()]
        self.assertEqual(len(first_day), 6)

    def test_rolls_past_window_end_to_next_day(self):
        start = datetime(2026, 9, 23, 20, 0)
        assigned, _ = se.allocate_interval(3, [_plan()], start, 120, earliest=start)
        times = [at for _, at in assigned]
        self.assertEqual(times[0], datetime(2026, 9, 23, 20, 0))
        self.assertEqual(times[1], datetime(2026, 9, 24, 9, 0))    # 22시는 시간대 밖 → 다음 날 시작
        self.assertEqual(times[2], datetime(2026, 9, 24, 11, 0))

    def test_keeps_min_gap_around_existing_reservations(self):
        """이미 걸린 예약 앞뒤 min_gap 안에는 못 들어간다 — 같은 칸만 피하는 게 아니다."""
        plan = _plan()                                   # min_gap 120분
        plan.taken.add(datetime(2026, 9, 23, 11, 0))     # 네이버에 이미 있는 글
        plan.taken.add(datetime(2026, 9, 23, 16, 30))
        start = datetime(2026, 9, 23, 9, 0)
        assigned, remaining = se.allocate_interval(3, [plan], start, 120, earliest=start)
        self.assertEqual(remaining, 0)
        self.assertEqual([at for _, at in assigned], [
            datetime(2026, 9, 23, 9, 0),     # 11:00 에서 정확히 120분 전 → 경계는 쓸 수 있다
            datetime(2026, 9, 23, 13, 0),    # 11:00 완충이 끝나는 첫 칸(11:00 자체와 그 앞뒤는 막힘)
            datetime(2026, 9, 23, 18, 30),   # 15:00 은 16:30 완충 안 → 완충이 끝나는 칸으로
        ])

    def test_our_own_posts_keep_the_chosen_gap_not_min_gap(self):
        """완충은 남의 예약에만 건다. 30분 간격을 골랐으면 우리끼리는 30분이다."""
        start = datetime(2026, 9, 23, 9, 0)
        assigned, _ = se.allocate_interval(3, [_plan()], start, 30, earliest=start)
        self.assertEqual([at for _, at in assigned], [
            datetime(2026, 9, 23, 9, 0), datetime(2026, 9, 23, 9, 30), datetime(2026, 9, 23, 10, 0)])

    def test_avoids_taken_slots(self):
        start = datetime(2026, 9, 23, 9, 0)
        plan = _plan(limit=3)
        plan.min_gap_minutes = 0                          # 완충을 끈 블로그
        plan.taken.add(datetime(2026, 9, 23, 11, 0))
        assigned, _ = se.allocate_interval(2, [plan], start, 120, earliest=start)
        self.assertEqual([at for _, at in assigned],
                         [datetime(2026, 9, 23, 9, 0), datetime(2026, 9, 23, 11, 10)])

    def test_latest_reserved_is_the_start_of_after_last(self):
        plan = _plan()
        plan.taken.update({datetime(2026, 9, 23, 11, 0), datetime(2026, 9, 25, 18, 0)})
        last = se.latest_reserved([plan], after=datetime(2026, 9, 22, 12, 0))
        self.assertEqual(last, datetime(2026, 9, 25, 18, 0))
        assigned, _ = se.allocate_interval(1, [plan], last + timedelta(minutes=120), 120,
                                           earliest=datetime(2026, 9, 22, 12, 0))
        self.assertEqual(assigned[0][1], datetime(2026, 9, 25, 20, 0))

    def test_latest_reserved_ignores_the_past(self):
        plan = _plan()
        plan.taken.add(datetime(2026, 9, 20, 11, 0))
        self.assertIsNone(se.latest_reserved([plan], after=datetime(2026, 9, 22, 12, 0)))

    def test_round_robin_across_blogs(self):
        start = datetime(2026, 9, 23, 9, 0)
        assigned, _ = se.allocate_interval(4, [_plan("a"), _plan("b")], start, 60, earliest=start)
        self.assertEqual([ref for ref, _ in assigned], ["a", "b", "a", "b"])

    def test_never_earlier_than_earliest(self):
        """지금 바로를 골라도 실행기가 받을 수 있는 시각(earliest) 앞으로는 못 간다."""
        earliest = datetime(2026, 9, 23, 14, 35)
        assigned, _ = se.allocate_interval(1, [_plan()], datetime(2026, 9, 23, 9, 0), 120, earliest=earliest)
        self.assertEqual(assigned[0][1], datetime(2026, 9, 23, 14, 40))   # 10분 단위 올림

    def test_snaps_gap_to_ten_minutes(self):
        start = datetime(2026, 9, 23, 9, 0)
        assigned, _ = se.allocate_interval(2, [_plan()], start, 95, earliest=start)
        self.assertEqual(assigned[1][1], datetime(2026, 9, 23, 10, 30))


if __name__ == "__main__":
    unittest.main()
