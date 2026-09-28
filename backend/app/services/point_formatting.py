"""Select a small number of existing phrases; never rewrite the manuscript."""
from copy import deepcopy
import re
from typing import List
from pydantic import BaseModel, Field


class PointFormatting(BaseModel):
    enabled: bool = False
    bold: bool = True
    quote: bool = True
    color: bool = True
    background: bool = True
    text_color: str = Field(default='#0078cb', pattern=r'^#[0-9a-fA-F]{6}$')
    background_color: str = Field(default='#fff8b2', pattern=r'^#[0-9a-fA-F]{6}$')
    phrases: List[str] = Field(default_factory=list, max_length=20)


def _text(block):
    return ''.join(s.get('t', '') for s in block.get('spans') or []) or block.get('content', '')


# 인용·참고문헌 줄. 「제목」이 있거나 학회·저널 이름 뒤에 연도가 붙는다.
_CITATION = re.compile(r'[「『].+?[」』]|(?:학회|학술지|저널|논문집|Journal)\s*[,·]?\s*(?:19|20)\d{2}')


_STYLE_KEYS = ('b', 'i', 'u', 'color', 'background')


def _style(span):
    return tuple(span.get(k) for k in _STYLE_KEYS)


def _restyle(span, style):
    out = {k: v for k, v in span.items() if k not in _STYLE_KEYS}
    out.update({k: v for k, v in zip(_STYLE_KEYS, style) if v})
    return out


def _channels(hex_color):
    value = (hex_color or '').strip()
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
        return None
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


# 사람 눈으로 본문 검정과 구분되지 않는 범위. #222b2f(47) 는 들어오고 #666e73(115) 는 아니다.
DEFAULT_TEXT_MAX = 80
DEFAULT_BACKGROUND_MIN = 240


def drop_default_colors(blocks):
    """본문 기본색에 가까운 글자색과 흰 배경은 '색 없음'으로 본다.

    워드는 본문 글자에도 색을 적어 둔다(#222b2f). 그 색은 네이버 팔레트에 없어서 실행기가
    문단마다 클립보드로 붙여 넣어야 하고, 붙여 넣은 글을 되읽는 확인이 한 번 어긋나면
    글 **전체**가 발행되지 않는다(2026-09-28 실측: '입력한 강조 문구가 본문에 표시되지
    않았습니다'로 예약 1건 실패). 눈에 보이지도 않는 색을 재현하려고 발행을 잃지 않는다.
    진짜 강조색(청록·회색 캡션 등)은 그대로 둔다."""
    result = deepcopy(blocks)
    for block in result:
        for span in block.get('spans') or []:
            text = _channels(span.get('color'))
            if text and max(text) <= DEFAULT_TEXT_MAX:
                span.pop('color', None)
            back = _channels(span.get('background'))
            if back and min(back) >= DEFAULT_BACKGROUND_MIN:
                span.pop('background', None)
    return result


def trim_stray_emphasis(blocks):
    """중요하지 않은 곳에 붙은 강조를 떼어 낸다. 글자와 순서는 건드리지 않는다.

    워드 원고는 제목을 색+굵게로 잡아 두는데, 같은 서식이 참고문헌의 저자·학회 이름이나
    문장 속 고유명사에도 붙어 온다. 그대로 올리면 글 곳곳이 알록달록해져서 정작 중요한
    포인트가 묻힌다(2026-09-23 사용자 지적: 인용 줄의 '김남익', '한국발육발달학회').

    '색이 있으면 강조'로 보면 안 된다 — 워드는 본문 글자에도 색(#222b2f)을 적어 둔다.
    그래서 **그 문단에서 가장 길게 쓰인 서식을 본문 서식으로 보고**, 거기서 벗어난 조각만
    강조로 센다. 문단 전체가 한 서식이면 제목이거나 그냥 본문이므로 손대지 않는다.

    남기는 규칙은 둘뿐이다.
    1) 참고문헌·인용 줄은 강조를 모두 본문 서식으로 되돌린다 — 출처는 포인트가 아니다.
    2) 보통 문단에서는 강조 조각을 **하나만** 남긴다.
    """
    result = deepcopy(blocks)
    for block in result:
        spans = block.get('spans') or []
        if block.get('type') not in ('text', 'quote') or len(spans) < 2:
            continue
        weight = {}
        for span in spans:
            weight[_style(span)] = weight.get(_style(span), 0) + len(span.get('t', ''))
        base = max(weight, key=lambda k: weight[k])
        marked = [i for i, span in enumerate(spans) if _style(span) != base]
        if not marked:
            continue
        drop = marked if _CITATION.search(_text(block)) else marked[1:]
        for i in drop:
            spans[i] = _restyle(spans[i], base)
    return result


