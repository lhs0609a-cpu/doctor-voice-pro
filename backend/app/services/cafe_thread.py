"""카페 바이럴 스레드 — 질문글 1개 + 댓글 N개를 한 덩어리로 만들고 검수한다.

2026-09-30 고객(소잠한의원) 요청:
  "후기 작성 원고 말고, 본문은 질문형식, 댓글 6개 중 댓글 2 부분만 특정 병원 정보 언급"

왜 한 번에 만드는가
  댓글을 따로 만들면 서로 말이 안 맞고 같은 소리를 반복한다. 사람이 읽으면 바로 티가 난다.
  한 번의 호출로 질문글과 댓글 6개를 함께 받아야 2번 댓글 뒤에 3번이 "거기 어떠셨어요?"
  하고 이어지는 대화가 된다.

왜 검사를 따로 두는가
  "2번 댓글에만 병원 이름"은 지시만으로는 지켜지지 않는다. 오늘 제목 키워드에서 같은 일을
  겪었다 — 모델은 시키면 대체로 하지만 가끔 흘린다. 그 '가끔'이 광고 티를 낸다.
  그래서 생성과 별개로 **결정적으로** 확인하고, 어긋나면 사람에게 돌려보낸다.

이 모듈은 1단계(원고 생성·검수)까지만 한다. 카페에 올리는 것은 사람이 한다.
자동 게시는 PC 실행기로 가야 하며(서버에서 브라우저를 띄우면 데이터센터 IP로 계정을
돌리는 꼴이라 정지 사유다) 그것은 2단계다.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Sequence

from app.services import claude_client as cc
from app.services.editorial_quality import clinic_number_misses

logger = logging.getLogger(__name__)

DEFAULT_COMMENT_COUNT = 6
DEFAULT_PROMO_INDEX = 2          # 순서상 두 번째 댓글(1-based). 고객 확정.
MIN_COMMENTS, MAX_COMMENTS = 3, 12

# 댓글에 있으면 안 되는 것들. 병원 이름은 2번 댓글에만, 링크·연락처·가격은 어디에도.
_URL = re.compile(r'https?://|www\.|blog\.naver|naver\.me|카카오톡|오픈톡|톡방')
_PHONE = re.compile(r'0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}|\d{4}[-\s]?\d{4}')
_PRICE = re.compile(r'\d[\d,]*\s*(?:원|만원|천원)')

SYSTEM = """당신은 네이버 카페에 실제로 글과 댓글을 쓰는 평범한 회원들이다.
한 사람이 고민을 묻는 글을 올리고, 서로 다른 회원들이 거기에 댓글을 단다.
광고처럼 보이면 실패다. 카페 회원들은 광고를 귀신같이 알아본다.
출력은 JSON 하나만: {"title": "...", "body": "...", "comments": [{"seq": 1, "persona": "...", "body": "..."}]}"""


def _rules(clinic_name: str, comment_count: int, promo_index: int) -> str:
    others = [str(i) for i in range(1, comment_count + 1) if i != promo_index]
    return f"""글과 댓글을 쓰는 규칙:

[질문글]
- **질문 형식이다.** 진짜로 궁금해서 묻는 사람의 글이다. 후기가 아니다.
- 자기 경험을 단정하지 않는다. "저 이거 해봤는데 좋았어요" 같은 문장은 쓰지 않는다.
  "이런 상황인데 어떻게들 하셨나요?" 처럼 묻는다.
- 상황을 구체적으로 적되(언제부터, 어떤 점이 불편한지) 병원 이름은 **쓰지 않는다**.
- 제목도 질문처럼 쓴다. 30자 이내.
- 본문은 250~600자. 문단 사이는 빈 줄 하나.

[댓글 {comment_count}개]
- 서로 **다른 사람**이다. 말투·길이·맞춤법 습관을 다르게 한다. 어떤 사람은 두 줄,
  어떤 사람은 한 줄만 쓴다. 모두가 친절하고 길게 쓰면 그게 광고다.
- 앞 댓글을 읽고 반응한다. 대화가 이어져야 한다.
- persona 에는 그 사람이 누구인지 한 마디로 적는다(예: "같은 고민 중인 30대").

[{promo_index}번 댓글 — 여기서만 병원을 말한다]
- **'{clinic_name}' 이라는 이름만** 자연스럽게 말한다. "저는 {clinic_name} 갔어요" 정도.
- 링크·전화번호·주소·가격·할인은 절대 쓰지 않는다.
- 효과를 단정하지 않는다("완치됐어요" 금지). 과장하지 않는다.
- 추천하는 말투로 밀지 않는다. 자기가 한 일을 담담히 말할 뿐이다.

[{', '.join(others)}번 댓글 — 병원 이름 금지]
- 병원·의원·한의원 **이름을 단 한 글자도 쓰지 않는다**. '{clinic_name}' 도 물론 금지.
- 공감하거나, 일반적인 조언을 하거나, 되묻는다.
- {promo_index}번 댓글 바로 뒤 댓글은 그 말에 자연스럽게 반응해도 좋지만,
  병원 이름을 다시 부르지는 않는다("거기 어떠셨어요?" 처럼 받는다)."""


async def generate_thread(
    *,
    clinic_name: str,
    topic: str,
    cafe_name: str = "",
    tone: str = "",
    comment_count: int = DEFAULT_COMMENT_COUNT,
    promo_index: int = DEFAULT_PROMO_INDEX,
    forbidden_words: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """→ {"title", "body", "comments": [{"seq", "persona", "body"}]}"""
    comment_count = max(MIN_COMMENTS, min(MAX_COMMENTS, int(comment_count or DEFAULT_COMMENT_COUNT)))
    promo_index = max(1, min(comment_count, int(promo_index or DEFAULT_PROMO_INDEX)))
    banned = ", ".join(w for w in (forbidden_words or []) if w) or "없음"
    user = f"""카페: {cafe_name or "지역 커뮤니티/맘카페"}
