"""카페 글쓰기의 순수 로직 — 브라우저 없이 확인할 수 있는 것들.

화면을 다루는 부분은 실제 카페에서만 확인할 수 있다. 여기서는 '두 번 올리지 않는다'를
지키는 데 필요한 판단만 본다.
"""
import unittest

from cafe_editor import CafeOutcome, cafe_write_url, post_url_from


class WriteUrlTests(unittest.TestCase):
    def test_the_write_screen_hangs_off_the_cafe_address(self):
        self.assertEqual(cafe_write_url('https://cafe.naver.com/mom'),
                         'https://cafe.naver.com/mom?iframe_url=/ArticleWrite.nhn')

    def test_a_trailing_slash_does_not_double_up(self):
        self.assertEqual(cafe_write_url('https://cafe.naver.com/mom/'),
                         'https://cafe.naver.com/mom?iframe_url=/ArticleWrite.nhn')


class PostUrlTests(unittest.TestCase):
    def test_the_post_number_is_the_receipt(self):
        self.assertEqual(post_url_from('https://cafe.naver.com/mom/12345?art=x'),
                         'https://cafe.naver.com/mom/12345')

    def test_the_write_screen_is_not_a_post(self):
        self.assertIsNone(post_url_from('https://cafe.naver.com/mom?iframe_url=/ArticleWrite.nhn'))

    def test_nothing_in_nothing_out(self):
        for raw in ('', None, 'https://example.com'):
            with self.subTest(raw=raw):
                self.assertIsNone(post_url_from(raw))


class OutcomeTests(unittest.TestCase):
    def test_an_unconfirmed_submit_is_uncertain_not_failure(self):
        """등록을 누른 뒤 모르는 것은 실패가 아니다. 실패로 두면 다시 올려서 두 번 올라간다."""
        outcome = CafeOutcome(ok=False, uncertain=True, message='확인하지 못했습니다')
        self.assertTrue(outcome.uncertain)
        self.assertFalse(outcome.ok)


if __name__ == '__main__':
    unittest.main()
