"""링크 카드 뒤에 뜨는 네이버 '글감 검색창'이 본문 글자를 가로채던 것.

2026-10-23 실물 측정(로그인한 크롬, platonmarketing 글쓰기 화면, 발행 없음).
사진 → 링크 카드 → 문단 순서로 넣는데, 카드 바로 뒤에서 포커스가 **아래쪽 글감 검색
막대**로 넘어가 뒤이어 친 한 문단이 통째로 그 검색칸에 들어갔다.

    보낸 글자 : '일주일에  두세 번  두통약을 먹습니다. …'
    들어간 곳 : 글감 검색칸(화면 아래 '전체 글감 🔍' 막대)
    본문      : 그 문단이 **없다**
    결과      : EditorError: 입력한 강조 문구가 본문에 표시되지 않았습니다

이 창은 **본문 첫 줄을 가리지 않고 크지도 않아서** 기존 선택창 감시('가려졌나',
240x160 이상)에 걸리지 않는다. 그래서 따로 본다(`dismiss_material_search`).

고객이 말한 "17·16·18 버전 모두 항상 같은 곳에서 멈춥니다"가 이 모양이었다 —
창이 그대로 있으니 **다시 쳐도 또 그 칸으로** 들어가 재시도도 같은 자리에서 떨어진다.
"""
from __future__ import annotations

import asyncio
import functools
import re
import sys
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from naver_editor import NaverEditor  # noqa: E402

URL = "https://map.naver.com/p/entry/place/1754941463"
# 카드 뒤에 오는 본문. **한 문단으로 끝나는 길이**여야 한다.
#
# 2026-10-27 에 문단 규격이 25~35자(공백 제외)로 줄면서 이 문장이 두 문단으로 쪼개졌는데,
# 그때 가짜 편집기에서 뒤 문단이 사라졌다. 가짜 편집기는 `contenteditable` 을 `<p>` **자체**에
# 걸어 두기 때문에 엔터가 새 `.se-text-paragraph` 를 만들지 않고 `<p>` 안에 `<div>` 를 쌓는다
# (실제 SE ONE 은 형제 문단을 만든다). 그 구조에서 카드 직후 두 번째 문단이 들어가지 않는다 —
# **대역의 한계이고 실행기 코드와는 무관하다**(카드 없이 세 문단은 멀쩡히 들어간다).
# 그 자리를 억지로 눌러 보면 앞 문단까지 잃는다. 그래서 이 시험은 원래 보려던 것 —
# '카드 뒤 문단을 글감 검색칸에 빼앗기지 않는가' — 에 머물게 하고, 문단이 몇 개로 쪼개지는지는
# test_link_card_keeps_following_paragraphs 가 계획(ops) 단계에서 본다.
AFTER = "일주일에  두세 번  두통약을 먹습니다."


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def _browser_available() -> bool:
    async def probe():
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            try:
                b = await p.chromium.launch(headless=True)
                await b.close()
                return True
            except Exception:  # noqa: BLE001
                return False

    return asyncio.run(probe())


