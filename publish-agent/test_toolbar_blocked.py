"""네이버 선택창이 툴바를 덮었을 때, 글 하나를 통째로 버리지 않는다.

2026-10-20 고객 신고(위례 원고): '손봐야 할 글 5건'이 전부 같은 줄로 실패했다 —
`TimeoutError: Timeout 15000ms exceeded ... button[data-name="font-color"]`.
단추를 찾기는 했는데 **눌리지 않는다**. 글감 선택창이 툴바를 덮고 있으면 이렇게 되고,
사진·링크 카드 바로 뒤처럼 색 툴바가 아예 없는 자리에서도 그렇다.
색은 모양일 뿐인데 그것 때문에 원고가 통째로 떨어지면 안 된다.
"""
import unittest

from rich_editor import blocked, press_toolbar, unblock


class FakeButton:
    """처음 몇 번은 안 눌리는 단추(= 무언가가 덮고 있다)."""

    def __init__(self, fails=0, klass=''):
        self.fails = fails
        self.klass = klass
        self.clicks = 0
        self.timeouts = []

    async def click(self, timeout=None):
        self.clicks += 1
        self.timeouts.append(timeout)
        if self.clicks <= self.fails:
            raise RuntimeError('Timeout 4000ms exceeded.\nCall log: - waiting for locator(...)')

    async def get_attribute(self, name):
        return self.klass


class FakeEditor:
    def __init__(self, layers=()):
        self.layers = [{'name': name} for name in layers]
        self.cleared = []

    async def scan_blocking_layers(self):
        return list(self.layers)

    async def clear_blocking_layers(self, where=''):
        self.cleared.append(where)
        self.layers = []
        return True


class BarEditor:
    """선택창을 볼 줄 모르는 편집기(테스트용 가짜 편집기가 이렇다)."""


class ToolbarPressTests(unittest.IsolatedAsyncioTestCase):
    async def test_a_covered_button_is_pressed_again_after_the_layer_is_cleared(self):
        editor, button = FakeEditor(['전체 글감']), FakeButton(fails=1)
        self.assertTrue(await press_toolbar(editor, button, '글자색 변경'))
        self.assertEqual(editor.cleared, ['글자색 변경'], '창을 치우고 다시 눌러야 한다')
        self.assertEqual(button.clicks, 2)

    async def test_it_gives_up_quickly_instead_of_waiting_fifteen_seconds(self):
        """빨리 포기해야 색을 붙여넣기로 대신 넣을 시간이 남는다."""
        editor, button = FakeEditor(['전체 글감']), FakeButton(fails=9)
        self.assertFalse(await press_toolbar(editor, button, '글자색 변경'))
        self.assertEqual(button.clicks, 2, '두 번만 해 보고 넘어간다')
        self.assertTrue(all(t and t <= 8000 for t in button.timeouts), button.timeouts)

    async def test_a_button_that_presses_normally_is_left_alone(self):
        editor, button = FakeEditor(), FakeButton()
        self.assertTrue(await press_toolbar(editor, button, '글자색 변경'))
        self.assertEqual(editor.cleared, [], '멀쩡할 때는 화면에 손대지 않는다')

    async def test_an_editor_that_cannot_see_layers_still_works(self):
        editor, button = BarEditor(), FakeButton(fails=1)
        self.assertTrue(await press_toolbar(editor, button, '글자색 변경'))
        self.assertFalse(await blocked(editor))
        self.assertFalse(await unblock(editor, '어디든'))


class PlainReasonTests(unittest.TestCase):
    """'손봐야 할 글'에 뜨는 이유는 사람이 읽을 수 있어야 한다."""

    REAL = ('Timeout 15000ms exceeded.\nCall log:\n  - waiting for '
            'locator("button[data-name=\\"font-color\\"]")\n'
            '  - locator resolved to <button title="" type="button" data-log="prt.color" ...')

    def test_a_browser_timeout_becomes_a_sentence_with_what_to_do(self):
        from agent import plain_reason

        class TimeoutError_(Exception):
            pass
        TimeoutError_.__name__ = 'TimeoutError'
        reason = plain_reason(TimeoutError_(self.REAL))
        self.assertIn('글자색', reason)
        self.assertIn('다시 시도', reason)
        self.assertNotIn('locator', reason)
        self.assertNotIn('Call log', reason)

    def test_an_unknown_error_keeps_its_text(self):
        from agent import plain_reason

        self.assertEqual(plain_reason(ValueError('잘못된 강조 색상입니다')),
                         'ValueError: 잘못된 강조 색상입니다')


if __name__ == '__main__':
    unittest.main()
