"""글을 올리기 전에 '방금 넣은 문구의 서식'을 다시 읽는 자바스크립트(rich_editor.READ_BACK).

여기서 지키는 약속 둘.
1) 검사하는 글자는 **방금 넣은 그 문구**다. 편집기가 연속 공백을 한 칸으로 합쳐도, 바로 앞
   문구(굵게)의 서식까지 끌어다 보지 않는다. 예전에는 '문단 길이 - 글자 수'로 자리를 잡아서
   공백이 합쳐진 만큼 범위가 앞으로 밀렸다 — 멀쩡한 원고가 '서식이 요청과 다릅니다'로
   한 건도 못 나갔다(2026-10-02 사용자 신고: 손봐야 할 글 3건).
2) 템플릿을 불러온 글처럼 **아래에 남아 있는 문단**이 같은 말로 끝나도, 캐럿이 있는 문단을
   읽는다.

    python test_read_back.py
브라우저가 없으면 통째로 건너뛴다(계산이 아니라 실제 렌더링 결과를 보는 테스트라서).
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from rich_editor import READ_BACK  # noqa: E402


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

    try:
        return asyncio.run(probe())
    except Exception:  # noqa: BLE001
        return False


# 네이버 본문 한 문단의 모양. 굵은 조각 뒤에 일반 조각이 붙어 있다.
def page(body: str) -> str:
    return f"<!doctype html><meta charset='utf-8'><body>{body}</body>"


def paragraph(*runs: str) -> str:
    return ("<div class='se-component se-text'><div class='se-text-paragraph'>"
            + "".join(runs) + "</div></div>")


BOLD = "<span style='font-weight:700'>핵심은 성장판입니다.</span>"


@unittest.skipUnless(_browser_available(), "Playwright Chromium 이 설치되지 않았습니다 (playwright install chromium)")
class ReadBackTests(unittest.TestCase):
    def read(self, body: str, text: str):
        async def run():
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                try:
                    tab = await browser.new_page()
                    await tab.set_content(page(body))
                    return await tab.evaluate(READ_BACK, text)
                finally:
                    await browser.close()

        return asyncio.run(run())

    def test_collapsed_spaces_do_not_drag_in_the_previous_run(self):
        """HTML 로 붙여 넣은 연속 공백은 한 칸으로 합쳐진다 — 그만큼 범위가 밀리면 안 된다.

        보낸 글자는 '  검사는 10분이면 끝납니다.'(앞 공백 둘)인데 화면에는 한 칸으로 줄어
        들어간다. 예전 계산('문단 길이 - 글자 수')이면 앞의 굵은 조각까지 검사 대상이 되어
        '굵게를 빼 달라고 했는데 그렇게 들어가지 않았습니다'로 글 전체가 막혔다."""
        got = self.read(paragraph(BOLD, "<span> 검사는 10분이면 끝납니다.</span>"),
                        "  검사는 10분이면 끝납니다.")
        self.assertEqual([s["bold"] for s in got], [False], got)

    def test_the_run_itself_is_still_read(self):
        got = self.read(paragraph("<span>앞 문장입니다.</span>", BOLD), "핵심은 성장판입니다.")
        self.assertEqual([s["bold"] for s in got], [True], got)

    def test_a_template_line_below_does_not_hijack_the_check(self):
        """템플릿을 불러온 글에서는 쓰는 자리 **아래로** 템플릿 문단이 남는다.

        그 문단이 같은 말로 끝나면, 문서를 뒤에서부터 훑던 예전 방식은 엉뚱한 줄(병원 정보)의
        서식을 읽었다. 캐럿이 있는 문단을 먼저 본다."""
        body = (paragraph("<span id='here'>오시는 길 안내드립니다.</span>")
                + paragraph(BOLD, "<span style='font-style:italic'>오시는 길 안내드립니다.</span>"))

        async def run():
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                try:
                    tab = await browser.new_page()
                    await tab.set_content(page(body))
                    await tab.evaluate("""() => {
                      const node = document.getElementById('here').firstChild;
                      const range = document.createRange();
                      range.setStart(node, node.length); range.collapse(true);
                      const sel = getSelection(); sel.removeAllRanges(); sel.addRange(range);
                    }""")
                    return await tab.evaluate(READ_BACK, "오시는 길 안내드립니다.")
                finally:
                    await browser.close()

        got = asyncio.run(run())
        self.assertEqual([s["italic"] for s in got], [False], got)   # 아래 템플릿 줄이 아니다

    def test_text_that_is_nowhere_reads_as_missing(self):
        self.assertIsNone(self.read(paragraph("<span>다른 문장</span>"), "없는 문구"))


if __name__ == "__main__":
    unittest.main()
