"""읽어서 확인하지 못했다고 다 쓴 원고를 버리지 않는다 — 본문 글자 수로 갈라 본다.

2026-10-25 실측: 10월에 취소된 112건 가운데 17건이
'입력한 강조 문구가 본문에 표시되지 않았습니다'였다. 그런데 네이버 편집기는 **읽기가
믿을 만하지 않다**(getSelection 은 늘 비어 있고, 합성 화면·이모지 줄에서 방금 친 글자를
그대로 돌려주지 않는 날이 있다). '못 읽었다'를 '안 들어갔다'로 보고 글을 통째로 버린 것이다.

이제 본문 글자 수가 넣은 만큼 늘었으면 **들어간 것**으로 보고 적어만 둔다.
정말로 글자가 빠졌을 때(이모지 줄처럼 한 글자만 남는 경우)는 그대로 막는다.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import rich_editor  # noqa: E402
from naver_editor import EditorError  # noqa: E402


class Indicator:
    async def count(self):
        return 0                      # 색 툴바가 없는 자리


class Button:
    async def get_attribute(self, name, timeout=None):
        return ''                     # 단추는 모두 꺼져 있다


class Frame:
    """읽기는 늘 실패하고, 본문 길이만 '실제로 들어간 만큼' 늘어나는 편집기."""

    def __init__(self, lands: int):
        self.lands = lands            # _insert 때 본문에 실제로 남는 글자 수
        self.body_len = 0

    def locator(self, selector):
        # 색 표시기는 'button[data-name="font-color"] [data-role="color"]' 꼴이다 — 단추가 아니다.
        if 'data-role="color"' in selector:
            return Indicator()
        if 'data-name=' in selector:
            return Button()
        return Indicator()

    async def evaluate(self, script, text=None):
        if script is rich_editor.BODY_LEN:
            return self.body_len
        if script is rich_editor.CARET_AT:
            return 0
        if script is rich_editor.END_POINT:
            return {'x': 1, 'y': 1}
        return None                   # READ_BACK — 무엇을 물어도 못 읽는다


class Editor:
    def __init__(self, frame):
        self._frame = frame
        self.page = mock.Mock()
        self.page.keyboard = mock.Mock(press=mock.AsyncMock(), down=mock.AsyncMock(), up=mock.AsyncMock())
        self.page.main_frame = frame
        self.page.mouse = mock.Mock(click=mock.AsyncMock())
        self.typed = []

    async def frame(self):
        return self._frame

    async def scan_blocking_layers(self):
        return []

    async def ensure_body_focus(self, where):
        return None

    async def _refocus_body_end(self):
        return None

    async def _insert(self, text):
        self.typed.append(text)
        self._frame.body_len += self._frame.lands


class UnreadableTextTests(unittest.IsolatedAsyncioTestCase):
    TEXT = '일주일에 두세 번 두통약을 먹습니다'

    async def _run(self, lands):
        frame = Frame(lands)
        editor = Editor(frame)
        with mock.patch.object(rich_editor.asyncio, 'sleep', mock.AsyncMock()):
            await rich_editor.styled_text(editor, self.TEXT, {'b': True})
        return editor

    async def test_text_that_landed_is_kept_even_when_it_cannot_be_read_back(self):
        editor = await self._run(lands=len(self.TEXT))
        # 글을 버리지 않았고, 사람이 볼 자리로 적어만 두었다.
        notes = getattr(editor, 'format_notes', [])
        self.assertTrue(any('확인하지 못했습니다' in n for n in notes), notes)

    async def test_mostly_landed_text_still_counts_as_in(self):
        # 편집기가 공백을 다듬어 몇 글자 줄어도 버리지 않는다.
        editor = await self._run(lands=int(len(self.TEXT) * 0.8))
        self.assertTrue(getattr(editor, 'format_notes', []))

    async def test_a_line_eaten_down_to_one_character_is_still_blocked(self):
        # 이모지 줄 사고(2026-10-23): 줄이 통째로 사라지고 한 글자만 남는다 — 이건 내용 누락이다.
        with self.assertRaises(EditorError) as caught:
            await self._run(lands=1)
        self.assertIn('표시되지 않았습니다', str(caught.exception))

    async def test_nothing_landing_at_all_is_blocked(self):
        with self.assertRaises(EditorError):
            await self._run(lands=0)


if __name__ == '__main__':
    unittest.main()
