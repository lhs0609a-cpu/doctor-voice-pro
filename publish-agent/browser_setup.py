"""처음 켠 PC에서도 브라우저가 준비되게 한다.

실행기는 네이버를 크롬으로 조종한다. 그런데 설치 파일에는 브라우저가 들어 있지 않다
(50MB — Chromium 하나가 150MB 다). 지금까지는 개발용 PC에 크롬과 Playwright 브라우저가
이미 있어서 드러나지 않았을 뿐, **아무것도 안 깔린 새 PC에서는 발행이 시작조차 안 된다**
(2026-09-27 확인: 번들에 .local-browsers 폴더가 없다).

설치 파일에 Chromium 을 넣으면 200MB 가 되어 내려받기가 부담스럽다. 대신 브라우저를
**처음 한 번만** 받아 둔다. Playwright 의 내려받기 도구(node.exe + cli.js)는 이미 번들에
들어 있으므로 인터넷만 되면 된다.

순서는 셋이다.
1) 이 PC 에 구글 크롬이 있으면 그걸 쓴다 — 아무것도 받지 않는다(대부분의 PC 가 여기서 끝난다).
2) 예전에 받아 둔 Playwright 브라우저가 있으면 그걸 쓴다.
3) 둘 다 없을 때만 받는다.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, List, Optional

log = logging.getLogger(__name__)

CHROME_PATHS = (
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
)
DOWNLOAD_TIMEOUT = 15 * 60      # 회선이 느린 병원도 있다


def system_chrome() -> Optional[Path]:
    """이 PC 에 설치된 구글 크롬. 없으면 None."""
    if sys.platform != "win32":
        return None
    for raw in CHROME_PATHS:
        path = Path(os.path.expandvars(raw))
        if path.is_file():
            return path
    return None


def browsers_dir() -> Path:
    """Playwright 가 브라우저를 두는 곳. 실행기를 업데이트해도 이 폴더는 남는다."""
    custom = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if custom:
        return Path(custom)
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "ms-playwright"


def bundled_chromium() -> bool:
    """이미 받아 둔 Chromium 이 있는가."""
    folder = browsers_dir()
    if not folder.is_dir():
        return False
    return any(p.name.startswith("chromium-") and p.is_dir() for p in folder.iterdir())


def ready() -> bool:
    """지금 당장 브라우저를 띄울 수 있는가."""
    return bool(system_chrome()) or bundled_chromium()


def _driver() -> Optional[List[str]]:
    """번들된 Playwright 내려받기 도구. 없으면 None."""
    try:
        from playwright._impl._driver import compute_driver_executable
        parts = compute_driver_executable()
    except Exception as error:  # noqa: BLE001
        log.info("Playwright 드라이버를 찾지 못했습니다: %s", error)
        return None
    parts = [str(p) for p in (parts if isinstance(parts, (list, tuple)) else [parts])]
    if parts and Path(parts[0]).exists():
        return parts
    # 얼린 실행 파일에서는 경로 계산이 어긋날 수 있다. 번들 안을 직접 찾아본다.
    root = Path(getattr(sys, "_MEIPASS", "")) if getattr(sys, "frozen", False) else Path(__file__).parent
    for base in (root, root / "app", Path(sys.executable).parent / "app"):
        node = base / "playwright" / "driver" / "node.exe"
        cli = base / "playwright" / "driver" / "package" / "cli.js"
        if node.is_file() and cli.is_file():
            return [str(node), str(cli)]
    log.info("Playwright 드라이버 파일을 번들에서 찾지 못했습니다")
    return None


def install_chromium(progress: Optional[Callable[[str], None]] = None) -> bool:
    """Chromium 을 받는다. 받았으면 True.

    실패해도 예외를 올리지 않는다 — 크롬이 나중에 깔릴 수도 있고, 사람이 직접 깔 수도 있다.
    """
    say = progress or (lambda _m: None)
    parts = _driver()
    if not parts:
        say("브라우저 내려받기 도구를 찾지 못했습니다. 구글 크롬을 설치해 주세요.")
        return False

    env = dict(os.environ)
    env.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(browsers_dir()))
    say("처음 한 번, 브라우저를 내려받습니다 (약 150MB · 회선에 따라 몇 분 걸립니다)")
    try:
        done = subprocess.run(
            [*parts, "install", "chromium"],
            env=env, timeout=DOWNLOAD_TIMEOUT,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        say("브라우저 내려받기가 너무 오래 걸려 멈췄습니다. 인터넷 연결을 확인해 주세요.")
        return False
    except Exception as error:  # noqa: BLE001
        say(f"브라우저를 내려받지 못했습니다: {error}")
        return False

    if done.returncode == 0 and bundled_chromium():
        say("브라우저 준비를 마쳤습니다.")
        return True
    tail = (done.stdout or b"").decode("utf-8", "replace").strip().splitlines()
    log.warning("브라우저 내려받기 실패(코드 %s): %s", done.returncode, tail[-1] if tail else "")
    say("브라우저를 내려받지 못했습니다. 구글 크롬을 설치하시면 그것으로 동작합니다.")
    return False


def prepare(progress: Optional[Callable[[str], None]] = None) -> bool:
    """발행을 시작하기 전에 부른다. 준비됐으면 True."""
    if ready():
        return True
    return install_chromium(progress)
