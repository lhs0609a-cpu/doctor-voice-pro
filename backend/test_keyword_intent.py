"""간절함(내원 의도) — 검색량이 아니라 '얼마나 급한가'로 줄을 세운다.

'아토피에좋은음식'은 한 달에 수천 번 검색되지만 그 사람들은 병원을 찾는 중이 아니다.
'강남역아토피피부과'는 검색량이 20이어도 지금 갈 곳을 고르는 중이다. 글은 뒤쪽부터 쓴다.
이 파일은 그 순서가 뒤집히지 않게 잡아 둔다.
"""
import unittest

from app.models.campaign import CampaignKeyword
from app.services import keyword_taxonomy as tx
from app.services.keyword_hunt import _pick_by_quota

REGIONS = ["강남", "서초"]
SUBJECTS = ["아토피", "한포진"]


def score(keyword: str) -> int:
    return tx.intent(keyword, REGIONS, SUBJECTS)[0]


class IntentScoreTest(unittest.TestCase):
    def test_going_to_a_clinic_outranks_reading_about_it(self):
        order = ["서초 아토피 잘보는 병원 추천", "강남역아토피피부과", "아토피 치료비용",
                 "아토피 치료", "아토피 초기증상", "아토피", "아토피에좋은음식"]
        scores = [score(k) for k in order]
        self.assertEqual(scores, sorted(scores, reverse=True), list(zip(order, scores)))

    def test_pain_and_waiting_raise_the_score(self):
        self.assertGreater(score("아토피 안낫는이유"), score("아토피 원인"))
        self.assertGreater(score("한포진 3주째"), score("한포진"))
        self.assertGreater(score("아기 아토피 밤에 잠못자"), score("아토피 관리법"))

    def test_curiosity_and_home_remedies_sink(self):
        self.assertLess(score("아토피 뜻"), score("아토피"))
        self.assertLess(score("아토피에좋은음식"), score("아토피 초기증상"))

    def test_our_own_region_beats_a_bare_clinic_word(self):
        self.assertGreater(score("강남 아토피 피부과"), score("아토피 피부과"))

    def test_reason_is_a_sentence_a_person_can_read(self):
        _, why = tx.intent("강남역아토피피부과", REGIONS, SUBJECTS)
        self.assertEqual(why, "우리 지역을 찍어 찾는 중")
        self.assertEqual(tx.intent("아토피 뜻", REGIONS, SUBJECTS)[1], "뜻·정보만 확인")

    def test_level_reads_as_words(self):
        self.assertEqual(tx.intent_level(score("강남역아토피피부과")), "높음")
        self.assertEqual(tx.intent_level(score("아토피에좋은음식")), "낮음")


def _row(keyword: str, volume: int, probability: float = 0.8) -> CampaignKeyword:
    category = tx.classify(keyword, REGIONS, SUBJECTS)
    intent, reason = tx.intent(keyword, REGIONS, SUBJECTS, category)
    row = CampaignKeyword(keyword=keyword, disease="아토피", category=category,
                          total_volume=volume, my_probability=probability, my_verdict="likely",
                          intent_score=intent, intent_reason=reason)
    row.id = keyword
    return row


class PickOrderTest(unittest.TestCase):
    def test_volume_no_longer_decides_who_gets_written(self):
        """같은 성격 안에서는 검색량 9,000짜리보다 검색량 20짜리 '지역+병원'이 먼저다."""
        rows = [_row("아토피 피부과", 9000), _row("강남 아토피 피부과", 20)]
        picked = _pick_by_quota(rows, 1, ["아토피"], None, None)
        self.assertEqual(picked[0].keyword, "강남 아토피 피부과")

    def test_volume_still_breaks_ties(self):
        rows = [_row("아토피 초기증상", 100), _row("아토피 초기징후", 900)]
        picked = _pick_by_quota(rows, 1, ["아토피"], None, None)
        self.assertEqual(picked[0].keyword, "아토피 초기징후")

    def test_the_requested_mix_still_wins_over_pure_urgency(self):
        """간절한 순이라고 병원 글만 뽑지는 않는다 — 비율을 달라고 했으면 그 비율이 먼저다.

        블로그는 증상·원인·관리 글이 함께 있어야 주제 적합도가 쌓인다. 간절함은
        '같은 칸 안에서 누구를 먼저 쓰나'와 '목록을 어떤 순서로 보여 주나'를 정한다."""
        rows = [_row("강남 아토피 피부과", 20), _row("서초 아토피 의원", 20),
                _row("아토피 초기증상", 800), _row("아토피 원인", 700)]
        picked = _pick_by_quota(rows, 2, ["아토피"], None, {"병원": 50, "증상": 50})
        self.assertEqual({r.category for r in picked}, {"병원", "증상"})


if __name__ == "__main__":
    unittest.main()
