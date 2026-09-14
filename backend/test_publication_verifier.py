import unittest
from datetime import datetime, timedelta
from app.services.publication_verifier import GRACE_HOURS, overdue, public_evidence, rss_match


class RssMatchTests(unittest.TestCase):
    """글 번호 없이 '네이버 예약됨'이 된 글을 예약 시각 뒤 RSS 로 찾는다."""

    def test_finds_same_title_ignoring_spaces_and_entities(self):
        items = [{"title": "다른 글", "post_no": "223000000001"},
                 {"title": "강남 아토피, 생활&amp;습관 점검", "post_no": "223000000002"}]
        self.assertEqual(rss_match(items, "testblog", "강남 아토피,생활&습관 점검"), "https://blog.naver.com/testblog/223000000002")

    def test_no_match_without_numeric_post_or_title(self):
        self.assertIsNone(rss_match([{"title": "제목", "post_no": ""}], "b", "제목"))
        self.assertIsNone(rss_match([{"title": "제목", "post_no": "1"}], "b", ""))
        self.assertIsNone(rss_match([], "b", "제목"))

    def test_hands_over_to_person_only_after_grace(self):
        at = datetime(2026, 9, 13, 14, 30)
        self.assertFalse(overdue(at, at + timedelta(hours=GRACE_HOURS - 1)))
        self.assertTrue(overdue(at, at + timedelta(hours=GRACE_HOURS)))


class VerificationTests(unittest.TestCase):
    def test_matches_exact_blog_and_post(self):
        html = '<meta property="og:url" content="https://blog.naver.com/test/123"><meta property="og:title" content="title"><div class="se-main-container"><p>body</p></div>'
        self.assertTrue(public_evidence(html, 'test', '123'))
        self.assertFalse(public_evidence(html, 'other', '123'))
        self.assertFalse(public_evidence(html, 'test', '124'))
        self.assertFalse(public_evidence(html, 'test', '123', 'different title'))

    def test_login_error_and_lookalike_are_not_publication(self):
        for html in ('<title>로그인</title>', '<meta property="og:url" content="https://blog.naver.com.evil.com/test/123"><meta property="og:title" content="title"><div class="se-main-container">body</div>', '<meta property="og:url" content="https://blog.naver.com/test/123"><meta property="og:title" content="title">'):
            self.assertFalse(public_evidence(html, 'test', '123'))


if __name__ == '__main__':
    unittest.main()
