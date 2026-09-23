"""
글쓰기 규격 설계 + Gemini 프롬프트 컴파일러

지금까지 이 앱의 분석 자산(상위글 실측, 설득력 스코어러, 의료법/금칙어 체커)은
전부 '글을 쓴 뒤에 채점하는' 용도로만 쓰였다. 정작 글을 쓰는 프롬프트에는
키워드 문자열 하나만 들어갔다.

이 모듈은 그 순서를 뒤집는다. 쓰기 '전'에

    딥리서치(serp_research_service)
      + 실측 규격(상위글 글자수/이미지/소제목)
      + 전환 설계(PersuasionScorer 가 채점하는 4축)
      + 네이버 노출 원칙
      + 의료법/금칙어 금지 목록

을 하나의 한국어 프롬프트로 컴파일해서 Gemini 에게 넘긴다.
그러면 생성물이 채점 기준을 이미 만족한 상태로 나온다.

전부 실측/규칙 기반이며 LLM 을 쓰지 않는다.
"""

import hashlib
import math
from typing import Dict, List, Optional

from app.services.forbidden_words_checker import ForbiddenWordsChecker
from app.services.medical_law_checker import MedicalLawChecker


# ============================================================
# 기본값 - 실측 데이터를 못 얻었을 때만 쓰는 보수적인 값
# ============================================================
FALLBACK = {
    "content_length": 2000,
    "image_count": 8,
    "heading_count": 5,
    "title_length": 32,
    "keyword_count": 8,
}

# 상위글을 '살짝' 넘어서는 배수. 과하게 늘리면 체류시간 대비 이탈이 커진다.
LENGTH_MULTIPLIER = 1.15

# 네이버 모바일 검색결과에서 제목이 잘리는 지점
TITLE_MAX = 40
TITLE_MIN = 22


def _avg(summary: Optional[Dict], *path, default: float = 0.0) -> float:
    """summary 딕셔너리에서 중첩 키를 안전하게 꺼낸다"""
    node = summary or {}
    for key in path:
        if not isinstance(node, dict):
            return default
        node = node.get(key, {})
    if isinstance(node, (int, float)):
        return float(node)
    return default


def build_spec(research: Dict, search_volume: int = 0) -> Dict:
    """
    딥리서치 결과 -> 이 키워드에 맞는 글쓰기 규격

    상위글이 세워놓은 기준을 조금씩 넘어서되, 무리하게 부풀리지 않는다.
    """
    keyword = research.get("keyword", "")
    summary = research.get("summary")
    sample_count = int(_avg(summary, "sample_count"))

    avg_length = _avg(summary, "content", "avg_length")
    max_length = _avg(summary, "content", "max_length")
    avg_headings = _avg(summary, "content", "avg_headings")
    avg_images = _avg(summary, "media", "avg_images")
    avg_title_length = _avg(summary, "title", "avg_length")
    keyword_rate = _avg(summary, "title", "keyword_rate")

    # --- 분량 ---------------------------------------------------
    if avg_length > 0:
        target_length = int(max(1500, round(avg_length * LENGTH_MULTIPLIER / 100) * 100))
        # 1등 글보다 과하게 길어질 필요는 없다
        if max_length > 0:
            target_length = min(target_length, int(max_length * 1.2))
    else:
        target_length = FALLBACK["content_length"]

    # --- 소제목 -------------------------------------------------
    if avg_headings >= 2:
        heading_count = max(4, math.ceil(avg_headings) + 1)
    else:
        # 상위글이 소제목을 거의 안 쓰더라도, 분량이 길면 구조는 필요하다
        heading_count = max(4, round(target_length / 450))
    heading_count = min(heading_count, 9)

    # --- 이미지 -------------------------------------------------
    image_count = max(5, math.ceil(avg_images) + 1) if avg_images > 0 else FALLBACK["image_count"]
    image_count = min(image_count, 20)

    # --- 제목 ---------------------------------------------------
    title_length = int(avg_title_length) if avg_title_length > 0 else FALLBACK["title_length"]
    title_min = max(TITLE_MIN, title_length - 6)
    title_max = min(TITLE_MAX, max(title_min + 6, title_length + 6))

    # --- 키워드 반복 --------------------------------------------
    # 밀도는 상위글을 따라가되 과최적화(스팸) 구간은 피한다.
    # 1,000자당 3~5회면 자연스럽고, 그 이상은 반복이 눈에 띈다.
    keyword_count = max(5, min(15, round(target_length / 1000 * 4)))

    return {
        "keyword": keyword,
        "search_volume": search_volume,
        "sample_count": sample_count,
        "evidence": "measured" if sample_count > 0 else "fallback",
        "title": {
            "min_length": title_min,
            "max_length": title_max,
            "keyword_required": True,
            "keyword_position": "앞쪽",
            "competitor_keyword_rate": round(keyword_rate, 1),
        },
        "content": {
            "target_length": target_length,
            "min_length": int(target_length * 0.9),
            "heading_count": heading_count,
            "keyword_count": keyword_count,
            "competitor_avg_length": int(avg_length),
            "competitor_max_length": int(max_length),
        },
        "media": {
            "image_count": image_count,
            "competitor_avg_images": round(avg_images, 1),
        },
    }


