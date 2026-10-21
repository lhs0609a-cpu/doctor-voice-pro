"""툴바 단추로 서식이 들어갔는지 모를 때는 다시 누르지 않고, 서식을 입혀 붙여 넣는다.

2026-10-21 위례 원고: 링크 카드 뒤에 글감 창이 떴다 닫힌 자리에서 기울임을 끄려고 Ctrl+I 를
눌렀는데 단추 모양이 바뀌지 않았다. 그 상태로 글자를 넣었더니 기울임이 그대로 들어가
"기울임을(를) 빼 달라고 했는데 편집기에는 그렇게 들어가지 않았습니다"로 글 한 건이 떨어졌다.
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
    def __init__(self, buttons):
        self.buttons = buttons

    def locator(self, selector):
        for name, button in self.buttons.items():
            if selector == f'button[data-name="{name}"]':
                return button
        if 'input_buffer' in selector:
            return mock.Mock(evaluate=mock.AsyncMock())
        return Indicator()

    async def evaluate(self, script, text):
        return [{'quote': False, 'bold': False, 'italic': False, 'underline': False,
                 'color': 'rgb(0, 0, 0)', 'background': 'rgba(0, 0, 0, 0)'}]


class Keyboard:
    def __init__(self):
        self.pressed = []

    async def press(self, key):
        self.pressed.append(key)


class Editor:
    def __init__(self, frame):
        self._frame = frame
        self.page = mock.Mock()
        self.page.keyboard = Keyboard()
        self.typed = []

    async def frame(self):
        return self._frame

    async def scan_blocking_layers(self):
        return []

    async def _insert(self, text):
        self.typed.append(text)


class UnsureToggleTest(unittest.IsolatedAsyncioTestCase):
    async def test_a_toggle_that_does_not_show_is_not_pressed_twice(self):
        # 기울임 단추가 켜져 있는데(남아 있던 상태) 끄라고 했다. 단축키는 눌러도 단추가 그대로다.
        frame = Frame({'bold': Button(False), 'italic': Button(True), 'underline': Button(False)})
        editor = Editor(frame)
        pasted = []

        @contextlib.contextmanager
        def fake_clipboard(fragment, text):
            pasted.append(fragment)
            yield

        with mock.patch.object(rich_editor.sys, 'platform', 'win32'), \
                mock.patch.dict(sys.modules, {'html_clipboard': mock.Mock(temporary_html=fake_clipboard)}), \
                mock.patch.object(rich_editor.asyncio, 'sleep', mock.AsyncMock()):
            await rich_editor.styled_text(editor, '일주일에 두세 번 두통약을 먹습니다', {})

        self.assertEqual(editor.page.keyboard.pressed.count('Control+i'), 1)   # 거꾸로 되돌리지 않는다
        self.assertEqual(editor.typed, [])                                      # 그 상태로 치지 않는다
        self.assertEqual(len(pasted), 1)
        self.assertIn('font-style:normal', pasted[0])                          # 서식을 글자에 직접 입힌다


if __name__ == '__main__':
    unittest.main()
