"""브라우저 없이 검증 가능한 순수 로직.

- 모바일 가독성 포맷(chrome-extension/background.js mobileFormat 포트, 멱등)
- 강조어 정리(pickEmphasize 포트)
- 블록 → 타이핑 계획(typeBlocksInterleaved + typeBody 포트)
- 예약 시각 파싱/10분 내림
- data URL 디코드
"""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# background.js 와 같은 상수 (backend/app/services/post_formatter.py 규칙과 동일)
MOBILE_LINE_MAX = 45
SENTENCES_PER_GROUP = 2

_CONNECTIVE_RE = re.compile(
    r"(?:지만|는데|은데|면서|어서|아서|여서|라서|니까|므로|거나|도록)\s"
    r"|(?<=[가-힣][가-힣])(?<!그리)(?:고|며)\s"
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。？！])\s+|\n+")


# ---------------------------------------------------------------- 모바일 포맷
def _find_cut(s: str) -> int:
    n = len(s)
    mid = n / 2
    best = -1

    def consider(i: int) -> None:
        nonlocal best
        if i < n * 0.3 or i > n * 0.7:
            return
        if best < 0 or abs(i - mid) < abs(best - mid):
            best = i

    for i, ch in enumerate(s):
        if ch == ",":
            consider(i)
    if best >= 0:
        return best
    for m in _CONNECTIVE_RE.finditer(s):
        consider(m.start() + len(m.group(0)) - 1)
    if best >= 0:
        return best
    for i, ch in enumerate(s):
        if ch == " ":
            consider(i)
    return best


def _split_long(s: str) -> List[str]:
    if len(s) <= MOBILE_LINE_MAX:
        return [s]
    cut = _find_cut(s)
    if cut < 0:
        return [s]
    return [s[: cut + 1].strip(), *_split_long(s[cut + 1 :].strip())]


def split_sentences(body: str) -> List[str]:
    return [p.strip() for p in _SENTENCE_SPLIT_RE.split(body or "") if p and p.strip()]


def mobile_format(text: str) -> str:
    """한 줄 한 문장, 두 문장마다 빈 줄. 이미 정리된 글에 다시 걸어도 결과가 같다."""
    lines: List[str] = []
    for s in split_sentences(text):
        lines.extend(_split_long(s))
    groups = ["\n".join(lines[i : i + SENTENCES_PER_GROUP]) for i in range(0, len(lines), SENTENCES_PER_GROUP)]
    return "\n\n".join(g for g in groups if g)


def pick_emphasize(raw: Optional[Iterable[Any]]) -> List[str]:
    """'#' 제거, 2글자 미만 제외, 중복 제거(순서 유지)."""
    out: List[str] = []
    for w in raw or []:
        if not isinstance(w, str):
            continue
        w = re.sub(r"^#", "", w).strip()
        if len(w) >= 2 and w not in out:
            out.append(w)
    return out


# ---------------------------------------------------------------- 타이핑 계획
@dataclass(frozen=True)
class Op:
    """에디터에 보낼 한 동작. kind: text | bold | enter | image"""

    kind: str
    payload: str = ""

    def __repr__(self) -> str:  # 테스트/로그 가독성
        if self.kind in ("text", "bold"):
            p = self.payload if len(self.payload) <= 24 else self.payload[:21] + "..."
            return f"{self.kind}({p!r})"
        if self.kind == "image":
            return f"image(<{len(self.payload)}b>)"
        return self.kind


def _emphasis_regex(words: Sequence[str]) -> Optional["re.Pattern[str]"]:
    uniq = sorted(set(w.strip() for w in words if isinstance(w, str) and len(w.strip()) >= 2), key=len, reverse=True)
    if not uniq:
        return None
    return re.compile("(" + "|".join(re.escape(w) for w in uniq) + ")")


