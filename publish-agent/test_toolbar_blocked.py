"""네이버 선택창이 툴바를 덮었을 때, 글 하나를 통째로 버리지 않는다.

2026-10-20 고객 신고(위례 원고): '손봐야 할 글 5건'이 전부 같은 줄로 실패했다 —
`TimeoutError: Timeout 15000ms exceeded ... button[data-name="font-color"]`.
단추를 찾기는 했는데 **눌리지 않는다**. 글감 선택창이 툴바를 덮고 있으면 이렇게 되고,
사진·링크 카드 바로 뒤처럼 색 툴바가 아예 없는 자리에서도 그렇다.
색은 모양일 뿐인데 그것 때문에 원고가 통째로 떨어지면 안 된다.
"""
import unittest
from types import SimpleNamespace

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


class FakeToolbarItem:
    """꺼져 있는 서식 단추 / 없는 색 표시칸."""

    async def count(self):
        return 0

    async def get_attribute(self, name, timeout=None):
        return ''


class FakeFrame:
    """편집기에서 읽어 오는 것만 흉내 낸다 — 본문 길이와 읽어 본 서식."""

    def __init__(self, visible_from=99, style=None):
        self.reads = 0
        self.visible_from = visible_from
        self.style = style or {'quote': False, 'bold': False, 'italic': False,
                               'underline': False, 'color': 'rgb(0, 0, 0)',
                               'background': 'rgb(255, 255, 255)'}

    def locator(self, selector):
        return FakeToolbarItem()

    async def evaluate(self, script, arg=None):
        if 'reduce' in script:          # BODY_LEN
            return 0
        if 'indexOf' in script:         # CARET_AT
            return -1
        self.reads += 1
        return [dict(self.style)] if self.reads >= self.visible_from else None


class TypedTextEditor(FakeEditor):
    """글자를 받아 두는 가짜 편집기."""

    def __init__(self, frame, layers=()):
        super().__init__(layers)
        self._frame = frame
        self.typed = []
        self.pressed = []
        self.timeline = []          # 친 글자와 누른 키를 **순서대로**
        self.page = SimpleNamespace(keyboard=SimpleNamespace(
            press=self._press, down=self._noop, up=self._noop))

    async def _noop(self, *a, **k):
        return None

    async def _press(self, key):
        self.pressed.append(key)
        self.timeline.append(('key', key))

    async def frame(self):
        return self._frame

    async def _insert(self, text):
        self.typed.append(text)
        self.timeline.append(('text', text))

    async def _refocus_body_end(self):
        return None


class KeepGoingTests(unittest.IsolatedAsyncioTestCase):
    """서식이 어긋나도 글은 올린다 — 2026-10-22 요청.

    "오류 뜨는 부분은 넘어가면서 예약발행 / 임시저장 되게 해주실 수 있을까요?? 오류 뜬 부분은
    저희가 수기로 고쳐서 바로 발행 걸겠습니다! (지금은 오류가 뜨면 이제까지 작업한 것들이
    아예 삭제되어버리네요..!)"
    """

    async def test_a_wrong_italic_is_written_down_instead_of_throwing_the_post_away(self):
        from rich_editor import styled_text

        italic = {'quote': False, 'bold': False, 'italic': True, 'underline': False,
                  'color': 'rgb(0, 0, 0)', 'background': 'rgb(255, 255, 255)'}
        frame = FakeFrame(visible_from=1, style=italic)       # 편집기는 기울임으로 그렸는데
        editor = TypedTextEditor(frame)
        await styled_text(editor, '일주일에 두세 번 두통약을 먹습니다', {})   # 요청은 기울임 없음
        notes = getattr(editor, 'format_notes', [])
        self.assertTrue(notes, '글은 올리되 손볼 자리는 남겨야 한다')
        self.assertIn('기울임', notes[0])

    async def test_the_published_result_says_what_to_fix_by_hand(self):
        from agent import with_format_notes

        editor = SimpleNamespace(format_notes=['"두통약" — 기울임을(를) 빼 달라고 했는데'])
        message = with_format_notes(editor, '예약 등록됨')
        self.assertIn('예약 등록됨', message)
        self.assertIn('서식 1곳', message)
        self.assertIn('직접 고쳐', message)

    async def test_a_clean_post_says_nothing_extra(self):
        from agent import with_format_notes

        self.assertEqual(with_format_notes(SimpleNamespace(), '예약 등록됨'), '예약 등록됨')


class UnreadableToolbarTests(unittest.IsolatedAsyncioTestCase):
    """단추를 못 읽는다고 원고를 버리지 않는다 (2026-10-22 위례:
    "네이버 편집기에서 '굵게' 단추를 제때 누르지 못했습니다")."""

    async def test_an_unreadable_button_reads_as_unknown_not_an_error(self):
        from rich_editor import toggled

        class Gone:
            async def get_attribute(self, name, timeout=None):
                raise RuntimeError(f'Timeout {timeout}ms exceeded. waiting for locator("button")')

        self.assertIsNone(await toggled(Gone()))

    async def test_an_unknown_button_is_not_pressed_blindly(self):
        from rich_editor import styled_text

        class UnreadableFrame(FakeFrame):
            def locator(self, selector):
                if 'data-name="bold"' in selector:
                    class Gone:
                        async def get_attribute(self, name, timeout=None):
                            raise RuntimeError('Timeout')
                    return Gone()
                return FakeToolbarItem()

        frame = UnreadableFrame(visible_from=1)
        editor = TypedTextEditor(frame)
        await styled_text(editor, '여름에도 손발이 시리다면', {'b': True})
        # 글자부터 친다 — 상태를 모르는 채 단축키를 먼저 누르면 서식이 거꾸로 들어간다.
        self.assertEqual(editor.timeline[0], ('text', '여름에도 손발이 시리다면'))
        self.assertTrue(getattr(editor, 'format_notes', []), '못 고치면 적어 두고 글은 올린다')