고민 주제: {topic}
{promo_index}번 댓글에서 말할 병원 이름: {clinic_name}
쓰면 안 되는 말: {banned}
{f"말투 참고: {tone}" if tone else ""}

{_rules(clinic_name, comment_count, promo_index)}

댓글은 정확히 {comment_count}개, seq 는 1부터 {comment_count}까지 빠짐없이."""
    raw = await cc.complete_json(SYSTEM, user)
    if not isinstance(raw, dict):
        raise ValueError("카페 스레드 생성 결과를 읽지 못했습니다")
    comments = []
    for i, item in enumerate(raw.get("comments") or [], start=1):
        if not isinstance(item, dict):
            continue
        comments.append({
            "seq": int(item.get("seq") or i),
            "persona": str(item.get("persona") or "").strip()[:60],
            "body": str(item.get("body") or "").strip(),
        })
    return {
        "title": str(raw.get("title") or "").strip(),
        "body": str(raw.get("body") or "").strip(),
        "comments": comments,
        "promo_index": promo_index,
        "comment_count": comment_count,
    }


def clinic_aliases(client: Dict[str, Any]) -> List[str]:
    """이 병원을 가리키는 말들. 하나라도 엉뚱한 댓글에 있으면 광고 티가 난다."""
    out: List[str] = []
    for key in ("name", "short_name", "brand_keyword"):
        value = str((client or {}).get(key) or "").strip()
        if value and value not in out:
            out.append(value)
    return out


def _has_alias(text: str, aliases: Sequence[str]) -> Optional[str]:
    flat = re.sub(r"\s+", "", text or "")
    for alias in aliases:
        if alias and re.sub(r"\s+", "", alias) in flat:
            return alias
    return None


def check_thread(thread: Dict[str, Any], client: Dict[str, Any]) -> Dict[str, Any]:
    """→ {"ok": bool, "issues": [...]}. 지시가 아니라 **확인**이다.

    가장 중요한 검사는 '{promo_index}번 말고 다른 댓글에 병원 이름이 있는가'다.
    하나라도 새어 나가면 그 글은 광고로 읽힌다."""
    issues: List[str] = []
    aliases = clinic_aliases(client)
    promo_index = int(thread.get("promo_index") or DEFAULT_PROMO_INDEX)
    comments = list(thread.get("comments") or [])
    want = int(thread.get("comment_count") or DEFAULT_COMMENT_COUNT)
    title, body = str(thread.get("title") or ""), str(thread.get("body") or "")

    if len(comments) != want:
        issues.append(f"댓글이 {want}개여야 하는데 {len(comments)}개입니다")
    seqs = [int(c.get("seq") or 0) for c in comments]
    if sorted(seqs) != list(range(1, len(comments) + 1)):
        issues.append("댓글 번호가 1부터 차례대로가 아닙니다")

    # ── 질문글 ──────────────────────────────────────────────────────────
    if not title or not body:
        issues.append("질문글 제목이나 본문이 비어 있습니다")
    if "?" not in title + body and not re.search(r"(나요|까요|would|을까|ㄹ까|세요\?)", title + body):
        issues.append("질문글이 질문처럼 읽히지 않습니다(묻는 문장이 없습니다)")
    leaked = _has_alias(title + body, aliases)
    if leaked:
        issues.append(f"질문글에 병원 이름 '{leaked}'이(가) 있습니다 — 묻는 사람이 병원을 알고 있으면 광고로 읽힙니다")

    # ── 댓글 ────────────────────────────────────────────────────────────
    promo = next((c for c in comments if int(c.get("seq") or 0) == promo_index), None)
    if promo is None:
        issues.append(f"{promo_index}번 댓글이 없습니다")
    elif not _has_alias(promo.get("body", ""), aliases):
        issues.append(f"{promo_index}번 댓글에 병원 이름이 없습니다")

    for comment in comments:
        seq = int(comment.get("seq") or 0)
        text = str(comment.get("body") or "")
        if not text.strip():
            issues.append(f"{seq}번 댓글이 비어 있습니다")
            continue
        if seq != promo_index:
            found = _has_alias(text, aliases)
            if found:
                issues.append(f"{seq}번 댓글에 병원 이름 '{found}'이(가) 있습니다 — "
                              f"{promo_index}번에만 있어야 합니다")
        if _URL.search(text):
            issues.append(f"{seq}번 댓글에 링크나 연락처가 있습니다 — 병원 이름만 말합니다")
        if _PHONE.search(text):
            issues.append(f"{seq}번 댓글에 전화번호로 보이는 숫자가 있습니다")
        if _PRICE.search(text):
            issues.append(f"{seq}번 댓글에 가격이 있습니다 — 카페 광고 규정에 걸립니다")

    # ── 병원 금칙어 · 지어낸 실적 숫자 ─────────────────────────────────
    whole = "\n".join([title, body, *(str(c.get("body") or "") for c in comments)])
    hits = [w.strip() for w in (client.get("forbidden_words") or []) if w and w.strip() and w.strip() in whole]
    if hits:
        issues.append("병원 금칙어가 있습니다: " + ", ".join(hits[:5]))
    invented = clinic_number_misses(whole, client.get("facts"))
    if invented:
        issues.append("병원이 준 적 없는 실적 숫자: " + ", ".join(invented[:3]))

    return {"ok": not issues, "issues": issues, "promo_index": promo_index}
