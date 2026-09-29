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

# 문단 하나의 길이(공백 제외). 문장을 이 범위가 될 때까지 이어 붙이고 마침표에서 끊는다.
# 2026-09-29 고객(키네스·소잠) 확정 규격.
PARA_MIN_CHARS = 35
PARA_MAX_CHARS = 50

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。？！])\s+")
_BLANK_LINE_RE = re.compile(r"\n\s*\n+")
# 줄 전체가 따옴표로 감싸인 경우에만 소제목이다. 문장 속 인용("어느 것이 제일 좋습니까" 같은)까지
# 소제목으로 올리면 본문이 제목투성이가 된다.
_HEADING_RE = re.compile(r'^\s*["“「『](?P<t>[^"”」』\n]{2,60})["”」』]\s*[.!?]?\s*$')
# 따옴표가 없어도 소제목인 모양: 한 줄이고, 짧고, 문장부호로 끝나지 않는다.
# 서버(campaign_writer.is_heading)가 사진 자리를 정할 때 쓰는 바로 그 규칙이다 — 같은 줄을
# 서버는 소제목으로 보는데 발행은 본문으로 흘려보내면, 이미 써 둔 원고들이 전부 밋밋해진다.
HEADING_MAX_CHARS = 30


def _heading_text(source: str) -> Optional[str]:
    """이 원고 문단이 소제목이면 그 글자(따옴표 제거), 아니면 None."""
    quoted = _HEADING_RE.match(source)
    if quoted:
        return quoted.group("t").strip()
    if "\n" in source or len(source) > HEADING_MAX_CHARS:
        return None
    return source if not re.search(r"[.!?…]$", source) else None


def nospace_len(text: str) -> int:
    """공백을 뺀 글자 수. 문단 길이는 이 값으로 잰다(띄어쓰기는 읽는 부담이 아니다)."""
    return len(re.sub(r"\s+", "", text or ""))


# ---------------------------------------------------------------- 모바일 포맷
def split_sentences(body: str) -> List[str]:
    """마침표·물음표·느낌표 뒤에서만 문장을 나눈다.

    줄바꿈으로는 나누지 않는다 — 원고가 한 문장을 두 줄에 걸쳐 써 두었을 때 그것까지 문장
    경계로 보면 토막이 난다. 문단 경계(빈 줄)는 split_paragraphs 가 따로 지킨다."""
    parts: List[str] = []
    for chunk in re.split(r"\n+", body or ""):
        parts.extend(p.strip() for p in _SENTENCE_SPLIT_RE.split(chunk) if p and p.strip())
    return parts


def group_sentences(sentences: Sequence[str]) -> List[str]:
    """문장들을 공백 제외 35~50자 문단으로 묶는다. 문장 중간은 절대 끊지 않는다.

    - 이어 붙였을 때 50자를 넘기면, 넘기기 전에 문단을 닫는다(넘치느니 조금 모자란 편이 낫다).
    - 35자를 채우면 닫는다.
    - 그래서 50자가 넘는 긴 문장 하나는 혼자 한 문단이 된다 — 마침표에서만 끊기 때문이다.
    """
    out: List[str] = []
    buf: List[str] = []
    for s in sentences:
        if buf and nospace_len(" ".join(buf)) + nospace_len(s) > PARA_MAX_CHARS:
            out.append(" ".join(buf))
            buf = [s]
        else:
            buf.append(s)
        if nospace_len(" ".join(buf)) >= PARA_MIN_CHARS:
            out.append(" ".join(buf))
            buf = []
    if buf:
        out.append(" ".join(buf))
    return out


def split_paragraphs(text: str) -> List[Dict[str, str]]:
    """원고 → [{kind: 'heading'|'text', text: …}]. 원고가 나눠 둔 문단은 그대로 지킨다.

    원고의 빈 줄은 글쓴이가 화제를 바꾼 자리다. 그 경계를 넘어 문장을 이어 붙이면 상관없는
    두 이야기가 한 문단에 섞인다 — 문단 묶기는 **원고 문단 안에서만** 한다."""
    out: List[Dict[str, str]] = []
    for source in _BLANK_LINE_RE.split(text or ""):
        source = source.strip()
        if not source:
            continue
        heading = _heading_text(source)
        if heading:
            out.append({"kind": "heading", "text": heading})
            continue
        for para in group_sentences(split_sentences(source)):
            out.append({"kind": "text", "text": para})
    return out


