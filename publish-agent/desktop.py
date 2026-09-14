"""Windows desktop entry point. Reuses the journaled agent; credentials stay in memory.

화면이 하는 일은 세 가지다.
1) 로그인해서 서버와 연결하고, 살아 있다는 신호(하트비트)를 보낸다 → 웹의 연결 신호등이 켜진다.
2) 자동 발행을 시작/중단하고, 진행 상황과 대기 건수를 보여준다.
3) 새 버전을 스스로 확인해 설치한다.
"""
import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import queue
import socket
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.parse import urlparse
import uuid
import webbrowser

import agent
import credential_store
import updater
from local_bridge import LocalBridge
from server_client import ServerClient, ServerError
from version import APP_MUTEX, VERSION

SERVER = 'https://doctor-voice-pro-backend.fly.dev'
WEBSITE = 'https://doctor-voice-pro-ghwi.vercel.app/dashboard/one-stop'
BEAT_SECONDS = 60          # 서버가 150초 침묵을 '꺼짐'으로 본다 → 그보다 짧게


def hold_single_instance():
    """설치 프로그램(AppMutex)이 실행 중인 실행기를 알아보게 이름 있는 뮤텍스를 잡습니다.

    이미 잡혀 있으면 False — 두 번 켜면 크롬 프로필이 겹쳐 로그인 세션이 깨집니다."""
    if sys.platform != 'win32':
        return True
    import ctypes
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, APP_MUTEX)
    if not handle or kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        return False
    hold_single_instance.handle = handle  # 프로세스가 끝날 때까지 유지
    return True


def valid_server(value):
    try:
        p = urlparse(value)
        return bool(p.hostname and not p.username and not p.password and not p.query and not p.fragment
                    and p.path in ('', '/') and (p.scheme == 'https' or
                    (p.scheme == 'http' and p.hostname in ('localhost', '127.0.0.1'))))
    except ValueError:
        return False


def make_args(server, email, password, folder, stop_event):
    if not valid_server(server):
        raise ValueError('서버 주소는 HTTPS 주소 또는 로컬 서버여야 합니다')
    return argparse.Namespace(server=server.rstrip('/'), email=email, password=password,
        profiles_dir=str(folder / 'profiles'), log_dir=str(folder / 'logs'), blog=None,
        once=False, dry_run=False, headless=False, window_pos=None, interval=60,
        max_per_blog=5, min_gap=20, max_gap=60, captcha_wait=180, no_images=False,
        verbose=False, stop_event=stop_event)


def summary_note(blogs) -> str:
    """웹 신호등 옆에 뜰 한 줄 + 앱 현황 라벨. 예: '대기 3건 · 다음 09-11 14:30'"""
    if not blogs:
        return '등록된 블로그 없음'
    pending = sum(int(b.get('pending') or 0) for b in blogs)
    trouble = [b for b in blogs if (b.get('status') or 'active') != 'active']
    nexts = sorted(b['next_at'] for b in blogs if b.get('next_at'))
    parts = [f'대기 {pending}건']
    if nexts:
        parts.append('다음 ' + nexts[0].replace('T', ' ')[5:16])
    if trouble:
        names = ', '.join((b.get('label') or b.get('naver_blog_id') or '') for b in trouble[:2])
        parts.append(f'확인 필요: {names}')
    return ' · '.join(parts)


class QueueLog(logging.Handler):
    def __init__(self, output):
        super().__init__()
        self.output = output

    def emit(self, record):
        try:
            self.output.put_nowait(self.format(record))
        except queue.Full:
            pass


