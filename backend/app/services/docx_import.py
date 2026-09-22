"""워드(.docx) → 발행 블록.

서식을 살려서 읽는다: 굵게·기울임·밑줄·글자색·글자크기, 소제목, 인용구, 표, 문서 안 사진.

문서 순서를 지키려고 body 의 자식을 직접 순회한다. `doc.paragraphs` 는 표 안 문단을 건너뛰기
때문에 그것만 읽으면 표가 통째로 사라진다 — 지금까지 업로드가 표를 조용히 잃던 이유다.

블록 규격(발행 실행기와 공유):
    {"type": "text",    "spans": [span…]}
    {"type": "heading", "level": 1|2|3, "spans": [span…]}
    {"type": "quote",   "spans": [span…]}
    {"type": "list",    "ordered": bool, "items": [[span…], …]}
    {"type": "table",   "header": bool, "rows": [[[span…], …], …]}
    {"type": "image",   "image": "data:image/png;base64,…", "name": "사진.png"}
span = {"t": "글자", "b": 굵게, "i": 기울임, "u": 밑줄, "color": "#RRGGBB", "size": 15.0}
서식이 없는 span 은 키를 아예 넣지 않는다(전송량과 눈으로 읽기 위해).

옛 실행기는 {"type":"text","content":…} 만 안다. 그래서 모든 블록에 평문 `content` 를 같이
넣어 두고, 서버가 능력(capabilities)에 따라 골라 보낸다.
"""
from __future__ import annotations

import base64
import io
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

MAX_IMAGE_BYTES = 8 * 1024 * 1024        # 한 장 상한. 넘으면 버리고 경고한다
MAX_IMAGES = 30
MAX_TABLE_CELLS = 400
TITLE_MAX = 60

# 한국어 워드는 스타일 이름이 '제목 1', '인용'이다. style_id 는 보통 영어라 그것을 먼저 본다.
_HEADING_RE = re.compile(r"^(heading|title)\s*(\d)?$|^제목\s*(\d)?$", re.I)
_QUOTE_RE = re.compile(r"quote|인용", re.I)
_LIST_RE = re.compile(r"^list|list\s*paragraph|목록|글머리|번호", re.I)
_ORDERED_RE = re.compile(r"number|decimal|번호", re.I)


@dataclass
class ParsedDoc:
    title: str
    blocks: List[Dict[str, Any]]
    warnings: List[str] = field(default_factory=list)
    # 원고 안에 걸려 있던 링크들 [{"text": 보이는 글자, "url": 주소}]. 본문에 그대로 살려 넣는다.
    links: List[Dict[str, str]] = field(default_factory=list)

    @property
    def text(self) -> str:
        """정적 검사·글자수·유사도에 쓰는 평문. 블록 사이는 빈 줄로."""
        return "\n\n".join(p for p in (block_text(b) for b in self.blocks) if p)


# ─────────────────────────────────────────────────────────── span / 평문
def _clean(value: Optional[str]) -> str:
    # 워드가 넣는 비분리 공백·제로폭 문자는 에디터에서 깨져 보인다.
    return (value or "").replace("\xa0", " ").replace("​", "")


def _span(text: str, *, bold=False, italic=False, underline=False,
          color: Optional[str] = None, size: Optional[float] = None,
          background: Optional[str] = None) -> Dict[str, Any]:
    span: Dict[str, Any] = {"t": text}
    if bold:
        span["b"] = True
    if italic:
        span["i"] = True
    if underline:
        span["u"] = True
    if color:
        span["color"] = color
    if background:
        span["background"] = background
    if size:
        span["size"] = size
    return span


def spans_text(spans: List[Dict[str, Any]]) -> str:
    return "".join(s.get("t", "") for s in spans)


def block_text(block: Dict[str, Any]) -> str:
    kind = block.get("type")
    if kind in ("text", "heading", "quote"):
        return spans_text(block.get("spans") or [])
    if kind == "list":
        return "\n".join(spans_text(item) for item in block.get("items") or [])
    if kind == "table":
        return "\n".join(" | ".join(spans_text(cell) for cell in row) for row in block.get("rows") or [])
    return ""


