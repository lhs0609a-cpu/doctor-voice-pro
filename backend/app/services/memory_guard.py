"""쓰고 버린 메모리를 운영체제에 돌려주고, 한도에 닿기 전에 알린다.

발행 claim 한 건은 사진을 base64 로 바꿔 응답에 싣는다. GIF 는 장당 평균 2.8MB 라
한 글에 몇 장만 들어가도 수십 MB 가 한 번에 잡히고, 그게 DB 로 한 번(payload) ·
응답으로 한 번 더 복사된다. 다 쓰고 놓아도 **RSS 는 내려오지 않는다** — glibc 는
한 번 늘린 힙을 프로세스 안에 그대로 쥐고 있다가 다음 요청에 재사용한다. 그래서
묶음이 돌수록 톱니처럼 올라가기만 하고, 끝내 한도에 부딪혀 커널이 프로세스를 죽인다.

2026-10-27 실측(메모리 1GB 시절):
  - 14:09:09 `exit_code=137, oom_killed=true` — 커널이 죽였다. 13:01 에도 한 번.
  - 부팅 직후 300MB → 발행 20분 만에 568MB. 한 묶음이 지나갈 때 1분에 52MB 가
    올라가고, 그 자리에 머물렀다.
  - 죽을 때마다 부팅을 다시 하므로 그 사이 요청은 거절도 못 되고 매달려 있었다
    (Fly 300초 · 홈페이지 180초). 사람 눈에는 '무한 로딩'으로 보였다.
  - 발행 묶음은 22~23시에 몰려 있다(최근 7일 시도 929건 중 73건). 그래서 저녁·밤에
    자주 났다.

여기서 하는 일은 두 가지뿐이다.
  1) 파이썬이 놓은 공간을 malloc_trim 으로 **운영체제까지** 내려보낸다. 톱니를 깎는다.
  2) 한도의 85% 를 넘으면 로그에 띄운다. 2026-10-27 까지 OOM 전에 남은 경고는
     하나도 없었다 — 죽은 뒤의 재시작 줄만 있었다.

MALLOC_ARENA_MAX 는 Dockerfile 에서 함께 묶어 둔다(스레드마다 힙을 따로 늘리지
않게). 사진 처리를 run_in_threadpool 로 돌리기 때문에 그게 없으면 trim 으로도
따라잡지 못한다.
"""
from __future__ import annotations

import ctypes
import gc
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# 돌려주기는 **매 주기 그냥 한다**(1분에 한 번). 문턱을 두면 그 선까지는 톱니가
# 자라도록 내버려 두는 셈이고, 그러면 한도를 올려 번 여유를 다시 톱니로 메운다.
# trim 은 '놓은 공간'만 내려보내므로 쓰고 있는 메모리는 건드리지 않고, 1분에 한 번은
# 비용이 없다. 되돌린 양이 작으면 로그에도 남기지 않는다.

# 한도에 이만큼 닿으면 로그에 띄운다. 100% 가 되면 커널이 말없이 죽인다.
WARN_USED_PCT = 85
CRITICAL_USED_PCT = 95
# 이만큼은 돌아왔을 때만 로그에 적는다(MB). 1분마다 같은 줄을 쌓지 않는다.
TRIM_LOG_MB = 20

_last_warned_pct: Optional[int] = None
_libc: Optional[ctypes.CDLL] = None
_libc_tried = False


def _read_int(path: str, key: str = "") -> Optional[int]:
    """파일에서 숫자 하나. 없거나 못 읽으면 None — 리눅스가 아니면 전부 None 이다."""
    try:
        text = Path(path).read_text()
    except OSError:
        return None
    if not key:
        text = text.strip()
        return int(text) if text.isdigit() else None
    for line in text.splitlines():
        if line.startswith(key):
            digits = "".join(c for c in line if c.isdigit())
            return int(digits) if digits else None
    return None


