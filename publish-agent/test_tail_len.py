"""고칠 글자를 고를 때 **보이는 글자 수**로 센다 — 실제 브라우저로 잰다.

2026-10-22 실측. 워드 원고에 흔한 연속 공백이 편집기에서 한 칸으로 합쳐지면, 보낸 글자
수(len(text))만큼 뒤로 고를 때 그 차이만큼 **앞 문구까지** 골라진다:

    보낸 것   '일주일에  두세 번  두통약을 먹습니다'   (21자)
    골라진 것 '문구일주일에 두세 번 두통약을 먹습니다'  ← 앞 문구의 '문구' 가 딸려 왔다

그 상태로 Ctrl+I 를 누르면 앞 문구의 기울임까지 함께 뒤집혀, 고치려던 문구가 되레 기울어
나온다 — 위례·kibundang 의 "기울임을(를) 빼 달라고 했는데 편집기에는 그렇게 들어가지
않았습니다" 가 이것이다.

    python test_tail_len.py
브라우저가 없으면 건너뛴다(계산이 아니라 실제 캐럿 움직임을 보는 테스트라서).
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from rich_editor import TAIL_LEN  # noqa: E402

PAGE = ("data:text/html,<meta charset=utf-8>"
        "<div class='se-component se-text'><div class='se-text-paragraph' id=a contenteditable "
        "style=\"font:16px sans-serif\"><span style='font-style:italic'>앞 문구</span></div></div>")


def browser_available() -> bool:
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


async def select_back(text):
    """글자를 친 뒤 TAIL_LEN 이 센 만큼 뒤로 골라, 무엇이 골라졌는지 돌려준다."""
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(PAGE)
        await page.click('#a')
        await page.keyboard.press('End')
        await page.keyboard.insert_text(text)
        counted = await page.evaluate(TAIL_LEN, text)
        await page.keyboard.down('Shift')
        for _ in range(counted or len(text)):
            await page.keyboard.press('ArrowLeft')
        await page.keyboard.up('Shift')
        picked = await page.evaluate("() => String(document.getSelection())")
        await browser.close()
        return counted, picked


@unittest.skipUnless(browser_available(), 'Chromium 이 없으면 건너뜀')
class TailLengthTests(unittest.TestCase):
    def picks_exactly(self, text):
        counted, picked = asyncio.run(select_back(text))
        self.assertEqual(picked.replace('\xa0', ' ').strip(), ' '.join(text.split()),
                         f'{text!r} 를 고르려다 {picked!r} 가 골라졌다(센 글자 {counted})')
        return counted

    def test_a_plain_sentence_is_picked_as_it_is(self):
        self.assertEqual(self.picks_exactly('보통 문장입니다'), 8)

    def test_collapsed_double_spaces_do_not_eat_into_the_previous_run(self):
        """워드 원고의 연속 공백 — 고치지 않으면 앞 문구를 건드린다."""
        text = '일주일에  두세 번  두통약을 먹습니다'
        self.assertEqual(self.picks_exactly(text), 19)      # 보낸 21자, 화면 19자
        self.assertEqual(len(text), 21)

    def test_a_trailing_space_becomes_one_caret_stop(self):
        self.assertEqual(self.picks_exactly('줄 끝 공백 '), 7)   # nbsp 는 한 자리다


if __name__ == '__main__':
    unittest.main()
