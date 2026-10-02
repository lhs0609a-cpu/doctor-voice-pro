"""한 PC에서 계정마다 실행기를 따로 돌리기 위한 '자리(slot)'.

창 하나가 계정 하나를 맡는다. 자리마다 기기 키·크롬 프로필·로그·설정을 따로 두어야 한다 —
한 자리를 두 계정이 돌려쓰면 크롬 로그인 세션이 섞이고, 홈페이지에서 다른 계정으로
들어갔을 때 "원스톱 자동화 프로그램이 a@naver.com 으로 연결되어 있습니다"로 막힌다
(2026-09-30 지적: "계정별로 다 실행기 다른거 아니야").

파일 구조
  DoctorVoicePro/accounts.json        {"slots": {"slot1": "a@naver.com", "slot2": "b@naver.com"}}
  DoctorVoicePro/accounts/slot1/      desktop.json · device.bin · profiles · logs · updates
옛 버전은 이 파일들을 DoctorVoicePro/ 바로 아래에 두었다 → 처음 켤 때 slot1 로 옮긴다.
옮기면 기기 키가 그대로라 다시 연결하지 않아도 된다.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# 옛 버전이 DoctorVoicePro/ 바로 아래에 두던 것들
LEGACY_NAMES = ('desktop.json', 'device.bin', 'credential.bin', 'profiles', 'logs', 'updates')
# 홈페이지가 창구 포트로 **찾아낼 수 있는** 창 수(local_bridge.PORTS 와 같아야 한다).
# 계정 수의 상한이 아니다 — 자리 이름은 계정에서 만들기 때문에 100개든 1000개든 들어간다
# (slot_for). 이 수를 넘는 창은 포트를 못 잡아 홈페이지가 '찾지는' 못하지만,
# 코드를 들고 태어난 창은 스스로 연결하므로 발행은 정상으로 돈다.
MAX_SLOTS = 16


def root() -> Path:
    return Path(os.environ.get('LOCALAPPDATA') or Path.home()) / 'DoctorVoicePro'


def index_file() -> Path:
    return root() / 'accounts.json'


def folder(slot: str) -> Path:
    return root() / 'accounts' / (slot or 'slot1')


def load_index() -> Dict[str, str]:
    """자리 → 그 자리가 맡은 계정."""
    try:
        data = json.loads(index_file().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    slots = data.get('slots')
    if not isinstance(slots, dict):
        return {}
    return {str(key): str(value or '') for key, value in slots.items()}


def save_index(slots: Dict[str, str]) -> None:
    try:
        root().mkdir(parents=True, exist_ok=True)
        index_file().write_text(json.dumps({'slots': slots}, ensure_ascii=False, indent=2), encoding='utf-8')
    except OSError as error:
        log.info('계정 자리 목록을 저장하지 못했습니다: %s', error)


def remember(slot: str, email: str) -> None:
    """이 자리가 어느 계정을 맡았는지 적어 둔다.

    다음에 아이콘을 누르면 적어 둔 자리부터 차례로 열린다 — 계정마다 같은 자리로 돌아온다."""
    if not slot:
        return
    slots = load_index()
    if slots.get(slot) == (email or ''):
        return
    slots[slot] = email or ''
    save_index(slots)


def derived_slot(email: str) -> str:
    """그 계정만의 자리 이름 — 계정 글자에서 만든다.

    번호 자리(slotN)는 MAX_SLOTS 에서 멈춰 그 뒤 계정이 **같은 자리를 돌려쓰게** 된다.
    그러면 크롬 로그인 세션이 섞여 엉뚱한 블로그에 글이 올라간다. 계정에서 만든 이름은
    겹치지 않으므로 계정이 100개여도 자리가 100개 생긴다."""
    key = (email or "").strip().lower()
    if not key:
        return fresh_slot()
    return "acct" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:10]


def slot_for(email: str) -> str:
    """그 계정이 쓸 자리. 이미 쓰던 자리가 있으면 그대로(연결을 다시 하지 않아도 된다)."""
    return slot_of(email) or derived_slot(email)


def slot_of(email: str) -> Optional[str]:
    """그 계정이 쓰던 자리. 처음 보는 계정이면 None."""
    want = (email or '').strip().lower()
    if not want:
        return None
    for slot, owner in load_index().items():
        if owner.strip().lower() == want:
            return slot
    return None


def fresh_slot(used=()) -> str:
    """아직 쓰지 않은 자리 이름."""
    taken = set(load_index()) | set(used)
    for number in range(1, MAX_SLOTS + 1):
        name = f'slot{number}'
        if name not in taken:
            return name
    return f'slot{MAX_SLOTS}'


def migrate_legacy() -> None:
    """옛 버전이 DoctorVoicePro/ 바로 아래 두던 파일을 slot1 로 옮긴다(한 번만)."""
    base = root()
    if index_file().exists():
        return
    legacy = [name for name in LEGACY_NAMES if (base / name).exists()]
    if not legacy:
        return
    target = folder('slot1')
    try:
        target.mkdir(parents=True, exist_ok=True)
        for name in legacy:
            source, destination = base / name, target / name
            if destination.exists():
                continue
            shutil.move(str(source), str(destination))
    except OSError as error:
        log.info('옛 설정을 첫 번째 자리로 옮기지 못했습니다: %s', error)
        return
    email = ''
    try:
        saved = json.loads((target / 'desktop.json').read_text(encoding='utf-8'))
        email = str(saved.get('paired_email') or '')
    except (OSError, ValueError):
        pass
    save_index({'slot1': email})
    log.info('옛 설정을 첫 번째 자리(slot1)로 옮겼습니다')


def candidates(email: str = '') -> List[Tuple[str, str]]:
    """열어 볼 자리 순서 — (자리, 그 자리의 계정).

    계정을 지정하면 그 계정의 자리 하나만 본다(없으면 빈 자리를 만든다).
    지정하지 않으면 알고 있는 자리를 차례로 본다. 아무것도 없으면 빈 목록 —
    부르는 쪽이 첫 자리를 새로 만든다."""
    migrate_legacy()
    slots = load_index()
    if email:
        return [(slot_for(email), email)]
    return [(slot, slots[slot]) for slot in sorted(slots, key=lambda name: (len(name), name))]


def label(slot: str, email: str = '') -> str:
    """창 제목과 로그에 쓰는 이름. 계정이 붙기 전에는 몇 번째 자리인지 보여 준다."""
    if email:
        return email
    number = slot[4:] if slot.startswith('slot') else slot
    return f'{number}번째 계정' if number.isdigit() else slot


def emails() -> List[str]:
    """이 PC가 맡고 있는 계정들. 홈페이지가 '이 PC에 내 계정 자리가 있나'를 볼 때 쓴다."""
    return [owner for owner in load_index().values() if owner]
