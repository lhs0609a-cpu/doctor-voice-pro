"""비어 있는 항목 하나만 집중해서 채운다.

지적을 여덟 개 한꺼번에 주면 모델은 쉬운 것만 고친다 — 실측 네 번 모두 two_sided 가
0/5 였고, 매번 지적했는데 매번 안 고쳤다. 분량 맞추기가 잘 듣는 이유는 단 하나만
요구하기 때문이다(2026-09-25).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.ai_rewrite_engine import ai_rewrite_engine as engine
from app.services import evidence_context


def report(**axes):
    return {axis: {"details": items} for axis, items in axes.items()}


class PicksTheRightThing(unittest.TestCase):
    def test_it_picks_the_biggest_hole(self):
        r = report(
            trust={"two_sided": {"score": 0, "max": 5, "notes": ["인정하고 받아주세요"]},
                   "naturalness": {"score": 1.0, "max": 3, "notes": ["번역체"]}},
            engagement={"hook": {"score": 4.5, "max": 5, "notes": ["조금만 더"]}},
        )
        name, item = engine._weakest(r)
        self.assertEqual(name, "trust.two_sided")
        self.assertEqual(item["notes"], ["인정하고 받아주세요"])

    def test_items_that_are_nearly_full_are_left_alone(self):
        """거의 채운 항목을 건드리면 멀쩡한 문단이 흔들린다."""
        r = report(trust={"naturalness": {"score": 2.6, "max": 3, "notes": ["조금"]}})
        self.assertIsNone(engine._weakest(r))

    def test_an_item_with_no_advice_is_skipped(self):
        """무엇을 고치라는 말이 없으면 집중 패스를 돌릴 수 없다."""
        r = report(trust={"evidence": {"score": 0, "max": 5, "notes": []}})
        self.assertIsNone(engine._weakest(r))

    def test_a_perfect_report_has_nothing_to_reinforce(self):
        r = report(trust={"two_sided": {"score": 5, "max": 5, "notes": []}})
        self.assertIsNone(engine._weakest(r))


class RealEvidenceOnly(unittest.TestCase):
    # content_evidence 는 본문을 'excerpt' 에 담는다. 키를 잘못 보면 근거가 늘 비어 있다
    # (2026-09-25 실측: collect 는 kdca 문서 2건을 가져왔는데 블록이 0자였다).
    SOURCES = [{"title": "질병관리청 무릎관절증", "url": "https://health.kdca.go.kr/x",
                "excerpt": "무릎 관절증은 연골이 닳아 생깁니다. 체중 관리가 도움이 됩니다."}]

    def test_the_body_reaches_both_the_writer_and_the_scorer(self):
        """채점기 대조본에도 들어가야 인용이 '지어낸 출처'로 몰리지 않는다."""
        block, corpus = evidence_context.build(self.SOURCES)
        self.assertIn("질병관리청 무릎관절증", block)
        self.assertIn("질병관리청 무릎관절증", corpus)
        self.assertIn("연골이 닳아", corpus)

    def test_it_forbids_naming_any_other_institution(self):
        block, _ = evidence_context.build(self.SOURCES)
        self.assertIn("다른 기관을 지어내지 않는다", block)

    def test_a_source_that_is_not_about_the_subject_is_dropped(self):
        """검색이 걸리는 대로 가져오면 '포털 사업 개요' 같은 문서가 온다(2026-09-25 실측).
        주제가 안 맞는 자료를 쥐여 주고 인용하라고 하면 그게 곧 조작이다."""
        off = [{"title": "국가건강정보포털", "url": "https://health.kdca.go.kr/y",
                "excerpt": "인터넷 건강정보 인포데믹 대응 사업 개요와 배경입니다. 이용 통계는 다음과 같습니다."}]
        self.assertEqual(evidence_context.build(off, "무릎통증"), ("", ""))

    def test_spacing_does_not_decide_relevance(self):
        """'무릎통증' 과 '무릎 통증' 은 같은 말이다."""
        spaced = [{"title": "질병관리청 무릎관절증", "url": "https://health.kdca.go.kr/z",
                   "excerpt": "무릎 관절증은 무릎 연골이 닳아 생깁니다. 무릎 통증이 이어지면 진료가 필요합니다."}]
        self.assertNotEqual(evidence_context.build(spaced, "무릎통증")[0], "")

    def test_empty_or_textless_sources_produce_nothing(self):
        self.assertEqual(evidence_context.build([]), ("", ""))
        self.assertEqual(evidence_context.build([{"title": "x", "excerpt": "  "}]), ("", ""))


if __name__ == "__main__":
    unittest.main()
