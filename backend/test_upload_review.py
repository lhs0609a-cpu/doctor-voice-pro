"""올린 원고가 '검토 필요'로 막히는 조건과, 사람이 확인해 푸는 길.

2026-09-23 결정: 의료광고법 글자 패턴 검사는 걷어냈다. '1,000원'·'무료 상담'·'보장'
같은 평범한 문장이 걸려 올린 원고가 전부 막혔고, 진짜 위반은 문맥을 봐야 해서 글자
매칭으로는 어차피 못 잡는다. 이제 막는 것은 **병원이 직접 등록한 금칙어**뿐이다.
"""
import unittest

from app.services.campaign_writer import run_static_checks


class StaticCheckTest(unittest.TestCase):
    def test_ordinary_sentences_are_not_blocked_any_more(self):
        """예전에는 이 한 줄이 다섯 곳에 걸려 원고가 통째로 막혔다."""
        checks = run_static_checks(
            "성장클리닉, 살만 빼면 키가 클까요",
            "상담은 무료이며 검사비는 30,000원입니다. 꾸준히 관리하면 좋아질 수 있습니다.")
        self.assertTrue(checks["ok"])
        self.assertEqual(checks["medical_law"], [])
        self.assertEqual(checks["forbidden"], [])

    def test_the_clinic_s_own_words_still_block(self):
        """무엇을 막을지는 그 병원이 정한다 — 등록한 금칙어는 그대로 잡는다."""
        checks = run_static_checks("우리 병원 최고", "본문", ["최고"])
        self.assertFalse(checks["ok"])
        self.assertEqual(checks["forbidden"], ["최고"])

    def test_the_shape_of_checks_does_not_change(self):
        """옛 원고와 화면이 같은 모양을 기대한다 — medical_law 칸은 빈 목록으로 남긴다."""
        checks = run_static_checks("제목", "본문")
        self.assertEqual(set(checks), {"medical_law", "forbidden", "ok"})


if __name__ == "__main__":
    unittest.main()
