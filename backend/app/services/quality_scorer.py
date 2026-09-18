"""
원고 품질 종합 채점기

생성된 원고를 여섯 축으로 채점하고, 어디를 어떻게 고쳐야 하는지 지시문을 돌려준다.
이 지시문이 그대로 재작성 프롬프트로 들어간다 (ai_rewrite_engine.generate 참고).

배점 (합계 100점 = 규칙 80 + LLM 심사 20)
  A. 의료광고법   게이트. 위반 심각도에 따라 총점 상한 (의료법 제56조 제2항)
  B. 몰입·공감    14점. 첫 문단 후킹, 자기참조, 장면 전개, 문체 리듬
  C. 이해도       14점. 쉬운 말, 능동태, 문장·문단 길이, 정보를 주는 소제목  [PEMAT-U]
  D. 행동가능성   14점. 구체적 행동, 단계·빈도, 언제 병원에 와야 하는지      [PEMAT-A]
  E. 신뢰         18점. 근거 인용, 양면+반박, 위협/효능 균형, AI 티 없음
  F. 차별화       12점. 이 병원에만 있는 내용이 실제로 글에 녹아 있는가
  G. 네이버 적합도  8점. 분량, 주제 집중, 구체 정보 밀도
  H. LLM 심사     20점. 독창성/경험/검색의도/소제목정합/차별성

근거
  - PEMAT (AHRQ): 환자 교육자료의 이해도와 행동가능성을 나눠 재는 검증 도구
  - EPPM (Witte & Allen 2000 메타분석): 위협 > 효능이면 방어적 회피로 역효과
  - 양면 메시지 메타분석 (Eisend): 단점 인정은 반박이 붙어야 설득력이 오른다
  - 서사 몰입 (Green & Brock): 장면·시간순 전개가 태도 변화와 상관
  - E-E-A-T / YMYL: 의료 콘텐츠는 신뢰가 최우선

규칙 기반 지표는 매 생성마다 공짜로 돌고, LLM 심사는 호출 1회를 더 쓴다.
"""

import json
import re
import statistics
from typing import Dict, List, Optional


# ── 의료광고법 위반 패턴 (의료법 제56조 제2항 각 호) ──────────────────────
# severity: critical = 확실한 위반, high = 위반 소지 큼, medium = 심의에서 지적 가능
MEDICAL_AD_RULES = [
    # 2호. 치료경험담 등 치료효과 오인 우려
    {
        "id": "testimonial_named",
        "severity": "critical",
        "clause": "제56조 제2항 제2호(치료경험담)",
        "pattern": r"(\d{1,2}0?대\s*[가-힣]{1,3}(?:OO|○○|씨|님|환자|어르신|할머니|할아버지))"
                   r"|([가-힣]{1,2}(?:OO|○○)\s*(?:씨|님|환자|어르신))",
        "message": "특정 개인을 지목한 치료 사례는 치료경험담 광고로 금지됩니다",
        "fix": "이름·이니셜·나이/성별을 붙인 개인 사례를 지우고 '이런 경우가 많습니다' 같은 반복 패턴 서술로 바꾸세요",
    },
    {
        "id": "testimonial_outcome",
        "severity": "high",
        "clause": "제56조 제2항 제2호(치료경험담)",
        "pattern": r"(치료\s*후|시술\s*후|수술\s*후)[^.!?\n]{0,40}"
                   r"(완전히|말끔히|깨끗하게|싹|씻은 듯)[^.!?\n]{0,20}(나았|사라졌|좋아졌|해결)",
        "message": "치료 전후 결과를 단정적으로 서술하면 치료효과 오인 광고가 됩니다",
        "fix": "결과 단정 대신 '개인차가 있습니다', '경과는 상태에 따라 다릅니다' 로 바꾸세요",
    },
    # 3호. 거짓 광고 / 8호. 과장 광고
    {
        "id": "absolute_claim",
        "severity": "critical",
        "clause": "제56조 제2항 제3호·제8호(거짓·과장)",
        # '통증 없이 지내다' 같은 부사구는 위반이 아니다. 단정하는 서술형만 잡는다.
        "pattern": r"(100\s*%|완치|영구적으로|절대\s*안전"
                   r"|(?:부작용|통증|흉터|후유증|다운타임)\s*(?:이|가)?\s*없(?:습니다|다|음|어요|는)"
                   r"|무조건\s*(?:낫|좋아)|반드시\s*(?:낫|치료))",
        "message": "효과를 단정하거나 부작용이 없다고 하는 표현은 과장 광고입니다",
        "fix": "'대부분', '개인차가 있습니다', '부작용이 적은 편입니다' 처럼 정도를 낮춰 쓰세요",
    },
    {
        "id": "superlative",
        "severity": "high",
        "clause": "제56조 제2항 제8호(과장)",
        "pattern": r"(최고의|최상의|국내\s*최초|세계\s*최초|유일한|넘버\s*원|No\.?\s*1|1위|"
                   r"기적적|획기적|가장\s*뛰어난)",
        "message": "최상급·최초·유일 표현은 객관적 근거 없이는 과장 광고로 봅니다",
        "fix": "최상급 표현을 지우고 사실 서술로 바꾸세요",
    },
    # 4호. 비교 광고 / 5호. 비방 광고
    {
        "id": "comparison",
        "severity": "high",
        "clause": "제56조 제2항 제4호·제5호(비교·비방)",
        "pattern": r"(타\s*병원|다른\s*병원|일반\s*병원)[^.!?\n]{0,20}(보다|대비|과\s*달리|와\s*달리)"
                   r"|(보다|대비)\s*(?:훨씬\s*)?(?:뛰어|우수|좋습|낫습)",
        "message": "다른 의료기관과 비교하는 내용은 비교 광고로 금지됩니다",
        "fix": "다른 병원과의 비교를 삭제하고 우리 진료 내용만 설명하세요",
    },
    # 13호. 비급여 진료비 할인·면제
    {
        "id": "price_discount",
        "severity": "critical",
        "clause": "제56조 제2항 제13호(비급여 할인·면제)",
        "pattern": r"(할인|이벤트\s*가|특가|프로모션|무료\s*(?:시술|수술|검사|진료)|"
                   r"\d+\s*만\s*원|\d{4,}\s*원|선착순|한정\s*수량)",
        "message": "비급여 진료비 할인·면제나 가격 노출은 환자 유인으로 금지됩니다",
        "fix": "가격·할인·이벤트 표현을 모두 지우고 '상담 시 안내' 로 바꾸세요",
    },
    # 7호. 부작용 정보 누락
    {
        "id": "missing_risk",
        "severity": "medium",
        "clause": "제56조 제2항 제7호(부작용 누락)",
        "pattern": None,  # 별도 로직으로 판정
        "message": "시술·수술을 다루면서 부작용이나 주의사항 언급이 없습니다",
        "fix": "부작용 가능성이나 주의해야 할 경우를 한 문단 넣으세요",
    },
    # 14호. 인증·보증·추천
    {
        "id": "endorsement",
        "severity": "medium",
        "clause": "제56조 제2항 제14호(인증·보증·추천)",
        "pattern": r"(수상|대상\s*수상|인증\s*병원|보건복지부\s*지정|추천\s*병원|"
                   r"[0-9]+년\s*연속\s*(?:1위|선정))",
        "message": "상장·인증·추천을 내세우는 표현은 허용된 경우가 아니면 금지됩니다",
        "fix": "수상·인증·추천 문구를 삭제하세요",
    },
    # 환자 유인 (제27조 제3항)
    {
        "id": "solicitation",
        "severity": "high",
        "clause": "제27조 제3항(환자 유인·알선)",
        "pattern": r"(지금\s*바로\s*(?:예약|상담|연락)|서둘러|오늘\s*안에|마감\s*임박|"
                   r"당장\s*예약|놓치지\s*마)",
        "message": "즉시 행동을 재촉하는 표현은 환자 유인으로 볼 수 있습니다",
        "fix": "'편하신 시간에 상담받아보세요' 정도로 낮추세요",
    },
]