def apply_points(blocks, config, keywords=()):
    """Preserve all text/images and author formatting. At most six new accents.

    Explicit phrases rank first; otherwise use keywords and editorial cue words.
    A phrase receives only one treatment. Links, tables, lists and long passages
    are excluded from automatic changes. Existing Word styles remain untouched.
    """
    result = deepcopy(blocks)
    cfg = PointFormatting.model_validate(config or {})
    if not cfg.enabled:
        return result
    phrases = [p.strip() for p in cfg.phrases if 2 <= len(p.strip()) <= 120]
    terms = phrases or [k.strip() for k in keywords if isinstance(k, str) and 2 <= len(k.strip()) <= 60]
    candidates = []
    total = sum(len(_text(b)) for b in result)
    for index, block in enumerate(result):
        if block.get('type') != 'text':
            continue
        text = _text(block)
        if not text or re.search(r'https?://|www\.', text):
            continue
        # Respect explicit Word formatting instead of stacking another effect.
        if any(any(s.get(key) for key in ('b','i','u','color','background')) for s in block.get('spans') or []):
            continue
        matches = [(text.find(term), term) for term in terms if term in text]
        if matches:
            start, phrase = sorted(matches, key=lambda item: (-len(item[1]), item[0]))[0]
            candidates.append((4 if phrases else 2, index, start, start + len(phrase)))
        else:
            for match in re.finditer(r'[^\n.!?。！？]+[.!?。！？]?', text):
                sentence = match.group().strip()
                if 12 <= len(sentence) <= 90 and re.search(r'핵심|중요|반드시|기억|주의|먼저 확인|선택.*기준|결론', sentence):
                    start = match.start() + len(match.group()) - len(match.group().lstrip())
                    candidates.append((1, index, start, start + len(sentence)))
                    break
    treatments = [key for key in ('bold','color','background','quote') if getattr(cfg, key)]
    if not treatments:
        return result
    used = 0
    budget = max(30, int(total * .15))
    for _, index, start, end in sorted(candidates, key=lambda row: (-row[0], row[1]))[:6]:
        block = result[index]
        text = _text(block)
        if end - start > budget:
            continue
        treatment = treatments[used % len(treatments)]
        # Quotes wrap a complete short paragraph, never detach a phrase or change order.
        if treatment == 'quote':
            if 12 <= len(text.strip()) <= 150 and len(text) <= budget and '\n' not in text:
                block['type'] = 'quote'
                block['spans'] = block.get('spans') or [{'t':text}]
                budget -= len(text)
                used += 1
                continue
            alternatives = [key for key in treatments if key != 'quote']
            if not alternatives:
                continue
            treatment = alternatives[used % len(alternatives)]
        style = {'b':True} if treatment == 'bold' else {'color':cfg.text_color} if treatment == 'color' else {'background':cfg.background_color}
        source = block.get('spans') or [{'t':text}]
        spans, offset = [], 0
        for span in source:
            value = span.get('t','')
            cuts = sorted({0,len(value),max(0,min(len(value),start-offset)),max(0,min(len(value),end-offset))})
            for lo, hi in zip(cuts,cuts[1:]):
                if hi > lo:
                    piece = {**span,'t':value[lo:hi]}
                    if offset + lo >= start and offset + hi <= end:
                        piece.update(style)
                    spans.append(piece)
            offset += len(value)
        block['spans'] = spans
        budget -= end - start
        used += 1
    return result
