"""고칠 글자를 고를 때 몇 글자를 세는가 — **네이버 실물 기준**.

2026-10-22 실물 측정(글쓰기 화면, 로그인한 프로필). 네이버 편집기에서 ← 는 **원래 글자
하나씩** 움직인다. 워드 원고의 연속 공백도 **각각 캐럿 자리를 차지한다** — 편집기가
공백을 살려 두기 때문이다.

    보낸 것        '앞문구' + '일주일에  두세 번  두통약을 먹습니다'(21자)
    19번 ← 로 고침 ['앞문구일주'=기울임]['일에  두세 번  두통약을 먹습니다'=보통]
                   ← '일주' 두 자를 놓쳐 앞쪽만 기울임이 남았다
    21번 ← 로 고침 ['앞문구'=기울임]['일주일에 … 먹습니다'=보통]   ← 정확

**합성 contenteditable 로 재면 반대 결론이 난다**(거기서는 연속 공백이 합쳐져 캐럿이
건너뛴다). 한때 '보이는 글자 수'로 세게 고쳤다가 실물에서 되돌렸다(1.7.13 → 1.7.18).
여기서는 TAIL_LEN 이 **화면에 찍힌 그대로의 글자 수**를 돌려주는지만 본다.

    python test_tail_len.py
브라우저가 없으면 건너뛴다.
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

    def counted(self, text):
        """TAIL_LEN 이 센 글자 수. 고르기 결과는 합성 화면 기준이라 보지 않는다."""
        counted, _ = asyncio.run(select_back(text))
        return counted

    def test_a_plain_sentence_counts_as_it_was_sent(self):
        self.assertEqual(self.counted('보통 문장입니다'), len('보통 문장입니다'))

    def test_double_spaces_still_count_one_each(self):
        """네이버는 연속 공백을 살려 두고 ← 가 하나씩 지난다 — 합쳐 세면 앞 글자를 놓친다."""
        text = '일주일에  두세 번  두통약을 먹습니다'
        self.assertEqual(self.counted(text), 21)
        self.assertEqual(len(text), 21)

    def test_a_trailing_space_is_counted_even_when_it_became_nbsp(self):
        self.assertEqual(self.counted('줄 끝 공백 '), len('줄 끝 공백 '))


if __name__ == '__main__':
    unittest.main()


if __name__ == '__main__':
    unittest.main()
