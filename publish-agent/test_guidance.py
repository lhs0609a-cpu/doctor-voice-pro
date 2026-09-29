"""안내 한 줄이 지켜야 하는 약속(2026-09-29 사용자 요청).

"저런거 뜨면 구체적으로 어떤 액션을 하라는건지 가이드를 안내해줘, 오류가 아니라면 이해돼?"

두 가지다.
1) 조치가 필요하면 **무엇을 누르면 되는지**가 문장 안에 있어야 한다(→ 로 표시).
2) 조치가 필요 없으면 [정상]이라고 분명히 말해야 한다. 조용한 화면을 고장으로 읽으면
   멀쩡한 예약을 지우고 다시 거는 헛수고를 한다.
"""
import unittest

from guidance import ACTION, OK, blog_status, overall


def blog(**over):
    base = {'label': '메인', 'status': 'active', 'pending': 0,
            'blocked': 0, 'stalled': 0, 'hold_reason': None, 'next_at': None}
    base.update(over)
    return base


class GuidanceTests(unittest.TestCase):
    def assert_actionable(self, level, text):
        self.assertEqual(level, ACTION, text)
        self.assertIn(f'[{ACTION}]', text)
        self.assertIn('→', text, "무엇을 누르면 되는지가 없다")

    # ---------------------------------------------------- 조치가 필요한 경우
    def test_an_unresolved_publication_names_the_two_buttons(self):
        level, text = blog_status(blog(blocked=1, pending=4))
        self.assert_actionable(level, text)
        self.assertIn('예약 등록 확인', text)
        self.assertIn('미등록 확인', text)
        self.assertIn('4건', text, '풀면 몇 건이 이어지는지도 알려 준다')

    def test_a_lost_login_points_at_the_chrome_window(self):
        level, text = blog_status(blog(status='login_required', pending=2))
        self.assert_actionable(level, text)
        self.assertIn('크롬', text)

    def test_a_captcha_points_at_the_chrome_window(self):
        level, text = blog_status(blog(status='captcha', pending=2))
        self.assert_actionable(level, text)
        self.assertIn('보안문자', text)

    def test_a_server_hold_reason_is_passed_through(self):
        level, text = blog_status(blog(pending=1, hold_reason="'자동 운영'이 꺼져 있습니다. → 켜 주세요"))
        self.assert_actionable(level, text)
        self.assertIn('자동 운영', text)

    def test_work_that_ran_out_of_retries_asks_for_a_retry(self):
        level, text = blog_status(blog(stalled=2))
        self.assert_actionable(level, text)
        self.assertIn('재시도', text)

    def test_the_most_blocking_thing_is_said_first(self):
        """'확인 필요'가 있으면 그것부터. 그 한 건이 나머지를 전부 세우기 때문이다."""
        _, text = blog_status(blog(blocked=1, stalled=3, pending=2))
        self.assertIn('예약 등록 확인', text)
        self.assertNotIn('재시도', text)

    # ---------------------------------------------------------- 정상인 경우
    def test_waiting_for_a_future_slot_is_plainly_normal(self):
        """'대기 1건 · 다음 10-03 15:30' 만 보고 고장이라 읽던 화면(2026-09-29)."""
        level, text = overall([blog(pending=1, next_at='2026-10-03T15:30')])
        self.assertEqual(level, OK)
        self.assertIn(f'[{OK}]', text)
        self.assertIn('10-03 15:30', text)
        self.assertIn('기다립니다', text)

    def test_nothing_to_do_says_so_without_sounding_broken(self):
        level, text = blog_status(blog())
        self.assertEqual(level, OK)
        self.assertIn(f'[{OK}]', text)

    def test_one_blog_needing_help_wins_over_the_quiet_ones(self):
        level, text = overall([blog(label='메인'), blog(label='서브', blocked=1, pending=1)])
        self.assertEqual(level, ACTION)
        self.assertIn('서브', text)

    def test_no_blogs_is_actionable_not_a_dead_end(self):
        level, text = overall([])
        self.assert_actionable(level, text)


if __name__ == '__main__':
    unittest.main()
