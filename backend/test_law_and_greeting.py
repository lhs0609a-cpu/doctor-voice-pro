"""실제 생성본에서 잡은 두 가지.

1) "통증이 없는 범위에서 움직이세요" 가 '부작용 없음 단정 광고'로 걸려 원점수 79.3 짜리
   원고가 총점 55(D) 로 깎였다. 규칙 주석은 스스로 "부사구는 위반이 아니다" 라고 적어
   두고 관형형 '없는' 을 패턴에 넣어 두었다.
2) 인사 도입을 프롬프트로 세 번 막았는데 세 번 다 "안녕하세요" 로 시작했다.
   지시로 안 되는 것은 지우는 편이 확실하다.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.quality_scorer import quality_scorer, strip_greeting


def breaks_law(text: str) -> bool:
    return quality_scorer.check_medical_ad_law(text)["counts"]["critical"] > 0


class PatientGuidanceIsNotAnAdvertisement(unittest.TestCase):
    def test_telling_a_patient_to_stay_within_a_painless_range_is_fine(self):
        self.assertFalse(breaks_law("통증이 없는 범위에서 가벼운 활동을 유지하세요"))
        self.assertFalse(breaks_law("무릎에 무리가 없는 선에서 걸으세요"))

    def test_claiming_a_procedure_has_no_side_effects_is_still_caught(self):
        self.assertTrue(breaks_law("부작용이 없는 시술입니다"))
        self.assertTrue(breaks_law("흉터가 없는 수술로 진행합니다"))

    def test_the_plain_declaration_is_still_caught(self):
        self.assertTrue(breaks_law("부작용이 없습니다"))
        self.assertTrue(breaks_law("통증이 없어요"))

    def test_a_good_article_is_no_longer_capped_by_a_false_positive(self):
        body = ("계단을 내려갈 때 아픈 경우와 올라갈 때는 원인이 다릅니다. "
                "통증이 없는 범위에서 가벼운 활동을 유지하는 것이 좋습니다.")
        self.assertEqual(quality_scorer.check_medical_ad_law(body)["score_cap"], 100)


class GreetingIsRemovedNotRequested(unittest.TestCase):
    ARTICLE = ("무릎통증, 계단에서 아픈 이유\n\n"
               "안녕하세요. 정형외과 전문의입니다.\n\n"
               "계단을 내려갈 때 무릎 앞쪽이 시큰거리시나요? 아침에 첫발을 디딜 때 특히 그렇습니다. "
               "3주 넘게 그렇다면 그냥 두기 어렵습니다.")

    def test_the_greeting_and_the_self_introduction_both_go(self):
        out = strip_greeting(self.ARTICLE)
        self.assertNotIn("안녕하세요", out)
        self.assertNotIn("정형외과 전문의입니다", out)

    def test_the_title_and_the_real_body_survive(self):
        out = strip_greeting(self.ARTICLE)
        self.assertTrue(out.startswith("무릎통증, 계단에서 아픈 이유"))
        self.assertIn("아침에 첫발을 디딜 때", out)

    def test_the_hook_score_actually_recovers(self):
        before = quality_scorer.score_engagement(self.ARTICLE)["details"]["hook"]["score"]
        after = quality_scorer.score_engagement(strip_greeting(self.ARTICLE))["details"]["hook"]["score"]
        self.assertGreater(after, before)

    def test_an_article_that_never_greeted_is_untouched(self):
        clean = strip_greeting(self.ARTICLE)
        self.assertEqual(strip_greeting(clean), clean)

    def test_an_article_that_is_only_a_greeting_is_left_alone(self):
        """지우고 나면 본문이 없다. 3.5점 잃는 편이 본문을 날리는 것보다 낫다."""
        only = "제목\n\n안녕하세요. 정형외과 전문의입니다."
        self.assertEqual(strip_greeting(only), only)


if __name__ == "__main__":
    unittest.main()
