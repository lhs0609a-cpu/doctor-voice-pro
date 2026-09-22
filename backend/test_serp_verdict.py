"""② 통검 자리 판정 — '블로그가 들어갈 자리가 있나'만 본다.

핵심 규약: **점유자가 병원이냐 아니냐로 키워드를 버리지 않는다.**
우리 블로그가 뚫는지는 ③(keyword_verdict)이 내 점수와 1페이지 컷라인을 실제로 재서 판단한다.
일반 블로거가 점령한 자리는 오히려 점유자 지수가 낮아 뚫기 쉬운 자리다.
"""
import unittest

from app.services import serp_analyzer as sa


def _posts(**counts):
    """blog_type 별 개수로 posts 리스트를 만든다."""
    out = []
    for blog_type, n in counts.items():
        for i in range(n):
            out.append({"blog_type": blog_type, "analyzed": False, "kw_count": 0,
                        "image_count": 0, "chars": 0, "headings": 0})
    return out


def _verdict(cafe_count=0, **counts):
    summary = sa._build_summary(_posts(**counts), cafe_count)
    return sa._decide_verdict(summary, None)


class NonHospitalPagesAreNotDiscarded(unittest.TestCase):
    """예전 규칙(병원 0건 + 노출 4건↑ → avoid)이 버리던 자리들."""

    def test_page_full_of_daily_bloggers_is_winnable(self):
        verdict, reason = _verdict(daily=8)
        self.assertEqual(verdict, "possible", reason)
        self.assertNotIn("병원 블로그가 전혀", reason)

    def test_page_of_unknown_bloggers_reaches_my_blog_judging(self):
        # 병원 0건이라 예전에는 avoid 였다. 이제 ③ 으로 넘어가야 한다.
        verdict, _ = _verdict(unknown=7)
        self.assertIn(verdict, ("possible", "contested"))

    def test_experience_posts_count_as_weak_occupants(self):
        verdict, reason = _verdict(experience=5, hospital=1)
        self.assertEqual(verdict, "possible", reason)

    def test_mixed_page_without_hospitals_is_contested_not_avoided(self):
        # 약한 점유자가 과반이 안 되고 인플루언서도 과반은 아닌 섞인 구성.
        verdict, _ = _verdict(influencer=4, daily=3, unknown=1)
        self.assertEqual(verdict, "contested")


class OnlyStructurallyClosedPagesAreAvoided(unittest.TestCase):
    def test_influencer_dominated_page_is_avoided(self):
        verdict, reason = _verdict(influencer=7, daily=3)
        self.assertEqual(verdict, "avoid")
        self.assertIn("인플루언서", reason)

    def test_hospital_absence_alone_never_avoids(self):
        for counts in ({"daily": 9}, {"unknown": 6}, {"experience": 8},
                       {"daily": 4, "unknown": 4}):
            verdict, reason = _verdict(**counts)
            self.assertNotEqual(verdict, "avoid",
                                f"병원이 없다는 이유로 버리면 안 된다: {counts} → {reason}")

    def test_empty_page_stays_unknown(self):
        verdict, _ = _verdict()
        self.assertEqual(verdict, "unknown")

    def test_blocked_serp_is_unknown(self):
        summary = sa._build_summary(_posts(daily=5), 0)
        verdict, _ = sa._decide_verdict(summary, "blocked")
        self.assertEqual(verdict, "unknown")


class ThinPagesAreOpenSeats(unittest.TestCase):
    def test_few_exposed_posts_means_a_free_seat(self):
        verdict, reason = _verdict(influencer=2)
        self.assertEqual(verdict, "possible", reason)

    def test_hospital_heavy_page_is_contested_not_automatically_easy(self):
        # 예전에는 병원 비중 40%↑ 를 possible 로 봤다. 병원도 전문 운영이라 만만치 않다.
        verdict, _ = _verdict(hospital=6, influencer=2, daily=2)
        self.assertEqual(verdict, "contested")


class SummaryKeepsHospitalSignalForDisplay(unittest.TestCase):
    def test_hospital_counts_are_still_reported(self):
        summary = sa._build_summary(_posts(hospital=3, daily=5), 0)
        self.assertEqual(summary["hospital_count"], 3)
        self.assertEqual(summary["soft_count"], 5)
        self.assertAlmostEqual(summary["soft_ratio"], 0.625)


if __name__ == "__main__":
    unittest.main()
