"""다 쓰고 뒤에서 깨진 글은 버리지 않고, 다음 시도가 이어받는다.

2026-10-25 실측: 10월 400편에 시도 811회(평균 2.0회)가 들었고, 재시도는 매번 본문
3,000자와 사진 10장을 처음부터 다시 올렸다. 대량 병원에서 시간이 두 배로 드는 이유다.

제일 나쁜 것은 반쯤 쓰인 글이나 남의 글이 그대로 발행되는 것이다. 그래서 이어받기는
**제목이 맞고 본문이 끝까지 들어가 있을 때만** 하고, 하나라도 어긋나면 처음부터 쓴다.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent  # noqa: E402
import naver_editor  # noqa: E402


class FakeOutcome:
    def __init__(self, ok=True):
        self.ok = ok
        self.message = '임시저장'


class FakeEditor:
    """keep_body_for_resume 가 보는 최소 인터페이스."""

    def __init__(self, body_done=True, clicked_publish=False, save_ok=True, save_raises=False):
        self.body_done = body_done
        self.clicked_publish = clicked_publish
        self.save_ok = save_ok
        self.save_raises = save_raises
        self.saved = 0

    async def save_draft(self):
        if self.save_raises:
            raise RuntimeError('임시저장 버튼을 찾지 못했습니다')
        self.saved += 1
        return FakeOutcome(self.save_ok)


class KeepBodyTests(unittest.IsolatedAsyncioTestCase):
    async def test_a_finished_body_is_saved_for_the_next_attempt(self):
        editor = FakeEditor()
        self.assertTrue(await agent.keep_body_for_resume(editor))
        self.assertEqual(editor.saved, 1)

    async def test_nothing_is_saved_before_the_body_is_in(self):
        """반쯤 쓰인 글을 남기면 다음 시도가 그걸 이어받아 빠진 채로 발행된다."""
        editor = FakeEditor(body_done=False)
        self.assertFalse(await agent.keep_body_for_resume(editor))
        self.assertEqual(editor.saved, 0)

    async def test_nothing_is_saved_after_publish_was_clicked(self):
        """이미 올라갔을 수 있다 — 임시저장은 사본을 만든다."""
        editor = FakeEditor(clicked_publish=True)
        self.assertFalse(await agent.keep_body_for_resume(editor))
        self.assertEqual(editor.saved, 0)

    async def test_dry_run_never_touches_naver(self):
        editor = FakeEditor()
        self.assertFalse(await agent.keep_body_for_resume(editor, dry_run=True))
        self.assertEqual(editor.saved, 0)

    async def test_a_failed_save_is_not_reported_as_resumable(self):
        for editor in (FakeEditor(save_ok=False), FakeEditor(save_raises=True)):
            self.assertFalse(await agent.keep_body_for_resume(editor))


class RestoreFrame:
    def __init__(self, clicked, title, chars):
        self.clicked, self.title, self.chars = clicked, title, chars

    async def evaluate(self, script, arg=None):
        if script is naver_editor.JS_RESTORE_DRAFT:
            return self.clicked
        if script is naver_editor.JS_BODY_CHARS:
            return self.chars
        return self.title        # JS_READ_TEXT


class RestoreEditor:
    def __init__(self, frame):
        self._frame = frame

    async def frame(self):
        return self._frame


class RestoreDraftTests(unittest.IsolatedAsyncioTestCase):
    TITLE = '동탄레이저제모, 몇회를 해야할지 여기서 정해드립니다'

    async def restore(self, clicked='확인', title=None, chars=3000, want_chars=3000):
        frame = RestoreFrame(clicked, self.TITLE if title is None else title, chars)
        editor = RestoreEditor(frame)
        with mock.patch.object(naver_editor.asyncio, 'sleep', mock.AsyncMock()):
            return await naver_editor.NaverEditor.restore_draft(editor, self.TITLE, want_chars)

    async def test_our_own_complete_draft_is_resumed(self):
        self.assertTrue(await self.restore())

    async def test_no_popup_means_nothing_to_resume(self):
        self.assertFalse(await self.restore(clicked=None))

    async def test_someone_elses_draft_is_refused(self):
        self.assertFalse(await self.restore(title='전혀 다른 글 제목입니다'))

    async def test_a_half_written_body_is_refused(self):
        # 본문이 모자라면 뒷부분이 빠진 채 발행된다 — 처음부터 다시 쓴다.
        self.assertFalse(await self.restore(chars=1500, want_chars=3000))

    async def test_a_few_characters_trimmed_by_naver_still_resumes(self):
        self.assertTrue(await self.restore(chars=2960, want_chars=3000))


if __name__ == '__main__':
    unittest.main()
