"""
붙여넣기 글 → 블로그형 자동 포맷 엔진.

동작(사용자 확정 규격):
- 첫 줄(맨 위 문장) = 제목, 나머지 = 본문.
- 본문에서 '반복되는 단어'를 키워드로 추출(빈도 기반, 한글 조사 제거 + 불용어 제외).
- 본문을 단락으로 나누되 **단락 1개당 키워드 1개**가 들어가도록 배치.
- 단락 안은 '한 줄 한 문장, 두 문장마다 빈 줄'로 펼친다(모바일 가독성).
- 단락 사이에 이미지 슬롯을 끼워 글-이미지-글-이미지 인터리브.
- 키워드는 본문 전반에 고르게 분산 + 해시태그로도 제공.

의존성 없음(순수 파이썬). 키워드 추출은 형태소 분석기 대신 경량 빈도 방식.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Optional

# 흔한 한글 조사(단어 끝에서 제거해 어간을 통일)
_JOSA = (
    "으로써", "으로서", "이라고", "라고", "에서는", "에서도", "에게서", "한테서",
    "으로", "에서", "에게", "한테", "께서", "부터", "까지", "처럼", "같이", "마다",
    "조차", "밖에", "이나", "이라도", "라도", "이란", "이든", "든지",
    "은", "는", "이", "가", "을", "를", "에", "와", "과", "도", "만", "의", "로",
    "나", "야", "아", "여", "께", "든",
)

# 의미 약한 일반어(키워드에서 제외)
_STOPWORDS = {
    "그리고", "그러나", "하지만", "그래서", "또한", "또는", "그런데", "그러면",
    "때문", "위해", "통해", "대해", "관해", "경우", "정도", "가지", "우리", "여러분",
    "이것", "그것", "저것", "여기", "거기", "저기", "이런", "그런", "저런",
    "있습니다", "합니다", "입니다", "습니다", "됩니다", "있는", "하는", "되는",
    "매우", "정말", "너무", "아주", "가장", "모든", "많은", "다양한", "다음", "오늘",
    "안녕하세요", "감사합니다",
}

_WORD_RE = re.compile(r"[가-힣A-Za-z0-9]+")


@dataclass
class PostBlock:
    type: str                    # 'text' | 'image'
    content: str = ""            # text 블록의 본문
    keyword: Optional[str] = None  # 이 단락에 배정된 키워드


@dataclass
class FormattedPost:
    title: str
    keywords: List[str]
    hashtags: List[str]
    blocks: List[PostBlock] = field(default_factory=list)
    image_slots: int = 0         # 필요한 이미지 개수

    def text_only(self) -> str:
        return "\n\n".join(b.content for b in self.blocks if b.type == "text")


def _strip_josa(word: str) -> str:
    if not re.search(r"[가-힣]$", word):
        return word  # 영문/숫자는 그대로
    for j in _JOSA:  # 긴 조사부터 시도
        if word.endswith(j) and len(word) - len(j) >= 2:
            return word[: -len(j)]
    return word


def extract_title_body(raw: str) -> tuple[str, str]:
    """첫 비어있지 않은 줄 = 제목, 나머지 = 본문."""
    lines = [ln.rstrip() for ln in (raw or "").replace("\r\n", "\n").split("\n")]
    title = ""
    body_start = 0
    for i, ln in enumerate(lines):
        if ln.strip():
            title = ln.strip()
            body_start = i + 1
            break
    body = "\n".join(lines[body_start:]).strip()
    return title, body


def _sentences(body: str) -> List[str]:
    """본문을 문장 단위로 분해(마침표/물음표/느낌표/줄바꿈 기준)."""
    # 줄바꿈은 문장 경계로, 문장부호 뒤 공백도 경계로
    parts = re.split(r"(?<=[.!?。？！])\s+|\n+", body)
    return [p.strip() for p in parts if p.strip()]


# 모바일 가독성: 한 줄 = 한 문장, 두 문장마다 빈 줄.
# (독자 대부분이 휴대폰이라, 문장을 스페이스로 이어 붙인 통짜 단락은 그냥 안 읽힌다)
_SENTENCES_PER_GROUP = 2
_MOBILE_LINE_MAX = 60


def _split_long(s: str) -> List[str]:
    """긴 문장은 '가운데 근처' 쉼표에서 나눈다.

    가운데(30~70% 구간)로 제한하는 게 핵심이다. 아무 쉼표에서나 끊으면
    '하지만 실제 현장에서 소방 시설 확충,' 같은 토막 한 줄 + 여전히 긴 한 줄이
    나와서 안 끊느니만 못하다. 마땅한 자리가 없으면 문장을 그대로 둔다.
    """
    n = len(s)
    if n <= _MOBILE_LINE_MAX:
        return [s]
    mid = n / 2
    cut = -1
    for i, ch in enumerate(s):
        if ch != "," or i < n * 0.3 or i > n * 0.7:
            continue
        if cut < 0 or abs(i - mid) < abs(cut - mid):
            cut = i
    if cut < 0:
        return [s]
    return [s[: cut + 1].strip()] + _split_long(s[cut + 1 :].strip())


def _mobile_paragraph(sents: List[str]) -> str:
    """문장 목록 → 한 줄 한 문장, 두 문장마다 빈 줄."""
    lines: List[str] = []
    for s in sents:
        lines.extend(_split_long(s.strip()))
    groups = [
        "\n".join(lines[i : i + _SENTENCES_PER_GROUP])
        for i in range(0, len(lines), _SENTENCES_PER_GROUP)
    ]
    return "\n\n".join(g for g in groups if g)


def extract_keywords(body: str, top_n: int = 6) -> List[str]:
    """빈도 기반 키워드(2회 이상 반복 단어 우선). 조사 제거 + 불용어 제외."""
    counter: Counter[str] = Counter()
    for raw_w in _WORD_RE.findall(body):
        w = _strip_josa(raw_w)
        if len(w) < 2:
            continue
        if w in _STOPWORDS:
            continue
        if re.fullmatch(r"[0-9]+", w):  # 숫자만 제외
            continue
        counter[w] += 1
    # 2회 이상 반복을 우선, 부족하면 1회 단어로 채움
    repeated = [w for w, c in counter.most_common() if c >= 2]
    if len(repeated) >= top_n:
        return repeated[:top_n]
    singles = [w for w, c in counter.most_common() if c == 1]
    return (repeated + singles)[:top_n]


def _assign_sentences_to_keywords(
    sentences: List[str], keywords: List[str]
) -> List[tuple[Optional[str], List[str]]]:
    """문장을 키워드에 배정하되, 여러 키워드를 가진 문장은 '지금까지 문장이
    가장 적은 키워드'에 몰아줘 단락 균형을 맞춘다(지배 키워드 독점 방지).
    최종적으로 단락 1개당 키워드 1개."""
    groups: dict[Optional[str], List[str]] = {k: [] for k in keywords}
    groups[None] = []
    for s in sentences:
        hits = [k for k in keywords if k in s]
        if not hits:
            groups[None].append(s)
            continue
        # 후보 키워드 중 현재 배정 문장이 가장 적은 것 선택 → 균형
        chosen = min(hits, key=lambda k: (len(groups[k]), keywords.index(k)))
        groups[chosen].append(s)

    ordered: List[tuple[Optional[str], List[str]]] = []
    for k in keywords:
        if groups[k]:
            ordered.append((k, groups[k]))
    # 키워드 없는 문장은 앞 단락들에 순환 분배(맥락 유지)
    leftover = groups.get(None, [])
    if leftover and ordered:
        for i, s in enumerate(leftover):
            ordered[i % len(ordered)][1].append(s)
    elif leftover and not ordered:
        ordered.append((None, leftover))
    return ordered


def format_post(
    raw: str,
    top_keywords: int = 6,
    image_between: bool = True,
) -> FormattedPost:
    """붙여넣은 글 하나를 블로그형으로 포맷.

    image_between=True 이면 단락 사이마다 이미지 슬롯을 넣어
    글-이미지-글-이미지-…-글 구조(마지막 단락 뒤에도 1장)를 만든다.
    """
    title, body = extract_title_body(raw)
    if not body:
        # 제목만 있고 본문이 없으면 제목을 본문 취급
        body = title

    keywords = extract_keywords(body, top_n=top_keywords)
    sentences = _sentences(body)
    grouped = _assign_sentences_to_keywords(sentences, keywords)

    blocks: List[PostBlock] = []
    image_slots = 0
    for idx, (kw, sents) in enumerate(grouped):
        para = _mobile_paragraph(sents).strip()
        if not para:
            continue
        blocks.append(PostBlock(type="text", content=para, keyword=kw))
        # 단락 뒤에 이미지 (마지막 단락 뒤에도 1장 → 글 이미지 글 이미지 …)
        if image_between:
            blocks.append(PostBlock(type="image"))
            image_slots += 1

    # 텍스트 블록이 하나도 없으면(아주 짧은 글) 통짜 1단락
    if not any(b.type == "text" for b in blocks):
        blocks = [PostBlock(type="text", content=body, keyword=keywords[0] if keywords else None)]
        if image_between:
            blocks.append(PostBlock(type="image"))
            image_slots = 1

    hashtags = [f"#{k}" for k in keywords]
    return FormattedPost(
        title=title or "제목 없음",
        keywords=keywords,
        hashtags=hashtags,
        blocks=blocks,
        image_slots=image_slots,
    )


def split_bulk(raw: str, delimiter: str = "") -> List[str]:
    """대량 붙여넣기를 여러 글로 분리.
    delimiter 가 주어지면 그 줄로 분리, 없으면 빈 줄 2개 이상을 글 경계로 사용."""
    text = (raw or "").replace("\r\n", "\n").strip()
    if not text:
        return []
    if delimiter:
        chunks = re.split(rf"^\s*{re.escape(delimiter)}\s*$", text, flags=re.MULTILINE)
    else:
        chunks = re.split(r"\n\s*\n\s*\n+", text)  # 빈 줄 2개 이상 = 글 경계
    return [c.strip() for c in chunks if c.strip()]
