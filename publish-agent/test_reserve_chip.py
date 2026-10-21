"""'예약 발행 N건'은 네이버가 다 채운 뒤에 읽는다(2026-10-21 실측).

글쓰기 화면을 연 직후에는 예약이 2건 있어도 0.6초쯤 '0건'으로 그려졌다가 바뀐다. 그 0 을 읽어
서버에 '예약 0건'이라고 알렸다 — 서버는 이미 걸린 시각에 또 예약을 잡을 수 있었다.
"""
import asyncio
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import naver_editor  # noqa: E402
from naver_editor import NaverEditor  # noqa: E402


class LateChip:
    """처음 몇 번은 0건, 그 뒤로는 진짜 건수를 보여 주는 화면."""

    def __init__(self, real: int, zeros: int):
        self.real, self.zeros, self.reads = real, zeros, 0

    async def evaluate(self, script, *args):
        if script == naver_editor.JS_RESERVE_CHIP:
            self.reads += 1
            return {'found': True, 'count': 0 if self.reads <= self.zeros else self.real}
        raise AssertionError(script[:40])


class ReserveChipTest(unittest.TestCase):
    def read(self, scope, wait=1.0):
        editor = NaverEditor.__new__(NaverEditor)
        return asyncio.run(editor._settled_reserve_chip(scope, wait_sec=wait))

    def test_the_zero_drawn_before_naver_fills_the_count_is_not_believed(self):
        self.assertEqual(self.read(LateChip(real=2, zeros=3))['count'], 2)

    def test_a_real_zero_is_still_zero(self):
        scope = LateChip(real=0, zeros=0)
        self.assertEqual(self.read(scope, wait=0.6)['count'], 0)
        self.assertGreater(scope.reads, 1, '한 번 보고 0 이라 하지 않는다')


if __name__ == '__main__':
    unittest.main()
