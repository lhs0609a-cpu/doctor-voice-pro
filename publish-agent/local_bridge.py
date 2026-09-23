"""홈페이지가 같은 PC의 실행기를 찾는 작은 창구(127.0.0.1 전용).

로그인된 홈페이지가 여기로 1회용 연결 코드를 건네면 실행기가 그 계정으로 연결된다.
사용자는 아무것도 입력하지 않는다.

지키는 것
- 127.0.0.1 에만 붙는다 — 다른 PC에서는 보이지 않는다.
- 우리 홈페이지가 보낸 요청만 받는다(allowed_origin). 다른 사이트가 이 PC에서 열려도 코드를 넣지 못한다.
- Host 헤더가 127.0.0.1/localhost 가 아니면 거절한다(DNS 리바인딩 방어).
- 받는 것은 서버가 발급한 1회용 코드뿐이다. 코드가 진짜인지는 실행기가 서버에 물어 확인한다.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Dict, Optional, Tuple

log = logging.getLogger("bridge")

PORTS = (47815, 47816, 47817)
ALLOWED_ORIGINS = (
    'https://doctor-voice-pro-ghwi.vercel.app',
    'http://localhost:3000',
    'http://127.0.0.1:3000',
)
# Vercel 은 배포마다 주소를 새로 만든다: doctor-voice-pro-ghwi-git-<브랜치>-<팀>.vercel.app.
# 주소 하나만 적어 두면 미리보기 배포에서 창구가 문을 닫아 '실행기를 찾지 못했습니다'가 된다.
# 끝까지 맞춰 보는 정규식이라 doctor-voice-pro-ghwi.vercel.app.evil.com 같은 흉내는 걸리지 않는다.
PREVIEW_HOST = re.compile(r'doctor-voice-pro[a-z0-9-]*\.vercel\.app')
# 나중에 우리 도메인을 붙이면 실행기를 새로 빌드하지 않고 여기에 적어 연다(쉼표로 여러 개).
EXTRA_ORIGINS_ENV = 'DOCTORVOICE_SITE_ORIGINS'
LOCAL_HOSTS = ('127.0.0.1', 'localhost')
MAX_BODY = 4096


def extra_origins() -> Tuple[str, ...]:
    raw = os.environ.get(EXTRA_ORIGINS_ENV) or ''
    return tuple(part.strip().rstrip('/').lower() for part in raw.split(',') if part.strip())


def allowed_origin(origin: Optional[str]) -> Optional[str]:
    """우리 홈페이지가 보낸 요청이면 그 Origin 을 그대로, 아니면 None.

    돌려주는 값은 받은 문자열 그대로다 — 크롬은 Access-Control-Allow-Origin 이 보낸 값과
    글자까지 같아야 응답을 읽게 해 준다."""
    if not origin:
        return None
    seen = origin.strip().rstrip('/').lower()
    if seen in ALLOWED_ORIGINS or seen in extra_origins():
        return origin
    scheme, _, host = seen.partition('://')
    if scheme == 'https' and PREVIEW_HOST.fullmatch(host):
        return origin
    return None


class LocalBridge:
    """status() → dict 를 돌려주고, pair(code) → (ok, message, extra) 를 처리한다."""

    def __init__(self, status: Callable[[], Dict], pair: Callable[[str], Tuple[bool, str, Dict]],
                 wake: Optional[Callable[[], Tuple[bool, str]]] = None):
        self.status = status
        self.pair = pair
        # 홈페이지에서 예약을 걸자마자 '지금 가져가라'고 두드리는 창구.
        self.wake = wake
        self.server: Optional[ThreadingHTTPServer] = None
        self.port: Optional[int] = None

    def start(self) -> Optional[int]:
        """비어 있는 포트 하나에 붙는다. 모두 막혀 있으면 None(자동 연결만 못 할 뿐 실행기는 돈다)."""
        handler = _handler_for(self)
        for port in PORTS:
            try:
                self.server = ThreadingHTTPServer(('127.0.0.1', port), handler)
            except OSError:
                continue
            self.server.daemon_threads = True
            self.port = self.server.server_address[1]   # 0 을 주면 운영체제가 고른 포트
            threading.Thread(target=self.server.serve_forever, daemon=True).start()
            log.info("홈페이지 자동 연결 창구: 127.0.0.1:%d", self.port)
            return self.port
        log.warning("자동 연결 창구를 열 포트가 없습니다(%s). 이메일로 로그인하면 연결됩니다", PORTS)
        return None

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None


def _handler_for(bridge: LocalBridge):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # 요청마다 줄을 남기지 않는다
            pass

        # -------------------------------------------------------- 검사
        def _origin(self) -> Optional[str]:
            return allowed_origin(self.headers.get('Origin'))

        def _local_host(self) -> bool:
            host = (self.headers.get('Host') or '').rsplit(':', 1)[0].strip('[]').lower()
            return host in LOCAL_HOSTS

        def _send(self, code: int, body: Optional[Dict] = None):
            data = json.dumps(body or {}, ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            origin = self._origin()
            if origin:
                self.send_header('Access-Control-Allow-Origin', origin)
                self.send_header('Vary', 'Origin')
                # 공개 사이트 → 로컬 기기 요청에 크롬이 요구하는 허락(Private/Local Network Access)
                self.send_header('Access-Control-Allow-Private-Network', 'true')
                self.send_header('Access-Control-Allow-Local-Network', 'true')
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)

        def _refuse(self) -> bool:
            if not self._local_host():
                self._send(403, {'error': 'host'})
                return True
            if not self._origin():
                self._send(403, {'error': 'origin'})
                return True
            return False

        # -------------------------------------------------------- 경로
        def do_OPTIONS(self):
            if self._refuse():
                return
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin', self._origin())
            self.send_header('Vary', 'Origin')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.send_header('Access-Control-Allow-Private-Network', 'true')
            self.send_header('Access-Control-Allow-Local-Network', 'true')
            self.send_header('Access-Control-Max-Age', '600')
            self.send_header('Content-Length', '0')
            self.end_headers()

        def do_GET(self):
            if self._refuse():
                return
            if self.path.split('?')[0] != '/status':
                return self._send(404, {'error': 'not found'})
            try:
                self._send(200, bridge.status())
            except Exception as error:  # noqa: BLE001
                self._send(500, {'error': str(error)})

        def do_POST(self):
            if self._refuse():
                return
            path = self.path.split('?')[0]
            if path == '/wake':
                if not bridge.wake:
                    return self._send(404, {'error': 'not found'})
                try:
                    ok, message = bridge.wake()
                except Exception as error:  # noqa: BLE001
                    return self._send(500, {'ok': False, 'error': str(error)})
                return self._send(200, {'ok': ok, 'message': message})
            if path != '/pair':
                return self._send(404, {'error': 'not found'})
            size = int(self.headers.get('Content-Length') or 0)
            if size <= 0 or size > MAX_BODY:
                return self._send(400, {'error': '요청 형식이 올바르지 않습니다'})
            try:
                body = json.loads(self.rfile.read(size) or b'{}')
                code = str(body.get('code') or '').strip()
            except (ValueError, AttributeError):
                return self._send(400, {'error': '요청 형식이 올바르지 않습니다'})
            if not code:
                return self._send(400, {'error': '연결 코드가 없습니다'})
            try:
                ok, message, extra = bridge.pair(code)
            except Exception as error:  # noqa: BLE001
                log.warning("자동 연결 실패: %s", error)
                return self._send(502, {'ok': False, 'error': str(error)})
            self._send(200 if ok else 409, {'ok': ok, 'message': message, **(extra or {})})

    return Handler