# ============================================================
# 전환 설계 - PersuasionScorer 가 채점하는 축과 같은 것을 요구한다
#   (쓰고 나서 감점될 요소를 애초에 쓰게 만드는 게 목적)
# ============================================================
CONVERSION_BLOCKS = [
    (
        "공감 (도입부)",
        "검색한 사람이 지금 겪고 있는 상황을 첫 3줄 안에 그대로 묘사한다. "
        "인사말·자기소개로 시작하지 말고 독자의 문제부터 꺼낸다.",
    ),
    (
        "근거",
        "숫자를 최소 3개 쓴다. 기간, 비율, 횟수, 개수처럼 검증 가능한 형태로 쓴다. "
        "출처가 불확실한 통계는 지어내지 말고, 일반적으로 알려진 범위로 표현한다.",
    ),
    (
        "전문성",
        "왜 그런지 원리를 한 단계 더 설명한다. 결론만 말하지 않고 이유를 붙인다. "
        "경력·진료 경험 같은 신뢰 신호를 자연스럽게 한 번 언급한다.",
    ),
    (
        "구체 사례",
        "실제 상황처럼 읽히는 사례를 1개 넣는다. 나이대·증상·경과를 구체적으로 쓰되 "
        "특정 개인을 식별할 수 있게 쓰지 않는다.",
    ),
    (
        "비교 기준",
        "독자가 스스로 판단할 수 있는 기준을 표나 목록으로 제시한다. "
        "'이런 경우엔 A, 저런 경우엔 B' 형태가 가장 잘 읽힌다.",
    ),
    (
        "반론 처리",
        "독자가 망설이는 이유(비용, 통증, 시간, 부작용) 중 최소 2개를 직접 언급하고 답한다.",
    ),
    (
        "행동 유도 (마무리)",
        "마지막 문단에서 부담 없는 다음 행동 하나만 제안한다. "
        "강매하듯 쓰지 말고 '궁금하면 상담으로 확인해보라' 수준으로 쓴다.",
    ),
]

# 도입부 진입 방식. 키워드마다 다른 것을 배정해서
# 여러 편을 한 번에 뽑아도 서로 복제본처럼 읽히지 않게 한다.
OPENING_STYLES = [
    "검색자가 지금 겪고 있는 장면을 3인칭으로 묘사하며 시작한다. (예: 어젯밤부터 이런 상태였다면)",
    "검색자가 속으로 하고 있는 질문을 그대로 첫 문장에 쓴다.",
    "많은 사람이 잘못 알고 있는 통념 하나를 먼저 깨면서 시작한다.",
    "지금 결정을 미루면 무엇이 달라지는지 시간 순으로 짧게 보여주며 시작한다.",
    "비슷한 상황으로 내원했던 사례의 한 장면으로 시작한다.",
]


def pick_opening_style(keyword: str) -> str:
    """
    키워드로 결정론적으로 고른다 - 같은 키워드는 늘 같은 진입 방식.

    글자 합으로 고르면 "임플란트 가격"과 "임플란트 부작용"처럼
    앞부분이 같은 키워드끼리 자주 충돌한다. 해시를 써야 고르게 흩어진다.
    """
    if not keyword:
        return OPENING_STYLES[0]
    digest = hashlib.md5(keyword.encode("utf-8")).hexdigest()
    return OPENING_STYLES[int(digest, 16) % len(OPENING_STYLES)]