class Desktop:
    def __init__(self, root):
        self.root = root
        self.worker = None
        self.stop_event = threading.Event()
        self.output = queue.Queue(maxsize=500)
        self.ui = queue.Queue(maxsize=100)      # 백그라운드 스레드 → 화면 갱신
        self.closing = False
        self.client = None                      # 하트비트·현황용 서버 연결
        self.client_lock = threading.Lock()
        self.beat_wake = threading.Event()      # 종료할 때 하트비트 대기를 깨운다
        self.folder = Path(os.environ.get('LOCALAPPDATA') or Path.home()) / 'DoctorVoicePro'
        self.folder.mkdir(parents=True, exist_ok=True)
        self.settings_file = self.folder / 'desktop.json'
        try:
            saved = json.loads(self.settings_file.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            saved = {}
        self.device_id = str(saved.get('device_id') or uuid.uuid4().hex)
        # 홈페이지 자동 연결로 받은 이 기기 전용 키(이 PC에서만 풀린다)와 연결된 계정
        self.device_secret = credential_store.load(self.folder, credential_store.DEVICE_FILE)
        self.paired_email = str(saved.get('paired_email') or '')
        # tkinter 변수는 다른 스레드에서 읽으면 안 된다 → 연결 창구가 읽을 사본
        self.server_url = str(saved.get('server') or SERVER)

        root.title('닥터보이스 자동 발행')
        root.geometry('820x780')
        root.minsize(780, 740)
        style = ttk.Style(root)
        style.configure('.', font=('Malgun Gothic', 10))
        style.configure('TButton', padding=(10, 6))
        frame = ttk.Frame(root, padding=22)
        frame.pack(fill='both', expand=True)
        header = ttk.Frame(frame)
        header.pack(fill='x')
        ttk.Label(header, text=f'닥터보이스 자동 발행  v{VERSION}', font=('Malgun Gothic', 20, 'bold')).pack(side='left')
        ttk.Button(header, text='업데이트 확인', command=lambda: self.check_update(manual=True)).pack(side='right')
        ttk.Label(frame, text='이 창은 네이버에 글을 등록하는 PC 실행기입니다. 아래 순서대로 준비하세요.').pack(anchor='w', pady=10)
        guide = ttk.LabelFrame(frame, text='처음이라면 이렇게 하세요', padding=12)
        guide.pack(fill='x', pady=(0, 12))
        ttk.Label(guide, text='1. [홈페이지 열어 연결하기] → 홈페이지에 로그인하세요.\n   브라우저에서 로컬 네트워크 접근을 물으면 허용하세요.\n2. 아래에 [연결됨]이 표시되면 [자동 발행 시작]을 누르세요.\n3. 네이버 로그인 창이 열리면 로그인하고, 홈페이지에서 글을 준비하세요.',
                  justify='left').pack(anchor='w')
        ttk.Button(guide, text='1. 홈페이지 열어 연결하기', command=lambda: webbrowser.open(WEBSITE)).pack(anchor='w', pady=(10, 0))
        ttk.Label(guide, text='웹에 연결 필요로 나오나요? 창을 여는 것과 계정 연결은 별개입니다.\n자동 연결이 안 되면 아래 [직접 로그인]을 사용하세요.', foreground='#526174').pack(anchor='w', pady=(8, 0))

        self.server = tk.StringVar(value=saved.get('server', SERVER))
        self.email = tk.StringVar(value=saved.get('email', ''))
        self.password = tk.StringVar()
        self.auto_login = tk.BooleanVar(value=bool(saved.get('auto_login')))
        self.auto_start = tk.BooleanVar(value=bool(saved.get('auto_start')))
        manual = ttk.LabelFrame(frame, text='자동 연결이 안 될 때만 직접 로그인', padding=10)
        toggle = ttk.Button(frame, text='직접 로그인 / 서버 설정 펼치기')
        toggle.pack(anchor='w', pady=(0, 8))
        for title, var, secret in [('서버 주소 (기본값을 그대로 사용하세요)', self.server, False), ('홈페이지에 로그인한 닥터보이스 이메일', self.email, False), ('닥터보이스 비밀번호 (네이버 비밀번호가 아닙니다)', self.password, True)]:
            ttk.Label(manual, text=title).pack(anchor='w')
            entry = ttk.Entry(manual, textvariable=var, show='•' if secret else '')
            entry.pack(fill='x', pady=(2, 8))
            if secret:
                entry.bind('<Return>', lambda _e: self.start())

        options = ttk.Frame(frame)
        options.pack(fill='x', pady=(0, 8))
        def toggle_manual():
            if manual.winfo_manager():
                manual.pack_forget()
                toggle.configure(text='직접 로그인 / 서버 설정 펼치기')
            else:
                manual.pack(fill='x', before=options, pady=(0, 8))
                toggle.configure(text='직접 로그인 / 서버 설정 접기')
        toggle.configure(command=toggle_manual)
        ttk.Checkbutton(options, text='이 PC에서 자동 로그인 (다음부터 켜자마자 연결)', variable=self.auto_login,
                        command=self.on_auto_login_toggle).pack(side='left')
        ttk.Checkbutton(options, text='켜지면 바로 발행 시작', variable=self.auto_start,
                        command=self.save_settings).pack(side='left', padx=12)

        buttons = ttk.Frame(frame)
        buttons.pack(fill='x', pady=8)
        self.start_button = ttk.Button(buttons, text='자동 발행 시작', command=self.start)
        self.start_button.pack(side='left')
        self.connect_button = ttk.Button(manual, text='입력한 계정으로 연결', command=self.connect_now)
        self.connect_button.pack(anchor='w')
        self.stop_button = ttk.Button(buttons, text='실행 중단', command=self.stop, state='disabled')
        self.stop_button.pack(side='left', padx=8)
        ttk.Button(buttons, text='운영 설정 열기', command=lambda: webbrowser.open(WEBSITE)).pack(side='left')
        ttk.Button(buttons, text='기록 복사', command=self.copy_logs).pack(side='right')

        # 웹 신호등이 왜 꺼져 있는지 여기서 바로 알 수 있어야 한다.
        self.link = tk.StringVar(value='홈페이지 연결: 끊김 — 로그인하면 홈페이지 신호등이 켜집니다')
        self.link_label = ttk.Label(frame, textvariable=self.link, wraplength=680, foreground='#b42318')
        self.link_label.pack(anchor='w', pady=(2, 0))
        self.status = tk.StringVar(value='지금 할 일: [홈페이지 열어 연결하기]를 누르세요. Chrome이 필요합니다.')
        ttk.Label(frame, textvariable=self.status, wraplength=680).pack(anchor='w', pady=6)
        self.summary = tk.StringVar(value='연결하면 대기 건수와 다음 예약을 보여줍니다')
        ttk.Label(frame, textvariable=self.summary, wraplength=680, foreground='#3b6cb7').pack(anchor='w')

        self.logs = tk.Text(frame, height=12, state='disabled', wrap='word')
        self.logs.pack(fill='both', expand=True, pady=(8, 0))
        ttk.Label(frame, text='네이버 로그인·캡차 요청은 열린 Chrome에서 처리하세요.\nPC를 끄면 새 예약 등록이 멈춥니다. 이미 네이버에 걸어둔 예약은 그대로 발행됩니다.').pack(anchor='w', pady=8)

        handler = QueueLog(self.output)
        handler.setFormatter(logging.Formatter('%(asctime)s %(message)s', '%H:%M:%S'))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)
        # 내부 HTTP 요청 줄까지 보여주면 사용자가 읽을 수 없다. 경고 이상만 남긴다.
        for noisy in ('httpx', 'httpcore', 'urllib3'):
            logging.getLogger(noisy).setLevel(logging.WARNING)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(300, self.poll)

        self.bridge = LocalBridge(status=self.bridge_status, pair=self.bridge_pair)
        self.bridge.start()
        threading.Thread(target=self.beat_loop, daemon=True).start()
        if updater.installed_build():
            threading.Thread(target=self.check_update, daemon=True).start()
        if self.device_secret:
            self.set_link(False, '홈페이지 계정으로 연결하는 중…')
            self.connect_device_async()
            if self.auto_start.get():
                self.root.after(1500, self.start)
        else:
            self.set_link(False, '1번 버튼으로 홈페이지에 로그인하세요. 자동 연결을 기다립니다')
            self.restore_login()

    # ------------------------------------------------------------ 설정·자격
    def save_settings(self):
        self.server_url = self.server.get().strip() or SERVER
        try:
            self.settings_file.write_text(json.dumps({
                'server': self.server_url, 'email': self.email.get().strip(),
                'auto_login': bool(self.auto_login.get()), 'auto_start': bool(self.auto_start.get()),
                'device_id': self.device_id, 'paired_email': self.paired_email,
            }), encoding='utf-8')
        except OSError:
            pass

    def on_auto_login_toggle(self):
        """켜면 지금 입력된 비밀번호를 이 PC에서만 풀 수 있게 저장하고, 끄면 지운다."""
        if self.auto_login.get():
            if not credential_store.available():
                self.auto_login.set(False)
                self.status.set('자동 로그인은 Windows에서만 쓸 수 있습니다')
            elif not self.password.get():
                self.status.set('비밀번호를 입력한 뒤 자동 로그인을 켜면 저장됩니다')
            elif credential_store.save(self.folder, self.password.get()):
                self.status.set('이 PC에서만 풀 수 있게 비밀번호를 저장했습니다')
            else:
                self.auto_login.set(False)
                self.status.set('비밀번호를 저장하지 못했습니다')
        else:
            credential_store.clear(self.folder)
            self.status.set('저장한 비밀번호를 지웠습니다')
        self.save_settings()

    def restore_login(self):
        """자동 로그인이 켜져 있으면 저장된 비밀번호로 연결하고, 설정에 따라 바로 시작한다."""
        if not self.auto_login.get():
            return
        stored = credential_store.load(self.folder)
        if not stored:
            return
        self.password.set(stored)
        if self.auto_start.get():
            self.root.after(600, self.start)
        else:
            self.root.after(300, lambda: self.connect_async(self.server.get().strip(), self.email.get().strip(), stored))

    def set_link(self, connected, detail=''):
        """홈페이지 신호등과 같은 뜻의 한 줄. 초록이면 웹에서도 켜져 보인다."""
        if connected:
            who = f' ({self.paired_email})' if self.paired_email else ''
            self.link.set('홈페이지 연결: 연결됨' + who + (f' · {detail}' if detail else ''))
            self.link_label.configure(foreground='#067647')
        else:
            self.link.set('홈페이지 연결: 확인 필요' + (f' — {detail}' if detail else ' — 홈페이지를 열어 연결하세요'))
            self.link_label.configure(foreground='#946200')

    def connect_now(self):
        """발행은 시작하지 않고 로그인만 한다 — 웹 신호등을 켜 두고 현황만 보고 싶을 때."""
        email, password = self.email.get().strip(), self.password.get()
        if not email or not password:
            self.status.set('이메일과 비밀번호를 입력한 뒤 눌러 주세요')
            return
        self.status.set('서버에 연결하는 중…')
        self.save_settings()
        if self.auto_login.get():
            credential_store.save(self.folder, password)
        self.connect_async(self.server.get().strip(), email, password)

    def connect_async(self, server, email, password):
        threading.Thread(target=self.connect, args=(server, email, password), daemon=True).start()

    # ------------------------------------------------------------ 서버 연결·신호등
    def connect(self, server, email, password):
        """하트비트·현황용 연결. 발행을 시작하지 않아도 웹 신호등을 켜 둔다.

        비밀번호는 인자로만 받는다 — 화면 입력칸은 시작과 동시에 비우기 때문이다."""
        if not (valid_server(server) and email and password):
            return False
        try:
            client = ServerClient(server.rstrip('/'), timeout=20.0)
            client.login(email, password)
        except Exception as error:  # noqa: BLE001
            self.ui.put(('status', f'서버 연결 실패: {error}'))
            self.ui.put(('link', (False, '이메일·비밀번호를 다시 확인하세요')))
            return False
        self.adopt_client(client)
        return True

    def adopt_client(self, client):
        """로그인된 연결로 바꿔 끼우고 곧바로 신호를 보낸다 → 홈페이지 신호등이 켜진다."""
        with self.client_lock:
            old, self.client = self.client, client
        if old and old is not client:
            try:
                old.close()
            except Exception:  # noqa: BLE001
                pass
        self.ui.put(('status', '연결 완료 · [자동 발행 시작]을 누른 뒤 홈페이지에서 글을 준비하세요'))
        self.ui.put(('link', (True, '')))
        self.beat_once()

    def connect_device_async(self):
        threading.Thread(target=self.connect_device, daemon=True).start()

    def connect_device(self):
        """기기 키로 로그인한다. 홈페이지에서 연결을 해제했으면 키를 버리고 다시 연결을 기다린다."""
        secret = self.device_secret
        if not secret or not valid_server(self.server_url):
            return False
        client = ServerClient(self.server_url.rstrip('/'), timeout=20.0)
        try:
            data = client.device_login(self.device_id, secret)
        except ServerError as error:
            client.close()
            if error.status == 401:
                self.device_secret = None
                credential_store.clear(self.folder, credential_store.DEVICE_FILE)
                self.ui.put(('link', (False, '연결이 해제되었습니다 — 홈페이지를 열면 다시 연결됩니다')))
            else:
                self.ui.put(('link', (False, f'서버에 닿지 못했습니다({error.detail})')))
            return False
        except Exception as error:  # noqa: BLE001
            client.close()
            self.ui.put(('link', (False, f'서버에 닿지 못했습니다({error})')))
            return False
        if data.get('email'):
            self.ui.put(('paired', data['email']))
        self.adopt_client(client)
        return True

    # ------------------------------------------------------------ 홈페이지 연결 창구(127.0.0.1)
    def bridge_status(self):
        """홈페이지가 '이 PC에 실행기가 있나, 누구로 연결돼 있나'를 묻는다."""
        with self.client_lock:
            connected = self.client is not None
        return {'app': 'doctorvoice-launcher', 'version': VERSION, 'device_id': self.device_id,
                'paired': bool(self.device_secret), 'email': self.paired_email or None,
                'connected': connected, 'running': bool(self.worker and self.worker.is_alive())}

    def bridge_pair(self, code):
        """로그인된 홈페이지가 건넨 1회용 코드로 이 PC를 그 계정에 연결한다(창구 스레드에서 불린다)."""
        if not valid_server(self.server_url):
            return False, '실행기의 서버 주소가 올바르지 않습니다', {}
        client = ServerClient(self.server_url.rstrip('/'), timeout=20.0)
        try:
            claim = client.pair_claim(code, self.device_id, socket.gethostname()[:120])
            data = client.device_login(self.device_id, claim['device_secret'])
        except Exception as error:  # noqa: BLE001
            client.close()
            detail = getattr(error, 'detail', None) or str(error)
            return False, f'연결하지 못했습니다: {detail}', {}
        email = data.get('email') or claim.get('email') or ''
        if (self.worker and self.worker.is_alive()) and self.paired_email and email and email != self.paired_email:
            # 발행 도중 계정이 바뀌면 엉뚱한 계정의 글을 올릴 수 있다. 중단한 뒤 다시 연결하게 한다.
            client.close()
            return False, '발행 중에는 다른 계정으로 바꿀 수 없습니다. 실행기에서 중단한 뒤 새로고침하세요', {}
        self.device_secret = claim['device_secret']
        credential_store.save(self.folder, self.device_secret, credential_store.DEVICE_FILE)
        self.ui.put(('paired', email))
        self.adopt_client(client)
        # 연결만 되고 발행이 멈춰 있으면 웹은 '켜짐'인데 아무것도 올라가지 않는다(초보자가 가장 많이 막히는 곳).
        # 홈페이지에서 연결한 것 자체가 '이 계정으로 발행하겠다'는 뜻이므로 바로 시작하고, 다음부터도 켜지면 시작한다.
        self.ui.put(('autostart', None))
        logging.getLogger().info('홈페이지 계정(%s)으로 자동 연결했습니다', email or '?')
        return True, '연결됨', {'email': email}

    def beat_once(self):
        with self.client_lock:
            client = self.client
        if not client:
            if self.device_secret and not self.closing:
                self.connect_device()   # 켤 때 인터넷이 늦게 붙은 경우
            return
        running = bool(self.worker and self.worker.is_alive())
        note = '발행 진행 중' if running else '대기 중'
        try:
            blogs = client.summary()
            note = summary_note(blogs)
            self.ui.put(('summary', ('발행 중 · ' if running else '') + note))
        except Exception:  # noqa: BLE001
            pass
        try:
            client.heartbeat(device_id=self.device_id, version=VERSION, running=running,
                             label=socket.gethostname()[:120], note=note)
            self.ui.put(('link', (True, note)))
        except Exception as error:  # noqa: BLE001
            # 신호등이 잠깐 꺼지는 것뿐이다. 발행에는 영향을 주지 않는다.
            self.ui.put(('link', (False, f'서버에 신호를 보내지 못했습니다({error})')))

    def beat_loop(self):
        while not self.closing:
            self.beat_once()
            if self.beat_wake.wait(BEAT_SECONDS):   # 종료 요청이면 바로 빠진다
                return

    # ------------------------------------------------------------ 업데이트
    def check_update(self, manual=False):
        """새 버전을 확인하고 받아 둔 뒤, 설치 여부는 사용자에게 묻는다."""
        if not updater.installed_build():
            if manual:
                self.ui.put(('status', '개발용 실행에서는 업데이트를 확인하지 않습니다'))
            return
        try:
            update = updater.fetch()
            if not update:
                logging.getLogger().info('업데이트 확인: 최신 버전입니다 (v%s)', VERSION)
                if manual:
                    self.ui.put(('status', f'최신 버전입니다 (v{VERSION})'))
                return
            if manual:
                self.ui.put(('status', f'새 버전 {update["version"]} 을 받는 중입니다…'))
            installer = updater.download(update, self.folder / 'updates')
        except Exception as error:  # noqa: BLE001
            logging.getLogger().info('업데이트 확인을 건너뜁니다: %s', error)
            if manual:
                self.ui.put(('status', f'업데이트 확인 실패: {error}'))
            return
        self.ui.put(('update', (update['version'], installer)))

    def offer_update(self, version, installer):
        if self.closing:
            return
        running = bool(self.worker and self.worker.is_alive())
        note = '\n설치하는 동안 진행 중인 발행은 멈췄다가 설치 후 이어서 실행됩니다.' if running else ''
        if not messagebox.askyesno('업데이트', f'새 버전 {version} 이 준비됐습니다. 지금 설치할까요?{note}', parent=self.root):
            self.status.set(f'새 버전 {version} 은 다음에 켤 때 설치할 수 있습니다')
            return
        try:
            updater.install(installer)
        except Exception as error:  # noqa: BLE001
            self.status.set(f'업데이트를 실행하지 못했습니다: {error}')
            return
        self.status.set('업데이트를 설치합니다. 설치가 끝나면 실행기가 다시 열립니다.')
        self.stop_event.set()
        self.root.after(1500, self.root.destroy)

    # ------------------------------------------------------------ 실행
    def start(self):
        if self.worker and self.worker.is_alive():
            return
        use_device = bool(self.device_secret) and not self.password.get()
        if not use_device and (not self.email.get().strip() or not self.password.get()):
            self.status.set('먼저 1번 [홈페이지 열어 연결하기]를 누르세요. 연결되지 않으면 [직접 로그인]을 펼쳐 홈페이지 계정으로 로그인하세요.')
            return
        self.stop_event.clear()
        try:
            account = self.paired_email if use_device else self.email.get().strip()
            args = make_args(self.server.get().strip(), account, self.password.get(), self.folder, self.stop_event)
            if use_device:
                args.device_id, args.device_secret = self.device_id, self.device_secret
        except (ValueError, OSError) as error:
            self.status.set(str(error))
            return
        if self.auto_login.get():
            credential_store.save(self.folder, self.password.get())
        self.save_settings()
        password = self.password.get()
        self.password.set('')
        self.start_button.configure(state='disabled')
        self.stop_button.configure(state='normal')
        self.status.set('서버 연결 및 자동 발행 실행 중')

        def run():
            try:
                result = asyncio.run(agent.main_async(args))
                self.output.put('실행 종료' if result == 0 else '연결 실패 — 위 오류를 확인하세요')
            except Exception as error:  # noqa: BLE001
                self.output.put(f'실행 오류: {error}')
            finally:
                args.password = None
        self.worker = threading.Thread(target=run, daemon=False)
        self.worker.start()

        if use_device:
            with self.client_lock:
                connected = self.client is not None
            if not connected:
                self.connect_device_async()
        else:
            self.connect_async(args.server, args.email, password)

    def stop(self):
        self.stop_event.set()
        self.status.set('중단 요청됨 · 진행 중인 작업의 결과를 보존한 뒤 종료합니다')
        self.stop_button.configure(state='disabled')

    def copy_logs(self):
        text = self.logs.get('1.0', 'end').strip()
        if not text:
            self.status.set('복사할 기록이 없습니다')
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status.set('기록을 복사했습니다. 문의할 때 붙여넣어 주세요.')

    def close(self):
        self.closing = True
        self.beat_wake.set()
        try:
            self.bridge.stop()
        except Exception:  # noqa: BLE001
            pass
        with self.client_lock:
            client, self.client = self.client, None
        if client:
            # 창을 닫으면 웹 신호등도 바로 꺼지게 마지막 신호를 보낸다(실패해도 그만).
            try:
                client.heartbeat(device_id=self.device_id, version=VERSION, running=False,
                                 label=socket.gethostname()[:120], note='실행기를 껐습니다')
                client.close()
            except Exception:  # noqa: BLE001
                pass
        self.stop()

    # ------------------------------------------------------------ 화면 갱신
    def poll(self):
        while True:
            try:
                line = self.output.get_nowait()
            except queue.Empty:
                break
            self.logs.configure(state='normal')
            self.logs.insert('end', line + '\n')
            if int(self.logs.index('end-1c').split('.')[0]) > 300:
                self.logs.delete('1.0', '50.0')
            self.logs.see('end')
            self.logs.configure(state='disabled')
        while True:
            try:
                kind, value = self.ui.get_nowait()
            except queue.Empty:
                break
            if kind == 'status':
                self.status.set(value)
            elif kind == 'link':
                self.set_link(*value)
            elif kind == 'paired':
                self.paired_email = value or self.paired_email
                if value:
                    self.email.set(value)
                self.save_settings()
            elif kind == 'summary':
                self.summary.set(value)
            elif kind == 'update':
                self.offer_update(*value)
            elif kind == 'autostart':
                if not (self.worker and self.worker.is_alive()):
                    self.auto_start.set(True)
                    self.save_settings()
                    self.start()
        if not self.worker or not self.worker.is_alive():
            self.start_button.configure(state='normal')
            self.stop_button.configure(state='disabled')
            if self.worker:
                self.status.set('실행이 종료되었습니다. 작업 결과는 위 기록과 웹 발행 현황에서 확인하세요.')
            if self.closing:
                self.root.destroy()
                return
        self.root.after(300, self.poll)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--self-check':
        import naver_editor, journal
        interpreter = tk.Tcl()
        Path(sys.argv[2]).write_text(json.dumps({'ok': True, 'tcl': interpreter.eval('info patchlevel'),
                                               'editor': bool(naver_editor), 'journal': bool(journal)}), encoding='utf-8')
        return
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    if not hold_single_instance():
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo('닥터보이스 자동 발행', '이미 실행 중입니다. 작업 표시줄에서 열려 있는 창을 확인하세요.')
        return
    root = tk.Tk()
    Desktop(root)
    root.mainloop()


if __name__ == '__main__':
    main()
