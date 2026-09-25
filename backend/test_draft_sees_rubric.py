"""초안을 쓰는 모델이 자기가 채점받을 기준을 본다.

2026-09-25 실측: 최근 20건 평균 65점. 차별화는 20건 전부 6.0/12 — 감점이 아니라
'재료 없음' 기본값이었다. 재료(differentiators)는 시스템 프롬프트에서만 조립돼
재작성(80점 미만)에만 들어갔는데, 채점기는 그 재료로 채점하고 있었다.
보여주지 않고 채점하던 셈이다.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.ai_rewrite_engine import ai_rewrite_engine as engine
from app.services.quality_scorer import quality_scorer

PROFILE = {
    "differentiators": {
        "philosophy": "먼저 걷는 모습을 본다",
        "items": [{"category": "검사", "text": "초음파로 연골을 한 번 더 확인한다"}],
    }
}


def prompt(profile=PROFILE, length=1500):
    return engine._build_user_prompt(
        "무릎이 아침에 뻣뻣합니다.", "정보전달형", 3, length,
        target_audience=None, top_post_rules=None, keyword="무릎통증",
        doctor_profile=profile,
    )


class DraftSeesTheRubric(unittest.TestCase):
    def test_the_clinic_material_reaches_the_first_draft(self):
        text = prompt()
        self.assertIn("초음파로 연골을 한 번 더 확인한다", text)
        self.assertIn("먼저 걷는 모습을 본다", text)

    def test_the_counts_the_scorer_measures_are_stated(self):
        """채점기는 문장을 센다. '잘 써라'로는 점수가 안 움직인다."""
        text = prompt()
        for demand in ("한계나 예외를 인정", "오늘 바로 할 수 있는 행동",
                       "언제 병원에 와야 하는지", "시간과 장면"):
            self.assertIn(demand, text)

    def test_the_counts_scale_with_length(self):
        short, long = prompt(length=1000), prompt(length=4000)
        self.assertNotEqual(short, long)

    def test_no_example_sentences_that_would_be_copied_verbatim(self):
        """예시 문구를 주면 그대로 베껴 모든 글이 판박이가 된다."""
        text = engine._quality_contract(1500)
        for seed in ("다만", "그럴 때는", "3주", "혹시 이런 적"):
            self.assertNotIn(seed, text)

    def test_a_clinic_with_nothing_registered_adds_no_empty_block(self):
        text = prompt(profile={})
        self.assertNotIn("<이 병원만의 것>", text)
        self.assertIn("<이 글에 반드시 들어갈 것>", text)   # 개수 계약은 재료와 무관하다


class GreetingOpening(unittest.TestCase):
    def test_the_prompt_no_longer_asks_for_the_opening_the_scorer_penalises(self):
        """채점기는 인사로 시작하면 첫 문단 5점 중 3.5점을 깎는다(GREETING_START)."""
        import inspect
        from app.services import ai_rewrite_engine as mod
        source = inspect.getsource(mod)
        self.assertNotIn("인사로 시작해 독자의", source)

    def test_the_scorer_really_does_punish_a_greeting(self):
        greeted = "제목\n\n안녕하세요, 저희 병원입니다. 오늘은 무릎 이야기를 해보겠습니다. 아침마다 뻣뻣합니다."
        scene = "제목\n\n아침에 첫발을 디딜 때 무릎이 뻣뻣한 적 있으신가요? 계단을 내려갈 때 특히 그렇습니다. 3개월째 그렇다면 그냥 두기 어렵습니다."
        self.assertLess(quality_scorer.score_engagement(greeted)["details"]["hook"]["score"],
                        quality_scorer.score_engagement(scene)["details"]["hook"]["score"])


class JudgeSeesTheTitle(unittest.TestCase):
    def test_the_judge_prompt_carries_the_title(self):
        """제목도 키워드도 빈칸으로 주면 '검색 의도가 해결되는가'를 판정할 수 없다."""
        built = quality_scorer.build_judge_prompt("본문", title="무릎통증 아침에 뻣뻣한 이유")
        self.assertIn("무릎통증 아침에 뻣뻣한 이유", built)


if __name__ == "__main__":
    unittest.main()