def plan_text(content: str, emphasize: Sequence[str]) -> List[Op]:
    """background.js typeBody 포트: 줄 단위 insertText, 줄 사이 Enter,
    빈 줄(문단 경계)마다 강조 이력 초기화, 문단당 키워드 1회만 Ctrl+B."""
    ops: List[Op] = []
    rx = _emphasis_regex(emphasize)
    word_set = set(w.strip() for w in emphasize if isinstance(w, str) and len(w.strip()) >= 2)
    bolded: set = set()
    lines = (content or "").split("\n")
    for i, line in enumerate(lines):
        if not line:
            bolded = set()
        else:
            if re.fullmatch(r'https://\S+', line):
                ops.append(Op('text', line))
                if i == len(lines) - 1:
                    ops.append(Op('enter'))
            elif rx:
                for part in rx.split(line):
                    if not part:
                        continue
                    if part in word_set and part not in bolded:
                        bolded.add(part)
                        ops.append(Op("bold", part))
                    else:
                        ops.append(Op("text", part))
            else:
                ops.append(Op("text", line))
        if i < len(lines) - 1:
            ops.append(Op("enter"))
    return ops


def plan_blocks(blocks: Sequence[Dict[str, Any]], emphasize: Sequence[str], *, reformat: bool = True) -> List[Op]:
    """background.js typeBlocksInterleaved 포트.
    글→글 사이엔 Enter 2번(빈 줄), 글↔이미지 사이엔 Enter 1번."""
    ops: List[Op] = []
    first = True
    prev: Optional[str] = None
    for b in blocks or []:
        t = b.get("type")
        if t == "text" and b.get("content"):
            content = mobile_format(b["content"]) if reformat else b["content"]
            if not first:
                ops.append(Op("enter"))
                if prev == "text":
                    ops.append(Op("enter"))
            ops.extend(plan_text(content, emphasize))
            first, prev = False, "text"
        elif t == "image" and b.get("image"):
            if not first:
                ops.append(Op("enter"))
            ops.append(Op("image", b["image"]))
            first, prev = False, "image"
    return ops


def merge_text_ops(ops: Sequence[Op]) -> List[Op]:
    """연속된 text 를 하나로 합쳐 insertText 호출 수를 줄인다(의미 동일)."""
    out: List[Op] = []
    for op in ops:
        if op.kind == "text" and out and out[-1].kind == "text":
            out[-1] = Op("text", out[-1].payload + op.payload)
        else:
            out.append(op)
    return out


