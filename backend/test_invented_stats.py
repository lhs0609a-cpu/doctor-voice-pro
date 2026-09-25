"""원본에 없는 숫자를 붙이면 잡는다.

2026-09-25 실측 생성: 원본에 숫자가 '하루 10분'과 '3주' 뿐인데 모델이
"열에 아홉은", "70% 이상을 차지합니다" 를 만들어 붙였다. 점수는 86점(A)이었다 —
즉 점수만 보면 통과하는 글에 지어낸 통계가 실려 나간다. 환자는 그 숫자를 믿는다.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.ai_rewrite_engine import ai_rewrite_engine as engine
from app.services.quality_scorer import quality_scorer

SOURCE = ("계단을 내려갈 때와 올라갈 때는 원인이 다릅니다. "
          "집에서는 벽에 등을 대고 앉는 자세를 하루 10분 권합니다. "
          "3주 넘게 이어지면 진료를 받아보세요.")


def evidence(body: str, source=SOURCE):
    return quality_scorer.score_trust("제목\n\n" + body, source_text=source)["details"]["evidence"]


class InventedNumbers(unittest.TestCase):
    def test_a_made_up_percentage_is_caught(self):
        self.assertIn("70%", evidence("실제로는 70% 이상이 근력 부족입니다.")["invented_stats"])

    def test_a_made_up_proportion_phrase_is_caught(self):
        self.assertIn("열에 아홉", evidence("열에 아홉은 파열을 걱정하십니다.")["invented_stats"])

    def test_numbers_that_are_in_the_source_are_left_alone(self):
        """'하루 10분'과 '3주'는 원장이 준 것이다. 이걸 잡으면 쓸 수 있는 말이 없어진다."""
        found = evidence("하루 10분씩 해 보세요. 3주 넘게 이어지면 진료를 받으세요.")
        self.assertEqual(found["invented_stats"], [])

    def test_the_writer_is_told_what_went_wrong(self):
        note = " ".join(evidence("70% 이상이 그렇습니다.")["notes"])
        self.assertIn("원본에 없는 숫자", note)

    def test_it_costs_points_so_the_rewrite_loop_fixes_it(self):
        # 근거 표현이 2개 이상 있어야 근거 점수가 0이 아니다(감점은 곱셈이라 0에는 안 먹는다).
        clean = ("여러 임상 현장에서 근력 부족이 흔하게 보고됩니다. 관련 연구에서도 같은 흐름입니다. "
                 "하루 10분씩 해 보세요. 3주 넘게 이어지면 진료를 받으세요.")
        dirty = clean + " 70% 이상이 그렇고 열에 아홉이 그렇습니다."
        self.assertLess(evidence(dirty)["score"], evidence(clean)["score"])

    def test_without_a_source_nothing_is_flagged(self):
        """원본을 모르면 지어낸 것인지 알 수 없다. 모를 때 벌하지 않는다."""
        self.assertEqual(evidence("70% 이상입니다.", source=None)["invented_stats"], [])


class GreetingIsSpelledOut(unittest.TestCase):
    def test_the_contract_names_the_words_the_model_actually_used(self):
        """'인사로 시작하지 마라'는 지켜지지 않았다 — 실제로 쓴 말을 그대로 적어 막는다."""
        contract = engine._quality_contract(1500)
        self.assertIn("안녕하세요", contract)

    def test_the_contract_forbids_inventing_numbers_to_fill_its_own_quotas(self):
        contract = engine._quality_contract(1500)
        self.assertIn("숫자를 지어내지 않는다", contract)


if __name__ == "__main__":
    unittest.main()
