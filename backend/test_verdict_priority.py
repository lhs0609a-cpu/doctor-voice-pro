"""판정에서 '내 블로그'가 경쟁자보다 먼저 채점되는지.

왜 중요한가: compute_verdict 는 내 점수가 없으면 무조건 unknown 을 돌려준다. 경쟁자를 스무 명
다 재도 내 블로그를 못 재면 판정이 나오지 않는다. 예전에는 내 블로그를 경쟁자 뒤에 줄 세워서,
경쟁자 채점이 느린 키워드에서는 예산이 끊기며 내 블로그가 통째로 취소됐다(화면에 '판정 불가').
"""
import asyncio
import unittest
from unittest.mock import patch

from app.blogindex import keyword_verdict as kv


class VerdictRefusesWithoutMyScore(unittest.TestCase):
    def test_no_my_score_means_unknown_no_matter_how_many_competitors(self):
        competitors = [{"blog_id": f"c{i}", "rank": i + 1, "score": 80.0} for i in range(10)]
        out = kv.compute_verdict(my=None, competitors=competitors, volume=2880, my_rank=None,
                                 topical=5, ceiling=None)
        self.assertEqual(out["verdict"], "unknown")
        self.assertIsNone(out["probability"])

    def test_my_score_present_produces_a_real_verdict(self):
        competitors = [{"blog_id": f"c{i}", "rank": i + 1, "score": 70.0 + i} for i in range(10)]
        out = kv.compute_verdict(my={"score": 79.6}, competitors=competitors, volume=2880,
                                 my_rank=None, topical=5, ceiling=None)
        self.assertNotEqual(out["verdict"], "unknown")
        self.assertIsNotNone(out["probability"])
        self.assertIsNotNone(out["cut_line"])


async def _topical(*_a, **_k):
    return 4, "내 블로그"


async def _nothing(*_a, **_k):
    return None


class MyBlogIsScoredFirst(unittest.IsolatedAsyncioTestCase):
    """경쟁자 채점이 예산을 다 먹어도 내 블로그 점수는 살아남아야 한다."""

    async def test_my_blog_survives_a_competitor_stampede(self):
        order = []

        async def slow_score(blog_id, keyword, use_cache):
            order.append(blog_id)
            if blog_id != "platonmarketing":
                await asyncio.sleep(0.25)        # 경쟁자는 느리다
                return {"score": 75.0, "blog_name": blog_id, "recent_activity_days": 3}
            return {"score": 79.6, "blog_name": "내 블로그", "recent_activity_days": 0}

        # facts.facts 를 채워 두면 stage1(네트워크)을 타지 않는다.
        facts = {"ok": True, "facts": {
            "page1": [{"blog_id": f"c{i}", "rank": i + 1} for i in range(20)],
            "serp_parse_mode": "list", "my_rank": None, "volume": 2880, "already_page1": False,
        }}
        with patch.object(kv, "_score_blog", slow_score), \
             patch.object(kv, "STAGE2_BUDGET", 0.6), \
             patch.object(kv, "_topical_fit", _topical), \
             patch.object(kv, "_ceiling_from_cache", _nothing), \
             patch.object(kv, "_record", _nothing):
            out = await kv.stage2_verdict(None, "platonmarketing", "아토피 치료", facts=facts)

        self.assertEqual(order[0], "platonmarketing",
                         f"내 블로그가 먼저여야 한다. 실제 순서: {order[:3]}")
        self.assertEqual((out.get("my") or {}).get("score"), 79.6,
                         "경쟁자 채점이 예산을 넘겨도 내 점수는 남아야 한다")
        # 못 잰 것은 경쟁자다. 내 블로그 탓으로 돌리면 사용자가 자기 블로그를 의심하게 된다.
        self.assertFalse(any("내 블로그를 채점하지 못했습니다" in r for r in out.get("reasons") or []),
                         f"실패 사유가 잘못 지목됐다: {out.get('reasons')}")


if __name__ == "__main__":
    unittest.main()