def build_differentiation(research: Dict, brand: Optional[Dict]) -> Dict:
    """
    이 원고만의 차별화 각도를 정한다.

    차별화는 세 가지가 맞물려야 나온다.
      1) 이 키워드 검색자가 실제로 겪는 걱정 (페인포인트)
      2) 그 걱정에 상위글이 답해주지 않는 지점 (콘텐츠 갭)
      3) 우리가 그 지점에서 실제로 내세울 수 있는 것 (병원 차별점)

    셋 중 하나라도 비면 "좋은 글"은 나와도 "우리에게 문의할 이유"는 안 나온다.
    """
    pains = research.get("pain_points") or []
    gaps = research.get("content_gaps") or []
    brand = brand or {}

    primary = pains[0] if pains else None
    secondary = pains[1] if len(pains) > 1 else None

    # 경쟁글이 안 다루는 것 중 페인포인트와 직접 연결되는 것을 쐐기로 삼는다
    wedge = None
    if primary:
        for gap in gaps:
            if any(
                signal in gap["from_keyword"]
                for signal in _pain_signal_words(primary["id"])
            ):
                wedge = gap
                break
    if wedge is None and gaps:
        wedge = gaps[0]

    differentiators = [d for d in (brand.get("differentiators") or []) if d]
    proof_points = [p for p in (brand.get("proof_points") or []) if p]

    return {
        "primary_pain": primary,
        "secondary_pain": secondary,
        "wedge": wedge,
        "opening_style": pick_opening_style(research.get("keyword", "")),
        "differentiators": differentiators,
        "proof_points": proof_points,
        "has_brand_material": bool(differentiators or proof_points),
    }


def _pain_signal_words(pain_id: str) -> List[str]:
    """페인포인트 id 에 해당하는 신호 단어 (딥리서치 사전을 그대로 참조)"""
    from app.services.serp_research_service import PAIN_SIGNALS

    for pain in PAIN_SIGNALS:
        if pain["id"] == pain_id:
            return pain["signals"]
    return []


# 체류시간 - 네이버 상위 유지의 실질 변수
DWELL_RULES = [
    "첫 문장은 질문이나 상황 묘사로 시작해 바로 읽히게 한다. 인사말 금지.",
    "한 문단은 2~3문장까지만 쓰고 문단 사이를 한 줄 비운다.",
    "한 문장은 60자를 넘기지 않는다. 길어지면 끊는다.",
    "핵심 정보는 글 중반에도 배치해 끝까지 스크롤할 이유를 만든다.",
    "표나 번호 목록을 최소 1개 넣어 훑어보는 독자도 붙잡는다.",
]


def _naver_seo_rules(spec: Dict) -> List[str]:
    """네이버 노출 관련 작성 원칙 (공개 알고리즘이 아니라 관측된 통념 + 실측 규격)"""
    title = spec["title"]
    content = spec["content"]
    return [
        f"제목은 {title['min_length']}~{title['max_length']}자로 쓰고, 핵심 키워드를 앞쪽에 배치한다.",
        "제목에 낚시성 과장이나 대괄호 남발을 쓰지 않는다. 검색어와 글 내용이 일치해야 한다.",
        f"키워드를 본문에 {content['keyword_count']}회 안팎으로 자연스럽게 넣는다. "
        "억지로 반복하면 오히려 감점 요인이 된다.",
        "같은 말만 반복하지 말고 유의어·연관어를 섞어 쓴다.",
        "첫 문단 안에 핵심 키워드가 한 번 나오게 한다.",
        "소제목에도 키워드나 연관어를 자연스럽게 분산시킨다.",
        "다른 글을 복사하지 말고 직접 쓴 문장으로만 구성한다. 중복 문서는 노출에서 밀린다.",
    ]


def _forbidden_terms(category: str) -> Dict:
    """의료법/금칙어 체커가 잡아내는 표현을 미리 금지시킨다"""
    forbidden = list(ForbiddenWordsChecker.FORBIDDEN_WORDS.keys())

    medical_notes = [
        "100%·완치·무조건·반드시 같은 절대적 표현",
        "최고·최상·1위·유일·세계 최초 같은 비교 우위 표현",
        "즉시 효과·획기적·기적 같은 과장 표현",
        "할인·특가·이벤트·무료 같은 가격 유인 표현",
        "효과를 보장하거나 약속하는 표현",
        "다른 병원과 직접 비교하는 표현",
    ]

    return {
        "words": forbidden,
        "categories": medical_notes,
        "is_medical": category == "hospital",
    }