# 시술/수술을 다루는 글인지 판정 (부작용 누락 검사용)
PROCEDURE_HINT = re.compile(r"(시술|수술|주사|레이저|보톡스|필러|이식|절개|마취|처치)")
RISK_HINT = re.compile(r"(부작용|합병증|주의|위험|드물게|나타날\s*수\s*있|개인차|재발|후유증)")

# AI 티 / 번역체
AI_CLICHES = [
    "결론적으로", "종합하면", "종합해보면", "알아보겠습니다", "소개해드리려고 합니다",
    "살펴보겠습니다", "다양한 방법이 있습니다", "도움이 되셨길 바랍니다",
    "중요한 점은", "핵심은 바로",
]
TRANSLATIONESE = [
    "것이 중요합니다", "것이 좋습니다", "되어집니다", "되어지고", "지는 것입니다",
    "하는 것을 추천드립니다", "라고 할 수 있습니다",
]
FILLER_WORDS = ["매우", "정말", "굉장히", "아주", "너무나", "참으로"]

# 근거·권위 신호
EVIDENCE_SIGNALS = re.compile(
    r"(학회|가이드라인|보건복지부|질병관리청|건강보험|심사평가원|의사협회|"
    r"연구(?:에|를|가|팀)|논문|임상|통계|조사\s*결과|자료에\s*따르면)"
)

# 특정 기관·연구를 이름 대고 인용한 대목.
# 근거 점수가 인용을 보상하다 보니 모델이 그럴듯한 출처를 지어내는 일이 있다
# (예: 원본에 없는 "미국 정형외과 학회(AAOS) 자료에 따르면").
# 의료 콘텐츠에서 허위 출처는 위험하므로, 점수로 보상하지 말고 사람이 확인하도록 뽑아낸다.
NAMED_CITATION = re.compile(
    r"[^.!?\n]{0,60}"
    r"(?:[가-힣A-Za-z]{2,}\s*(?:학회|협회|재단|대학교?|의과대학|연구소|연구팀|저널|위원회)"
    r"|보건복지부|질병관리청|국민건강보험공단|건강보험심사평가원|식품의약품안전처"
    r"|WHO|FDA|NIH|CDC|[A-Z]{3,5}\s*(?:가이드라인|지침)?)"
    r"[^.!?\n]{0,60}(?:에\s*따르면|자료|발표|보고|연구|지침|가이드라인|권고)[^.!?\n]{0,40}"
)
# 정직성 신호 (한계·개인차 인정)
HONESTY_SIGNALS = re.compile(
    r"(개인차|사람마다|경우에\s*따라|다를\s*수\s*있|아직\s*(?:연구|밝혀지지)|"
    r"단정하기\s*어렵|확실하지\s*않|모든\s*분(?:께|에게)\s*(?:해당|적용)되는\s*것은\s*아)"
)
# 구체성 신호
CONCRETE_SIGNALS = re.compile(r"(\d+\s*(?:%|퍼센트|년|개월|주|일|시간|분|회|명|kg|킬로|배|mm|cm))")

GREETING_START = re.compile(
    r"^\s*(안녕하세요|반갑습니다|오늘은|이번\s*시간에는|저는\s|우리\s*병원|저희\s*병원|"
    r"[가-힣]+\s*(?:병원|의원|한의원)\s*(?:원장|입니다))"
)


# ── 문헌 기반 신호들 ─────────────────────────────────────────────────────
# 아래 지표들은 다음 연구에서 가져왔다.
#  - PEMAT (AHRQ): 환자 교육자료의 '이해도(Understandability)' 와 '행동가능성(Actionability)'
#    을 나눠서 재는 검증된 도구. 일상어, 능동태, 청킹, 정보를 주는 소제목, 구체적 행동 제시.
#  - EPPM (Witte & Allen 2000 메타분석): 위협만 키우고 대처 방법을 주지 않으면
#    독자가 '방어적 회피' 로 빠져 오히려 역효과. 효능 표현이 위협 표현을 받쳐줘야 한다.
#  - 양면 메시지 메타분석 (Eisend): 단점을 인정하되 '반박'이 붙어야 설득력이 올라간다.
#    인정만 하고 대응이 없으면 일면 메시지보다 못하다.
#  - 서사 몰입 (Green & Brock): 장면·시간순 전개가 태도 변화와 상관(r≈.17~.23).
#  - 자기참조/동일시: 독자가 자기 상황이라고 느낄수록 설득력이 올라간다.

# 피동 표현 (PEMAT: 능동태를 쓸 것)
PASSIVE_PATTERNS = re.compile(
    r"(되어집니다|되어지고|여겨집니다|보여집니다|만들어집니다|알려져\s*있습니다|"
    r"[가-힣]되고\s*있습니다|[가-힣]되어\s*있습니다|[가-힣]되는\s*것으로)"
)

