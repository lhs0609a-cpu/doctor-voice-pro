"""사진이 '그 글에 맞는 그 위치에' 들어가는지 — 구조 판정·자리 교정·매칭 문턱.

여기서 지키려는 것
- 소제목은 문단으로 세되 사진 자리로는 쓰지 않는다(소제목과 첫 문장 사이에 사진이 끼면 글이 끊긴다).
- 글 맨 끝에는 넣지 않는다(푸터 이미지가 따로 있다).
- 한 대목에는 한 장만.
- 어울리는 사진이 없으면 비워 둔다. 억지로 넣은 사진은 없느니만 못하다.
"""
import unittest

from app.services import photo_matcher as pm
from app.services.campaign_writer import (
    image_positions, is_heading, sections, split_paragraphs, _repair_slots,
)

BODY = (
    "강남아토피로 고민하시는 분들이 많습니다. 밤마다 가렵습니다.\n\n"
    "아토피의 원인\n\n"
    "피부 장벽이 약해집니다. 면역 반응이 과해집니다.\n\n"
    "건조한 계절에 특히 심합니다. 실내 습도도 봅니다.\n\n"
    "치료 방법\n\n"
    "보습이 먼저입니다. 생활 습관을 함께 점검합니다.\n\n"
    "증상이 오래가면 상담을 권합니다."
)


class StructureTests(unittest.TestCase):
    def setUp(self):
        self.paras = split_paragraphs(BODY)

    def test_headings_are_separated_from_body(self):
        self.assertEqual([i for i, p in enumerate(self.paras) if is_heading(p)], [1, 4])

    def test_a_sentence_is_not_a_heading(self):
        self.assertFalse(is_heading("보습이 먼저입니다."))      # 문장부호로 끝난다
        self.assertFalse(is_heading("a" * 40))                  # 너무 길다
        self.assertTrue(is_heading("치료 방법"))

    def test_sections_group_paragraphs_under_their_heading(self):
        self.assertEqual(
            [(s["heading"], s["body_indices"]) for s in sections(self.paras)],
            [(None, [0]), ("아토피의 원인", [2, 3]), ("치료 방법", [5, 6])],
        )

    def test_photo_never_goes_after_a_heading_or_at_the_very_end(self):
        spots = image_positions(self.paras)
        self.assertEqual(spots, [0, 2, 3, 5])
        self.assertNotIn(1, spots)                  # 소제목
        self.assertNotIn(4, spots)                  # 소제목
        self.assertNotIn(len(self.paras) - 1, spots)  # 글 맨 끝


class SlotRepairTests(unittest.TestCase):
    def setUp(self):
        self.paras = split_paragraphs(BODY)

    def repair(self, raw, count=5):
        return _repair_slots(raw, self.paras, count, "아토피")

    def test_illegal_positions_from_the_model_are_dropped(self):
        got = self.repair([
            {"after_paragraph": 1, "keywords": ["원인"]},    # 소제목 뒤
            {"after_paragraph": 6, "keywords": ["인사"]},    # 글 맨 끝
            {"after_paragraph": 99, "keywords": []},         # 없는 번호
            {"after_paragraph": "둘", "keywords": []},        # 숫자가 아님
        ])
        self.assertNotIn(1, [s["after_paragraph"] for s in got])
        self.assertNotIn(6, [s["after_paragraph"] for s in got])
        self.assertTrue(all(s["after_paragraph"] in image_positions(self.paras) for s in got))

    def test_one_photo_per_section(self):
        got = self.repair([
            {"after_paragraph": 2, "keywords": ["피부"]},
            {"after_paragraph": 3, "keywords": ["계절"]},    # 같은 대목 → 버린다
        ], count=2)
        self.assertEqual([s["after_paragraph"] for s in got if s["after_paragraph"] in (2, 3)], [2])

    def test_it_does_not_pad_beyond_the_sections_available(self):
        got = self.repair(None, count=10)     # 대목 3개뿐
        self.assertEqual(len(got), 3)

    def test_slots_come_back_in_document_order(self):
        got = self.repair([{"after_paragraph": 5}, {"after_paragraph": 0}, {"after_paragraph": 2}])
        self.assertEqual([s["after_paragraph"] for s in got], [0, 2, 5])
        self.assertEqual([s["slot"] for s in got], [0, 1, 2])

    def test_model_silence_falls_back_to_one_per_section(self):
        got = self.repair(None, count=5)
        self.assertEqual([s["after_paragraph"] for s in got], [0, 2, 5])


class MatchingTests(unittest.TestCase):
    def slot(self, keywords, stage="진료과정"):
        return pm.Slot(index=0, after_paragraph=2, need="", keywords=keywords, stage=stage)

    def test_repeated_tags_do_not_inflate_the_score(self):
        """로컬 비전 모델은 같은 태그를 여러 번 뱉는다. 그대로 세면 그 사진이 늘 1등이 된다."""
        spammy = pm.Photo(id="a", tags=["진료실"] * 10, scene="consult")
        honest = pm.Photo(id="b", tags=["진료실"], scene="consult")
        s = self.slot(["진료실"])
        self.assertAlmostEqual(pm.score(s, spammy, set()), pm.score(s, honest, set()), places=3)

    def test_one_letter_keywords_do_not_match_everything(self):
        photo = pm.Photo(id="a", tags=["대기실", "장기"])
        self.assertEqual(pm._keyword_hits(["기"], photo.tags), [])
        self.assertEqual(pm._keyword_hits(["대기"], photo.tags), ["대기실"])

    def test_unrelated_photo_leaves_the_slot_empty(self):
        slot = self.slot(["임플란트", "치아"], stage="시술")
        unrelated = [pm.Photo(id="x", tags=["한약재", "약장"], scene="herbal", suitable_for=["기타"])]
        self.assertEqual(pm.assign([slot], unrelated), [])

    def test_a_matching_photo_is_still_assigned(self):
        slot = self.slot(["진료실", "상담"])
        photos = [
            pm.Photo(id="x", tags=["한약재"], scene="herbal"),
            pm.Photo(id="ok", tags=["진료실", "상담"], scene="consult", suitable_for=["진료과정"]),
        ]
        got = pm.assign([slot], photos)
        self.assertEqual([a["pool_image_id"] for a in got], ["ok"])

    def test_heavily_used_photos_lose_ground(self):
        slot = self.slot(["진료실"])
        fresh = pm.Photo(id="fresh", tags=["진료실"], scene="consult", use_count=0)
        worn = pm.Photo(id="worn", tags=["진료실"], scene="consult", use_count=12)
        self.assertGreater(pm.score(slot, fresh, set()), pm.score(slot, worn, set()))


if __name__ == "__main__":
    unittest.main()
