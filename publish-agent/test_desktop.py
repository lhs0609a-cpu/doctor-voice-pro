import asyncio
import os
import sys
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
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

    def test_url_not_split_by_emphasis_and_becomes_a_card(self):
        """주소는 강조어로 쪼개지 않는다. 쪼개면 주소가 깨지고 카드도 못 만든다.
        2026-09-30부터 주소 한 줄은 글자가 아니라 링크 카드로 나간다."""
        url = 'https://example.com/booking?utm_content=abc#faq'
        ops = plan_text(url, ['booking', 'abc'])
        self.assertEqual([(o.kind, o.payload) for o in ops], [('link', url)])


class SummaryNoteTests(unittest.TestCase):
    """앱 현황 한 줄 = 웹 신호등 옆에 뜨는 문구."""

    def test_waiting_for_a_future_slot_reads_as_normal(self):
        """'대기 3건 · 다음 09-11 09:10' 만 보고 고장이라 읽던 화면(2026-09-29 지적).

        기다리는 중이라는 것과 손이 필요하다는 것이 한눈에 갈려야 한다."""
        note = summary_note([
            {'label': '메인', 'status': 'active', 'pending': 2, 'next_at': '2026-09-11T14:30'},
            {'label': '서브', 'status': 'active', 'pending': 1, 'next_at': '2026-09-11T09:10'},
        ])
        self.assertIn('[정상]', note)
        self.assertIn('대기 3건', note)
        self.assertIn('09-11 09:10', note)   # 가장 이른 예약

    def test_flags_blogs_that_need_a_person_with_what_to_do(self):
        note = summary_note([{'label': '메인', 'status': 'captcha', 'pending': 0}])
        self.assertIn('[조치 필요]', note)
        self.assertIn('메인', note)
        self.assertIn('보안문자', note)
        self.assertIn('→', note)

    def test_no_blogs_says_what_to_do(self):
        self.assertIn('블로그를 먼저 등록', summary_note([]))

    def test_stuck_work_is_not_hidden_inside_the_waiting_count(self):
        """'대기 1건'만 떠 있고 아무것도 안 올라가던 화면(2026-09-29 실측)을 고친 자리."""
        note = summary_note([{'label': '메인', 'status': 'active', 'pending': 0,
                              'stalled': 1, 'blocked': 0}])
        self.assertIn('[조치 필요]', note)
        self.assertIn('재시도', note)

    def test_an_unresolved_publication_says_it_blocks_the_rest(self):
        note = summary_note([{'label': '메인', 'status': 'active', 'pending': 3, 'blocked': 1}])
        self.assertIn('예약 등록 확인', note)
        self.assertIn('3건', note)

    def test_a_hold_reason_from_the_server_is_shown_as_is(self):
        note = summary_note([{'label': '메인', 'status': 'active', 'pending': 2,
                              'hold_reason': "'자동 운영'이 꺼져 있습니다. → 켜 주세요"}])
        self.assertIn('자동 운영', note)


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
                manual = app.manual.box          # 카드 통째로 접었다 폈다 한다
                self.assertEqual(manual.winfo_manager(), '')
                toggle.invoke()
                self.assertEqual(manual.winfo_manager(), 'pack')
                app.start()
                self.assertIsNone(app.worker)
                self.assertIn('아직 홈페이지에 연결되지 않았습니다', app.status.get())
                toggle.invoke()
                self.assertEqual(manual.winfo_manager(), '')
                self.assertIs(app.connect_button.master, app.manual)
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
class UpdateNoticeTests(unittest.TestCase):
    """새 버전은 묻지 않고 설치하되, 무슨 일인지는 알린다.

    말없이 창이 닫혔다 열리면 사람은 프로그램이 꺼진 줄 안다(2026-09-23 실측: 실행기가
    사라져 '왜 안 보이냐'가 됐다). 반대로 '설치할까요?'를 물으면 아무도 안 눌러서 고친 것이
    영영 닿지 않는다. 그래서 알림 창은 뜨되 **답을 기다리지 않아야** 한다.
    """

    def setUp(self):
        # Tk 는 임시 폴더 수명과 얽히지 않게 패치 바깥에서 먼저 만든다.
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        self.root.destroy()

    def test_the_notice_appears_and_the_install_still_runs_without_an_answer(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict('os.environ', {'LOCALAPPDATA': folder}),
            patch('desktop.LocalBridge.start'),
            patch('desktop.threading.Thread.start'),
            patch('desktop.updater.installed_build', return_value=False),
            patch('desktop.updater.install') as install,
            patch('desktop.messagebox.askyesno') as asked,
        ):
            app = Desktop(self.root)
            app.offer_update('9.9.9', 'setup.exe')
            tops = [w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)]
            self.assertEqual(len(tops), 1, '알림 창이 떠야 한다')
            text = ' '.join(w.cget('text') for w in tops[0].winfo_children() if 'text' in w.keys())
            self.assertIn('9.9.9', text)
            asked.assert_not_called()       # 묻지 않는다
            install.assert_not_called()     # 읽을 시간을 준 뒤에 설치한다
            app.install_update('9.9.9', 'setup.exe')
            install.assert_called_once_with('setup.exe')

    def test_an_update_waits_until_the_post_being_written_is_finished(self):
        """발행 한복판에 설치하면 창이 닫히고 크롬까지 같이 꺼진다 — 그 글이 통째로 날아간다.

        2026-10-20 고객 신고: "글감 선택 창에서 멈춰버리고, 조금 기다리니 창이 아예
        꺼져버리네요(실행기도 꺼집니다)". 창이 스스로 닫히는 길은 업데이트 설치뿐이었다."""
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict('os.environ', {'LOCALAPPDATA': folder}),
            patch('desktop.LocalBridge.start'),
            patch('desktop.threading.Thread.start'),
            patch('desktop.updater.installed_build', return_value=False),
            patch('desktop.updater.install') as install,
        ):
            app = Desktop(self.root)
            app.worker = SimpleNamespace(is_alive=lambda: True)   # 자동 발행이 돌고 있고
            app.busy_event.set()                                  # 지금 글을 올리는 중이다
            app.offer_update('9.9.9', 'setup.exe')
            # 미루는 것도 팝업으로 알린다 — 말이 없으면 '업데이트 왜 안 되나'가 된다.
            waiting = [w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)]
            self.assertEqual(len(waiting), 1)
            said = ' '.join(w.cget('text') for w in waiting[0].winfo_children() if 'text' in w.keys())
            self.assertIn('받아 두었습니다', said)
            self.assertNotIn('설치합니다', said.split('받아 두었습니다')[0])
            install.assert_not_called()
            self.assertFalse(app.stop_event.is_set(), '발행을 끊지 않는다')
            self.assertIn('끝낸 뒤', app.status.get())
            app.install_update('9.9.9', 'setup.exe')              # 3초 뒤 길로 들어와도
            install.assert_not_called()                           # 아직은 설치하지 않는다

            app.busy_event.clear()                                # 그 글이 끝났다
            for w in self.root.winfo_children():
                if isinstance(w, tk.Toplevel):
                    w.destroy()                                   # 기다림 알림은 치우고 센다
            app.offer_update('9.9.9', 'setup.exe')
            installing = [w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)]
            self.assertEqual(len(installing), 1)
            self.assertIn('설치합니다', ' '.join(
                w.cget('text') for w in installing[0].winfo_children() if 'text' in w.keys()))
            app.install_update('9.9.9', 'setup.exe')
            install.assert_called_once_with('setup.exe')

    def test_the_close_button_answers_right_away_and_a_second_press_quits(self):
        """2026-10-20 신고: "창에 x표시를 눌러도 화면이 꺼지지 않아서요".

        원고 한 건은 사진까지 올리면 몇 분이 걸린다. 그동안 창은 그대로 있고 [실행 중단]은
        이미 꺼져 있어 사람이 할 수 있는 일이 없었다 — 결국 작업 관리자로 강제 종료하게 된다."""
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict('os.environ', {'LOCALAPPDATA': folder}),
            patch('desktop.LocalBridge.start'),
            patch('desktop.threading.Thread.start'),
            patch('desktop.updater.installed_build', return_value=False),
            patch('desktop.os._exit') as quit_now,
        ):
            app = Desktop(self.root)
            app.worker = SimpleNamespace(is_alive=lambda: True)   # 올리는 중이라 바로는 못 끝낸다
            app.close()
            self.assertTrue(app.stop_event.is_set())              # 마무리를 요청하고
            self.assertIn('한 번 더', app.status.get())            # 무엇을 하면 되는지 적는다
            quit_now.assert_not_called()                          # 아직 끄지는 않는다

            with patch.object(app.root, 'destroy') as closed:     # 창은 tearDown 이 닫는다
                app.close()                                       # [X] 두 번째
            closed.assert_called_once()
            quit_now.assert_called_once_with(0)

    def test_the_screen_keeps_refreshing_even_if_one_update_blows_up(self):
        """화면 갱신이 한 번 터지면 그걸로 끝이라, 기록도 멈추고 [X]도 안 듣는 상태가 된다."""
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict('os.environ', {'LOCALAPPDATA': folder}),
            patch('desktop.LocalBridge.start'),
            patch('desktop.threading.Thread.start'),
            patch('desktop.updater.installed_build', return_value=False),
        ):
            app = Desktop(self.root)
            with patch.object(Desktop, '_poll_once', side_effect=RuntimeError('화면 갱신 실패')):
                app.poll()                                        # 터져도 조용히 넘어가고
            self.assertTrue(self.root.tk.call('after', 'info'), '다음 바퀴가 예약돼 있어야 한다')

    def test_the_launcher_says_so_itself_once_the_update_is_done(self):
        """2026-10-22 문의: "닥터보이스 어플 업데이트 완료되면 말씀 한 번 부탁드립니다".

        설치가 끝나면 창이 저절로 닫혔다 열린다 — 사람은 그게 끝난 것인지 알 수 없어
        사람에게 물어볼 수밖에 없다. 프로그램이 먼저 말하게 한다."""
        from desktop import VERSION

        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict('os.environ', {'LOCALAPPDATA': folder}),
            patch('desktop.LocalBridge.start'),
            patch('desktop.threading.Thread.start'),
            patch('desktop.updater.installed_build', return_value=False),
        ):
            app = Desktop(self.root)
            app.updated_popup('1.7.12', VERSION)
            tops = [w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)]
            said = ' '.join(w.cget('text') for w in tops[-1].winfo_children() if 'text' in w.keys())
            self.assertIn('업데이트가 끝났습니다', said)
            self.assertIn('1.7.12', said)
            self.assertIn(VERSION, said)
            self.assertIn('업데이트 완료', app.status.get())

    def test_the_version_it_started_with_is_remembered_for_next_time(self):
        """다음에 켤 때 '전에 쓰던 버전'과 달라야 완료를 알릴 수 있다."""
        import json
        from desktop import VERSION

        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict('os.environ', {'LOCALAPPDATA': folder}),
            patch('desktop.LocalBridge.start'),
            patch('desktop.threading.Thread.start'),
            patch('desktop.updater.installed_build', return_value=False),
        ):
            app = Desktop(self.root)
            saved = json.loads(app.settings_file.read_text(encoding='utf-8'))
            self.assertEqual(saved.get('last_version'), VERSION)

    def test_it_books_its_own_restart_so_nobody_has_to_press_the_icon(self):
        """2026-10-22 요청: "자동업데이트되어서 자동으로 껐다 켜지게끔 하면 안돼?"

        설치 프로그램도 끝나고 한 번 띄우지만, 조용한 설치에서 그쪽이 막히면 창이 영영
        안 돌아온다. 실행기가 스스로도 예약해 둔다 — 둘 다 떠도 자리 이름표가 막아 준다."""
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict('os.environ', {'LOCALAPPDATA': folder}),
            patch('desktop.LocalBridge.start'),
            patch('desktop.threading.Thread.start'),
            patch('desktop.updater.installed_build', return_value=False),
            patch('desktop.updater.install'),
            patch('desktop.updater.installed_exe', return_value=Path(r'C:pp\DoctorVoiceAutopilot.exe')),
            patch('desktop.updater.relaunch_after') as relaunch,
            patch.object(self.root, 'destroy'),
        ):
            app = Desktop(self.root)
            app.paired_email = 'a@naver.com'
            app.install_update('9.9.9', 'setup.exe')
            relaunch.assert_called_once()
            args = relaunch.call_args[0]
            self.assertEqual(str(args[0]), r'C:pp\DoctorVoiceAutopilot.exe')
            self.assertEqual(args[2], 'a@naver.com', '맡던 계정 자리로 돌아와야 한다')

    def test_a_failed_install_leaves_the_launcher_running_on_the_old_version(self):
        """설치가 막혀도(서명 없는 파일 차단 등) 실행기를 죽이지 않는다."""
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict('os.environ', {'LOCALAPPDATA': folder}),
            patch('desktop.LocalBridge.start'),
            patch('desktop.threading.Thread.start'),
            patch('desktop.updater.installed_build', return_value=False),
            patch('desktop.updater.install', side_effect=OSError('앱 제어가 막았습니다')),
        ):
            app = Desktop(self.root)
            app.install_update('9.9.9', 'setup.exe')
            self.assertIn('설치하지 못했습니다', app.status.get())
            self.assertFalse(app.stop_event.is_set())


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