def rss_bytes() -> Optional[int]:
    """이 프로세스가 지금 실제로 쥐고 있는 메모리."""
    kb = _read_int("/proc/self/status", "VmRSS:")
    return kb * 1024 if kb else None


def limit_bytes() -> Optional[int]:
    """커널이 이 프로세스를 죽이는 선. cgroup 한도가 있으면 그것이 진짜 한도다."""
    for path in ("/sys/fs/cgroup/memory.max",
                 "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        value = _read_int(path)
        # cgroup v2 는 한도가 없으면 'max' 라고 적는다(_read_int 가 None 을 준다).
        # v1 은 아주 큰 수를 적으므로 머신 전체 메모리보다 크면 한도가 아니라고 본다.
        if value and value < (1 << 50):
            return value
    kb = _read_int("/proc/meminfo", "MemTotal:")
    return kb * 1024 if kb else None


def report() -> Dict[str, Any]:
    """지금 얼마나 쓰고 있는지. 사람이 보고 판단할 숫자만."""
    out: Dict[str, Any] = {}
    rss, limit = rss_bytes(), limit_bytes()
    if rss:
        out["rss_mb"] = round(rss / 1048576, 1)
    if limit:
        out["limit_mb"] = round(limit / 1048576)
    if rss and limit:
        out["used_pct"] = round(rss * 100 / limit)
    return out


def trim() -> Optional[float]:
    """놓은 공간을 운영체제에 돌려준다. 돌려준 MB, 재지 못했으면 None.

    glibc 가 아니거나(musl·윈도) libc 를 못 찾으면 조용히 아무것도 하지 않는다."""
    global _libc, _libc_tried
    before = rss_bytes()
    gc.collect()
    if not _libc_tried:
        _libc_tried = True
        try:
            candidate = ctypes.CDLL("libc.so.6")
            candidate.malloc_trim.argtypes = [ctypes.c_size_t]
            candidate.malloc_trim.restype = ctypes.c_int
            _libc = candidate
        except (OSError, AttributeError) as error:
            logger.info("[메모리] malloc_trim 을 쓸 수 없습니다(%s) — 되돌리기는 건너뜁니다", error)
            _libc = None
    if _libc is None:
        return None
    try:
        _libc.malloc_trim(0)
    except Exception:  # noqa: BLE001  여기서 터져 유지보수 루프를 멈추게 하지 않는다
        logger.exception("[메모리] malloc_trim 실패")
        return None
    after = rss_bytes()
    if before is None or after is None:
        return None
    return round((before - after) / 1048576, 1)


def watch() -> Dict[str, Any]:
    """유지보수 루프가 1분마다 부른다. 돌려주고, 한도에 가까우면 알린다."""
    global _last_warned_pct
    info = report()
    pct = info.get("used_pct")
    if not isinstance(pct, int):
        return info
    freed = trim()
    if freed and freed >= TRIM_LOG_MB:
        info = report()
        logger.info("[메모리] %sMB 를 운영체제에 돌려주었습니다 (%d%% → %s%%)",
                    freed, pct, info.get("used_pct"))
        if isinstance(info.get("used_pct"), int):
            pct = info["used_pct"]
    if pct < WARN_USED_PCT:
        _last_warned_pct = None
        return info
    # 같은 구간에서 1분마다 같은 줄을 쌓지 않는다 — 1%p 움직였을 때만 다시 적는다.
    if _last_warned_pct is not None and abs(pct - _last_warned_pct) < 1:
        return info
    _last_warned_pct = pct
    log = logger.critical if pct >= CRITICAL_USED_PCT else logger.warning
    log("[메모리] %d%% 사용 (%sMB / %sMB). 100%% 가 되면 커널이 서버를 말없이 죽이고"
        " (exit 137) 다시 뜨는 동안 로그인·발행이 전부 매달린다 — fly scale memory 로"
        " 한도를 올려야 한다.", pct, info.get("rss_mb"), info.get("limit_mb"))
    return info
