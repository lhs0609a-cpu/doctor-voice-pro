"""블로그 계정 비밀번호 암호화(Fernet). 키는 CAMPAIGN_ENCRYPTION_KEY, 없으면 SECRET_KEY 에서 파생."""
from __future__ import annotations

import base64
import hashlib
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _key() -> bytes:
    raw = (settings.CAMPAIGN_ENCRYPTION_KEY or "").strip()
    if raw:
        try:
            Fernet(raw.encode())
            return raw.encode()
        except Exception:  # noqa: BLE001
            pass
    digest = hashlib.sha256(("campaign:" + settings.SECRET_KEY).encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt(plain: Optional[str]) -> Optional[str]:
    if not plain:
        return None
    return Fernet(_key()).encrypt(plain.encode()).decode()


def decrypt(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    try:
        return Fernet(_key()).decrypt(token.encode()).decode()
    except InvalidToken:
        return None
