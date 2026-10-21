"""글꼴·크기 목록에서 원하는 값을 고른다 — 실제 네이버 툴바 모양 그대로(2026-10-21 실측).

예전 코드는 여는 단추와 data-name 이 같은 것을 빼고 항목을 찾았는데, 목록 항목도 같은
data-name 을 달고 있어 목록 전체가 빠졌다. 글꼴이 한 번도 바뀌지 않았다.
"""
import asyncio
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from naver_editor import NaverEditor  # noqa: E402

# 실제 화면에서 읽은 마크업을 줄였다(클래스·data-* 는 그대로).
TOOLBAR = '''
<ul>
 <li class="se-toolbar-item se-toolbar-item-font-family">
  <div class="se-property-toolbar-label-select-container __select-container" data-type="label-select" data-name="font-family">
   <button type="button" class="se-font-family-toolbar-button se-property-toolbar-label-select-button"
     data-group="propertyToolbar" data-type="label-select" data-name="font-family"><span class="se-toolbar-label" data-role="label">마루부리</span><span class="se-toolbar-tooltip">서체 변경</span></button>
   <div class="se-toolbar-option se-toolbar-option-font-family" role="listbox" hidden>
    <button type="button" class="se-toolbar-option-text-button" data-name="font-family" data-role="option" data-value="nanumgothic" data-type="label-select"><span class="se-toolbar-option-label">나눔고딕</span><span class="blind">나눔고딕</span></button>
    <button type="button" class="se-toolbar-option-text-button" data-name="font-family" data-role="option" data-value="nanummyeongjo" data-type="label-select"><span class="se-toolbar-option-label">나눔명조</span><span class="blind">나눔명조</span></button>
    <button type="button" class="se-toolbar-option-text-button se-is-selected" data-name="font-family" data-role="option" data-value="nanummaruburi" data-type="label-select"><span class="se-toolbar-option-label">마루부리</span><span class="blind">선택됨</span></button>
   </div>
  </div>
 </li>
 <li class="se-toolbar-item se-toolbar-item-font-size-code">
  <div class="se-property-toolbar-label-select-container __select-container" data-type="label-select" data-name="font-size-code">
   <button type="button" class="se-font-size-code-toolbar-button se-property-toolbar-label-select-button"
     data-group="propertyToolbar" data-type="label-select" data-name="font-size"><span class="se-toolbar-label" data-role="label">16</span><span class="se-toolbar-tooltip">글자 크기 변경</span></button>
   <div class="se-toolbar-option se-toolbar-option-font-size-code" role="listbox" hidden>
    <button type="button" class="se-toolbar-option-text-button" data-name="font-size" data-role="option" data-value="fs16" data-type="label-select"><span class="se-toolbar-option-label">16</span></button>
    <button type="button" class="se-toolbar-option-text-button" data-name="font-size" data-role="option" data-value="fs19" data-type="label-select"><span class="se-toolbar-option-label">19</span></button>
   </div>
  </div>
 </li>
</ul>
<div class="se-documentTitle"></div>
<script>
 document.querySelectorAll('.se-property-toolbar-label-select-button').forEach(b => b.addEventListener('click', () => {
   b.parentElement.querySelector('[role=listbox]').hidden = false; }));
 document.querySelectorAll('[data-role=option]').forEach(o => o.addEventListener('click', () => {
   const box = o.closest('.__select-container');
   box.querySelector('[data-role=label]').textContent = o.querySelector('.se-toolbar-option-label').textContent;
   box.querySelector('[role=listbox]').hidden = true; }));
</script>
'''


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


@unittest.skipUnless(_browser_available(), 'Playwright Chromium 이 설치되지 않았습니다')
class FontPickerTest(unittest.TestCase):
    def pick(self, control, wanted):
        async def go():
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.set_content(TOOLBAR)
                editor = NaverEditor(page)
                ok = await editor._pick_toolbar_option(control, wanted)
                label = await page.locator(f'button[data-name="{control}"][data-type="label-select"]:not([data-role="option"]) [data-role=label]').text_content()
                await browser.close()
                return ok, label
        return asyncio.run(go())

    def test_font_family_is_picked_by_its_name(self):
        self.assertEqual(self.pick('font-family', '나눔명조'), (True, '나눔명조'))

    def test_font_size_opens_the_size_list(self):
        self.assertEqual(self.pick('font-size', '19'), (True, '19'))

    def test_a_missing_font_reports_failure(self):
        self.assertEqual(self.pick('font-family', '없는글꼴')[0], False)


if __name__ == '__main__':
    unittest.main()
