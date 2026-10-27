"""2026-10-27 고객 요청 네 가지 — 원고 모양과 사진 고르기.

2) 문단이 모바일에서 길다 → 공백 제외 35~50자였던 문단을 25~35자로 줄였다.
3) 워드에 '05' 와 '치료' 가 따로 한 줄씩 들어온다 → '05 치료' 한 소제목으로 합친다.
4) 생리통 원고에 다이어트 GIF 가 들어갔다 → 주제를 담은 사진은 태그가 맞을 때만 쓴다.
5) 산부인과·내과 키워드가 들어가면 "혈액검사를 먼저 받아라"가 나온다 → 그 문장을 덜어낸다.
"""
import unittest

from app.services.campaign_writer import drop_foreign_test_advice, reflow
from app.services.docx_import import _merge_number_headings, _span
from app.services.photo_matcher import Photo, Slot, assign, fits_subject, score
from app.services.post_formatter import _PARA_MAX_CHARS, _PARA_MIN_CHARS, _mobile_paragraph


def nospace(text: str) -> int:
    return len("".join(text.split()))


def block(text: str, kind: str = "text") -> dict:
    return {"type": kind, "spans": [_span(text)], "content": text}


class ShorterParagraphsTest(unittest.TestCase):
    """2) 문단은 짧아졌고, 문장 중간은 여전히 끊지 않는다."""

    def test_the_agreed_range_is_25_to_35(self):
        self.assertEqual((_PARA_MIN_CHARS, _PARA_MAX_CHARS), (25, 35))

    def test_the_launcher_uses_the_same_range(self):
        """웹에서 본 모양과 올라간 글의 모양이 다르면 매니저가 검수를 할 수 없다."""
        import importlib.util
        import pathlib
        import sys

        path = pathlib.Path(__file__).resolve().parent.parent / "publish-agent" / "plan.py"
        spec = importlib.util.spec_from_file_location("_agent_plan", path)
        module = importlib.util.module_from_spec(spec)
        # dataclass 가 애노테이션을 풀 때 sys.modules 에서 제 모듈을 찾는다.
        sys.modules["_agent_plan"] = module
        try:
            spec.loader.exec_module(module)
        finally:
            sys.modules.pop("_agent_plan", None)
        self.assertEqual((module.PARA_MIN_CHARS, module.PARA_MAX_CHARS),
                         (_PARA_MIN_CHARS, _PARA_MAX_CHARS))

    def test_short_sentences_are_joined_only_up_to_the_new_ceiling(self):
        out = _mobile_paragraph(["생리통은 참는 병이 아닙니다.", "원인을 먼저 봅니다.",
                                 "체질에 따라 관리가 달라집니다.", "꾸준함이 중요합니다."])
        for para in out.split("\n\n"):
            self.assertLessEqual(nospace(para), _PARA_MAX_CHARS, para)

    def test_a_long_sentence_stays_whole(self):
        """마침표에서만 끊는다 — 쉼표 자리에서 자르면 글이 부러진다(2026-09-29)."""
        long_one = "생리통이 심해 일상생활이 어려울 정도라면 원인을 나누어 살펴보아야 합니다."
        self.assertEqual(_mobile_paragraph([long_one]), long_one)

    def test_every_boundary_is_one_blank_line(self):
        out = _mobile_paragraph(["첫 문장입니다.", "두 번째 문장입니다.", "세 번째 문장입니다."])
        self.assertNotIn("\n\n\n", out)
        self.assertNotIn("\n ", out)


class NumberHeadingTest(unittest.TestCase):
    """3) 번호만 있는 줄은 다음 줄과 한 소제목으로."""

    def test_a_lone_number_joins_the_next_line(self):
        got = _merge_number_headings([block("05"), block("치료"), block("본문입니다.")])
        self.assertEqual([(b["type"], b["content"]) for b in got],
                         [("heading", "05 치료"), ("text", "본문입니다.")])

    def test_the_number_is_kept_as_written(self):
        got = _merge_number_headings([block("3."), block("생활 관리")])
        self.assertEqual(got[0]["content"], "3. 생활 관리")

    def test_a_sentence_is_not_a_subheading(self):
        blocks = [block("05"), block("치료는 사람마다 다릅니다.")]
        self.assertEqual([b["type"] for b in _merge_number_headings(blocks)], ["text", "text"])

    def test_a_long_line_is_left_alone(self):
        blocks = [block("05"), block("치료 과정과 그 뒤의 관리까지 한 줄에 적어 둔 아주 긴 줄입니다만")]
        self.assertEqual([b["type"] for b in _merge_number_headings(blocks)], ["text", "text"])

    def test_text_without_a_number_is_untouched(self):
        blocks = [block("치료"), block("본문")]
        self.assertEqual(_merge_number_headings(blocks), blocks)