# ---------------------------------------------------------------- 예약 시각
def floor_minute(dt: datetime, step: int = 10) -> datetime:
    """네이버 예약 분 select 는 00/10/…/50 만 허용 → 내림."""
    return dt.replace(minute=(dt.minute // step) * step, second=0, microsecond=0)


def parse_schedule(value: str) -> datetime:
    """'YYYY-MM-DDTHH:MM' (KST naive). 초/타임존이 붙어 있어도 naive 로 정규화."""
    if not value:
        raise ValueError("schedule.datetime 이 비어 있습니다")
    dt = datetime.fromisoformat(value.strip())
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone(timedelta(hours=9))).replace(tzinfo=None)
    return floor_minute(dt)


def schedule_is_safe(dt: datetime, now: datetime, margin_minutes: int = 15) -> Tuple[bool, str]:
    """예약 시각이 임박/경과면 네이버가 '지금'으로 처리할 위험 → 발행하지 않는다."""
    if dt <= now + timedelta(minutes=margin_minutes):
        return False, f"예약 시각({dt:%Y-%m-%d %H:%M})이 현재({now:%H:%M})로부터 {margin_minutes}분 이내라 즉시 발행 위험 — 중단"
    return True, ""


# ---------------------------------------------------------------- data URL
_DATA_URL_RE = re.compile(r"^data:(?P<mime>[^;,]+)?(?:;charset=[^;,]+)?(?P<b64>;base64)?,(?P<body>.*)$", re.S)


def decode_data_url(data_url: str) -> Tuple[str, bytes]:
    """→ (mime, bytes). base64 가 아니면 percent-decoded 문자열 바이트."""
    m = _DATA_URL_RE.match(data_url or "")
    if not m:
        raise ValueError("data URL 형식이 아닙니다")
    mime = m.group("mime") or "image/jpeg"
    body = m.group("body")
    if m.group("b64"):
        body = re.sub(r"\s+", "", body)
        body += "=" * (-len(body) % 4)
        return mime, base64.b64decode(body)
    from urllib.parse import unquote_to_bytes

    return mime, unquote_to_bytes(body)


def ext_for_mime(mime: str) -> str:
    return {"image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp"}.get(mime.lower(), "jpg")


def exif_make_and_time(data: bytes):
    """JPEG 의 EXIF 에서 (기종, 촬영시각)만 읽는다. 실행기에는 Pillow 가 없어 표준 라이브러리로 직접 푼다.
    못 읽으면 (None, None)."""
    from datetime import datetime

    try:
        if data[:2] != b"\xff\xd8":
            return None, None
        i = 2
        while i + 4 <= len(data) and data[i] == 0xFF:
            marker, seg = data[i + 1], int.from_bytes(data[i + 2:i + 4], "big")
            if marker == 0xE1 and data[i + 4:i + 10] == b"Exif\x00\x00":
                t = data[i + 10:i + 2 + seg]
                bo = "little" if t[:2] == b"II" else "big"
                u16 = lambda o: int.from_bytes(t[o:o + 2], bo)  # noqa: E731
                u32 = lambda o: int.from_bytes(t[o:o + 4], bo)  # noqa: E731

                def entries(off):
                    out = {}
                    for k in range(u16(off)):
                        e = off + 2 + 12 * k
                        tag, typ, cnt = u16(e), u16(e + 2), u32(e + 4)
                        if typ == 2:      # ASCII
                            vo = e + 8 if cnt <= 4 else u32(e + 8)
                            out[tag] = t[vo:vo + cnt].split(b"\x00")[0].decode("ascii", "ignore")
                        elif typ in (4, 13):  # LONG / IFD 포인터
                            out[tag] = u32(e + 8)
                    return out

                ifd0 = entries(u32(4))
                shot = ifd0.get(0x0132)
                if 0x8769 in ifd0:
                    shot = entries(ifd0[0x8769]).get(0x9003) or shot
                when = datetime.strptime(shot, "%Y:%m:%d %H:%M:%S") if shot else None
                return ifd0.get(0x010F), when
            if marker == 0xDA:   # 본문 시작 — 그 뒤엔 EXIF 가 없다
                break
            i += 2 + seg
    except Exception:  # noqa: BLE001 — 깨진 EXIF 는 이름만 기본값으로
        pass
    return None, None


def camera_filename(data: bytes, ext: str = "jpg") -> str:
    """사진 EXIF 의 기종·촬영시각에 어울리는 파일 이름.

    매번 같은 틀(image_타임스탬프_번호)로 올리면 그 이름 자체가 흔적이 된다. 서버가 넣은 메타값과
    이름이 맞아야 자연스럽다: 아이폰·캐논 IMG_1234.JPG, 소니 DSC01234.JPG, 삼성·LG 20260812_143512.jpg,
    샤오미 IMG_20260812_143512.jpg. 같은 사진은 다시 올려도 같은 이름이다(내용으로 난수를 고정)."""
    import hashlib
    import random
    from datetime import datetime, timedelta

    rnd = random.Random(hashlib.sha1(data).digest())
    make, shot = exif_make_and_time(data) if ext == "jpg" else (None, None)
    if shot is None:
        shot = datetime.now() - timedelta(days=rnd.randint(2, 90), seconds=rnd.randint(0, 86399))
    ts = shot.strftime("%Y%m%d_%H%M%S")
    m = (make or "").lower()
    if ext != "jpg":
        return f"{ts}.{ext}"
    if "apple" in m or "canon" in m:
        return f"IMG_{rnd.randint(1000, 9999)}.JPG"
    if "sony" in m:
        return f"DSC{rnd.randint(1000, 99999):05d}.JPG"
    if "xiaomi" in m:
        return f"IMG_{ts}.jpg"
    if "samsung" in m or "lg" in m:
        return f"{ts}.jpg"
    return rnd.choice((f"{ts}.jpg", f"IMG_{ts}.jpg", f"KakaoTalk_{ts[:8]}_{rnd.randint(100000000, 999999999)}.jpg"))
