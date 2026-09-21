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