def mobile_format(text: str) -> str:
    """문단 사이는 **언제나 빈 줄 하나**(2줄 엔터). 줄바꿈이 한 칸·두 칸으로 섞이지 않는다.

    예전에는 '한 줄 한 문장, 두 문장마다 빈 줄'이라 문단 안은 1줄·문단 사이는 2줄로 섞였다
    (2026-09-29 고객 지적: "한 부분은 1줄 엔터, 다른 부분은 2줄 엔터"). 이제 모든 경계가
    빈 줄이고, 문단 하나는 공백 제외 35~50자다. 소제목은 따옴표를 떼고 한 줄로 세운다.
    이미 정리된 글에 다시 걸어도 결과가 같다."""
    return "\n\n".join(p["text"] for p in split_paragraphs(text))


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
    """에디터에 보낼 한 동작.

    kind:
      text   글자 넣기. `attrs` 에 서식({'b','i','u','color','size'})이 있으면 그 서식으로.
      bold   강조어 한 번 굵게(Ctrl+B 켜고 끄기). 서식 없는 글에서만 쓴다.
      enter  줄바꿈
      image  사진(data URL)
      para   뒤따르는 글의 문단 종류. `attrs` {'kind': 'text'|'heading'|'quote'|'list', 'level', 'ordered'}
      table  표. `attrs` {'header': bool, 'rows': [[[span…], …], …]}
    """

    kind: str
    payload: str = ""
    attrs: Optional[Dict[str, Any]] = None

    def __repr__(self) -> str:  # 테스트/로그 가독성
        if self.kind in ("text", "bold"):
            p = self.payload if len(self.payload) <= 24 else self.payload[:21] + "..."
            return f"{self.kind}({p!r})" if not self.attrs else f"{self.kind}({p!r},{_attr_tag(self.attrs)})"
        if self.kind == "image":
            return f"image(<{len(self.payload)}b>)"
        if self.kind == "para":
            return f"para({_attr_tag(self.attrs or {})})"
        if self.kind == "table":
            rows = (self.attrs or {}).get("rows") or []
            return f"table({len(rows)}x{len(rows[0]) if rows else 0})"
        return self.kind


def _attr_tag(attrs: Dict[str, Any]) -> str:
    return ",".join(f"{k}={v}" for k, v in sorted(attrs.items()) if k != "rows")


def _emphasis_regex(words: Sequence[str]) -> Optional["re.Pattern[str]"]:
    uniq = sorted(set(w.strip() for w in words if isinstance(w, str) and len(w.strip()) >= 2), key=len, reverse=True)
    if not uniq:
        return None
    return re.compile("(" + "|".join(re.escape(w) for w in uniq) + ")")


# 단위가 붙은 숫자. 사람이 손으로 쓸 때 굵게 칠하는 바로 그 자리다(2026-09-29 고객 요청:
# "숫자나, 중요한 부분 강조 표시"). 단위를 요구하는 이유는 글 안의 아무 숫자(연번·각주)까지
# 칠하면 글이 알록달록해져 정작 중요한 값이 묻히기 때문이다. 긴 단위를 먼저 적어야
# '3mm' 가 '3m'+'m' 으로 끊기지 않는다.
# 뒤에 붙는 조사(3개월'이면', 5cm'가')는 그대로 두고 숫자+단위만 칠한다. 뒤를 막는 것은
# 영문·숫자뿐이다 — 그래야 '3mg' 이 '3m'+'g' 로, '20대' 가 '2'+'0대' 로 끊기지 않는다.
_NUMBER_RE = re.compile(
    r"\d[\d,.]*\s*(?:[~-]\s*\d[\d,.]*\s*)?"
    r"(?:퍼센트|개월|번째|주일|시간|만원|천원|가지|단계|%|mm|cm|kg|ml|cc|배|회|번|차|주|일|년|분|초|원|명|건|곳|세|대|종|위|점|층|m|g)"
    r"(?![A-Za-z0-9])"
)
# 문단 하나에 숫자 강조는 이만큼까지. 더 칠하면 강조가 아니라 배경이 된다.
NUMBERS_PER_PARAGRAPH = 2


