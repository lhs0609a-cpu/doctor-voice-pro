"""검색 결과를 초안이 참고한다 — 다만 생성을 절대 붙잡지 않는다.

LLM 심사 20점 중 originality(-2.7)와 intent(-1.6)는 재료 없이 안 움직인다.
serp_research_service 는 경쟁사 목차·콘텐츠 갭·실제 질문을 이미 계산해 두고도
어느 생성기에도 붙어 있지 않았다(2026-09-25).
"""
import asyncio
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services import research_context

RESEARCH = {
    "common_topics": [{"topic": "무릎 연골 구조"}, {"topic": "찜질 방법"}],
    "content_gaps": [{"topic": "계단 내려갈 때만 아픈 이유"}],
    "questions": [{"question": "무릎에서 소리가 나면 병원 가야 하나요"}],
}


class BlockShape(unittest.TestCase):
    def test_all_three_kinds_reach_the_writer(self):
        block = research_context.build_block(RESEARCH)
        self.assertIn("무릎 연골 구조", block)
        self.assertIn("계단 내려갈 때만 아픈 이유", block)
        self.assertIn("무릎에서 소리가 나면 병원 가야 하나요", block)

    def test_it_says_this_is_not_a_source_of_facts(self):
        """참고자료를 근거로 착각하면 없는 사실을 지어낸다 — 채점기가 허위 인용을 감점한다."""
        block = research_context.build_block(RESEARCH)
        self.assertIn("사실이나 출처로 쓰지 않는다", block)
        self.assertIn("만들지 않는다", block)

    def test_nothing_useful_means_no_block_at_all(self):
        self.assertEqual(research_context.build_block({}), "")
        self.assertEqual(research_context.build_block(None), "")
        self.assertEqual(research_context.build_block({"questions": []}), "")


class NeverBlocksGeneration(unittest.TestCase):
    def setUp(self):
        research_context._cache.clear()

    def test_a_slow_search_is_abandoned_not_waited_for(self):
        async def crawl(*a, **k):
            await asyncio.sleep(30)

        with patch.object(research_context, "TIME_BUDGET", 0.05), \
             patch("app.services.serp_research_service.research_keyword", crawl):
            started = time.monotonic()
            out = asyncio.run(research_context.for_keyword("무릎통증"))
        self.assertEqual(out, "")
        self.assertLess(time.monotonic() - started, 5)

    def test_a_broken_search_does_not_break_the_post(self):
        async def boom(*a, **k):
            raise RuntimeError("네이버가 막았습니다")

        with patch("app.services.serp_research_service.research_keyword", boom):
            self.assertEqual(asyncio.run(research_context.for_keyword("무릎통증")), "")

    def test_no_keyword_means_no_search(self):
        called = []

        async def spy(*a, **k):
            called.append(1)
            return RESEARCH

        with patch("app.services.serp_research_service.research_keyword", spy):
            self.assertEqual(asyncio.run(research_context.for_keyword("")), "")
        self.assertEqual(called, [])

    def test_the_same_keyword_is_not_crawled_twice(self):
        """크롤이라 느리고 남의 서버를 두드린다."""
        calls = []

        async def spy(*a, **k):
            calls.append(1)
            return RESEARCH

        with patch("app.services.serp_research_service.research_keyword", spy):
            first = asyncio.run(research_context.for_keyword("무릎통증"))
            second = asyncio.run(research_context.for_keyword("무릎통증"))
        self.assertEqual(len(calls), 1)
        self.assertEqual(first, second)
        self.assertIn("무릎 연골 구조", first)


if __name__ == "__main__":
    unittest.main()