# 의학 전문용어처럼 보이는 말 (설명이 붙었는지 보려고 쓴다)
JARGON_PATTERN = re.compile(
    r"[가-힣]{2,}(?:염|증후군|경화증|골절|연골|인대|건염|신경통|퇴행성|"
    r"관절강|활액막|대퇴사두근|반월상|슬개|자기공명|초음파|내시경|"
    r"소염진통제|스테로이드|히알루론산|아세트아미노펜)"
)
# 용어 옆에 설명이 붙었다는 신호
EXPLAIN_MARKERS = re.compile(
    r"(라고\s*부릅니다|이라고\s*합니다|즉\s|쉽게\s*말하면|다시\s*말해|"
    r"란\s|이란\s|라는\s*뜻|말하자면|풀어서|쉽게\s*설명하면|\(|–|—)"
)

# PEMAT Actionability: 독자가 할 수 있는 구체적 행동
ACTION_PATTERNS = re.compile(
    r"([가-힣]{2,}\s*해\s*보세요|[가-힣]{2,}하세요|[가-힣]{2,}하시면\s*됩니다|"
    r"[가-힣]{2,}부터\s*(?:시작|해)|권해드립니다|권합니다|점검해|확인해\s*보|"
    r"줄여\s*보|늘려\s*보|바꿔\s*보|해\s*보시는\s*것)"
)
# 단계로 안내하는 신호
STEP_PATTERNS = re.compile(
    r"(먼저|우선|그다음|그\s*다음|다음으로|마지막으로|첫째|둘째|셋째|"
    r"\d+\s*단계|하루\s*\d+|일주일에\s*\d+|\d+\s*분씩|\d+\s*회씩)"
)
# 언제 병원에 와야 하는지 기준 (의료 콘텐츠의 핵심 행동 지침)
VISIT_CRITERIA = re.compile(
    r"((?:\d+\s*(?:주|일|개월|년)|이런\s*증상|다음\s*중|아래\s*같)[^.!?\n]{0,50}"
    r"(?:이상\s*(?:지속|계속|이어)|라면|이면|경우)[^.!?\n]{0,50}"
    r"(?:진료|병원|전문의|검사|상담|내원|찾)"
    r"|(?:진료|병원|전문의|검사|내원)[^.!?\n]{0,30}(?:받아\s*보|찾아|권|필요))"
)

# EPPM 위협 표현 (susceptibility / severity)
THREAT_SIGNALS = re.compile(
    r"(방치하면|놔두면|악화|심해지|진행되면|늦어지면|손상|만성화|"
    r"돌이킬\s*수\s*없|수술까지|걷기\s*(?:어|힘)|위험합니다|커집니다|"
    r"더\s*나빠|되돌릴\s*수\s*없)"
)
# EPPM 효능 표현 (response efficacy = 이 방법이 듣는다 / self-efficacy = 내가 할 수 있다)
RESPONSE_EFFICACY = re.compile(
    r"(도움이\s*됩니다|효과가\s*있|늦출\s*수\s*있|줄일\s*수\s*있|"
    r"관리할\s*수\s*있|좋아지|호전|나아지|막을\s*수\s*있|예방할\s*수\s*있)"
)
SELF_EFFICACY = re.compile(
    r"(어렵지\s*않|간단합니다|집에서도|혼자서도|누구나|하루\s*\d+\s*분|"
    r"당장|오늘부터|바로\s*시작|쉽게\s*할\s*수\s*있|무리\s*없이)"
)

# 양면 메시지: 한계 인정 + 반박(대응) 세트
CONCESSION = re.compile(
    r"(다만|하지만|물론|그렇다고|아쉽게도|한계가\s*있|완전하지\s*않|"
    r"모든\s*경우에\s*(?:듣|맞|해당)|개인차가\s*(?:크|있))"
)
REFUTATION = re.compile(
    r"(그래서|그렇기\s*때문에|대신|그럴\s*때는|이럴\s*때는|그런\s*경우에는|"
    r"보완|함께\s*하면|병행|다른\s*방법|이를\s*줄이려면)"
)

# 자기참조 (독자를 직접 지목)
SELF_REFERENCE = re.compile(
    r"(신가요\?|하시나요\?|으신가요\?|보신\s*적|여러분|혹시\s|"
    r"당신|이런\s*경험|겪어\s*보셨|느끼신)"
)
# 서사 몰입 (장면·시간 전개)
NARRATIVE_SIGNALS = re.compile(
    r"(아침에|밤에|저녁이면|계단을|앉았다\s*일어|자고\s*일어나|"
    r"처음에는|그러다|어느\s*날|무렵|하다\s*보면|순간|때마다)"
)


def _sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if len(p.strip()) >= 2]


def _paragraphs(text: str) -> List[str]:
    return [p.strip() for p in text.split("\n") if p.strip()]


def split_title_body(text: str):
    """
    생성 결과는 '제목 한 줄 + 빈 줄 + 본문' 형태다.
    첫 줄을 본문 첫 문단으로 착각하면 후킹 점수가 늘 깎이므로 분리한다.

    Returns:
        (title, body). 제목처럼 보이지 않으면 title 은 빈 문자열.
    """
    lines = text.split("\n")
    first = lines[0].strip() if lines else ""
    rest = "\n".join(lines[1:]).lstrip("\n")
    looks_like_title = (
        bool(first)
        and len(first) <= 60
        and not first.endswith((".", "!", "?"))
        and bool(rest.strip())
    )
    if looks_like_title:
        return first, rest
    return "", text


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _band_score(value: float, lo_ok: float, hi_ok: float, lo_zero: float, hi_zero: float) -> float:
    """lo_ok~hi_ok 구간이면 1.0, lo_zero/hi_zero 바깥이면 0.0, 사이는 선형."""
    if lo_ok <= value <= hi_ok:
        return 1.0
    if value < lo_ok:
        if value <= lo_zero:
            return 0.0
        return (value - lo_zero) / (lo_ok - lo_zero)
    if value >= hi_zero:
        return 0.0
    return (hi_zero - value) / (hi_zero - hi_ok)


