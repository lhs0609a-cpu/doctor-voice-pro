"""자동 업데이트: 매니페스트 확인 → 설치 파일 내려받기 → SHA-256 검증 → 조용히 설치.

코드 서명이 없으므로 해시 검증과 신뢰 호스트 확인이 유일한 방어선입니다. 둘 중 하나라도
어긋나면 내려받은 파일을 지우고 업데이트를 포기합니다(실행기는 계속 씁니다).
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx

from version import VERSION

MANIFEST_URL = 'https://doctor-voice-pro-ghwi.vercel.app/downloads/launcher-version.json'
TRUSTED_HOSTS = ('doctor-voice-pro-ghwi.vercel.app',)
INSTALL_FLAGS = ('/SILENT', '/CLOSEAPPLICATIONS', '/RESTARTAPPLICATIONS', '/NORESTART', '/SUPPRESSMSGBOXES')
MAX_BYTES = 400 * 1024 * 1024


def version_tuple(text: str):
    parts = str(text).strip().split('.')
    if not 1 <= len(parts) <= 4 or not all(part.isdigit() for part in parts):
        raise ValueError(f'버전 형식이 아닙니다: {text!r}')
    return tuple(int(part) for part in parts) + (0,) * (4 - len(parts))


def is_newer(remote: str, local: str = VERSION) -> bool:
    return version_tuple(remote) > version_tuple(local)


def trusted_url(url: Any) -> bool:
    try:
        parsed = urlparse(str(url))
    except ValueError:
        return False
    return parsed.scheme == 'https' and parsed.hostname in TRUSTED_HOSTS


def read_manifest(payload: Any, local: str = VERSION) -> Optional[Dict[str, str]]:
    """설치해도 되는 새 버전이면 그 내용을, 아니면 None 을 돌려줍니다."""
    if not isinstance(payload, dict):
        return None
    version, url, digest = payload.get('version'), payload.get('url'), payload.get('sha256')
    if not all(isinstance(value, str) for value in (version, url, digest)):
        return None
    digest = digest.strip().lower()
    if len(digest) != 64 or any(letter not in '0123456789abcdef' for letter in digest):
        return None
    if not trusted_url(url):
        return None
    try:
        if not is_newer(version, local):
            return None
    except ValueError:
        return None
    return {'version': version.strip(), 'url': url, 'sha256': digest}


def fetch(url: str = MANIFEST_URL, *, client: Optional[httpx.Client] = None, local: str = VERSION):
    """새 버전이 있으면 매니페스트를, 없거나 확인 실패면 None. 예외는 밖으로 내보내지 않습니다."""
    owned = client is None
    client = client or httpx.Client(timeout=10.0, follow_redirects=False)
    try:
        response = client.get(url)
        response.raise_for_status()
        return read_manifest(response.json(), local)
    except (httpx.HTTPError, ValueError):
        return None
    finally:
        if owned:
            client.close()


def download(update: Dict[str, str], folder: Path, *, client: Optional[httpx.Client] = None) -> Path:
    """설치 파일을 받아 해시를 확인합니다. 어긋나면 지우고 ValueError."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"DoctorVoiceAutopilotSetup-{update['version']}.exe"
    owned = client is None
    client = client or httpx.Client(timeout=300.0, follow_redirects=False)
    digest = hashlib.sha256()
    written = 0
    try:
        with client.stream('GET', update['url']) as response:
            response.raise_for_status()
            with target.open('wb') as out:
                for chunk in response.iter_bytes():
                    written += len(chunk)
                    if written > MAX_BYTES:
                        raise ValueError('설치 파일이 너무 큽니다')
                    digest.update(chunk)
                    out.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        if owned:
            client.close()
    if digest.hexdigest() != update['sha256']:
        target.unlink(missing_ok=True)
        raise ValueError('설치 파일 검증에 실패했습니다')
    return target


def install(path: Path):
    """설치 프로그램을 조용히 실행합니다. 실행기는 곧바로 종료해 주세요(설치가 파일을 덮어씁니다)."""
    if sys.platform != 'win32':
        raise RuntimeError('Windows에서만 설치할 수 있습니다')
    return subprocess.Popen([str(path), *INSTALL_FLAGS], close_fds=True)


def installed_build() -> bool:
    """설치본으로 실행 중일 때만 업데이트합니다(개발 중 실행은 건드리지 않음)."""
    return sys.platform == 'win32' and bool(getattr(sys, 'frozen', False))