@unittest.skipUnless(_browser_available(), "Playwright Chromium 이 설치되지 않았습니다 (playwright install chromium)")
class TestMaterialSearchStealsTyping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler = functools.partial(_Quiet, directory=str(HERE / "fake_editor"))
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _run(self, blocks):
        from playwright.async_api import async_playwright

        async def go():
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(viewport={"width": 1280, "height": 900})
                try:
                    ed = NaverEditor(page, write_url=f"{self.base}/write.html?matsearch=1")
                    await ed.open_write_page()
                    await ed.dismiss_draft_popup()
                    await ed.insert_body_blocks(blocks, [])
                    frame = await ed.frame()
                    return await frame.evaluate("""() => ({
                      matOpen: !!(window.__state || {}).matOpen,
                      matTyped: (window.__state || {}).matTyped || '',
                      cards: [...document.querySelectorAll('.se-component.se-oglink a')].map(e => e.getAttribute('href')),
                      body: [...document.querySelectorAll('.se-component.se-text .se-text-paragraph')]
                              .map(e => e.innerText.trim()).filter(Boolean),
                    })""")
                finally:
                    await browser.close()

        return asyncio.run(go())

    @staticmethod
    def _flat(rows):
        """화면은 연속 공백을 한 칸으로 합쳐 보여 준다 — 글자가 남았는지만 본다."""
        return re.sub(r'\s+', ' ', ' '.join(rows))

    def test_the_material_bar_is_cleared_the_moment_the_write_page_opens(self):
        """막대는 **뜨고 나서 닫는 것이 아니라 열리기 전에 치운다.**

        2026-10-23 실물 측정: 이 막대는 우리가 여는 창이 아니라 글쓰기 화면 아래에
        처음부터 붙어 있는 것이다(412x44, 화면 맨 아래). 누르면 '전체 글감/책/음악…'
        판으로 펼쳐져 본문을 덮고, 사람이 손으로 닫을 때까지 발행이 거기서 멈춘다
        (고객: "클릭을 해줘야만 정상적으로 예약이 됩니다").
        """
        from playwright.async_api import async_playwright

        async def go():
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(viewport={"width": 1280, "height": 900})
                try:
                    ed = NaverEditor(page, write_url=f"{self.base}/write.html?matsearch=1")
                    await ed.open_write_page()          # 제목도 본문도 아직 건드리지 않았다
                    frame = await ed.frame()
                    return await frame.evaluate(
                        """() => {
                             const all = [...document.querySelectorAll('[class*="se-flayer-unified"]')];
                             return {
                               found: all.length,
                               cleared: all.filter(e => e.getAttribute('data-dv-matbar') === 'hidden').length,
                               reachable: all.filter(e => e.offsetParent !== null).length,
                             };
                           }""")
                finally:
                    await browser.close()

        got = asyncio.run(go())
        self.assertTrue(got["found"], "가짜 편집기에 글감 막대가 없다 — 테스트가 무의미해진다")
        self.assertTrue(got["cleared"], f"글쓰기 화면을 열자마자 글감 막대를 치워야 한다: {got}")
        self.assertEqual(got["reachable"], 0, f"치운 막대가 아직 화면에 남아 있다: {got}")

    def test_link_card_keeps_following_paragraphs(self):
        """카드 뒤 문단이 둘로 쪼개져도 계획에서는 둘 다 살아 있어야 한다(브라우저 없이).

        문단 규격이 25~35자로 줄어 카드 뒤가 여러 문단이 되는 일이 흔해졌다. 계획 단계에서
        빠지면 실제 네이버에서도 글이 빈다 — 대역으로는 못 보는 자리라 여기서 지킨다."""
        import plan

        tail_one = "일주일에 두세 번 두통약을 먹습니다."
        tail_two = "그런데도 통증이 가시지 않으면 다른 원인을 봐야 합니다."
        ops = plan.plan_blocks(
            [{"type": "text", "content": f"오시는 길입니다.\n\n{URL}\n\n{tail_one} {tail_two}"}],
            [], reformat=True)
        kinds = [o.kind for o in ops]
        self.assertEqual(kinds.count("link"), 1, kinds)
        texts = [o.payload for o in ops if o.kind == "text"]
        self.assertEqual(texts, ["오시는 길입니다.", tail_one, tail_two], texts)
        # 카드는 제 뒤에 빈 문단을 하나 남긴다 — 그래서 뒤따르는 줄바꿈은 둘이어야 한다
        # (하나는 편집기가 삼키고 하나가 실제로 쓰인다). insert_body_blocks 의 carded 참고.
        self.assertEqual(kinds[kinds.index("link") + 1:kinds.index("link") + 3], ["enter", "enter"], kinds)

    def test_plain_manuscript_keeps_the_paragraph_after_a_card(self):
        """평문 원고: 카드 뒤 문단이 본문에 남아야 한다(검색칸으로 새면 안 된다)."""
        got = self._run([{"type": "text", "content": f"오시는 길입니다.\n\n{URL}\n\n{AFTER}"}])
        self.assertEqual(got["cards"], [URL], got)
        self.assertIn(self._flat([AFTER]), self._flat(got["body"]), f"카드 뒤 문단을 글감 검색칸에 빼앗겼다: {got}")
        self.assertFalse(got["matOpen"], "글감 검색창을 닫지 않았다")

    def test_formatted_manuscript_keeps_the_paragraph_after_a_card(self):
        """서식 원고(워드에서 온 글): 같은 자리에서 멈추지 않고 문단이 그대로 들어가야 한다."""
        got = self._run([
            {"type": "text", "spans": [{"t": "오시는 길입니다.", "b": True}]},
            {"type": "text", "content": URL},
            {"type": "text", "spans": [{"t": AFTER}]},
        ])
        self.assertEqual(got["cards"], [URL], got)
        self.assertIn(self._flat([AFTER]), self._flat(got["body"]), f"카드 뒤 문단을 글감 검색칸에 빼앗겼다: {got}")
        self.assertFalse(got["matOpen"], "글감 검색창을 닫지 않았다")


if __name__ == "__main__":
    unittest.main(verbosity=2)