def _merge(spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """워드는 한 문장을 맞춤법 검사 흔적 때문에 run 여러 개로 쪼개 둔다. 서식이 같으면 도로 붙인다."""
    out: List[Dict[str, Any]] = []
    for span in spans:
        if not span.get("t"):
            continue
        if out:
            last = out[-1]
            if {k: v for k, v in last.items() if k != "t"} == {k: v for k, v in span.items() if k != "t"}:
                last["t"] += span["t"]
                continue
        out.append(dict(span))
    return out


# ─────────────────────────────────────────────────────────── 워드 읽기
def _color_of(run) -> Optional[str]:
    try:
        rgb = run.font.color.rgb if run.font.color is not None else None
    except (AttributeError, ValueError):       # 테마 색은 rgb 가 없다
        return None
    if rgb is None:
        return None
    value = f"#{rgb}".lower()
    return None if value in ("#000000", "#auto") else value


def _background_of(run) -> Optional[str]:
    properties = run._r.rPr
    if properties is None:
        return None
    palette = {'yellow':'#ffff00','green':'#00ff00','cyan':'#00ffff','magenta':'#ff00ff',
               'blue':'#0000ff','red':'#ff0000','darkBlue':'#000080','darkCyan':'#008080',
               'darkGreen':'#008000','darkMagenta':'#800080','darkRed':'#800000',
               'darkYellow':'#808000','darkGray':'#808080','lightGray':'#c0c0c0',
               'black':'#000000','white':'#ffffff'}
    highlight = properties.find(f'{W}highlight')
    if highlight is not None:
        value = palette.get(highlight.get(f'{W}val'))
        if value:
            return value
    shading = properties.find(f'{W}shd')
    fill = shading.get(f'{W}fill', '') if shading is not None else ''
    return '#' + fill.lower() if re.fullmatch(r'[0-9a-fA-F]{6}', fill) else None


def _size_of(run, paragraph) -> Optional[float]:
    for source in (run.font, getattr(run.style, "font", None), getattr(paragraph.style, "font", None)):
        size = getattr(source, "size", None) if source is not None else None
        if size is not None:
            try:
                return round(float(size.pt), 1)
            except (AttributeError, TypeError):
                continue
    return None


def _images_in(run, part, warnings: List[str], taken: List[int]) -> List[Dict[str, Any]]:
    """run 안의 그림(인라인·배치 모두). 문서 순서를 지키려고 run 을 훑을 때 같이 꺼낸다."""
    out: List[Dict[str, Any]] = []
    for blip in run._r.iter(f"{A}blip"):
        rid = blip.get(f"{R}embed") or blip.get(f"{R}link")
        if not rid:
            continue
        if taken[0] >= MAX_IMAGES:
            warnings.append(f"사진이 {MAX_IMAGES}장을 넘어 뒤쪽은 넣지 않았습니다")
            break
        try:
            image = part.related_parts[rid]
            blob, content_type = image.blob, (image.content_type or "image/png")
        except Exception as e:  # noqa: BLE001
            warnings.append(f"사진 하나를 읽지 못해 건너뜁니다 ({e})")
            continue
        if len(blob) > MAX_IMAGE_BYTES:
            warnings.append(f"사진 한 장이 너무 커서({len(blob) // 1024 // 1024}MB) 넣지 않았습니다")
            continue
        taken[0] += 1
        out.append({"type": "image", "content": "",
                    "image": f"data:{content_type};base64,{base64.b64encode(blob).decode()}",
                    "name": getattr(image, "partname", "").rpartition("/")[2] or f"사진{taken[0]}.png"})
    return out


def _paragraph_kind(paragraph) -> Tuple[str, int]:
    """문단 스타일 → (종류, 소제목 단계). 한국어 워드 스타일 이름도 본다."""
    style = paragraph.style
    names = [getattr(style, "style_id", "") or "", getattr(style, "name", "") or ""]
    for name in names:
        match = _HEADING_RE.match(name.strip().replace(" ", " "))
        if match:
            level = next((int(g) for g in match.groups() if g and g.isdigit()), 1)
            return "heading", max(1, min(3, level))
    # 스타일이 없어도 개요 수준이 잡혀 있으면 소제목으로 본다.
    outline = paragraph._p.find(f"{W}pPr/{W}outlineLvl")
    if outline is not None:
        try:
            return "heading", max(1, min(3, int(outline.get(f"{W}val", "0")) + 1))
        except (TypeError, ValueError):
            pass
    if any(_QUOTE_RE.search(name) for name in names):
        return "quote", 0
    if paragraph._p.find(f"{W}pPr/{W}numPr") is not None or any(_LIST_RE.search(n) for n in names):
        return "list", 0
    return "text", 0


def _ordered_list(paragraph) -> bool:
    """번호 매기기인지 글머리 기호인지. numbering.xml 을 못 읽으면 글머리 기호로 본다."""
    names = [getattr(paragraph.style, "style_id", "") or "", getattr(paragraph.style, "name", "") or ""]
    if any(_ORDERED_RE.search(name) for name in names):
        return True
    num_pr = paragraph._p.find(f"{W}pPr/{W}numPr")
    if num_pr is None:
        return False
    num_id = num_pr.find(f"{W}numId")
    if num_id is None:
        return False
    try:
        numbering = paragraph.part.numbering_part.element
        wanted = num_id.get(f"{W}val")
        abstract = next((n.find(f"{W}abstractNumId").get(f"{W}val")
                         for n in numbering.iter(f"{W}num") if n.get(f"{W}numId") == wanted), None)
        for node in numbering.iter(f"{W}abstractNum"):
            if node.get(f"{W}abstractNumId") != abstract:
                continue
            fmt = node.find(f"{W}lvl/{W}numFmt")
            return bool(fmt is not None and fmt.get(f"{W}val") not in (None, "bullet", "none"))
    except Exception:  # noqa: BLE001
        return False
    return False


def _hyperlink_url(node, paragraph) -> str:
    """w:hyperlink 가 가리키는 바깥 주소. 문서 안 책갈피(anchor)면 빈 문자열."""
    rid = node.get(f"{R}id")
    if not rid:
        return ""
    try:
        rel = paragraph.part.rels[rid]
    except (KeyError, AttributeError):
        return ""
    return rel.target_ref if getattr(rel, "is_external", False) else ""


def _paragraph_spans(paragraph, part, warnings: List[str], taken: List[int],
                     links: Optional[List[Dict[str, str]]] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """문단 → (글자 span 들, 그 문단에 들어 있던 사진 블록들).

    python-docx 의 paragraph.runs 는 **w:hyperlink 안의 글자를 돌려주지 않는다**.
    그것만 보고 읽으면 '여기서 예약하세요'의 '여기서'가 통째로 사라진다(2026-09-22 실측).
    그래서 문단의 자식을 순서대로 훑어 링크 안쪽 글자도 함께 읽고, 주소는 따로 모은다.
    """
    from docx.text.run import Run

    spans: List[Dict[str, Any]] = []
    images: List[Dict[str, Any]] = []

    def add(run, href: str = "") -> None:
        images.extend(_images_in(run, part, warnings, taken))
        text = _clean(run.text)
        if not text:
            return
        span = _span(text, bold=bool(run.bold), italic=bool(run.italic),
                     underline=bool(run.underline), color=_color_of(run),
                     size=_size_of(run, paragraph), background=_background_of(run))
        if href:
            span["href"] = href
            if links is not None and not any(l["url"] == href for l in links):
                links.append({"text": text, "url": href})
        spans.append(span)

    for node in paragraph._p:
        tag = node.tag
        if tag == f"{W}r":
            add(Run(node, paragraph))
        elif tag == f"{W}hyperlink":
            href = _hyperlink_url(node, paragraph)
            for child in node.findall(f"{W}r"):
                add(Run(child, paragraph), href)
    return _merge(spans), images


def _table_block(table, part, warnings: List[str], taken: List[int]) -> Optional[Dict[str, Any]]:
    rows: List[List[List[Dict[str, Any]]]] = []
    cells = 0
    for row in table.rows:
        line: List[List[Dict[str, Any]]] = []
        for cell in row.cells:
            spans: List[Dict[str, Any]] = []
            for paragraph in cell.paragraphs:
                part_spans, _ = _paragraph_spans(paragraph, part, warnings, taken)
                if part_spans and spans:
                    spans.append(_span("\n"))
                spans.extend(part_spans)
            line.append(_merge(spans))
            cells += 1
        rows.append(line)
        if cells > MAX_TABLE_CELLS:
            warnings.append(f"표가 너무 커서({MAX_TABLE_CELLS}칸 초과) 뒷부분을 잘랐습니다")
            break
    if not rows or not any(any(spans_text(c) for c in row) for row in rows):
        return None
    # 첫 줄이 모두 굵으면 제목 줄로 본다.
    header = all(all(s.get("b") for s in cell) and cell for cell in rows[0])
    block = {"type": "table", "header": bool(header), "rows": rows}
    block["content"] = block_text(block)
    return block


def _body_children(document) -> Iterator[Any]:
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    for child in document.element.body.iterchildren():
        if child.tag == f"{W}p":
            yield Paragraph(child, document)
        elif child.tag == f"{W}tbl":
            yield Table(child, document)


def parse_docx(data: bytes, *, name: str = "") -> ParsedDoc:
    """워드 한 개를 블록으로. 실패하면 ValueError."""
    from docx import Document
    from docx.table import Table

    try:
        document = Document(io.BytesIO(data))
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"워드 파일을 읽지 못했습니다 ({e})") from e

    part = document.part
    warnings: List[str] = []
    links: List[Dict[str, str]] = []
    taken = [0]
    blocks: List[Dict[str, Any]] = []
    pending_list: List[List[Dict[str, Any]]] = []
    pending_ordered = False

    def flush_list() -> None:
        nonlocal pending_list, pending_ordered
        if pending_list:
            block = {"type": "list", "ordered": pending_ordered, "items": pending_list}
            block["content"] = block_text(block)
            blocks.append(block)
            pending_list = []
            pending_ordered = False

    for node in _body_children(document):
        if isinstance(node, Table):
            flush_list()
            table = _table_block(node, part, warnings, taken)
            if table:
                blocks.append(table)
            continue
        kind, level = _paragraph_kind(node)
        spans, images = _paragraph_spans(node, part, warnings, taken, links)
        if kind == "list" and spans:
            if not pending_list:
                pending_ordered = _ordered_list(node)
            pending_list.append(spans)
            blocks.extend(images)
            continue
        flush_list()
        if spans:
            block: Dict[str, Any] = {"type": kind if kind != "list" else "text", "spans": spans}
            if block["type"] == "heading":
                block["level"] = level
            block["content"] = block_text(block)
            blocks.append(block)
            # 글자에 링크만 걸려 있고 주소가 화면에 안 보이면, 주소를 한 줄로 덧붙인다.
            # 네이버 에디터는 한 줄짜리 주소를 링크 카드로 만들어 준다 — 그래야 눌린다.
            shown = block["content"]
            for url in dict.fromkeys(sp.get("href") for sp in spans if sp.get("href")):
                if url and url not in shown:
                    blocks.append({"type": "text", "spans": [_span(url)], "content": url, "link": url})
        blocks.extend(images)
    flush_list()

    if not blocks:
        raise ValueError("워드 파일에서 읽을 내용이 없습니다")
    title, blocks = _split_title(blocks, name)
    if not any(b["type"] != "image" for b in blocks):
        raise ValueError("사진만 있고 글이 없습니다")
    return ParsedDoc(title=title, blocks=blocks, warnings=warnings, links=links)


def _split_title(blocks: List[Dict[str, Any]], name: str) -> Tuple[str, List[Dict[str, Any]]]:
    """제목 = 첫 소제목/제목 문단, 없으면 60자 이하인 첫 문단, 그것도 없으면 파일 이름."""
    for i, block in enumerate(blocks):
        if block["type"] == "image":
            continue
        text = block_text(block).strip()
        if not text:
            continue
        if block["type"] == "heading" or (block["type"] == "text" and len(text) <= TITLE_MAX):
            return text[:200], blocks[:i] + blocks[i + 1:]
        break
    stem = re.sub(r"\.docx?$", "", name, flags=re.I).strip()
    return (stem or "제목 없음")[:200], blocks


# ─────────────────────────────────────────────────────── 실행기로 보낼 모양
def flatten_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """서식을 모르는 옛 실행기용. 글 블록은 평문으로 합치고 사진은 그대로 둔다."""
    out: List[Dict[str, Any]] = []
    buf: List[str] = []
    for block in blocks:
        if block["type"] == "image":
            if buf:
                out.append({"type": "text", "content": "\n\n".join(buf)})
                buf = []
            out.append({"type": "image", "image": block.get("image")})
            continue
        text = block.get("content") or block_text(block)
        if text:
            buf.append(text)
    if buf:
        out.append({"type": "text", "content": "\n\n".join(buf)})
    return out