def compose_prompt(
    research: Dict,
    spec: Dict,
    brand: Optional[Dict] = None,
) -> str:
    """
    규격 + 리서치 결과 -> Gemini 에 그대로 넣을 한국어 프롬프트

    Args:
        research: serp_research_service.research_keyword 결과
        spec: build_spec 결과
        brand: 선택. {"name", "region", "specialty", "tone"} 형태의 업체 정보
    """
    keyword = spec["keyword"]
    title = spec["title"]
    content = spec["content"]
    media = spec["media"]
    intent = research.get("intent") or {}
    category = research.get("category", "general")
    forbidden = _forbidden_terms(category)

    lines: List[str] = []
    add = lines.append

    # ---- 역할 --------------------------------------------------
    add("당신은 네이버 블로그 상위노출과 전환율을 동시에 잡는 전문 카피라이터입니다.")
    add(f'아래 설계서에 맞춰 "{keyword}" 키워드로 네이버 블로그 글을 한 편 작성하세요.')
    add("")
    add("이 설계서는 지금 이 키워드로 네이버 1페이지에 노출되고 있는 글들을")
    add("실제로 수집·분석해서 만든 것입니다. 추측이 아니라 실측값이므로 그대로 지키세요.")
    add("")

    # ---- 독자 --------------------------------------------------
    add("━━━━━━━━━━━━━━━━━━━━━━━━")
    add("1. 이 글을 읽을 사람")
    add("━━━━━━━━━━━━━━━━━━━━━━━━")
    if spec.get("search_volume"):
        add(f"- 이 키워드는 월 {spec['search_volume']:,}회 검색됩니다.")
    if intent.get("primary"):
        add(f"- 검색 의도: {intent['primary']}")
        add(f"  {intent.get('description', '')}")

    questions = research.get("questions") or []
    if questions:
        add("- 이 사람들이 함께 검색하는 것들 (본문에서 답해야 할 질문):")
        for question in questions[:8]:
            add(f"    · {question}")
    add("")

    # ---- 경쟁글 ------------------------------------------------
    outline = research.get("competitor_outline") or []
    if outline:
        add("━━━━━━━━━━━━━━━━━━━━━━━━")
        add("2. 지금 1페이지에 있는 글들")
        add("━━━━━━━━━━━━━━━━━━━━━━━━")
        for post in outline[:5]:
            add(f"[{post['rank']}위] {post['title']} ({post['content_length']:,}자)")
            for heading in post["headings"][:5]:
                add(f"    · {heading}")
        add("")

    common = research.get("common_topics") or []
    if common:
        add("이 글들이 공통으로 다루는 주제입니다. 빠뜨리면 경쟁이 안 됩니다:")
        add("  " + ", ".join(topic["topic"] for topic in common[:10]))
        add("")

    # 금지어와 겹치는 글감은 빼둔다. 9번에서 못 쓰게 한 단어를
    # 3번에서 소제목으로 권하면 프롬프트가 자기모순이 된다.
    banned = {word.replace(" ", "") for word in forbidden["words"]}
    gaps = [
        gap for gap in (research.get("content_gaps") or [])
        if gap["topic"].replace(" ", "") not in banned
    ]
    if gaps:
        add("━━━━━━━━━━━━━━━━━━━━━━━━")
        add("3. 경쟁글이 빠뜨린 것 (여기서 이깁니다)")
        add("━━━━━━━━━━━━━━━━━━━━━━━━")
        add("검색하는 사람은 궁금해하는데 위 글들이 제대로 다루지 않은 주제입니다.")
        add("이 중 최소 3개를 소제목으로 만들어 정면으로 다루세요.")
        for gap in gaps[:8]:
            add(f"    · {gap['topic']}  (실제 검색어: {gap['from_keyword']})")
        add("")

    # ---- 차별화 (이 글의 존재 이유) ------------------------------
    diff = build_differentiation(research, brand)
    primary = diff["primary_pain"]

    add("━━━━━━━━━━━━━━━━━━━━━━━━")
    add("4. 이 글의 차별화 — 가장 중요한 항목")
    add("━━━━━━━━━━━━━━━━━━━━━━━━")
    add("정보만 잘 정리된 글은 이미 1페이지에 다섯 편 있습니다.")
    add("이 글은 '읽고 나서 여기에 물어봐야겠다'는 생각이 들어야 합니다.")
    add("그러려면 정보를 나열하지 말고, 아래 걱정 하나를 끝까지 풀어주세요.")
    add("")

    if primary:
        add(f"[이 키워드를 검색한 사람의 가장 큰 걱정]")
        add(f"  {primary['label']} — {primary['worry']}")
        add(f"  근거가 되는 실제 검색어: {', '.join(primary['evidence'][:5])}")
        add(f"  풀어주는 방법: {primary['answer']}")
        add("")
        add("이 걱정을 도입부 3줄 안에 그대로 언어화하세요.")
        add("독자가 '내 얘기다'라고 느끼는 순간 끝까지 읽습니다.")
        add("")

    if diff["secondary_pain"]:
        second = diff["secondary_pain"]
        add(f"[두 번째 걱정] {second['label']} — {second['worry']}")
        add(f"  글 중반에 한 번 짚어주세요. {second['answer']}")
        add("")

    if diff["wedge"]:
        add(f"[경쟁글이 이 걱정에 답하지 않는 지점]")
        add(f"  '{diff['wedge']['topic']}' (실제 검색어: {diff['wedge']['from_keyword']})")
        add("  여기를 정면으로 다루는 것이 이 글의 무기입니다. 소제목 하나를 통째로 배정하세요.")
        add("")

    add(f"[도입부 진입 방식] {diff['opening_style']}")
    add("")

    add("[왜 우리에게 문의해야 하는가]")
    if diff["has_brand_material"]:
        add("글 후반부에 아래 내용을 '자랑'이 아니라 '위 걱정에 대한 답'으로 연결해서 쓰세요.")
        for item in diff["differentiators"]:
            add(f"  - {item}")
        for item in diff["proof_points"]:
            add(f"  - (근거) {item}")
        add("")
        add("연결 방식이 중요합니다. '저희는 장비가 좋습니다'가 아니라")
        add("'앞에서 말한 그 위험을 줄이려면 이런 점검이 필요한데, 저희는 그 과정을 이렇게 합니다'")
        add("처럼 걱정 -> 해법 -> 우리 방식 순서로 이어 붙이세요.")
    else:
        add("업체 차별점이 입력되지 않았습니다. 없는 장점을 지어내지 마세요.")
        add("대신 '어디를 고르든 이것만은 확인하세요' 형태의 판단 기준을 제시하고,")
        add("그 기준을 함께 점검해보자는 흐름으로 상담을 제안하세요.")
        add("기준을 준 사람이 신뢰를 얻습니다.")
    add("")

    add("[하지 말 것]")
    add("- 상위글과 같은 목차를 순서만 바꿔 쓰는 것")
    add("- 걱정을 짚지 않고 정보만 나열하는 것")
    add("- 마지막에 갑자기 병원 홍보를 붙이는 것 (본문과 연결되지 않으면 이탈합니다)")
    add("")

    # ---- 규격 --------------------------------------------------
    add("━━━━━━━━━━━━━━━━━━━━━━━━")
    add("5. 분량·구조 규격 (실측 기준)")
    add("━━━━━━━━━━━━━━━━━━━━━━━━")
    if spec["evidence"] == "measured":
        add(
            f"- 상위 {spec['sample_count']}개 글 평균 {content['competitor_avg_length']:,}자, "
            f"이미지 {media['competitor_avg_images']}장"
        )
    add(f"- 본문 {content['target_length']:,}자 이상 (최소 {content['min_length']:,}자)")
    add(f"- 소제목 {content['heading_count']}개")
    add(f"- 이미지 들어갈 자리 {media['image_count']}곳을 [사진: 설명] 형태로 표시")
    add(f"- 제목 {title['min_length']}~{title['max_length']}자, 키워드를 앞쪽에 배치")
    add("")

    # ---- 네이버 SEO --------------------------------------------
    add("━━━━━━━━━━━━━━━━━━━━━━━━")
    add("6. 네이버 노출 규칙")
    add("━━━━━━━━━━━━━━━━━━━━━━━━")
    for rule in _naver_seo_rules(spec):
        add(f"- {rule}")
    add("")

    # ---- 체류시간 ----------------------------------------------
    add("━━━━━━━━━━━━━━━━━━━━━━━━")
    add("7. 끝까지 읽게 만들기 (체류시간)")
    add("━━━━━━━━━━━━━━━━━━━━━━━━")
    add("네이버는 독자가 글을 얼마나 오래 보는지를 중요하게 봅니다.")
    for rule in DWELL_RULES:
        add(f"- {rule}")
    add("")

    # ---- 전환 --------------------------------------------------
    add("━━━━━━━━━━━━━━━━━━━━━━━━")
    add("8. 전환 설계 (읽고 나서 문의하게 만들기)")
    add("━━━━━━━━━━━━━━━━━━━━━━━━")
    add("아래 요소를 글 안에 반드시 모두 넣으세요.")
    for name, rule in CONVERSION_BLOCKS:
        add(f"- {name}: {rule}")
    add("")

    # ---- 브랜드 ------------------------------------------------
    if brand and any(brand.values()):
        add("━━━━━━━━━━━━━━━━━━━━━━━━")
        add("9. 업체 정보")
        add("━━━━━━━━━━━━━━━━━━━━━━━━")
        if brand.get("name"):
            add(f"- 상호: {brand['name']}")
        if brand.get("region"):
            add(f"- 지역: {brand['region']} (지역명을 본문에 2~3회 자연스럽게 넣으세요)")
        if brand.get("specialty"):
            add(f"- 진료 분야: {brand['specialty']}")
        if brand.get("target_patient"):
            add(f"- 주로 오시는 분: {brand['target_patient']}")
        if brand.get("tone"):
            add(f"- 말투: {brand['tone']}")
        add("")

    # ---- 금지 --------------------------------------------------
    add("━━━━━━━━━━━━━━━━━━━━━━━━")
    add("10. 절대 쓰면 안 되는 표현")
    add("━━━━━━━━━━━━━━━━━━━━━━━━")
    if forbidden["is_medical"]:
        add("의료광고는 법으로 규제됩니다. 아래 유형은 사용 시 문제가 됩니다.")
    for note in forbidden["categories"]:
        add(f"- {note}")
    add("")
    add("특히 다음 단어는 한 번도 쓰지 마세요:")
    add("  " + ", ".join(forbidden["words"][:40]))
    add("")

    # ---- 출력 형식 ---------------------------------------------
    add("━━━━━━━━━━━━━━━━━━━━━━━━")
    add("11. 출력 형식")
    add("━━━━━━━━━━━━━━━━━━━━━━━━")
    add("- 첫 줄에 제목만 쓰고, 한 줄 띄운 뒤 본문을 시작하세요.")
    add("- 마크다운 기호(#, **, ---)를 쓰지 말고 일반 텍스트로만 작성하세요.")
    add("- 소제목은 그냥 한 줄로 쓰고 앞뒤로 빈 줄을 넣으세요.")
    add("- 이미지 자리는 [사진: 무엇을 보여주는 사진인지] 형태로 본문 흐름에 맞게 넣으세요.")
    add("- 설명·해설·머리말 없이 완성된 글만 출력하세요.")

    return "\n".join(lines)


def build_writing_package(
    research: Dict,
    search_volume: int = 0,
    brand: Optional[Dict] = None,
) -> Dict:
    """딥리서치 결과 -> {규격, 프롬프트} 한 묶음"""
    spec = build_spec(research, search_volume=search_volume)
    prompt = compose_prompt(research, spec, brand=brand)
    return {
        "keyword": spec["keyword"],
        "spec": spec,
        "prompt": prompt,
        "prompt_length": len(prompt),
        "differentiation": build_differentiation(research, brand),
        "research_summary": {
            "analyzed_count": research.get("analyzed_count", 0),
            "pain_points": [
                {"label": p["label"], "evidence": p["evidence"][:3]}
                for p in (research.get("pain_points") or [])[:3]
            ],
            "competitor_titles": research.get("competitor_titles", [])[:5],
            "common_topics": [t["topic"] for t in (research.get("common_topics") or [])[:10]],
            "content_gaps": [g["topic"] for g in (research.get("content_gaps") or [])[:8]],
            "questions": (research.get("questions") or [])[:8],
            "intent": research.get("intent", {}).get("primary", ""),
        },
    }
