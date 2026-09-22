"""키워드 비율 추출 — 질환별 개수 × 그 안의 글 성격 비율.

실측 전제: 어떤 칸은 후보가 구조적으로 모자란다(건선·습진 274개 중 '관리'는 10개뿐).
비율은 희망이고, **요청한 개수를 채우는 것이 우선**이다. 이 규약이 이 파일의 주제다.
"""
import unittest

from app.models.campaign import CampaignKeyword
from app.services import keyword_taxonomy as tx
from app.services.keyword_hunt import _pick_by_quota


def _row(keyword, disease, category, prob=0.5, volume=100):
    r = CampaignKeyword(keyword=keyword, disease=disease, category=category,
                        my_probability=prob, total_volume=volume, my_verdict="likely")
    r.id = f"{disease}:{category}:{keyword}"
    return r


def _pool(spec):
    """spec = {(질환, 성격): 개수} → 행 목록."""
    rows = []
    for (disease, category), n in spec.items():
        for i in range(n):
            rows.append(_row(f"{disease}{category}{i}", disease, category,
                             prob=0.9 - i * 0.001, volume=1000 - i))
    return rows


class Classify(unittest.TestCase):
    def test_intent_beats_generic(self):
        subjects = ["건선"]
        self.assertEqual(tx.classify("건선치료비용", (), subjects), "비용")
        self.assertEqual(tx.classify("건선 잘보는 병원", (), subjects), "병원")
        self.assertEqual(tx.classify("건선 습진 차이", (), subjects), "검사")
        self.assertEqual(tx.classify("건선초기증상", (), subjects), "증상")
        self.assertEqual(tx.classify("건선 생기는 이유", (), subjects), "원인")
        self.assertEqual(tx.classify("건선에 좋은 음식", (), subjects), "관리")

    def test_head_keywords_become_representative(self):
        subjects = ["건선", "가려움"]
        self.assertEqual(tx.classify("건선", (), subjects), "대표")
        self.assertEqual(tx.classify("손가락 건선", (), subjects), "대표")
        # 증상어가 곧 진료 항목인 경우에도 그 자체는 대표다.
        self.assertEqual(tx.classify("가려움", (), subjects), "대표")

    def test_region_without_intent_is_clinic(self):
        self.assertEqual(tx.classify("강남바이오", ["강남"], []), "병원")

    def test_unknown_stays_etc(self):
        self.assertEqual(tx.classify("주식 투자", [], ["건선"]), "기타")


class Allocate(unittest.TestCase):
    def test_allocation_sums_to_total_exactly(self):
        for total in (10, 37, 100, 137, 300):
            got = tx.allocate(total, tx.DEFAULT_RATIO)
            self.assertEqual(sum(got.values()), total, f"{total} → {got}")

    def test_ratio_is_respected_proportionally(self):
        got = tx.allocate(100, {"치료": 50, "증상": 50})
        self.assertEqual(got, {"치료": 50, "증상": 50})

    def test_empty_ratio_falls_back_to_default(self):
        self.assertEqual(tx.normalize_ratio({}), tx.DEFAULT_RATIO)
        self.assertEqual(tx.normalize_ratio({"없는카테고리": 5}), tx.DEFAULT_RATIO)

    def test_subject_quota_is_scaled_down_when_it_overflows(self):
        got = tx.split_by_subject(100, ["건선", "습진"], {"건선": 200, "습진": 200})
        self.assertEqual(sum(got.values()), 100)

    def test_subject_quota_is_used_as_is_when_it_fits(self):
        got = tx.split_by_subject(100, ["건선", "습진"], {"건선": 30, "습진": 20})
        self.assertEqual(got, {"건선": 30, "습진": 20})

    def test_no_quota_splits_evenly(self):
        got = tx.split_by_subject(100, ["건선", "습진", "아토피"])
        self.assertEqual(sum(got.values()), 100)
        self.assertEqual(max(got.values()) - min(got.values()), 1)  # 34/33/33


class PickByQuota(unittest.TestCase):
    SUBJECTS = ["건선", "습진"]

    def test_disease_quota_is_honoured(self):
        rows = _pool({("건선", "치료"): 50, ("건선", "증상"): 50,
                      ("습진", "치료"): 50, ("습진", "증상"): 50})
        picks = _pick_by_quota(rows, 40, self.SUBJECTS, {"건선": 30, "습진": 10}, None)
        self.assertEqual(len(picks), 40)
        self.assertEqual(sum(1 for r in picks if r.disease == "건선"), 30)
        self.assertEqual(sum(1 for r in picks if r.disease == "습진"), 10)

    def test_category_ratio_is_honoured_when_supply_allows(self):
        rows = _pool({("건선", "치료"): 100, ("건선", "증상"): 100})
        picks = _pick_by_quota(rows, 100, ["건선"], {"건선": 100}, {"치료": 75, "증상": 25})
        self.assertEqual(sum(1 for r in picks if r.category == "치료"), 75)
        self.assertEqual(sum(1 for r in picks if r.category == "증상"), 25)

    def test_short_category_is_backfilled_to_reach_target(self):
        """'관리' 를 20개 원했지만 후보가 3개뿐 — 빈자리를 남기지 않는다."""
        rows = _pool({("건선", "관리"): 3, ("건선", "치료"): 200})
        picks = _pick_by_quota(rows, 50, ["건선"], {"건선": 50}, {"관리": 40, "치료": 60})
        self.assertEqual(len(picks), 50, "요청 개수를 채우는 것이 우선이다")
        self.assertEqual(sum(1 for r in picks if r.category == "관리"), 3, "있는 만큼은 다 쓴다")

    def test_short_disease_is_backfilled_from_others(self):
        rows = _pool({("건선", "치료"): 5, ("습진", "치료"): 200})
        picks = _pick_by_quota(rows, 60, self.SUBJECTS, {"건선": 30, "습진": 30}, None)
        self.assertEqual(len(picks), 60)
        self.assertEqual(sum(1 for r in picks if r.disease == "건선"), 5)

    def test_highest_probability_wins_inside_a_cell(self):
        rows = _pool({("건선", "치료"): 10})
        picks = _pick_by_quota(rows, 3, ["건선"], {"건선": 3}, {"치료": 100})
        self.assertEqual([r.my_probability for r in picks],
                         sorted((r.my_probability for r in picks), reverse=True))
        self.assertAlmostEqual(picks[0].my_probability, 0.9)

    def test_no_duplicates_ever(self):
        rows = _pool({("건선", "치료"): 4, ("건선", "증상"): 4, ("습진", "치료"): 4})
        picks = _pick_by_quota(rows, 12, self.SUBJECTS, None, None)
        self.assertEqual(len(picks), len({r.id for r in picks}))

    def test_pool_smaller_than_target_returns_everything(self):
        rows = _pool({("건선", "치료"): 7})
        picks = _pick_by_quota(rows, 100, ["건선"], None, None)
        self.assertEqual(len(picks), 7)

    def test_rows_without_disease_still_get_used_as_filler(self):
        rows = _pool({("건선", "치료"): 2}) + [_row("무소속", None, "치료")]
        picks = _pick_by_quota(rows, 3, ["건선"], {"건선": 3}, None)
        self.assertEqual(len(picks), 3)

    def test_no_quota_no_ratio_falls_back_to_best_first(self):
        rows = _pool({("건선", "치료"): 5, ("습진", "증상"): 5})
        picks = _pick_by_quota(rows, 4, [], None, None)
        self.assertEqual(len(picks), 4)
        self.assertAlmostEqual(picks[0].my_probability, 0.9)


if __name__ == "__main__":
    unittest.main()
