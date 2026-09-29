"""같은 사진이 다음 글에 또 나오지 않는다(2026-09-29 고객 지적).

"1번째 포스팅에 사용된 사진 2번째 포스팅에도 사용" — 예전에는 '최근 쓴 사진'에 -1.5 를
감점만 줬다. 태그가 잘 맞는 사진은 키워드 하나에 +3.0 을 받으므로 감점을 이기고 다음 글에서
또 1등이 됐다. 이제는 **아직 아무도 안 쓴 사진을 먼저** 채우고, 자리가 남을 때만 쓴 사진을
꺼낸다.
"""
import unittest

from app.services.photo_matcher import Photo, Slot, assign


def slots(n: int, *keywords: str) -> list:
    """같은 성격의 자리 n 개 — 어느 글에서나 같은 사진이 1등이 되는 상황을 만든다."""
    return [Slot(index=i, after_paragraph=i * 2 + 1, need="", keywords=list(keywords), stage="시술")
            for i in range(n)]


# p-best 는 키워드 둘을 다 맞혀 +6.0, 나머지는 하나만 맞혀 +3.0. 감점 -1.5 로는 어림도 없다 —
# 사진 풀에 그 시술을 제대로 보여 주는 대표 사진 한 장이 있으면 실제로 이런 모양이 된다.
POOL = [
    Photo(id="p-best", tags=["레이저", "장비"], suitable_for=["시술"]),
    Photo(id="p-good", tags=["레이저"], suitable_for=["시술"]),
    Photo(id="p-ok", tags=["레이저"], suitable_for=["시술"]),
    Photo(id="p-plain", tags=["레이저"], suitable_for=["시술"]),
]


class PhotoReuseTests(unittest.TestCase):
    def test_the_second_post_does_not_reuse_the_first_posts_photos(self):
        first = assign(slots(2, "레이저", "장비"), POOL)
        used = {a["pool_image_id"] for a in first}
        self.assertEqual(len(used), 2, "한 글 안에서는 원래 겹치지 않았다")

        second = assign(slots(2, "레이저", "장비"), POOL, taken_ids=set(used))
        again = {a["pool_image_id"] for a in second}
        self.assertEqual(len(again), 2)
        self.assertFalse(used & again, f"1번 글의 사진이 2번 글에 또 나왔다: {used & again}")

    def test_a_penalty_alone_was_not_enough(self):
        """감점(recently_used_ids)만으로는 막지 못한다 — 이 시험이 예전 동작을 붙잡아 둔다."""
        first = assign(slots(1, "레이저", "장비"), POOL)
        best = first[0]["pool_image_id"]
        penalised = assign(slots(1, "레이저", "장비"), POOL, recently_used_ids={best})
        self.assertEqual(penalised[0]["pool_image_id"], best,
                         "감점만으로는 1등이 그대로다 — 그래서 taken_ids 가 필요하다")

    def test_slots_are_still_filled_when_the_pool_runs_out(self):
        """사진이 모자라면 빈 자리를 남기느니 쓴 사진이라도 넣는다."""
        assigned = assign(slots(3, "레이저", "장비"), POOL[:2], taken_ids={"p-best", "p-good"})
        self.assertEqual(len(assigned), 2, "가진 사진 수만큼은 채운다")
        self.assertEqual({a["pool_image_id"] for a in assigned}, {"p-best", "p-good"})

    def test_unused_photos_come_first_even_when_they_score_lower(self):
        """점수가 낮아도 '아직 안 쓴 사진'이 먼저다. 그것이 중복을 막는 유일한 방법이다."""
        assigned = assign(slots(1, "레이저", "장비"), POOL, taken_ids={"p-best", "p-good"})
        self.assertIn(assigned[0]["pool_image_id"], {"p-ok", "p-plain"})


if __name__ == "__main__":
    unittest.main()


class BeforeAfterTests(unittest.TestCase):
    """전후 사진은 자동 발행에서 아예 고르지 않는다(2026-09-30 사용자 결정).

    의료광고에서 가장 까다로운 사진이다. 빈 자리로 남기는 한이 있어도 자동으로 넣지 않는다.
    """

    def test_a_tagged_before_after_photo_is_never_chosen(self):
        pool = [Photo(id="p-ba", tags=["레이저", "장비"], suitable_for=["시술"], scene="before_after")]
        self.assertEqual(assign(slots(1, "레이저", "장비"), pool), [])

    def test_photos_tagged_before_the_new_scene_existed_are_also_caught(self):
        """다시 태깅하지 않아도 오늘부터 걸려야 한다 — 태그·설명 글자로도 본다."""
        for photo in (Photo(id="p1", tags=["전후", "비교"], suitable_for=["시술"]),
                      Photo(id="p2", tags=["레이저"], caption="치료 전후 비교 사진", suitable_for=["시술"]),
                      Photo(id="p3", tags=["Before/After"], suitable_for=["시술"])):
            with self.subTest(photo.id):
                self.assertEqual(assign(slots(1, "전후", "레이저"), [photo]), [], photo.id)

    def test_ordinary_photos_are_untouched(self):
        assigned = assign(slots(1, "레이저", "장비"), POOL)
        self.assertEqual(len(assigned), 1)
