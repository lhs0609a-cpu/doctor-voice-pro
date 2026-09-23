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
SITE = 'https://doctor-voice-pro-ghwi.vercel.app'
WEBSITE = SITE + '/dashboard/one-stop'
CONNECT_PAGE = SITE + '/launcher/connect'   # 실행기가 열면 로그인된 홈페이지가 이 PC를 승인한다
BEAT_SECONDS = 60          # 서버가 150초 침묵을 '꺼짐'으로 본다 → 그보다 짧게
CONNECT_POLL_SECONDS = 2   # 승인됐는지 묻는 간격
CONNECT_WAIT_SECONDS = 600 # 요청이 살아 있는 동안만 기다린다(서버와 같은 값)
UPDATE_EVERY_BEATS = 360   # 하트비트 360번 = 6시간마다 새 버전을 다시 본다


# ── 화면 색과 모양 ──────────────────────────────────────────────
# tkinter 기본값은 회색 상자라 낡아 보인다. 흰 카드 + 옅은 바탕 + 파란 단추로 정리한다.
FONT = 'Malgun Gothic'
BG = '#F8FAFC'        # 홈페이지와 같은 밝은 바탕
CARD = '#FFFFFF'      # 카드
INK = '#0F172A'       # 본문 글자
MUTED = '#64748B'     # 설명 글자
BLUE = '#3454EB'      # 홈페이지의 브랜드 블루
GREEN = '#059669'     # 연결됨
AMBER = '#D97706'     # 확인 필요
RED = '#DC2626'

PRIMARY = dict(bg=BLUE, fg='white', activebackground='#2843CA', activeforeground='white',
               disabledforeground='#AFC0FF', relief='flat', bd=0, padx=22, pady=11,
               font=(FONT, 10, 'bold'), cursor='hand2', highlightthickness=0)
GHOST = dict(bg='#EEF2F8', fg=INK, activebackground='#E2E8F0', activeforeground=INK,
             disabledforeground='#94A3B8', relief='flat', bd=0, padx=18, pady=11,
             font=(FONT, 10), cursor='hand2', highlightthickness=0)


