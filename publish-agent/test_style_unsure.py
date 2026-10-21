"""툴바 단추로 서식이 들어갔는지 모를 때는 다시 누르지 않고, 친 뒤 읽어 보고 틀린 글자만 골라 고친다.

2026-10-21 위례 원고: 링크 카드 뒤에 글감 창이 떴다 닫힌 자리에서 기울임을 끄려고 Ctrl+I 를
눌렀는데 단추 모양이 바뀌지 않았다. 그 상태로 글자를 넣었더니 기울임이 그대로 들어가
"기울임을(를) 빼 달라고 했는데 편집기에는 그렇게 들어가지 않았습니다"로 글 한 건이 떨어졌다.
1.7.8 은 그 자리에서 서식을 입혀 붙여 넣었는데, 붙여넣기가 본문에 들어가지 않아
"입력한 강조 문구가 본문에 표시되지 않았습니다"로 또 떨어졌다(kibundang).
"""
import contextlib
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import rich_editor  # noqa: E402


class Button:
    def __init__(self, on):
        self.on = on

    async def get_attribute(self, name):
        return 'se-is-selected' if self.on else ''


class Indicator:
    async def count(self):
        return 0          # 색 툴바가 없는 자리(카드 바로 뒤)


class Frame:
    def __init__(self, buttons, italic=False, landed=True):
        self.buttons = buttons
        self.italic = italic      # 본문에 들어간 글자가 실제로 기울어져 있나
        self.landed = landed      # 붙여넣기가 본문에 들어갔나
        self.text = None

    def locator(self, selector):
        for name, button in self.buttons.items():
            if selector == f'button[data-name="{name}"]':
                return button
        if 'input_buffer' in selector:
            return mock.Mock(evaluate=mock.AsyncMock())
        return Indicator()

    async def evaluate(self, script, text):
        if script is rich_editor.IN_BODY:
            return False
        if self.text != text:
            return None
        return [{'quote': False, 'bold': False, 'italic': self.italic, 'underline': False,
                 'color': 'rgb(0, 0, 0)', 'background': 'rgba(0, 0, 0, 0)'}]


class Keyboard:
    def __init__(self, frame):
        self.pressed = []
        self.frame = frame

    async def press(self, key):
        self.pressed.append(key)
        # 글자를 고른 채로 Ctrl+I 를 누르면 그 글자의 기울임이 뒤집힌다.
        if key == 'Control+i' and self.pressed[-2:-1] == ['Shift+ArrowLeft']:
            self.frame.italic = not self.frame.italic
        if key == 'Control+v' and self.frame.landed:
            self.frame.text = self.frame.pasting


class Editor:
    def __init__(self, frame):
        self._frame = frame
        self.page = mock.Mock()
        self.page.keyboard = Keyboard(frame)
        self.typed = []

    async def frame(self):
        return self._frame

    async def scan_blocking_layers(self):
        return []

    async def _insert(self, text):
        self.typed.append(text)
        self._frame.text = text


def fake_clipboard(frame, pasted):
    @contextlib.contextmanager
    def temporary_html(fragment, text):
        pasted.append(fragment)
        frame.pasting = text
        yield
    return temporary_html


class UnsureToggleTest(unittest.IsolatedAsyncioTestCase):
    async def run_styled(self, editor, frame, text, attrs, pasted):
        with mock.patch.object(rich_editor.sys, 'platform', 'win32'),                 mock.patch.dict(sys.modules, {'html_clipboard': mock.Mock(temporary_html=fake_clipboard(frame, pasted))}),                 mock.patch.object(rich_editor.asyncio, 'sleep', mock.AsyncMock()):
            await rich_editor.styled_text(editor, text, attrs)

    async def test_a_toggle_that_does_not_show_is_fixed_on_the_typed_text(self):
        # 기울임 단추가 켜져 있는데(남아 있던 상태) 끄라고 했다. 단축키는 눌러도 단추가 그대로고,
        # 친 글자는 실제로 기울어져 들어갔다.
        frame = Frame({'bold': Button(False), 'italic': Button(True), 'underline': Button(False)}, italic=True)
        editor = Editor(frame)
        pasted = []
        text = '일주일에 두세 번 두통약을 먹습니다'
        await self.run_styled(editor, frame, text, {}, pasted)

        pressed = editor.page.keyboard.pressed
        self.assertEqual(pasted, [])                              # 붙여 넣지 않는다
        self.assertEqual(editor.typed, [text])                    # 그대로 친다
        self.assertEqual(pressed.count('Shift+ArrowLeft'), len(text))   # 친 글자만 고른다
        self.assertEqual(pressed.count('Control+i'), 2)           # 처음 한 번 + 고른 글자에 한 번
        self.assertFalse(frame.italic)

    async def test_typed_text_that_came_out_right_is_left_alone(self):
        frame = Frame({'bold': Button(False), 'italic': Button(True), 'underline': Button(False)}, italic=False)
        editor = Editor(frame)
        await self.run_styled(editor, frame, '그대로 둡니다', {}, [])
        self.assertNotIn('Shift+ArrowLeft', editor.page.keyboard.pressed)

    async def test_a_paste_that_does_not_land_is_typed(self):
        # 색 툴바가 없는 자리라 붙여 넣었는데, 붙여넣기가 본문에 들어가지 않았다.
        frame = Frame({'bold': Button(False), 'italic': Button(False), 'underline': Button(False)}, landed=False)
        editor = Editor(frame)
        pasted = []
        await self.run_styled(editor, frame, '빨간 문구', {'color': '#ff0000'}, pasted)
        self.assertEqual(len(pasted), 1)
        self.assertEqual(editor.typed, ['빨간 문구'])             # 색 없이라도 글은 들어간다

    async def test_a_paste_that_lands_is_not_typed_again(self):
        frame = Frame({'bold': Button(False), 'italic': Button(False), 'underline': Button(False)}, landed=True)
        editor = Editor(frame)
        pasted = []
        with self.assertRaises(Exception):      # 가짜 편집기는 색을 안 입히므로 색 확인에서 걸린다
            await self.run_styled(editor, frame, '빨간 문구', {'color': '#ff0000'}, pasted)
        self.assertEqual(editor.typed, [])


if __name__ == '__main__':
    unittest.main()
