import asyncio
import os
import sys
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import tkinter as tk

import credential_store
from desktop import Desktop, summary_note, valid_server, make_args
from agent import interruptible_pause
from plan import plan_text


class DesktopTests(unittest.TestCase):
    def test_server_requires_https_or_loopback(self):
        self.assertTrue(valid_server('https://example.com'))
        self.assertTrue(valid_server('http://127.0.0.1:8010'))
        for url in ('http://example.com', 'https://user:password@example.com', 'https://example.com/path', 'https://example.com?key=secret'):
            self.assertFalse(valid_server(url))

    def test_stopping_does_not_wait_full_poll_interval(self):
        event = threading.Event()
        event.set()
        args = make_args('https://example.com', 'email', 'password', Path('.'), event)
        async def run():
            await asyncio.wait_for(interruptible_pause(300, args), timeout=.1)
        asyncio.run(run())

    def test_url_not_split_by_emphasis_and_receives_enter(self):
        url = 'https://example.com/booking?utm_content=abc#faq'
        ops = plan_text(url, ['booking', 'abc'])
        self.assertEqual([(o.kind, o.payload) for o in ops], [('text', url), ('enter', '')])


class SummaryNoteTests(unittest.TestCase):
    """앱 현황 한 줄 = 웹 신호등 옆에 뜨는 문구."""

    def test_counts_pending_across_blogs_and_shows_the_next_slot(self):
        note = summary_note([
            {'label': '메인', 'status': 'active', 'pending': 2, 'next_at': '2026-09-11T14:30'},
            {'label': '서브', 'status': 'active', 'pending': 1, 'next_at': '2026-09-11T09:10'},
        ])
        self.assertIn('대기 3건', note)
        self.assertIn('09-11 09:10', note)   # 가장 이른 예약

    def test_flags_blogs_that_need_a_person(self):
        note = summary_note([{'label': '메인', 'status': 'captcha', 'pending': 0}])
        self.assertIn('확인 필요', note)
        self.assertIn('메인', note)

    def test_no_blogs_is_said_plainly(self):
        self.assertEqual(summary_note([]), '등록된 블로그 없음')


@unittest.skipUnless(sys.platform == 'win32' or os.environ.get('DISPLAY'), 'GUI display required')
class DesktopGuideTests(unittest.TestCase):
    def test_manual_login_can_be_revealed_without_starting_publication(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', {'LOCALAPPDATA': folder}), \
                patch('desktop.LocalBridge.start'), patch('desktop.threading.Thread.start'), \
                patch('desktop.updater.installed_build', return_value=False):
            root = tk.Tk()
            root.withdraw()
            try:
                app = Desktop(root)
                def descendants(widget):
                    for child in widget.winfo_children():
                        yield child
                        yield from descendants(child)
                widgets = list(descendants(root))
                toggle = next(w for w in widgets if 'text' in w.keys() and w.cget('text') == '직접 로그인 / 서버 설정 펼치기')
                manual = app.connect_button.master
                self.assertEqual(manual.winfo_manager(), '')
                toggle.invoke()
                self.assertEqual(manual.winfo_manager(), 'pack')
                app.start()
                self.assertIsNone(app.worker)
                self.assertIn('아직 홈페이지에 연결되지 않았습니다', app.status.get())
                toggle.invoke()
                self.assertEqual(manual.winfo_manager(), '')
            finally:
                root.destroy()

    def test_unpaired_launcher_asks_the_browser_to_connect_by_itself(self):
        """켜기만 하면 연결돼야 한다 — 사용자가 이메일·비밀번호를 칠 일이 없다."""
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', {'LOCALAPPDATA': folder}),                 patch('desktop.LocalBridge.start'), patch('desktop.threading.Thread.start'),                 patch('desktop.updater.installed_build', return_value=False),                 patch('desktop.ServerClient') as server, patch('desktop.webbrowser.open') as opened:
            server.return_value.pair_request.return_value = {'request_id': 'REQ', 'expires_in': 600}
            server.return_value.pair_poll.return_value = {'status': 'waiting'}
            root = tk.Tk()
            root.withdraw()
            try:
                app = Desktop(root)
                self.assertFalse(app.device_secret)     # 처음 켠 PC
                app.closing = True                      # 기다리지 않고 한 바퀴만 돈다
                app.auto_connect()
                server.return_value.pair_request.assert_called_once()
                self.assertTrue(opened.call_args[0][0].endswith('?r=REQ'), opened.call_args)
            finally:
                root.destroy()


@unittest.skipUnless(credential_store.available(), 'DPAPI 는 Windows 에서만 쓴다')
class CredentialStoreTests(unittest.TestCase):
    """자동 로그인용 비밀번호는 이 PC에서만 풀린다."""

    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())

    def test_round_trip_and_clear(self):
        self.assertIsNone(credential_store.load(self.folder))
        self.assertTrue(credential_store.save(self.folder, 'pw-비밀!'))
        self.assertEqual(credential_store.load(self.folder), 'pw-비밀!')
        credential_store.clear(self.folder)
        self.assertIsNone(credential_store.load(self.folder))

    def test_empty_password_is_not_saved(self):
        self.assertFalse(credential_store.save(self.folder, ''))
        self.assertIsNone(credential_store.load(self.folder))

    def test_unreadable_file_is_discarded_not_raised(self):
        (self.folder / credential_store.FILE_NAME).write_bytes(b'not dpapi')
        self.assertIsNone(credential_store.load(self.folder))
        self.assertFalse((self.folder / credential_store.FILE_NAME).exists())


if __name__ == '__main__':
    unittest.main()