def card(parent, **pack):
    """흰 바탕에 여백을 둔 상자 하나. 화면은 이 상자들을 쌓아 만든다.

    내용은 안쪽 틀에 담고, 카드 통째로 숨길 일이 있으면 돌려받은 틀의 .box 를 pack_forget 한다."""
    box = tk.Frame(parent, bg=CARD, highlightbackground='#E2E8F0', highlightthickness=1)
    box.pack(**pack)
    inner = ttk.Frame(box, padding=22, style='Card.TFrame')
    inner.pack(fill='both', expand=True)
    inner.box = box
    return inner


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
        self.connect_thread = None              # 브라우저 승인을 기다리는 자동 연결
        self.connect_wake = threading.Event()   # 먼저 연결되면 그 기다림을 깨운다
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

        root.title('닥터보이스 프로 · PC 실행기')
        root.geometry('840x850')
        root.minsize(760, 680)
        root.configure(bg=BG)
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('.', font=(FONT, 10), background=CARD, foreground=INK)
        style.configure('Card.TFrame', background=CARD)
        style.configure('Page.TFrame', background=BG)
        style.configure('Card.TLabel', background=CARD, foreground=INK)
        style.configure('Muted.TLabel', background=CARD, foreground=MUTED, font=(FONT, 9))
        style.configure('Title.TLabel', background=CARD, foreground=INK, font=(FONT, 19, 'bold'))
        style.configure('Head.TLabel', background=CARD, foreground=INK, font=(FONT, 11, 'bold'))
        style.configure('Status.TLabel', background=CARD, foreground=INK, font=(FONT, 12, 'bold'))
        style.configure('Ghost.TButton', padding=(12, 8), font=(FONT, 9), background=CARD,
                        bordercolor='#E2E8F0', lightcolor=CARD, darkcolor=CARD, relief='flat')
        style.map('Ghost.TButton', background=[('active', '#EEF2FF')], foreground=[('disabled', '#94A3B8')])
        style.configure('TEntry', padding=8, fieldbackground=BG, bordercolor='#CBD5E1', lightcolor=BG, darkcolor=BG)
        style.configure('TCheckbutton', background=CARD, foreground=INK)
        style.map('TCheckbutton', background=[('active', CARD)])
        style.layout('Vertical.TScrollbar', [('Vertical.Scrollbar.trough', {'sticky': 'ns', 'children': [
            ('Vertical.Scrollbar.thumb', {'expand': '1', 'sticky': 'nswe'})]})])
        style.configure('Vertical.TScrollbar', background='#CBD5E1', troughcolor=BG,
                        bordercolor=BG, lightcolor='#CBD5E1', darkcolor='#CBD5E1', width=10,
                        gripcount=0, borderwidth=0)
        style.map('Vertical.TScrollbar', background=[('active', '#94A3B8'), ('pressed', '#94A3B8')])

        # 전체 내용이 스크롤되므로 작은 화면에서도 펼친 설정에 접근할 수 있다.
        surface = tk.Frame(root, bg=BG)
        surface.pack(fill='both', expand=True)
        canvas = tk.Canvas(surface, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(surface, orient='vertical', command=canvas.yview)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        page = ttk.Frame(canvas, padding=26, style='Page.TFrame')
        page_window = canvas.create_window((0, 0), window=page, anchor='nw')
        page.bind('<Configure>', lambda _e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(page_window, width=e.width))
        def scroll_page(event):
            if event.widget is not self.logs and page.winfo_reqheight() > canvas.winfo_height():
                canvas.yview_scroll(-int(event.delta / 120), 'units')
        root.bind('<MouseWheel>', scroll_page)

        # ── 머리말 ───────────────────────────────────────────────
        head = tk.Frame(page, bg=BG)
        head.pack(fill='x', pady=(0, 24))
        mark = tk.Canvas(head, width=42, height=42, bg=BLUE, highlightthickness=0)
        mark.pack(side='left', padx=(0, 12))
        mark.create_line(8, 22, 15, 22, 19, 12, 24, 31, 28, 20, 35, 20,
                         fill='white', width=3, joinstyle='round', capstyle='round')
        brand = tk.Frame(head, bg=BG)
        brand.pack(side='left')
        tk.Label(brand, text='닥터보이스 프로', bg=BG, fg=INK, font=(FONT, 13, 'bold')).pack(anchor='w')
        tk.Label(brand, text='by 플라톤마케팅', bg=BG, fg=MUTED, font=(FONT, 8)).pack(anchor='w')
        tk.Label(head, text=f'PC 실행기  /  v{VERSION}', bg=BG, fg=MUTED, font=(FONT, 9)).pack(side='right')
        tk.Label(page, text='블로그 운영, 이어서 자동으로', bg=BG, fg=INK,
                 font=(FONT, 21, 'bold')).pack(anchor='w')
        tk.Label(page, text='홈페이지에서 준비한 원고를 이 PC가 네이버에 예약 등록합니다.',
                 bg=BG, fg=MUTED, font=(FONT, 10)).pack(anchor='w', pady=(7, 22))

        # ── 상태 ─────────────────────────────────────────────────
        # 이 카드만 보면 지금 무슨 일이 일어나는지 알아야 한다. 점 하나 + 굵은 한 줄 + 설명 한 줄.
        state = card(page, fill='x')
        ttk.Label(state, text='연결 및 발행 상태', style='Muted.TLabel').pack(anchor='w', pady=(0, 12))
        dot_row = ttk.Frame(state, style='Card.TFrame')
        dot_row.pack(fill='x')
        self.dot = tk.Canvas(dot_row, width=12, height=12, bg=CARD, highlightthickness=0)
        self.dot_id = self.dot.create_oval(2, 2, 11, 11, fill=AMBER, outline='')
        self.dot.pack(side='left', pady=(4, 0))
        self.link = tk.StringVar(value='연결 확인 중…')
        self.link_label = ttk.Label(dot_row, textvariable=self.link, style='Status.TLabel')
        self.link_label.pack(side='left', padx=8)
        self.status = tk.StringVar(value='브라우저가 열리면 그대로 두세요. 홈페이지에 로그인돼 있으면 곧 연결됩니다.')
        ttk.Label(state, textvariable=self.status, style='Muted.TLabel', wraplength=660,
                  justify='left').pack(anchor='w', pady=(6, 0))
        self.summary = tk.StringVar(value='')
        ttk.Label(state, textvariable=self.summary, style='Muted.TLabel', wraplength=660,
                  justify='left').pack(anchor='w')

        buttons = ttk.Frame(state, style='Card.TFrame')
        buttons.pack(fill='x', pady=(14, 0))
        self.start_button = tk.Button(buttons, text='자동 발행 시작', command=self.start, **PRIMARY)
        self.start_button.pack(side='left')
        self.stop_button = tk.Button(buttons, text='실행 중단', command=self.stop, state='disabled', **GHOST)
        self.stop_button.pack(side='left', padx=8)
        ttk.Button(buttons, text='홈페이지 열기', style='Ghost.TButton',
                   command=lambda: webbrowser.open(WEBSITE)).pack(side='right')

        # ── 처음 연결 안내 — 연결되면 통째로 사라진다 ────────────
        self.guide = card(page, fill='x', pady=(10, 0))
        ttk.Label(self.guide, text='홈페이지에 연결하기', style='Head.TLabel').pack(anchor='w')
        ttk.Label(self.guide, style='Muted.TLabel', justify='left', wraplength=660,
                  text='이 창을 켜면 브라우저가 열리면서 홈페이지 계정에 저절로 연결됩니다. 따로 로그인하지 않아도 됩니다.\n'
                       '로그인 화면이 뜨면 한 번만 로그인하세요. 한 번 연결하면 다음부터는 창을 켜기만 하면 됩니다.'
                  ).pack(anchor='w', pady=(4, 10))
        tk.Button(self.guide, text='지금 연결하기', command=self.auto_connect_async, **PRIMARY).pack(anchor='w')

        # ── 기록 ─────────────────────────────────────────────────
        logs = card(page, fill='both', expand=True, pady=(14, 0))
        self.activity_card = logs.box
        log_head = ttk.Frame(logs, style='Card.TFrame')
        log_head.pack(fill='x')
        ttk.Label(log_head, text='활동 기록', style='Head.TLabel').pack(side='left')
        ttk.Button(log_head, text='복사', style='Ghost.TButton', command=self.copy_logs).pack(side='right')
        log_body = tk.Frame(logs, bg=BG)
        log_body.pack(fill='both', expand=True, pady=(12, 0))
        self.logs = tk.Text(log_body, height=7, state='disabled', wrap='word', relief='flat', bd=0,
                            bg=BG, fg=MUTED, font=(FONT, 9), padx=14, pady=12, spacing1=3, spacing3=4)
        log_scroll = ttk.Scrollbar(log_body, orient='vertical', command=self.logs.yview)
        log_scroll.pack(side='right', fill='y')
        self.logs.configure(yscrollcommand=log_scroll.set)
        self.logs.pack(side='left', fill='both', expand=True)
        ttk.Label(logs, style='Muted.TLabel', justify='left', wraplength=660,
                  text='네이버 로그인·보안문자는 실행기가 연 Chrome 창에서 처리하세요.\n'
                       'PC를 끄면 새 예약 등록만 멈춥니다. 이미 네이버에 걸어둔 예약은 그대로 발행됩니다.'
                  ).pack(anchor='w', pady=(8, 0))

        # ── 설정(접어 둔다) ──────────────────────────────────────
        self.server = tk.StringVar(value=saved.get('server', SERVER))
        self.email = tk.StringVar(value=saved.get('email', ''))
        self.password = tk.StringVar()
        self.auto_login = tk.BooleanVar(value=bool(saved.get('auto_login')))
        self.auto_start = tk.BooleanVar(value=bool(saved.get('auto_start')))

        settings_bar = ttk.Frame(page, style='Page.TFrame')
        settings_bar.pack(fill='x', pady=(16, 0))
        toggle = ttk.Button(settings_bar, text='직접 로그인 / 서버 설정 펼치기', style='Ghost.TButton')
        toggle.pack(side='left')
        ttk.Button(settings_bar, text='업데이트 확인', style='Ghost.TButton',
                   command=lambda: self.check_update(manual=True)).pack(side='right')
        self.manual = manual = card(page)
        manual.box.pack_forget()   # 설정은 접어 둔 채로 시작한다
        options = ttk.Frame(manual, style='Card.TFrame')
        ttk.Checkbutton(options, text='이 PC에서 자동 로그인', variable=self.auto_login,
                        command=self.on_auto_login_toggle).pack(side='left')
        ttk.Checkbutton(options, text='켜지면 바로 발행 시작', variable=self.auto_start,
                        command=self.save_settings).pack(side='left', padx=14)
        options.pack(fill='x', pady=(0, 10))
        for title, var, secret in [('서버 주소 (기본값 그대로 두세요)', self.server, False),
                                   ('닥터보이스 이메일', self.email, False),
                                   ('닥터보이스 비밀번호 (네이버 비밀번호가 아닙니다)', self.password, True)]:
            ttk.Label(manual, text=title, style='Muted.TLabel').pack(anchor='w')
            entry = ttk.Entry(manual, textvariable=var, show='•' if secret else '')
            entry.pack(fill='x', pady=(2, 8))
            if secret:
                entry.bind('<Return>', lambda _e: self.start())
        self.connect_button = ttk.Button(manual, text='입력한 계정으로 연결', style='Ghost.TButton', command=self.connect_now)
        self.connect_button.pack(anchor='w')

        def toggle_manual():
            if manual.box.winfo_manager():
                manual.box.pack_forget()
                toggle.configure(text='직접 로그인 / 서버 설정 펼치기')
            else:
                manual.box.pack(fill='x', pady=(8, 0))
                toggle.configure(text='직접 로그인 / 서버 설정 접기')
        toggle.configure(command=toggle_manual)

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
            # 처음 켠 PC다. 사용자가 아무것도 누르지 않아도 브라우저를 열어 스스로 연결한다.
            self.set_link(False, '홈페이지를 열어 이 PC를 연결하는 중…')
            self.restore_login()
            self.root.after(400, self.auto_connect_async)

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
        """상태 카드의 점과 굵은 한 줄. 웹 신호등과 같은 뜻이다.

        연결되면 처음 연결 안내는 통째로 감춘다 — 다 끝난 안내가 남아 있으면 뭘 더 해야 하나 싶어진다."""
        running = bool(self.worker and self.worker.is_alive())
        if connected:
            who = f' · {self.paired_email}' if self.paired_email else ''
            self.link.set(('자동 발행 중' if running else '연결됨') + who)
            self.paint_dot(GREEN)
            if self.guide.box.winfo_manager():
                self.guide.box.pack_forget()
        else:
            self.link.set('연결 확인 필요')
            self.paint_dot(AMBER)
            if not self.guide.box.winfo_manager():
                self.guide.box.pack(fill='x', pady=(14, 0), before=self.activity_card)
        if detail:
            self.status.set(detail)

    def paint_dot(self, color):
        self.dot.itemconfigure(self.dot_id, fill=color)

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
                # 홈페이지에서 이 PC의 연결을 끊었다. 버려진 키를 지우고 스스로 다시 연결을 청한다.
                self.device_secret = None
                credential_store.clear(self.folder, credential_store.DEVICE_FILE)
                self.ui.put(('link', (False, '연결이 해제되었습니다 — 브라우저를 열어 다시 연결합니다')))
                self.ui.put(('reconnect', None))
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
        # 한 번 연결한 PC는 켜기만 하면 되어야 한다. 대기 글이 없으면 크롬을 열지 않고 조용히 기다린다.
        self.ui.put(('autostart', None))
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
        if not self.may_switch_to(email):
            # 발행 도중 계정이 바뀌면 엉뚱한 계정의 글을 올릴 수 있다. 중단한 뒤 다시 연결하게 한다.
            client.close()
            return False, '발행 중에는 다른 계정으로 바꿀 수 없습니다. 실행기에서 중단한 뒤 새로고침하세요', {}
        self.adopt_pairing(claim['device_secret'], email, client)
        return True, '연결됨', {'email': email}

    def may_switch_to(self, email):
        """발행 중에 다른 계정으로 갈아타지 않는다 — 엉뚱한 계정의 블로그에 글이 올라간다."""
        running = bool(self.worker and self.worker.is_alive())
        return not (running and self.paired_email and email and email != self.paired_email)

    def adopt_pairing(self, device_secret, email, client):
        """연결 성공 뒤 공통 처리 — 창구로 받았든 실행기가 직접 물어서 받았든 같다."""
        self.device_secret = device_secret
        credential_store.save(self.folder, device_secret, credential_store.DEVICE_FILE)
        self.connect_wake.set()          # 기다리고 있던 자동 연결이 있으면 멈춘다
        self.ui.put(('paired', email))
        self.adopt_client(client)
        # 연결만 되고 발행이 멈춰 있으면 웹은 '켜짐'인데 아무것도 올라가지 않는다(초보자가 가장 많이 막히는 곳).
        # 홈페이지에서 연결한 것 자체가 '이 계정으로 발행하겠다'는 뜻이므로 바로 시작하고, 다음부터도 켜지면 시작한다.
        self.ui.put(('autostart', None))
        logging.getLogger().info('홈페이지 계정(%s)으로 자동 연결했습니다', email or '?')

    # ------------------------------------------------------------ 실행기가 먼저 손을 드는 연결
    # 창구(127.0.0.1)는 브라우저가 로컬 접근을 막으면 닿지 않는다. 그 때도 연결되게 반대 방향을 둔다.
    # 실행기가 서버에 연결 요청을 만들고 기본 브라우저로 승인 페이지를 연다 → 로그인돼 있으면 사용자는 아무것도 하지 않는다.
    def auto_connect_async(self):
        if self.connect_thread and self.connect_thread.is_alive():
            self.status.set('이미 브라우저에서 연결을 기다리는 중입니다. 열린 홈페이지 창을 확인하세요')
            return
        self.connect_wake.clear()
        self.connect_thread = threading.Thread(target=self.auto_connect, daemon=True)
        self.connect_thread.start()

    def auto_connect(self):
        if self.device_secret and self.client:
            return
        server = self.server_url if valid_server(self.server_url) else SERVER
        client = ServerClient(server.rstrip('/'), timeout=20.0)
        try:
            request = client.pair_request(self.device_id, socket.gethostname()[:120])
        except Exception as error:  # noqa: BLE001
            client.close()
            detail = getattr(error, 'detail', None) or error
            self.ui.put(('link', (False, f'서버에 닿지 못했습니다({detail}). 인터넷을 확인한 뒤 [지금 연결하기]를 누르세요')))
            return
        try:
            webbrowser.open(f"{CONNECT_PAGE}?r={request['request_id']}")
        except Exception:  # noqa: BLE001  브라우저가 안 열려도 아래 안내로 이어 간다
            pass
        self.ui.put(('status', '브라우저가 열렸습니다. 홈페이지에 로그인돼 있으면 곧바로 연결됩니다(입력할 것 없음).'))
        self.ui.put(('link', (False, '홈페이지에서 이 PC를 연결하는 중…')))

        waited = 0
        while waited < min(CONNECT_WAIT_SECONDS, int(request.get('expires_in') or CONNECT_WAIT_SECONDS)):
            if self.closing or self.connect_wake.wait(CONNECT_POLL_SECONDS):
                client.close()          # 창구로 먼저 연결됐거나 창을 닫았다
                return
            waited += CONNECT_POLL_SECONDS
            try:
                answer = client.pair_poll(request['request_id'], self.device_id)
            except ServerError as error:
                if error.status == 404:     # 요청이 만료·사용됨 — 다시 누르게 안내한다
                    break
                continue
            except Exception:  # noqa: BLE001  인터넷이 잠시 끊긴 경우 — 계속 기다린다
                continue
            if answer.get('status') != 'ok':
                continue
            email = answer.get('email') or ''
            if not self.may_switch_to(email):
                client.close()
                self.ui.put(('link', (False, '발행 중에는 다른 계정으로 바꿀 수 없습니다. [실행 중단] 후 다시 연결하세요')))
                return
            try:
                client.device_login(self.device_id, answer['device_secret'])
            except Exception as error:  # noqa: BLE001
                client.close()
                self.ui.put(('link', (False, f'연결은 승인됐지만 로그인하지 못했습니다({error})')))
                return
            self.adopt_pairing(answer['device_secret'], email, client)
            return
        client.close()
        self.ui.put(('link', (False, '연결을 기다리다 시간이 지났습니다. [지금 연결하기]를 다시 눌러 주세요')))

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
        beats = 0
        while not self.closing:
            self.beat_once()
            beats += 1
            # 켜 둔 채 며칠 쓰는 PC가 많다. 켤 때 한 번만 보면 새 버전을 영영 못 받는다.
            if beats % UPDATE_EVERY_BEATS == 0:
                self.check_update()
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
            self.status.set('아직 홈페이지에 연결되지 않았습니다. 브라우저를 열어 연결합니다 — 로그인돼 있으면 바로 시작됩니다.')
            self.auto_connect_async()
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
                if result == 3:
                    # 인증이 끊긴 것뿐이다. 새 열쇠를 받아 스스로 이어서 시작한다.
                    self.output.put('서버 연결이 끊어져 다시 연결합니다 — 연결되면 발행을 이어서 합니다')
                    self.ui.put(('reconnect', None))
                else:
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
        self.connect_wake.set()
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
            elif kind == 'reconnect':
                if not self.closing:
                    self.auto_connect_async()
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


def hand_over_to_installed() -> bool:
    """내려받아 풀어 둔 옛 복사본으로 켜졌으면 설치본을 대신 열고 True.

    설치 프로그램은 설치 폴더만 덮어쓴다. Downloads 에 풀어 둔 exe 는 그대로 남아서,
    그 창을 계속 켜는 사람에게는 업데이트가 몇 번을 성공해도 옛 화면만 보인다.
    그 시절 실행기에는 연결 창구도 없어 홈페이지가 영영 이 PC를 찾지 못한다.
    묻지 않고 넘기면 뭘 눌렀는지 모르게 창이 바뀌므로, 한 번 확인하고 넘긴다."""
    try:
        installed = updater.stray_copy()
    except Exception:  # noqa: BLE001  확인에 실패했다고 실행기를 못 켜게 할 이유는 없다
        return False
    if not installed:
        return False
    root = tk.Tk()
    root.withdraw()
    switch = messagebox.askyesno('닥터보이스 자동 발행', '\n'.join([
        '지금 연 파일은 예전에 내려받아 풀어 둔 복사본입니다.',
        '이 복사본은 업데이트되지 않아 홈페이지와 연결되지 않습니다.',
        '',
        '설치된 최신 실행기가 따로 있습니다:',
        str(installed.parent),
        '',
        '설치된 쪽을 열까요? (이 창은 닫힙니다)']))
    root.destroy()
    if not switch:
        return False
    try:
        updater.launch(installed)
    except OSError:
        return False    # 못 열었으면 지금 것이라도 쓰게 둔다
    return True


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--self-check':
        import naver_editor, journal, rich_editor, html_clipboard
        interpreter = tk.Tcl()
        Path(sys.argv[2]).write_text(json.dumps({'ok': True, 'tcl': interpreter.eval('info patchlevel'),
                                               'editor': bool(naver_editor), 'journal': bool(journal)}), encoding='utf-8')
        return
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    # 뮤텍스를 잡기 전에 확인한다 — 넘겨줄 참이면 이 복사본이 자리를 차지하지 않아야 한다.
    if hand_over_to_installed():
        return
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
