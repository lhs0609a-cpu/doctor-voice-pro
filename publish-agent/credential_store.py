"""이 PC에서만 풀 수 있게 비밀 값을 보관한다(Windows DPAPI).

두 가지를 담는다.
- credential.bin: 사용자가 켠 경우의 자동 로그인 비밀번호(예전 방식, 선택)
- device.bin: 홈페이지 자동 연결로 받은 이 기기 전용 키

값은 Windows 가 로그인 계정 키로 암호화하므로 파일을 다른 PC 나 다른 계정으로 옮기면 풀리지 않는다.
Windows 가 아니면 저장하지 않는다(개발용 실행에서는 매번 새로 연결).
"""
from __future__ import annotations

import ctypes
import sys
from pathlib import Path
from typing import Optional

FILE_NAME = 'credential.bin'
DEVICE_FILE = 'device.bin'
_blob_type = None


def available() -> bool:
    return sys.platform == 'win32'


def _blob_class():
    """wintypes 는 Windows 에서만 import 된다 → 필요할 때 한 번만 만든다."""
    global _blob_type
    if _blob_type is None:
        from ctypes import wintypes

        class _Blob(ctypes.Structure):
            _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]

        _blob_type = _Blob
    return _blob_type


def _in(data: bytes):
    blob = _blob_class()()
    buffer = ctypes.create_string_buffer(data, len(data))
    blob.cbData = len(data)
    blob.pbData = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))
    blob._buffer = buffer  # 호출이 끝날 때까지 살려 둔다
    return blob


def _take(blob) -> bytes:
    try:
        return ctypes.string_at(blob.pbData, blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob.pbData)


def _protect(secret: str) -> bytes:
    out = _blob_class()()
    if not ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(_in(secret.encode('utf-8'))), 'doctorvoice', None, None, None, 0, ctypes.byref(out)):
        raise OSError('비밀 값을 암호화하지 못했습니다')
    return _take(out)


def _unprotect(data: bytes) -> str:
    out = _blob_class()()
    if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(_in(data)), None, None, None, None, 0, ctypes.byref(out)):
        raise OSError('저장된 값을 풀지 못했습니다')
    return _take(out).decode('utf-8')


def save(folder: Path, secret: str, name: str = FILE_NAME) -> bool:
    """성공하면 True. 실패해도 예외를 올리지 않는다 — 없으면 다시 연결하면 된다."""
    if not available() or not secret:
        return False
    try:
        Path(folder).mkdir(parents=True, exist_ok=True)
        (Path(folder) / name).write_bytes(_protect(secret))
        return True
    except Exception:  # noqa: BLE001
        return False


def load(folder: Path, name: str = FILE_NAME) -> Optional[str]:
    """저장해 둔 값. 없거나 다른 PC·계정이면 None."""
    path = Path(folder) / name
    if not available() or not path.is_file():
        return None
    try:
        return _unprotect(path.read_bytes())
    except Exception:  # noqa: BLE001
        clear(folder, name)  # 못 푸는 파일은 남겨둘 이유가 없다
        return None


def clear(folder: Path, name: str = FILE_NAME) -> None:
    try:
        (Path(folder) / name).unlink(missing_ok=True)
    except OSError:
        pass