class SubjectFitTest(unittest.TestCase):
    """4) 단계가 맞는다고 아무 사진이나 넣지 않는다."""

    def setUp(self):
        self.slot = Slot(index=1, after_paragraph=2, need="생리통 설명",
                         keywords=["생리통", "한방 치료"], stage="도입")
        self.diet = Photo(id="gif-diet", scene="illustration",
                          tags=["다이어트", "체중감량", "운동"], suitable_for=["도입"])
        self.on_topic = Photo(id="gif-period", scene="illustration",
                              tags=["생리통", "복통"], suitable_for=["도입"])
        self.clinic = Photo(id="p-consult", scene="consult",
                            tags=["진료실", "상담"], suitable_for=["도입"])

    def test_the_old_score_alone_would_have_accepted_the_diet_gif(self):
        """이것이 고객이 본 그 사진이다 — 단계 점수 2.0 이 MIN_SCORE 1.0 을 혼자 넘었다."""
        self.assertGreaterEqual(score(self.slot, self.diet, set()), 1.0)

    def test_an_off_topic_picture_is_refused(self):
        self.assertFalse(fits_subject(self.slot, self.diet))
        self.assertEqual(assign([self.slot], [self.diet]), [])

    def test_an_on_topic_picture_is_used(self):
        self.assertTrue(fits_subject(self.slot, self.on_topic))
        got = assign([self.slot], [self.diet, self.on_topic])
        self.assertEqual([a["pool_image_id"] for a in got], ["gif-period"])

    def test_the_clinics_own_photos_fit_any_subject(self):
        """외관·대기실·진료실 사진은 글 주제를 가리지 않는다 — 그 병원 사진이니까."""
        self.assertTrue(fits_subject(self.slot, self.clinic))
        got = assign([self.slot], [self.diet, self.clinic])
        self.assertEqual([a["pool_image_id"] for a in got], ["p-consult"])

    def test_repeating_a_picture_still_respects_the_subject(self):
        slots = [self.slot, Slot(index=2, after_paragraph=4, need="관리",
                                 keywords=["생리통"], stage="마무리")]
        got = assign(slots, [self.diet], allow_repeat=True)
        self.assertEqual(got, [])


class ForeignTestAdviceTest(unittest.TestCase):
    """5) 다른 과 검사를 '먼저 받아라'는 문장만 덜어낸다."""

    def test_a_recommendation_is_removed(self):
        body = "생리통은 원인이 다양합니다. 혈액검사를 먼저 받아 보시는 것이 좋습니다."
        self.assertEqual(drop_foreign_test_advice(body), "생리통은 원인이 다양합니다.")

    def test_an_endoscopy_recommendation_is_removed(self):
        self.assertEqual(drop_foreign_test_advice("내시경 검사를 받아야 합니다. 한방은 다릅니다."),
                         "한방은 다릅니다.")

    def test_merely_mentioning_a_test_is_kept(self):
        """환자가 가져온 결과를 참고한다는 문장까지 지우면 글이 이상해진다."""
        body = "환자분이 가져오신 혈액검사 결과도 함께 참고합니다."
        self.assertEqual(drop_foreign_test_advice(body), body)

    def test_pointing_to_the_right_department_is_kept(self):
        body = "필요하면 산부인과에서 확인할 수 있습니다."
        self.assertEqual(drop_foreign_test_advice(body), body)

    def test_a_clean_manuscript_is_returned_unchanged(self):
        body = "생리통은 체질에 따라 관리가 달라집니다.\n\n꾸준히 보는 것이 중요합니다."
        self.assertEqual(drop_foreign_test_advice(body), body)

    def test_the_leftover_text_still_reflows(self):
        """문장을 덜어낸 자리에 빈 문단이 남지 않는다 — 그래서 덜어낸 뒤에 모양을 잡는다."""
        body = "혈액검사를 먼저 받아 보세요.\n\n생리통은 원인이 다양합니다. 체질을 함께 봅니다."
        out = reflow(drop_foreign_test_advice(body))
        self.assertNotIn("\n\n\n", out)
        self.assertNotIn("혈액검사", out)
        self.assertIn("생리통은 원인이 다양합니다.", out)


if __name__ == "__main__":
    unittest.main()