def _bold_spans(line: str, rx, word_set, bolded: set, budget: List[int]) -> List[Tuple[int, int]]:
    """이 줄에서 굵게 칠할 구간. 키워드는 문단당 한 낱말에 한 번, 숫자는 문단당 두 개까지."""
    spans: List[Tuple[int, int]] = []
    if rx:
        for m in rx.finditer(line):
            word = m.group(0)
            if word in word_set and word not in bolded:
                bolded.add(word)
                spans.append((m.start(), m.end()))
    for m in _NUMBER_RE.finditer(line):
        if budget[0] <= 0:
            break
        if any(start < m.end() and m.start() < end for start, end in spans):
            continue          # 키워드와 겹치는 자리는 두 번 칠하지 않는다
        budget[0] -= 1
        spans.append((m.start(), m.end()))
    return sorted(spans)


def plan_text(content: str, emphasize: Sequence[str]) -> List[Op]:
    """줄 단위 insertText, 줄 사이 Enter, 빈 줄(문단 경계)마다 강조 이력 초기화.

    굵게 칠하는 것은 둘이다 — 키워드(문단당 낱말마다 한 번)와 단위가 붙은 숫자(문단당 두 개까지)."""
    ops: List[Op] = []
    word_set = set(w.strip() for w in emphasize if isinstance(w, str) and len(w.strip()) >= 2)
    rx = _emphasis_regex(word_set)
    bolded: set = set()
    budget = [NUMBERS_PER_PARAGRAPH]
    lines = (content or "").split("\n")
    for i, line in enumerate(lines):
        if not line:
            bolded, budget = set(), [NUMBERS_PER_PARAGRAPH]
        elif re.fullmatch(r'https://\S+', line):
            ops.append(Op('text', line))
            if i == len(lines) - 1:
                ops.append(Op('enter'))
        else:
            cursor = 0
            for start, end in _bold_spans(line, rx, word_set, bolded, budget):
                if start > cursor:
                    ops.append(Op("text", line[cursor:start]))
                ops.append(Op("bold", line[start:end]))
                cursor = end
            if cursor < len(line):
                ops.append(Op("text", line[cursor:]))
        if i < len(lines) - 1:
            ops.append(Op("enter"))
    return ops


def plan_blocks(blocks: Sequence[Dict[str, Any]], emphasize: Sequence[str], *, reformat: bool = True) -> List[Op]:
    """블록 → 타이핑 동작. 글↔글 사이엔 빈 줄(Enter 2번), 글↔사진 사이엔 Enter 1번.

    reformat 이면 문단을 다시 묶는다(공백 제외 35~50자, 마침표에서만 끊음). 따옴표로만 이뤄진
    줄은 소제목이라 따옴표를 떼고 굵게 한 줄로 세운다. 워드 원고(reformat=False)는 글쓴이가
    잡아 둔 줄바꿈이 곧 원고이므로 손대지 않는다."""
    ops: List[Op] = []
    first = True
    prev: Optional[str] = None

    def gap(kind: str) -> None:
        nonlocal first
        if first:
            first = False
            return
        ops.append(Op("enter"))
        if prev != "image" and kind != "image":
            ops.append(Op("enter"))

    for b in blocks or []:
        t = b.get("type")
        if t == "text" and b.get("content"):
            if not reformat:
                gap("text")
                ops.extend(plan_text(b["content"], emphasize))
                prev = "text"
                continue
            for para in split_paragraphs(b["content"]):
                gap("text")
                if para["kind"] == "heading":
                    ops.append(Op("bold", para["text"]))
                else:
                    ops.extend(plan_text(para["text"], emphasize))
                prev = "text"
        elif t == "image" and b.get("image"):
            gap("image")
            ops.append(Op("image", b["image"]))
            prev = "image"
    return ops