class QualityScorer:
    """원고 품질 종합 채점기"""

    # LLM 심사가 맡는 배점 (나머지 70점은 규칙 기반)
    LLM_POINTS = 20

    # ── A. 의료광고법 ────────────────────────────────────────────────
    def check_medical_ad_law(self, text: str) -> Dict:
        violations = []
        for rule in MEDICAL_AD_RULES:
            if rule["id"] == "missing_risk":
                if PROCEDURE_HINT.search(text) and not RISK_HINT.search(text):
                    violations.append({
                        "id": rule["id"], "severity": rule["severity"], "clause": rule["clause"],
                        "message": rule["message"], "fix": rule["fix"], "samples": [],
                    })
                continue

            hits = [m.group(0).strip() for m in re.finditer(rule["pattern"], text)]
            if hits:
                # 중복 제거 후 최대 3개만 보여준다
                seen, samples = set(), []
                for h in hits:
                    if h not in seen:
                        seen.add(h)
                        samples.append(h)
                    if len(samples) >= 3:
                        break
                violations.append({
                    "id": rule["id"], "severity": rule["severity"], "clause": rule["clause"],
                    "message": rule["message"], "fix": rule["fix"], "samples": samples,
                })

        critical = [v for v in violations if v["severity"] == "critical"]
        high = [v for v in violations if v["severity"] == "high"]

        # 위반이 있으면 총점에 상한을 건다
        if critical:
            cap = 55
        elif len(high) >= 2:
            cap = 70
        elif high:
            cap = 80
        else:
            cap = 100

        return {
            "passed": not critical and not high,
            "score_cap": cap,
            "violations": violations,
            "counts": {
                "critical": len(critical),
                "high": len(high),
                "medium": len(violations) - len(critical) - len(high),
            },
        }

    # ── B. 몰입·공감 (14점) ──────────────────────────────────────────
    # 서사 몰입(Green & Brock) + 자기참조/동일시 연구 기반
    def score_engagement(self, text: str) -> Dict:
        _, body = split_title_body(text)
        sents = _sentences(body)
        paras = _paragraphs(body)
        details = {}

        # B1. 첫 문단 후킹 (5점)
        first = paras[0] if paras else ""
        hook = 5.0
        notes = []
        if GREETING_START.search(first):
            hook -= 3.5
            notes.append("인사말이나 자기소개로 시작합니다. 독자가 자기 얘기라고 느낄 장면으로 여세요")
        if len(first) < 60:
            hook -= 1.5
            notes.append("첫 문단을 독자가 자기 상황이라고 느낄 장면으로 3~4문장 늘리세요")
        if not CONCRETE_SIGNALS.search(first) and "?" not in first[:200]:
            hook -= 1.0
            notes.append("첫 문단에 구체적인 증상 장면이나 독자에게 던지는 질문을 넣으세요")
        details["hook"] = {"score": round(_clamp(hook, 0, 5), 1), "max": 5, "notes": notes}

        # B2. 자기참조 (3점) - 독자를 직접 지목할수록 동일시가 올라간다
        notes = []
        sr = len(SELF_REFERENCE.findall(body))
        per_1k = sr / max(1, len(body) / 1000)
        sr_score = 3.0 * _band_score(per_1k, 1.5, 6, 0, 14)
        if per_1k < 1.5:
            notes.append(
                "독자를 직접 지목하는 문장이 부족합니다. "
                "'혹시 이런 적 있으신가요' 처럼 읽는 사람 상황을 짚는 문장을 두세 군데 넣으세요"
            )
        elif per_1k > 6:
            notes.append("독자에게 묻는 문장이 너무 잦습니다. 절반으로 줄이세요")
        details["self_reference"] = {"score": round(sr_score, 1), "max": 3, "notes": notes}

        # B3. 장면·전개 (3점)
        notes = []
        nar = len(NARRATIVE_SIGNALS.findall(body))
        nar_score = 3.0 * _band_score(nar / max(1, len(body) / 1000), 1.5, 8, 0, 16)
        if nar < 2:
            notes.append(
                "언제 어떤 상황에서 그런지가 안 보입니다. "
                "'아침에 첫발을 디딜 때' 처럼 시간과 장면이 들어간 묘사를 넣으세요"
            )
        details["narrative"] = {"score": round(nar_score, 1), "max": 3, "notes": notes}

        # B4. 문체 리듬 (3점)
        notes = []
        rhythm = 3.0
        endings = []
        for s in sents:
            m = re.search(r"([가-힣]{2,4})[.!?]?$", s)
            if m:
                endings.append(m.group(1))
        if len(endings) >= 6:
            variety = len(set(endings)) / len(endings)
            rhythm *= _clamp(variety / 0.5, 0.3, 1.0)
            if variety < 0.35:
                notes.append("문장 끝맺음이 단조롭습니다. -습니다 / -죠 / -예요 를 섞어 쓰세요")
            streak = max_streak = 1
            for i in range(1, len(endings)):
                streak = streak + 1 if endings[i] == endings[i - 1] else 1
                max_streak = max(max_streak, streak)
            if max_streak >= 3:
                rhythm *= 0.85
                notes.append("같은 종결어미가 3번 이상 연속됩니다")
        if sents:
            lens = [len(s) for s in sents]
            if len(lens) >= 5 and statistics.pstdev(lens) < 12:
                rhythm *= 0.85
                notes.append("문장 길이가 다 비슷합니다. 긴 설명 뒤에 짧은 문장을 하나 넣으세요")
        filler = sum(body.count(w) for w in FILLER_WORDS)
        if filler > len(sents) * 0.25:
            rhythm *= 0.85
            notes.append(f"빈 수식어(매우/정말/굉장히)가 {filler}번 나옵니다. 대부분 지우세요")
        details["rhythm"] = {"score": round(_clamp(rhythm, 0, 3), 1), "max": 3, "notes": notes}

        return {"score": round(sum(d["score"] for d in details.values()), 1), "max": 14, "details": details}

    # ── C. 이해도 (14점) — PEMAT Understandability ────────────────────
    def score_understandability(self, text: str) -> Dict:
        _, body = split_title_body(text)
        sents = _sentences(body)
        paras = _paragraphs(body)
        details = {}

        # C1. 쉬운 말 (5점) - 전문용어를 쓰면 그 자리에서 풀어줬는가
        notes = []
        jargons = list(JARGON_PATTERN.finditer(body))
        if jargons:
            explained = 0
            for m in jargons:
                window = body[max(0, m.start() - 40): m.end() + 80]
                if EXPLAIN_MARKERS.search(window):
                    explained += 1
            ratio = explained / len(jargons)
            plain = 5.0 * _clamp(ratio / 0.5, 0, 1)
            if ratio < 0.5:
                unexplained = [m.group(0) for m in jargons if not EXPLAIN_MARKERS.search(
                    body[max(0, m.start() - 40): m.end() + 80])]
                sample = ", ".join(sorted(set(unexplained))[:3])
                notes.append(
                    f"전문용어를 설명 없이 씁니다({sample}). 처음 나올 때 '쉽게 말하면' 이나 "
                    "괄호로 한 번 풀어주세요"
                )
        else:
            plain = 5.0
        details["plain_language"] = {"score": round(plain, 1), "max": 5, "notes": notes}

        # C2. 능동태 (3점)
        notes = []
        passives = len(PASSIVE_PATTERNS.findall(body))
        ratio = passives / max(1, len(sents))
        act = 3.0 * _band_score(ratio, 0, 0.08, -1, 0.3)
        if ratio > 0.08:
            notes.append(
                f"피동 표현이 {passives}번 나옵니다. '~되어집니다', '~되고 있습니다' 를 "
                "'~합니다', '~입니다' 로 바꾸세요"
            )
        details["active_voice"] = {"score": round(act, 1), "max": 3, "notes": notes}

        # C3. 문장·문단 길이 (3점)
        notes = []
        chunk = 3.0
        if sents:
            lens = [len(s) for s in sents]
            avg = statistics.mean(lens)
            long_ratio = sum(1 for l in lens if l > 60) / len(lens)
            chunk *= 0.5 * _band_score(avg, 35, 58, 15, 90) + 0.5 * _band_score(long_ratio, 0, 0.25, -1, 0.6)
            if avg > 58:
                notes.append(f"문장이 깁니다(평균 {avg:.0f}자). 50자 넘는 문장은 둘로 나누세요")
            elif long_ratio > 0.25:
                notes.append(f"60자 넘는 문장이 {long_ratio*100:.0f}%입니다. 긴 문장을 쪼개세요")
        plens = [len(p) for p in paras if len(p) > 40]
        if plens and statistics.mean(plens) > 320:
            chunk *= 0.8
            notes.append(f"문단이 깁니다(평균 {statistics.mean(plens):.0f}자). 250자 안팎으로 끊으세요")
        details["chunking"] = {"score": round(_clamp(chunk, 0, 3), 1), "max": 3, "notes": notes}

        # C4. 정보를 주는 소제목 (3점)
        notes = []
        headings = [p for p in paras if len(p) <= 45 and not p.endswith((".", "!"))]
        n_head = len(headings)
        head_score = 3.0 * _band_score(n_head, 3, 7, 0, 12)
        if n_head < 3:
            notes.append(f"소제목이 {n_head}개뿐입니다. 4~5개로 나누세요. 긴 글이 벽처럼 보이면 이탈합니다")
        elif n_head > 7:
            notes.append(f"소제목이 {n_head}개로 너무 잘게 쪼개졌습니다. 5개 안팎으로 합치세요")
        # 소제목이 내용을 알려주는가 (너무 짧거나 명사 한 덩어리면 정보가 없다)
        if headings:
            vague = [h for h in headings if len(h) < 8]
            if vague:
                head_score *= 0.8
                notes.append(f"소제목이 너무 짧아 내용을 알려주지 못합니다: {', '.join(vague[:2])}")
        details["informative_headers"] = {"score": round(_clamp(head_score, 0, 3), 1), "max": 3, "notes": notes}

        return {"score": round(sum(d["score"] for d in details.values()), 1), "max": 14, "details": details}

    # ── D. 행동가능성 (14점) — PEMAT Actionability ────────────────────
    def score_actionability(self, text: str) -> Dict:
        _, body = split_title_body(text)
        details = {}
        per_k = max(1, len(body) / 1000)

        # D1. 구체적 행동 제시 (6점)
        notes = []
        acts = len(ACTION_PATTERNS.findall(body))
        a = 6.0 * _band_score(acts / per_k, 2, 10, 0, 22)
        if acts / per_k < 2:
            notes.append(
                "읽고 나서 뭘 하면 되는지가 없습니다. "
                "독자가 오늘 바로 할 수 있는 행동을 두세 개 넣으세요"
            )
        details["concrete_actions"] = {"score": round(a, 1), "max": 6, "notes": notes}

        # D2. 단계·빈도 안내 (3점)
        notes = []
        steps = len(STEP_PATTERNS.findall(body))
        s = 3.0 * _band_score(steps / per_k, 1.5, 8, 0, 18)
        if steps / per_k < 1.5:
            notes.append(
                "행동이 뭉뚱그려져 있습니다. '하루 10분씩', '먼저 ~하고 그다음 ~' 처럼 "
                "횟수나 순서를 붙이세요"
            )
        details["steps"] = {"score": round(s, 1), "max": 3, "notes": notes}

        # D3. 언제 병원에 와야 하는지 (5점)
        notes = []
        has_criteria = bool(VISIT_CRITERIA.search(body))
        v = 5.0 if has_criteria else 1.0
        if not has_criteria:
            notes.append(
                "언제 병원에 와야 하는지 기준이 없습니다. "
                "'통증이 3주 넘게 이어지면 진료를 받아보세요' 처럼 판단 기준을 한 문장 넣으세요"
            )
        details["when_to_visit"] = {"score": v, "max": 5, "notes": notes}

        return {"score": round(sum(d["score"] for d in details.values()), 1), "max": 14, "details": details}

    # ── E. 신뢰 (18점) — E-E-A-T + 양면 메시지 + EPPM 균형 ────────────
    def score_trust(self, text: str, source_text: Optional[str] = None) -> Dict:
        """
        Args:
            source_text: 원본 브리핑. 주면 글에 나온 기관 인용이 원본에 있던 것인지 대조한다.
        """
        _, body = split_title_body(text)
        sents = _sentences(body)
        details = {}
        per_k = max(1, len(body) / 1000)

        # E1. 근거 인용 (5점)
        # 지어낸 출처는 점수로 보상하지 않는다. 원본에 없는 기관명이 나오면 감점하고 확인 대상으로 뽑는다.
        notes = []
        ev = len(EVIDENCE_SIGNALS.findall(body))
        ev_score = 5.0 * _band_score(ev, 2, 8, 0, 20)

        citations = [m.group(0).strip() for m in NAMED_CITATION.finditer(body)]
        unverified = []
        if citations and source_text:
            for c in citations:
                # 인용문에서 기관 이름만 뽑아 원본에 있었는지 본다
                org = re.search(
                    r"([가-힣A-Za-z]{2,}\s*(?:학회|협회|재단|대학교?|의과대학|연구소|연구팀|저널|위원회)"
                    r"|보건복지부|질병관리청|국민건강보험공단|건강보험심사평가원|식품의약품안전처"
                    r"|WHO|FDA|NIH|CDC)",
                    c,
                )
                if org and org.group(0).strip() not in source_text:
                    unverified.append(c)
        elif citations:
            unverified = citations

        if unverified:
            # 원본에 없던 출처를 붙인 만큼 근거 점수를 깎는다 (허위 인용 유인 제거)
            ev_score *= _clamp(1 - 0.4 * len(unverified), 0.2, 1.0)
            notes.append(
                f"원본에 없던 출처를 인용했습니다({len(unverified)}건). "
                "사실이면 그대로 두시고, 아니면 기관명을 빼고 일반론으로 바꾸세요: "
                + " / ".join(u[:60] for u in unverified[:2])
            )
        if ev < 2:
            notes.append(
                "근거를 한두 군데 넣으세요. 확실히 아는 공공기관·학회 자료만 쓰고, "
                "없으면 출처를 지어내지 말고 '일반적으로 알려진 바로는' 처럼 쓰세요"
            )
        details["evidence"] = {
            "score": round(ev_score, 1), "max": 5, "notes": notes,
            "citations": citations, "unverified_citations": unverified,
        }

        # E2. 양면 + 반박 (5점)
        # 메타분석상 '단점 인정 + 반박' 이 일면 메시지보다 설득력이 높고,
        # 인정만 하고 대응이 없으면 오히려 못하다. 그래서 세트로 잡는다.
        notes = []
        pairs, lone = 0, 0
        for i, s in enumerate(sents):
            if CONCESSION.search(s):
                window = " ".join(sents[i: i + 3])
                if REFUTATION.search(window):
                    pairs += 1
                else:
                    lone += 1
        if pairs == 0 and lone == 0:
            ts = 1.0
            notes.append(
                "한계나 예외를 인정하는 대목이 없습니다. '다만 ~한 경우에는 효과가 덜합니다. "
                "그럴 때는 ~합니다' 처럼 인정과 대응을 붙여서 한 군데 넣으세요"
            )
        else:
            ts = 5.0 * _clamp(pairs / 2.0, 0, 1)
            if lone > pairs:
                ts *= 0.7
                notes.append(
                    "한계를 인정만 하고 어떻게 대응하는지가 없습니다. "
                    "인정한 다음에는 '그럴 때는 ~합니다' 로 반드시 받아주세요"
                )
            elif pairs < 2:
                notes.append("한계 인정과 대응을 한 세트 더 넣으면 신뢰가 올라갑니다")
        details["two_sided"] = {"score": round(_clamp(ts, 0, 5), 1), "max": 5, "notes": notes}

        # E3. 위협 / 효능 균형 (5점) — EPPM
        notes = []
        threat = len(THREAT_SIGNALS.findall(body))
        eff = len(RESPONSE_EFFICACY.findall(body)) + len(SELF_EFFICACY.findall(body))
        if threat == 0 and eff == 0:
            te = 2.5
            notes.append("방치했을 때의 위험도, 관리하면 나아진다는 이야기도 없습니다. 둘 다 넣으세요")
        elif threat == 0:
            te = 3.5
            notes.append("왜 지금 신경 써야 하는지가 약합니다. 미뤘을 때 어떻게 되는지 한 문장 넣으세요")
        else:
            ratio = eff / threat
            te = 5.0 * _clamp(ratio / 1.0, 0, 1)
            if ratio < 1.0:
                notes.append(
                    f"겁주는 대목({threat}곳)이 해결책({eff}곳)보다 많습니다. "
                    "위협만 크면 독자는 오히려 외면합니다. "
                    "'이렇게 하면 늦출 수 있습니다', '집에서도 할 수 있습니다' 같은 문장을 늘리세요"
                )
        details["threat_efficacy"] = {"score": round(_clamp(te, 0, 5), 1), "max": 5, "notes": notes}

        # E4. AI 티 / 번역체 (3점)
        notes = []
        cliche_hits = [c for c in AI_CLICHES if c in body]
        trans_hits = [t for t in TRANSLATIONESE if t in body]
        nat = _clamp(3.0 - (len(cliche_hits) * 0.8 + len(trans_hits) * 0.6), 0, 3)
        if cliche_hits:
            notes.append(f"AI 가 쓴 티가 나는 상투구를 지우세요: {', '.join(cliche_hits[:4])}")
        if trans_hits:
            notes.append(f"번역체를 자연스러운 한국어로 고치세요: {', '.join(trans_hits[:4])}")
        details["naturalness"] = {"score": round(nat, 1), "max": 3, "notes": notes}

        return {"score": round(sum(d["score"] for d in details.values()), 1), "max": 18, "details": details}

    # ── G. 네이버 적합도 (8점) ─────────────────────────────────
    def score_naver_fit(self, text: str, keyword: Optional[str] = None) -> Dict:
        details = {}
        length = len(text)

        # C1. 분량 (5점) - 체류시간 확보 하한과 이탈 상한
        notes = []
        ln = 3.0 * _band_score(length, 1200, 2600, 500, 4500)
        if length < 1200:
            notes.append(f"{length}자로 짧습니다. 체류 60초를 넘기려면 1,200자 이상이 안전합니다")
        elif length > 2600:
            notes.append(f"{length}자로 깁니다. 지나치게 길면 이탈률이 올라갑니다")
        details["length"] = {"score": round(ln, 1), "max": 3, "notes": notes}

        # C2. 주제 집중도 (5점) - 상위 명사의 반복 집중
        notes = []
        words = re.findall(r"[가-힣]{2,}", text)
        focus = 3.0
        if len(words) >= 50:
            freq: Dict[str, int] = {}
            for w in words:
                freq[w] = freq.get(w, 0) + 1
            top = sorted(freq.values(), reverse=True)[:5]
            share = sum(top) / len(words)
            focus = 3.0 * _band_score(share, 0.035, 0.12, 0.01, 0.25)
            if share < 0.035:
                notes.append("주제가 흩어져 보입니다. 핵심 주제어를 본문에 자연스럽게 더 쓰고 곁가지 내용을 덜어내세요")
            elif share > 0.12:
                notes.append("같은 단어 반복이 지나칩니다. 일부를 다른 표현으로 바꾸세요. 키워드 남용으로 보일 수 있습니다")
        if keyword:
            # '무릎 관절염 초기증상' 처럼 붙여 쓴 키워드는 본문에 그대로 안 나온다.
            # 구성 어절이 본문에 얼마나 등장하는지로 본다.
            tokens = [t for t in re.split(r"\s+", keyword.strip()) if len(t) >= 2]
            if tokens:
                covered = sum(1 for t in tokens if t in text)
                ratio = covered / len(tokens)
                if ratio < 0.5:
                    focus *= 0.6
                    missing = [t for t in tokens if t not in text]
                    notes.append(f"핵심 키워드 '{keyword}' 가 본문에 거의 안 나옵니다 (빠진 말: {', '.join(missing)})")
                elif ratio < 1.0:
                    focus *= 0.85
                    missing = [t for t in tokens if t not in text]
                    notes.append(f"키워드 구성어 중 '{', '.join(missing)}' 가 본문에 없습니다")
        details["topic_focus"] = {"score": round(_clamp(focus, 0, 3), 1), "max": 3, "notes": notes}

        # C3. 구체 정보 밀도 (5점) - DIA 가 보는 '실질 정보'
        notes = []
        concrete = len(CONCRETE_SIGNALS.findall(text))
        per_1k = concrete / max(1, length / 1000)
        dens = 2.0 * _band_score(per_1k, 4, 16, 0, 30)
        if per_1k < 4:
            notes.append(f"구체적인 수치가 1,000자당 {per_1k:.1f}개뿐입니다. 기간, 빈도, 정도를 나타내는 숫자를 본문에 더 넣어 일반론에서 벗어나게 하세요")
        details["concreteness"] = {"score": round(dens, 1), "max": 2, "notes": notes}

        total = sum(d["score"] for d in details.values())
        return {"score": round(total, 1), "max": 8, "details": details}

    # ── E. 차별화 (15점) ─────────────────────────────────────────────
    @staticmethod
    def _keyphrases(item_text: str) -> List[str]:
        """
        차별점 문장에서 '이 병원에만 있는' 티가 나는 말을 뽑는다.
        (장비명, 검사명, 술기명 같은 고유한 명사·영문·숫자)
        """
        cleaned = re.sub(r"[^\w가-힣\s]", " ", item_text)
        toks = [t for t in cleaned.split() if len(t) >= 2]
        # 흔한 말은 변별력이 없으므로 뺀다
        stop = {
            "환자", "진료", "치료", "병원", "우리", "저희", "경우", "때문", "위해", "통해",
            "합니다", "있습니다", "때는", "그리고", "하지만", "가능", "사용", "진행", "확인",
        }
        return [t for t in toks if t not in stop][:6]

    def score_differentiation(self, text: str, differentiators: Optional[Dict] = None) -> Dict:
        """
        프로필에 적어둔 '이 병원만의 것' 이 실제로 본문에 녹아 있는지 본다.
        재료 자체가 없으면 채점하지 않고 그 사실을 알린다.
        """
        items = (differentiators or {}).get("items") or []
        philosophy = (differentiators or {}).get("philosophy") or ""

        if not items and not philosophy:
            # 입력이 없으면 감점 대신 '재료 없음' 으로 절반만 준다.
            # 원장이 재료를 넣는 순간 만점까지 갈 수 있다는 걸 점수로 보여준다.
            return {
                "score": 6.0,
                "max": 12,
                "details": {
                    "differentiation": {
                        "score": 6.0, "max": 12,
                        "notes": [
                            "프로필에 이 병원만의 강점(장비·술기·검사·진료 과정·경력)이 등록돼 있지 않아 "
                            "글이 어느 병원에나 해당하는 내용이 됩니다. 프로필에서 차별점을 채우면 점수가 올라갑니다"
                        ],
                    }
                },
                "material_count": 0,
            }

        texts = [it.get("text", "") if isinstance(it, dict) else str(it) for it in items]
        if philosophy:
            texts.append(philosophy)

        reflected, missing = [], []
        for t in texts:
            if not t.strip():
                continue
            phrases = self._keyphrases(t)
            if not phrases:
                continue
            hit = sum(1 for p in phrases if p in text)
            if hit / len(phrases) >= 0.34:
                reflected.append(t)
            else:
                missing.append(t)

        total_items = len(reflected) + len(missing)
        notes = []
        if total_items == 0:
            score = 6.0
        else:
            ratio = len(reflected) / total_items
            # 전부 넣을 필요는 없다. 절반 이상 녹아 있으면 만점.
            score = 12.0 * _clamp(ratio / 0.5, 0, 1)
            if len(reflected) == 0:
                notes.append(
                    "이 병원만의 강점이 글에 하나도 안 들어갔습니다. "
                    f"다음 중 하나를 독자의 문제를 설명하는 흐름 안에서 녹이세요: {missing[0][:60]}"
                )
            elif ratio < 0.5:
                notes.append(
                    f"등록된 강점 {total_items}개 중 {len(reflected)}개만 반영됐습니다. "
                    f"'{missing[0][:50]}' 을 본문에 자연스럽게 더 넣으세요"
                )

        return {
            "score": round(score, 1),
            "max": 12,
            "details": {
                "differentiation": {
                    "score": round(score, 1), "max": 12, "notes": notes,
                    "reflected": reflected, "missing": missing,
                }
            },
            "material_count": total_items,
        }

    # ── 규칙 기반 종합 ───────────────────────────────────────────────
    def score_rules(
        self,
        text: str,
        keyword: Optional[str] = None,
        differentiators: Optional[Dict] = None,
        source_text: Optional[str] = None,
    ) -> Dict:
        law = self.check_medical_ad_law(text)
        engagement = self.score_engagement(text)
        understandability = self.score_understandability(text)
        actionability = self.score_actionability(text)
        trust = self.score_trust(text, source_text=source_text)
        diff = self.score_differentiation(text, differentiators)
        naver = self.score_naver_fit(text, keyword)
        # 14 + 14 + 14 + 18 + 12 + 8 = 80점
        rule_total = (
            engagement["score"] + understandability["score"] + actionability["score"]
            + trust["score"] + diff["score"] + naver["score"]
        )
        return {
            "law": law,
            "engagement": engagement,
            "understandability": understandability,
            "actionability": actionability,
            "trust": trust,
            "differentiation": diff,
            "naver_fit": naver,
            "rule_total": round(rule_total, 1),
            "rule_max": 80,
        }

    # ── LLM 심사 프롬프트 (주관 항목 25점) ───────────────────────────
    @staticmethod
    def build_judge_prompt(
        text: str, title: str = "", keyword: str = "", differentiators: Optional[Dict] = None
    ) -> str:
        head = f"제목: {title}\n키워드: {keyword}\n\n" if (title or keyword) else ""

        diff_block = ""
        items = (differentiators or {}).get("items") or []
        philosophy = (differentiators or {}).get("philosophy") or ""
        if items or philosophy:
            lines = []
            if philosophy:
                lines.append(f"- 진료 원칙: {philosophy}")
            for it in items:
                t = it.get("text", "") if isinstance(it, dict) else str(it)
                if t.strip():
                    lines.append(f"- {t}")
            diff_block = (
                "\n<이 병원이 내세운 강점>\n" + "\n".join(lines) + "\n</이 병원이 내세운 강점>\n"
            )

        return f"""<원고>
{head}{text}
</원고>
{diff_block}

너는 이 글이 네이버 검색에서 상위에 올라갈 만한지, 그리고 검색해서 들어온 사람이
끝까지 읽을 만한지 심사하는 사람이다. 후하게 주지 않는다. 근거 없이 점수를 주지 않는다.

다음 다섯 항목을 각각 0~4점으로 매긴다.

originality  이 글에만 있는 내용이 있는가. 같은 키워드로 검색하면 나오는 흔한 글과 구별되는가.
             일반론만 있으면 0~1점.
experience   직접 해본 사람만 아는 디테일이 있는가. 현장에서 오가는 말, 자주 나오는 오해,
             판단이 갈리는 지점 같은 것. 교과서 요약이면 0~1점.
intent       이 키워드로 검색한 사람의 질문이 글 안에서 해결되는가. 읽고 나서 다시 검색해야 하면 0~1점.
heading_fit  소제목이 그 아래 내용을 정직하게 알려주는가. 궁금증만 자극하고 답이 없으면 감점.
differentiation 이 글을 읽고 나서 '다른 데 말고 여기서 봐야겠다' 는 이유가 생기는가.
             위에 이 병원이 내세운 강점이 주어졌다면, 그것이 자랑처럼 나열되지 않고
             독자의 문제를 설명하는 흐름 안에 녹아 있는지를 본다.
             어느 병원 글에나 그대로 넣어도 말이 되는 내용뿐이면 0~1점.
             강점이 주어지지 않았다면, 글 자체에서 이 사람만의 판단 기준이 드러나는지로 본다.

각 항목마다 왜 그 점수인지 한 문장, 그리고 점수를 올리려면 무엇을 고쳐야 하는지 한 문장을 쓴다.
고칠 점은 추상적으로 쓰지 말고 이 원고의 어느 대목을 어떻게 바꾸라고 쓴다.

아래 JSON 만 출력한다. 다른 말은 쓰지 않는다.
{{"originality":{{"score":0,"why":"","fix":""}},
"experience":{{"score":0,"why":"","fix":""}},
"intent":{{"score":0,"why":"","fix":""}},
"heading_fit":{{"score":0,"why":"","fix":""}},
"differentiation":{{"score":0,"why":"","fix":""}}}}"""

    @staticmethod
    def parse_judge(raw: str) -> Optional[Dict]:
        """LLM 심사 결과 JSON 파싱. 실패하면 None."""
        if not raw:
            return None
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None

        keys = ["originality", "experience", "intent", "heading_fit", "differentiation"]
        details, total = {}, 0.0
        for k in keys:
            item = data.get(k) or {}
            try:
                sc = _clamp(float(item.get("score", 0)), 0, 4)
            except (TypeError, ValueError):
                sc = 0.0
            total += sc
            details[k] = {
                "score": sc,
                "max": 4,
                "why": str(item.get("why", ""))[:300],
                "fix": str(item.get("fix", ""))[:300],
            }
        return {"score": round(total, 1), "max": 20, "details": details}

    # ── 최종 합산 ────────────────────────────────────────────────────
    def combine(self, rules: Dict, judge: Optional[Dict]) -> Dict:
        if judge:
            raw_total = rules["rule_total"] + judge["score"]
            judged = True
        else:
            # LLM 심사를 못 했으면 규칙 점수를 100점 만점으로 환산한다
            raw_total = rules["rule_total"] / 80 * 100
            judged = False

        cap = rules["law"]["score_cap"]
        total = min(round(raw_total, 1), cap)

        if total >= 85:
            grade = "A"
        elif total >= 75:
            grade = "B"
        elif total >= 65:
            grade = "C"
        else:
            grade = "D"

        return {
            "total": total,
            # 상한에 걸린 경우 총점만 보면 개선이 안 보인다.
            # 재작성본과 비교할 때는 raw_total 과 위반 수를 같이 본다 (_better_than 참고).
            "raw_total": round(raw_total, 1),
            "grade": grade,
            "capped_by_law": raw_total > cap,
            "score_cap": cap,
            "judged_by_llm": judged,
            "law": rules["law"],
            "engagement": rules["engagement"],
            "understandability": rules["understandability"],
            "actionability": rules["actionability"],
            "trust": rules["trust"],
            "differentiation": rules["differentiation"],
            "naver_fit": rules["naver_fit"],
            "llm_judge": judge,
        }

    @staticmethod
    def is_better(new: Dict, old: Dict) -> bool:
        """
        재작성본이 원본보다 나은가.
        총점만 비교하면 법 위반 상한에 걸렸을 때 개선이 보이지 않으므로,
        '심각한 위반 수 -> 원점수' 순서로 본다.
        """
        def key(r):
            c = r["law"]["counts"]
            return (-(c["critical"] * 2 + c["high"]), r.get("raw_total", r["total"]))

        return key(new) > key(old)

    # ── 재작성 지시문 생성 ───────────────────────────────────────────
    def build_revision_notes(self, report: Dict, limit: int = 8) -> List[str]:
        """
        점수가 낮은 순서대로 '무엇을 어떻게 고쳐야 하는지'를 뽑는다.
        이 문장들이 그대로 재작성 프롬프트에 들어간다.
        """
        notes: List[str] = []

        # 법 위반이 최우선
        for v in report["law"]["violations"]:
            if v["severity"] in ("critical", "high"):
                sample = f" (예: {', '.join(v['samples'])})" if v.get("samples") else ""
                notes.append(f"[의료광고법 {v['clause']}] {v['message']}{sample}. {v['fix']}")

        # 규칙 기반 감점 항목을 손실이 큰 순서로
        buckets = []
        for axis in ("engagement", "understandability", "actionability", "trust",
                     "differentiation", "naver_fit"):
            for name, d in report[axis]["details"].items():
                loss = d["max"] - d["score"]
                if loss > 0.5 and d.get("notes"):
                    buckets.append((loss, d["notes"]))
        for _, ns in sorted(buckets, key=lambda x: -x[0]):
            notes.extend(ns)

        # LLM 심사에서 3점 미만인 항목의 개선 지시
        if report.get("llm_judge"):
            weak = [
                (d["score"], d["fix"])
                for d in report["llm_judge"]["details"].values()
                if d["score"] < 2.5 and d.get("fix")
            ]
            for _, fix in sorted(weak, key=lambda x: x[0]):
                notes.append(fix)

        # 중복 제거
        seen, out = set(), []
        for n in notes:
            if n and n not in seen:
                seen.add(n)
                out.append(n)
        return out[:limit]


quality_scorer = QualityScorer()
