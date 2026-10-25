import unittest
from datetime import datetime, timedelta, timezone
from app.services.publication_verifier import (
    GRACE_HOURS, MATCH_TOLERANCE_MIN, overdue, public_evidence, rss_match, rss_match_by_time,
)


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


class RssMatchByTimeTests(unittest.TestCase):
    """제목을 손으로 고쳐 올린 글 — 제목으로는 못 찾아도 예약 **시각**으로 찾는다.

    2026-10-25: '확인 필요' 93건 중 49건이 이 경우였다. 글은 예약 시각에 분 단위까지
    정확히 올라가 있었고 제목만 달랐다."""

    SCHEDULED = datetime(2026, 10, 22, 14, 0)

    def _items(self, *offsets_min):
        out = []
        for i, off in enumerate(offsets_min):
            when = self.SCHEDULED + timedelta(minutes=off)
            out.append({"title": "운영자가 바꾼 제목 %d" % i,
                        "post_no": "22300000000%d" % i,
                        "pub_date": when.replace(tzinfo=timezone(timedelta(hours=9))).isoformat()})
        return out

    def test_finds_the_post_published_at_the_scheduled_minute(self):
        got = rss_match_by_time(self._items(0), "testblog", self.SCHEDULED)
        self.assertEqual(got, "https://blog.naver.com/testblog/223000000000")

    def test_allows_small_drift_but_not_a_neighbouring_slot(self):
        self.assertIsNotNone(rss_match_by_time(self._items(MATCH_TOLERANCE_MIN), "b", self.SCHEDULED))
        # 예약은 10분 격자다 — 옆 자리 글을 잘못 집어오면 안 된다.
        self.assertIsNone(rss_match_by_time(self._items(10), "b", self.SCHEDULED))
        self.assertIsNone(rss_match_by_time(self._items(-10), "b", self.SCHEDULED))

    def test_does_not_hand_the_same_post_to_two_jobs(self):
        items = self._items(0)
        first = rss_match_by_time(items, "b", self.SCHEDULED)
        taken = {first.rsplit("/", 1)[-1]}
        self.assertIsNone(rss_match_by_time(items, "b", self.SCHEDULED, taken))

    def test_survives_missing_or_broken_pub_date(self):
        self.assertIsNone(rss_match_by_time([{"post_no": "1", "pub_date": None}], "b", self.SCHEDULED))
        self.assertIsNone(rss_match_by_time([{"post_no": "1", "pub_date": "어제"}], "b", self.SCHEDULED))
        self.assertIsNone(rss_match_by_time(None, "b", self.SCHEDULED))
        self.assertIsNone(rss_match_by_time(self._items(0), "b", None))

    def test_naive_pub_date_is_read_as_kst(self):
        items = [{"title": "x", "post_no": "9", "pub_date": self.SCHEDULED.isoformat()}]
        self.assertEqual(rss_match_by_time(items, "b", self.SCHEDULED), "https://blog.naver.com/b/9")


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