def merge_text_ops(ops: Sequence[Op]) -> List[Op]:
    """연속된 text 를 하나로 합쳐 insertText 호출 수를 줄인다(의미 동일).
    서식이 다르면 합치지 않는다 — 합치면 뒤 글자가 앞 글자의 서식을 뒤집어쓴다."""
    out: List[Op] = []
    for op in ops:
        if op.kind == "text" and out and out[-1].kind == "text" and out[-1].attrs == op.attrs:
            out[-1] = Op("text", out[-1].payload + op.payload, op.attrs)
        else:
            out.append(op)
    return out


# ------------------------------------------------- 서식 있는 블록(rich_text_v1)
_SPAN_STYLE_KEYS = ("b", "i", "u", "color", "background", "size")


def _span_style(span: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    style = {k: span[k] for k in _SPAN_STYLE_KEYS if span.get(k)}
    return style or None


def _spans_ops(spans: Sequence[Dict[str, Any]]) -> List[Op]:
    """span 들 → text 동작. 워드 원고는 글쓴이 서식이 곧 원고라서 강조어를 더 넣지 않는다."""
    ops: List[Op] = []
    for span in spans or []:
        text = span.get("t") or ""
        if not text:
            continue
        for i, line in enumerate(text.split("\n")):
            if i:
                ops.append(Op("enter"))
            if line:
                ops.append(Op("text", line, _span_style(span)))
    return ops


def plan_rich_blocks(blocks: Sequence[Dict[str, Any]]) -> List[Op]:
    """서식 블록(docx_import 규격) → 동작. 문단 사이는 빈 줄, 글↔사진/표 사이는 한 줄.

    소제목·인용구·목록은 `para` 로 문단 종류를 바꾸고, 끝나면 본문으로 되돌린다
    (되돌리지 않으면 다음 문단까지 소제목으로 이어진다)."""
    ops: List[Op] = []
    first = True
    prev: Optional[str] = None

    def gap(kind: str) -> None:
        nonlocal first
        if first:
            first = False
            return
        ops.append(Op("enter"))
        if prev in ("text", "heading", "quote") and kind in ("text", "heading", "quote"):
            ops.append(Op("enter"))

    for block in blocks or []:
        kind = block.get("type")
        if kind == "image" and block.get("image"):
            gap("image")
            ops.append(Op("image", block["image"]))
            prev = "image"
        elif kind == "table" and block.get("rows"):
            gap("table")
            ops.append(Op("table", attrs={"header": bool(block.get("header")), "rows": block["rows"]}))
            prev = "table"
        elif kind == "list" and block.get("items"):
            gap("list")
            ops.append(Op("para", attrs={"kind": "list", "ordered": bool(block.get("ordered"))}))
            for i, item in enumerate(block["items"]):
                if i:
                    ops.append(Op("enter"))
                ops.extend(_spans_ops(item))
            ops.append(Op("para", attrs={"kind": "text"}))
            prev = "list"
        elif kind in ("text", "heading", "quote") and block.get("spans"):
            gap(kind)
            if kind == "heading":
                ops.append(Op("para", attrs={"kind": "heading", "level": int(block.get("level") or 2)}))
            elif kind == "quote":
                ops.append(Op("para", attrs={"kind": "quote"}))
            ops.extend(_spans_ops(block["spans"]))
            if kind in ("heading", "quote"):
                ops.append(Op("para", attrs={"kind": "text"}))
            prev = kind
        elif kind == 'text' and block.get('content'):
            gap(kind)
            ops.extend(plan_text(block['content'], []))
            prev = kind
    return ops


def has_formatting(blocks: Sequence[Dict[str, Any]]) -> bool:
    """서식 블록이 섞여 있나. 평문 text/image 만 오면 예전 경로로 간다."""
    return any(b.get("type") in ("heading", "quote", "list", "table") or b.get("spans")
               for b in blocks or [])


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
