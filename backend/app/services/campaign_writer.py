"""
원고 생성/변형/검수 — Claude API.

세 가지 일을 한다.
1) write_from_keyword: 키워드 + 브리프 프리셋 + 통검 분석값 → 완성 원고(제목/본문/태그)
2) make_variants: 원본 원고 → 내용은 같고 문체·구조·화자가 다른 N개 (고정 사실 보존)
3) plan_image_slots: 원고 문단을 읽어 "어떤 사진이 어디에" 슬롯 목록
+ 검수: check_flow(브리프 흐름 준수), check_facts(고정 사실 보존), 의료광고법/금칙어(기존 검사기 재사용), 유사도

출력은 모두 JSON 으로 받아 파싱한다. 마크다운 기호는 쓰지 않게 하고, 모바일 가독성
(한 줄 한 문장, 두 문장마다 빈 줄)은 post_formatter 규칙을 프롬프트로 요구한 뒤
서버에서 한 번 더 정리한다(멱등).
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from app.services import claude_client as cc
from app.services.post_formatter import _mobile_paragraph, _sentences  # noqa: WPS450

logger = logging.getLogger(__name__)


# ─────────────────────────────── 공통 ───────────────────────────────

MOBILE_RULES = """모바일 가독성 규칙(독자의 대부분이 휴대폰):
- 한 줄에 한 문장만 쓰고, 두 문장마다 빈 줄을 넣는다.
- 한 문장은 45자 안팎, 60자를 넘기지 않는다. 길면 두 문장으로 나눈다.
- 마크다운 기호(#, *, -, >)와 이모지는 쓰지 않는다. 소제목은 그냥 한 줄로 쓴다.
- 광고성 최상급 표현(최고, 유일, 완치, 100%, 부작용 없음)과 가격·할인 언급은 금지한다."""


def _brief_text(brief: Optional[Dict]) -> str:
    if not brief:
        return "브리프 없음: 정보 전달형 블로그 글의 일반적인 흐름(문제 공감 → 원인/정보 → 진료·치료 안내 → 마무리)을 따른다."
    lines = [f"브리프 이름: {brief.get('name','')}"]
    if brief.get("description"):
        lines.append(f"설명: {brief['description']}")
    flow = brief.get("flow") or []
    if flow:
        lines.append("글 흐름(이 순서를 반드시 지킨다):")
        for i, sec in enumerate(flow, 1):
            goal = sec.get("goal") or ""
            mc = sec.get("min_chars")
            lines.append(f"  {i}. {sec.get('title','')} — {goal}" + (f" (최소 {mc}자)" if mc else ""))
    if brief.get("rules"):
        lines.append(f"작성 규칙: {brief['rules']}")
    if brief.get("must_include"):
        lines.append("반드시 포함: " + " / ".join(str(x) for x in brief["must_include"]))
    if brief.get("avoid"):
        lines.append("피할 표현: " + " / ".join(str(x) for x in brief["avoid"]))
    if brief.get("source_text"):
        lines.append("사실 소스(원본 원고 — 여기 없는 사실·수치·프로그램명을 지어내지 않는다):\n" + str(brief["source_text"])[:6000])
    return "\n".join(lines)


def reflow(body: str) -> str:
    """서버측 모바일 정리(멱등). 소제목 같은 짧은 줄은 그대로 둔다."""
    out: List[str] = []
    for para in re.split(r"\n\s*\n", (body or "").replace("\r\n", "\n").strip()):
        lines = [ln.strip() for ln in para.split("\n") if ln.strip()]
        if not lines:
            continue
        if len(lines) == 1 and len(lines[0]) <= 30 and not re.search(r"[.!?…]$", lines[0]):
            out.append(lines[0])  # 소제목
            continue
        sents: List[str] = []
        for ln in lines:
            sents.extend(_sentences(ln))
        out.append(_mobile_paragraph(sents))
    return "\n\n".join(o for o in out if o)


def count_chars(body: str) -> int:
    return len(re.sub(r"\s+", "", body or ""))


# ─────────────────────────────── 1) 키워드 → 원고 ───────────────────────────────

WRITER_SYSTEM = """당신은 한국 병원·한의원 블로그를 10년 쓴 의료 콘텐츠 작가다.
네이버 통합검색 상위 노출 글의 구조를 알고, 의료광고법을 지키며, 환자 입장의 언어로 쓴다.
지어낸 사실·수치·후기는 절대 넣지 않는다. 주어진 사실 소스 밖의 구체 정보가 필요하면 일반론으로 쓴다.
출력은 반드시 JSON 하나만: {"title": "...", "body": "...", "headings": ["..."], "tags": ["..."], "summary": "..."}"""


def _photo_text(hints: Optional[List[str]]) -> str:
    """보유 사진을 글쓰기 전에 알려 준다. 사진이 없으면 아무 말도 하지 않는다."""
    lines = [str(h).strip() for h in (hints or []) if str(h or "").strip()][:12]
    if not lines:
        return ""
    body = "\n".join(f"  · {h}" for h in lines)
    return ("\n이 병원이 가진 사진(이 중 어울리는 것이 본문에 들어간다):\n" + body +
            "\n위 사진이 자연스럽게 들어갈 대목이 생기도록 글을 구성한다. "
            "다만 사진에 없는 장면·장비·시설을 있다고 쓰지 않는다. 사진 이야기를 억지로 끼워 넣지도 않는다.\n")


async def write_from_keyword(
    *,
    keyword: str,
    client: Dict[str, Any],
    brief: Optional[Dict[str, Any]],
    serp: Optional[Dict[str, Any]] = None,
    target_chars: Optional[int] = None,
    heading_count: Optional[int] = None,
    keyword_count: Optional[int] = None,
    extra_instructions: str = "",
    landing: Optional[Dict[str, Any]] = None,
    photo_hints: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """키워드 1개로 완성 원고를 만든다. 반환 {title, body, headings, tags, summary, char_count}

    photo_hints 는 이 병원이 가진 사진의 한 줄 설명이다. 글을 다 쓴 뒤에 사진을 끼워 맞추면
    맞는 사진이 없는 대목이 생긴다. 쓰기 전에 무슨 사진이 있는지 알려 주면 글이 사진을 품고 나온다."""
    summary = (serp or {}).get("summary") or {}
    tc = target_chars or summary.get("recommended_chars") or (brief or {}).get("target_chars") or 2000
    hc = heading_count or (brief or {}).get("heading_count") or 4
    kc = keyword_count or summary.get("recommended_kw_count") or (brief or {}).get("keyword_count") or 6

    facts = client.get("facts") or ""
    tone = client.get("tone") or "정중하지만 딱딱하지 않게. 환자에게 설명하듯."
    forbidden = client.get("forbidden_words") or []

    user = f"""키워드: {keyword}
병원: {client.get('name','')} ({client.get('specialty','') or ''}) / 지역: {', '.join(client.get('regions') or [])}
병원 고정 사실(이 밖의 병원 정보는 쓰지 않는다): {facts or '없음'}
문체: {tone}
병원 금칙어: {', '.join(forbidden) if forbidden else '없음'}

{_brief_text(brief)}
{_photo_text(photo_hints)}
분량 목표: 공백 제외 {tc}자 안팎(±10%). 소제목 {hc}개. 키워드 '{keyword}'를 제목에 1회, 본문에 {kc}회 안팎 자연스럽게.
제목은 28자 이내, 키워드가 앞쪽에 오게.
{MOBILE_RULES}
{extra_instructions}

JSON 으로만 답한다. body 는 위 규칙대로 줄바꿈이 들어간 완성 본문 전체다."""
    if landing:
        import json
        user += ('\n랜딩페이지 안내 데이터: ' + json.dumps(landing, ensure_ascii=False)
                 + '\n본문에는 URL이나 방문 유도 문구를 넣지 않는다. 대신 JSON에 cta 필드를 추가한다. '
                 'cta는 본문에서 다룬 독자의 질문과 위 페이지의 목적을 자연스럽게 잇는 1~2문장(15~250자)이다. '
                 '목적에 없는 혜택/시설/치료효과를 약속하지 않는다. 필요할 때 안내를 확인할 수 있다는 선택형 표현을 쓴다. '
                 '명령형 광고, 긴급성, 반복 클릭 유도, URL은 cta에도 쓰지 않는다.')
    data = await cc.complete_json(WRITER_SYSTEM, user, max_tokens=16000)
    if not isinstance(data, dict):
        raise ValueError("원고 응답 형식 오류")
    body = reflow(str(data.get("body") or ""))
    title = str(data.get("title") or "").strip()[:200]
    tags = [str(t).lstrip("#").strip() for t in (data.get("tags") or []) if str(t).strip()][:10]
    if keyword and keyword not in tags:
        tags.insert(0, keyword)
    return {
        "title": title or keyword,
        "body": body,
        "headings": data.get("headings") or [],
        "tags": tags,
        "summary": data.get("summary") or "",
        "char_count": count_chars(body),
        "cta": data.get('cta') or '',
    }


# ─────────────────────────────── 2) 원본 → 변형 N개 ───────────────────────────────

FACTS_SYSTEM = """당신은 의료 원고 검수자다. 원고에서 '바뀌면 안 되는 사실'만 뽑는다.
JSON 배열로만 답한다: [{"fact": "...", "type": "병원명|시술명|수치|효능주장|지역|기간|기타"}]"""

VARIANT_SYSTEM = """당신은 한국 카페·블로그 후기/정보글을 쓰는 작가다. 원본 원고의 '내용'은 그대로 두고 '글'만 새로 쓴다.
- 원본에 있는 사실·수치·병원명·시술명은 하나도 빠뜨리지 않고, 없는 사실은 추가하지 않는다.
- 지정된 화자·문체·구조로 문장 단위까지 새로 쓴다(원본 문장을 그대로 복사하지 않는다).
- 광고성 최상급 표현과 가격·할인 언급은 금지한다.
출력은 JSON 하나만: {"title": "...", "body": "..."}"""

VARIANT_AXES = [
    {"voice": "환자 본인(1인칭 경험담)", "style": "구어체, 담담한", "structure": "경험담: 고민 → 방문 계기 → 과정 → 변화 → 팁"},
    {"voice": "보호자(부모/배우자)", "style": "정중한 존댓말", "structure": "질문답변형: 궁금했던 것 3~4개에 답하는 식"},
    {"voice": "정보 정리형 3인칭", "style": "담백하고 정보 위주", "structure": "정보형: 정의 → 원인 → 대처 → 병원 선택 기준"},
    {"voice": "지인에게 추천하는 사람", "style": "친근한 반말 섞인 구어체", "structure": "추천글: 결론 먼저 → 이유 → 주의점"},
    {"voice": "꼼꼼한 리뷰어", "style": "차분한 존댓말, 항목별", "structure": "항목별 정리: 상담 / 검사 / 치료 / 비용 언급 없이 만족도"},
    {"voice": "재방문 환자", "style": "편안한 존댓말", "structure": "비교형: 이전 경험과 이번 경험 대비"},
]


async def extract_facts(text: str) -> List[Dict[str, str]]:
    data = await cc.complete_json(FACTS_SYSTEM, f"원고:\n{text[:8000]}", max_tokens=4000, effort="low")
    if isinstance(data, dict):
        data = data.get("facts") or []
    out = []
    for f in data or []:
        if isinstance(f, dict) and f.get("fact"):
            out.append({"fact": str(f["fact"]).strip(), "type": str(f.get("type") or "기타")})
    return out[:40]


async def make_variant(source: str, axis: Dict[str, str], facts: List[Dict[str, str]], forbidden: List[str], target_chars: Optional[int] = None) -> Dict[str, Any]:
    tc = target_chars or max(600, min(3000, int(count_chars(source) * 1.0)))
    user = f"""원본 원고:
{source[:8000]}

보존해야 할 사실:
{chr(10).join('- ' + f['fact'] for f in facts) or '- (없음)'}

화자: {axis['voice']}
문체: {axis['style']}
구조: {axis['structure']}
분량: 공백 제외 {tc}자 안팎
금칙어: {', '.join(forbidden) if forbidden else '없음'}
{MOBILE_RULES}

JSON 으로만 답한다."""
    data = await cc.complete_json(VARIANT_SYSTEM, user, max_tokens=12000)
    body = reflow(str(data.get("body") or ""))
    return {"title": str(data.get("title") or "").strip()[:200], "body": body, "char_count": count_chars(body), "axis": axis}


# ─────────────────────────────── 3) 사진 슬롯 계획 ───────────────────────────────
# 본문 구조를 읽는 규칙은 여기 한 곳에만 둔다. reflow()·슬롯 계획·발행 블록 조립이
# 문단을 서로 다르게 세면 사진이 통째로 한 칸씩 밀린다.

HEADING_MAX_CHARS = 30


def is_heading(paragraph: str) -> bool:
    """reflow() 가 남기는 소제목 모양인가 — 한 줄이고, 짧고, 문장부호로 끝나지 않는다."""
    p = (paragraph or "").strip()
    if not p or "\n" in p:
        return False
    return len(p) <= HEADING_MAX_CHARS and not re.search(r"[.!?…]$", p)


def split_paragraphs(body: str) -> List[str]:
    """빈 줄로 나뉜 덩어리. 소제목도 하나의 덩어리로 들어 있다."""
    return [p.strip() for p in re.split(r"\n\s*\n", body or "") if p.strip()]


def sections(paragraphs: List[str]) -> List[Dict[str, Any]]:
    """소제목 기준으로 묶는다. → [{"heading": str|None, "body_indices": [문단 번호]}]

    사진을 고를 때 2문장짜리 문단만 보면 무슨 사진이 맞는지 알 수 없다. 섹션 단위로 봐야
    '이 대목이 무슨 이야기인지'가 잡힌다."""
    out: List[Dict[str, Any]] = []
    cur: Dict[str, Any] = {"heading": None, "body_indices": []}
    for i, p in enumerate(paragraphs):
        if is_heading(p):
            if cur["body_indices"] or cur["heading"]:
                out.append(cur)
            cur = {"heading": p, "body_indices": []}
        else:
            cur["body_indices"].append(i)
    if cur["body_indices"] or cur["heading"]:
        out.append(cur)
    return [s for s in out if s["body_indices"]]


def image_positions(paragraphs: List[str]) -> List[int]:
    """사진을 넣어도 되는 문단 번호(그 문단 '뒤'에 들어간다).

    - 소제목 뒤는 안 된다: 소제목과 첫 문장 사이에 사진이 끼면 글이 끊긴다.
    - 마지막 문단 뒤도 안 된다: 글 맨 밑에 사진만 남는다(푸터 이미지가 따로 있다).
    """
    last = len(paragraphs) - 1
    return [i for i, p in enumerate(paragraphs) if not is_heading(p) and i != last]


SLOT_SYSTEM = """당신은 병원 블로그 편집자다. 소제목으로 나뉜 각 대목을 읽고, 사진이 들어갈 자리와 어떤 사진이 어울리는지 정한다.
JSON 하나만: {"slots": [{"after_paragraph": 2, "need": "한 줄 설명", "keywords": ["진료실", "상담"], "stage": "도입|진료과정|시술|장비소개|마무리|기타"}]}
지킬 것
- after_paragraph 는 '사진 가능 위치'로 준 번호 중에서만 고른다. 다른 번호는 무시된다.
- 한 대목(소제목 구간)에는 사진을 최대 한 장만 넣는다. 사진이 대목 수보다 많으면 어울리는 대목에만 넣고 나머지는 비운다.
- 억지로 개수를 채우지 않는다. 사진이 어울리지 않는 대목은 건너뛴다.
- keywords 는 그 대목의 내용에서 뽑은 짧은 명사 3~6개(피사체/장소/장면). 사진 태그와 맞춰볼 값이다.
- need 는 '어떤 사진이 필요한지'를 한 줄로 적는다."""


def _slot_prompt(paragraphs: List[str], image_count: int, keyword: str) -> str:
    """LLM 이 대목 단위로 판단하게 구조를 그대로 보여 준다."""
    allowed = image_positions(paragraphs)
    lines: List[str] = [f"키워드: {keyword}", f"사진 최대 {image_count}장.",
                        f"사진 가능 위치(이 번호들 중에서만 고를 것): {allowed}", ""]
    for sec in sections(paragraphs):
        lines.append(f"[대목] {sec['heading'] or '(소제목 없는 도입부)'}")
        for i in sec["body_indices"]:
            lines.append(f"  {i}. {paragraphs[i][:400]}")
        lines.append("")
    return "\n".join(lines)


def _repair_slots(raw: Any, paragraphs: List[str], image_count: int, keyword: str) -> List[Dict[str, Any]]:
    """LLM 이 준 자리를 규칙에 맞게 고친다.

    모델은 소제목 뒤나 글 맨 끝을 곧잘 고르고, 한 대목에 여러 장을 몰아넣기도 한다.
    그대로 쓰면 사진이 엉뚱한 데 박히므로 여기서 걸러 낸다."""
    allowed = image_positions(paragraphs)
    if not allowed:
        return []
    section_of: Dict[int, int] = {}
    for si, sec in enumerate(sections(paragraphs)):
        for i in sec["body_indices"]:
            section_of[i] = si

    out: List[Dict[str, Any]] = []
    used_positions: set = set()
    used_sections: set = set()
    for s in (raw if isinstance(raw, list) else []):
        if len(out) >= image_count:
            break
        if not isinstance(s, dict):
            continue
        try:
            ap = int(s.get("after_paragraph"))
        except (TypeError, ValueError):
            continue
        if ap not in allowed or ap in used_positions:
            continue                      # 소제목 뒤·글 끝·중복 자리는 버린다
        si = section_of.get(ap)
        if si in used_sections:
            continue                      # 한 대목에 한 장
        used_positions.add(ap)
        used_sections.add(si)
        out.append({
            "after_paragraph": ap,
            "need": str(s.get("need") or "")[:200],
            "keywords": [str(k).strip() for k in (s.get("keywords") or []) if str(k).strip()][:8],
            "stage": str(s.get("stage") or "기타"),
        })

    # 모자라면 아직 사진이 없는 대목의 첫 자리에 채운다. 남는 대목이 없으면 그대로 둔다
    # — 억지로 넣은 무관한 사진은 없느니만 못하다.
    if len(out) < image_count:
        for si, sec in enumerate(sections(paragraphs)):
            if len(out) >= image_count:
                break
            if si in used_sections:
                continue
            spot = next((i for i in sec["body_indices"] if i in allowed and i not in used_positions), None)
            if spot is None:
                continue
            used_positions.add(spot)
            used_sections.add(si)
            out.append({"after_paragraph": spot, "need": sec["heading"] or "",
                        "keywords": [keyword] if keyword else [], "stage": "기타"})

    out.sort(key=lambda x: x["after_paragraph"])
    for i, s in enumerate(out):
        s["slot"] = i
    return out


async def plan_image_slots(body: str, image_count: int, keyword: str = "") -> List[Dict[str, Any]]:
    """사진이 들어갈 자리를 대목(소제목 구간) 단위로 정한다. 자리가 마땅치 않으면 요청보다 적게 돌려준다."""
    paragraphs = split_paragraphs(body)
    if not paragraphs or image_count <= 0:
        return []
    try:
        data = await cc.complete_json(SLOT_SYSTEM, _slot_prompt(paragraphs, image_count, keyword),
                                      max_tokens=4000, effort="low")
        raw = data.get("slots") if isinstance(data, dict) else data
    except Exception as e:  # noqa: BLE001
        logger.warning("[슬롯] LLM 실패, 대목별 기본 배치로 대체: %s", e)
        raw = None
    return _repair_slots(raw, paragraphs, image_count, keyword)


# ─────────────────────────────── 4) 검수 ───────────────────────────────

FLOW_CHECK_SYSTEM = """당신은 원고 검수자다. 주어진 '글 흐름'을 원고가 그 순서대로 따르는지 판정한다.
JSON 하나만: {"ok": true|false, "missing": ["빠진 단계"], "order_issue": "순서 문제 설명 or null", "notes": "한 줄"}"""

FACT_CHECK_SYSTEM = """당신은 의료 원고 검수자다. 변형 원고가 원본의 사실을 모두 담고 있고, 없는 사실을 추가하지 않았는지 본다.
JSON 하나만: {"ok": true|false, "missing": ["빠진 사실"], "added": ["원본에 없는 새 사실/수치/주장"], "notes": "한 줄"}"""


async def check_flow(body: str, flow: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not flow:
        return {"ok": True, "missing": [], "order_issue": None, "notes": "흐름 지정 없음"}
    steps = "\n".join(f"{i+1}. {s.get('title','')}: {s.get('goal','')}" for i, s in enumerate(flow))
    data = await cc.complete_json(FLOW_CHECK_SYSTEM, f"글 흐름:\n{steps}\n\n원고:\n{body[:8000]}", max_tokens=2000, effort="low")
    return data if isinstance(data, dict) else {"ok": False, "notes": "판정 실패"}


async def check_facts(variant: str, facts: List[Dict[str, str]]) -> Dict[str, Any]:
    if not facts:
        return {"ok": True, "missing": [], "added": [], "notes": "고정 사실 없음"}
    fl = "\n".join("- " + f["fact"] for f in facts)
    data = await cc.complete_json(FACT_CHECK_SYSTEM, f"보존할 사실:\n{fl}\n\n변형 원고:\n{variant[:8000]}", max_tokens=2000, effort="low")
    return data if isinstance(data, dict) else {"ok": False, "notes": "판정 실패"}


def similarity(a: str, b: str) -> float:
    """문장 3-gram 자카드 유사도(0~1). 0.35 넘으면 '너무 비슷'으로 본다."""
    def grams(t: str) -> set:
        t = re.sub(r"\s+", "", t or "")
        return {t[i : i + 3] for i in range(max(0, len(t) - 2))}
    ga, gb = grams(a), grams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


# 기존 검사기(medical_law_checker)가 놓치는 흔한 위반 표현. (정규식, 분류, 대안)
EXTRA_LAW_PATTERNS = [
    (r"완치", "치료효과_보장", "증상 개선"),
    (r"보장(합니다|해 드립니다|드립니다|됩니다)?", "치료효과_보장", "기대할 수 있습니다"),
    (r"100\s*%", "치료효과_보장", "많은 경우"),
    (r"부작용(이|은)?\s*(전혀\s*)?없", "치료효과_보장", "부작용이 적은 편"),
    (r"(즉시|바로)\s*효과", "치료효과_보장", "점차 개선"),
    (r"영구(적|히)", "치료효과_보장", "장기간"),
    (r"(유일|국내\s*최초|세계\s*최초)", "비교_우위", "(삭제)"),
    (r"\d[\d,]*\s*원", "가격_할인", "(가격 표기 삭제)"),
    (r"(할인|이벤트|무료|공짜)", "가격_할인", "(삭제)"),
    (r"(치료\s*후기|시술\s*후기|환자\s*후기)", "치료경험담", "치료 안내"),
]


def run_static_checks(title: str, body: str, forbidden: Optional[List[str]] = None) -> Dict[str, Any]:
    """LLM 없이 즉시 도는 검사: 의료광고법(기존 검사기 + 보강 패턴) + 병원 금칙어."""
    result: Dict[str, Any] = {"medical_law": [], "forbidden": [], "ok": True}
    try:
        from app.services.medical_law_checker import medical_law_checker  # type: ignore
        r = medical_law_checker.check(title + chr(10) + body)
        viol = r.get("violations") if isinstance(r, dict) else None
        if viol:
            result["medical_law"] = [
                {"text": v.get("text") or v.get("matched") or "", "category": v.get("category") or v.get("type") or "", "suggestion": v.get("suggestion") or v.get("replacement") or ""}
                for v in viol[:20]
            ]
    except Exception as e:  # noqa: BLE001
        logger.debug("[검수] 의료광고법 검사기 사용 불가: %s", e)
    text = f"{title}\n{body}"
    seen = {(v["text"], v["category"]) for v in result["medical_law"]}
    for pat, cat, alt in EXTRA_LAW_PATTERNS:
        for m in re.finditer(pat, text):
            key = (m.group(0), cat)
            if key in seen:
                continue
            seen.add(key)
            result["medical_law"].append({"text": m.group(0), "category": cat, "suggestion": alt})
        if len(result["medical_law"]) >= 30:
            break
    for w in forbidden or []:
        w = (w or "").strip()
        if w and w in text:
            result["forbidden"].append(w)
    result["ok"] = not result["medical_law"] and not result["forbidden"]
    return result
