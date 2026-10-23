"""사진이 아직 '전송중'일 때 난 실패는, 원고 탓처럼 보이지 않게 적어 준다.

2026-10-23 실측(pgandplt P139, 552건 실행 중):

    WARNING 사진 업로드가 90초 안에 끝나지 않았습니다({'total': 5, 'pending': 1, 'busy': True})
    WARNING 글자가 본문에 들어가지 않았습니다 — 쓰던 자리를 다시 눌러 칩니다
    ERROR   캐럿을 본문으로 되돌리지 못했습니다(OTHER)
    → 결과: "입력한 강조 문구가 본문에 표시되지 않았습니다"

사람은 이 문장을 보고 원고의 강조 문구를 뒤지게 된다. 그런데 원고에는 아무 잘못이 없다 —
사진이 아직 올라가는 중이어서 편집기가 글자를 받지 않은 것이고, PC가 바쁘거나 인터넷이
느릴 때 생긴다. 실제로 그때 그 PC는 메모리 31GB 중 8GB만 남아 있었다.
"""
import asyncio
import unittest

import agent


class _Editor:
    """글을 쓰다 EditorError 를 내는 대역. 발행 단추는 누르지 않는다."""

    def __init__(self, stalled=""):
        self.format_notes = []
        self.upload_stalled = stalled
        self.page = None

    async def open_write_page(self):
        return None

    async def dismiss_draft_popup(self):
        return None

    async def read_blog_id(self):
        return "testblog"

    async def reserve_count(self, reopen=False):
        return 0

    async def set_title(self, title):
        from naver_editor import EditorError
        raise EditorError("입력한 강조 문구가 본문에 표시되지 않았습니다")


JOB = {
    "id": "j1", "title": "제목", "content": "본문",
    "finalAction": "schedule", "schedule": {"datetime": "2026-12-01T10:00+09:00"},
    "options": {}, "expectedBlogId": "testblog",
}


def run(editor):
    from datetime import datetime
    return asyncio.run(agent.run_job(editor, JOB, dry_run=False, now=datetime(2026, 11, 30, 10, 0)))


class UploadStallTests(unittest.TestCase):
    def test_the_real_cause_is_added_to_the_message(self):
        editor = _Editor()
        editor.upload_stalled = "사진 1장이 90초가 지나도 '전송중'이었습니다"
        # run_job 은 시작할 때 메모를 지운다 — 지운 뒤에 멈춘 것처럼 다시 심는다.
        original = _Editor.set_title

        async def set_title(self, title):
            self.upload_stalled = "사진 1장이 90초가 지나도 '전송중'이었습니다"
            await original(self, title)

        _Editor.set_title = set_title
        try:
            result = run(editor)
        finally:
            _Editor.set_title = original
        self.assertFalse(result.ok)
        self.assertIn("강조 문구", result.message, "원래 오류는 그대로 남긴다")
        self.assertIn("전송중", result.message, "진짜 이유를 함께 적어야 한다")
        self.assertIn("인터넷이 느릴 때", result.message, "무엇을 보면 되는지도 적는다")

    def test_a_normal_failure_is_left_alone(self):
        result = run(_Editor())
        self.assertFalse(result.ok)
        self.assertEqual(result.message, "입력한 강조 문구가 본문에 표시되지 않았습니다",
                         "사진이 멀쩡했으면 군더더기를 붙이지 않는다")

    def test_the_note_is_cleared_at_the_start_of_each_job(self):
        """지난 글에서 멈췄던 사진 메모가 다음 글 결과에 따라붙으면 안 된다."""
        result = run(_Editor(stalled="사진 1장이 90초가 지나도 '전송중'이었습니다"))
        self.assertNotIn("전송중", result.message)


if __name__ == "__main__":
    unittest.main()
