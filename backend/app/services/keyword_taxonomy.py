"""키워드를 '글의 성격'으로 분류한다 — 글자만 보고, AI 없이.

발굴한 키워드 수백 개를 그냥 검색량 순으로 주면 '○○치료' 류만 잔뜩 뽑힌다.
블로그는 증상·원인·관리 글이 골고루 있어야 주제 적합도가 쌓이므로,
뽑을 때 카테고리 비율을 맞출 수 있어야 한다. 그 비율의 기준이 되는 분류기다.

AI 를 쓰지 않는 이유: 수백 개를 매번 분류해야 하는데 비용도 들고 결과가 흔들린다.
한국어 의료 키워드는 접미어가 정형적이라 글자 매칭으로 충분하다.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Sequence

# 표시 순서 = 블로그 기획에서 보통 쓰는 순서.
CATEGORIES: tuple[str, ...] = ("대표", "증상", "원인", "치료", "관리", "검사", "비용", "병원", "기타")

CATEGORY_LABELS: Dict[str, str] = {
    "대표": "대표(질환명)",
    "증상": "증상",
    "원인": "원인",
    "치료": "치료",
    "관리": "관리·예방",
    "검사": "검사·진단",
    "비용": "비용",
    "병원": "병원·지역",
    "기타": "기타",
}

# 기본 배분(%). 합이 100 이 되게 두되, 사용자가 덮어쓸 수 있다.
DEFAULT_RATIO: Dict[str, int] = {
    "대표": 15, "증상": 18, "원인": 12, "치료": 22, "관리": 18,
    "검사": 3, "비용": 2, "병원": 10, "기타": 0,
}

# ── 매칭 규칙 ────────────────────────────────────────────────────────────────
# 순서가 곧 우선순위다. 더 좁은 뜻이 먼저 와야 한다:
#   '건선치료비용' 은 비용 글이지 치료 글이 아니고,
#   '건선 잘보는 병원' 은 병원 글이지 치료 글이 아니다.
_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("비용", ("비용", "가격", "얼마", "실비", "보험", "급여", "본인부담", "할인", "이벤트")),
    ("병원", ("병원", "의원", "한의원", "클리닉", "센터", "피부과", "내과", "외과", "치과",
              "잘하는", "잘보는", "유명한", "추천", "후기", "예약", "진료시간", "근처")),
    ("검사", ("검사", "진단", "차이", "구분", "구별", "vs", "종류", "단계", "자가진단", "판별")),
    ("원인", ("원인", "이유", "왜", "생기는", "발생", "전염", "옮", "유전", "스트레스")),
    ("증상", ("증상", "초기", "징후", "전조", "나타", "통증", "가렵", "간지", "부어", "붓", "따가")),
    ("치료", ("치료", "시술", "수술", "주사", "약", "연고", "처방", "완치", "낫는", "낫게",
              "효과", "요법", "제거", "개선")),
    ("관리", ("관리", "예방", "음식", "식단", "먹으면", "보습", "생활", "홈케어", "재발",
              "운동", "습관", "좋은", "나쁜", "주의", "방법")),
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", (text or "")).lower()


def classify(keyword: str, regions: Sequence[str] = (), subjects: Sequence[str] = ()) -> str:
    """키워드 하나의 카테고리. 못 고르면 '기타'.

    regions 를 주면 지역명이 붙은 키워드('강남건선한의원')를 '병원'으로 본다 —
    지역 키워드는 사실상 내원 유도 글이라 성격이 정보 글과 다르다.
    subjects(진료 항목)를 주면 의도 접미어가 없는 머리 키워드를 '대표'로 본다.
    '한포진', '손가락 한포진' 같은 것들로, 검색량이 가장 크고 경쟁도 가장 세다.
    """
    k = _norm(keyword)
    if not k:
        return "기타"
    # 진료 항목 그 자체는 무조건 대표. ('가려움' 처럼 증상어가 곧 진료 항목인 경우가 있다)
    if any(k == _norm(s) for s in subjects if s):
        return "대표"
    for category, terms in _RULES:
        if any(t in k for t in terms):
            return category
    # 의도 접미어가 없는데 진료 항목을 품고 있으면 머리 키워드다. ('손가락 한포진')
    if any(_norm(s) and _norm(s) in k for s in subjects if s):
        return "대표"
    # 규칙에 안 걸렸는데 지역명이 들어 있으면 내원 의도로 본다.
    if any(_norm(r) and _norm(r) in k for r in regions):
        return "병원"
    return "기타"


def classify_all(keywords: Iterable[str], regions: Sequence[str] = (),
                 subjects: Sequence[str] = ()) -> Dict[str, str]:
    return {kw: classify(kw, regions, subjects) for kw in keywords}


def normalize_ratio(ratio: Optional[Dict[str, int]]) -> Dict[str, int]:
    """사용자가 준 비율을 정리한다. 모르는 카테고리는 버리고, 비면 기본값."""
    if not ratio:
        return dict(DEFAULT_RATIO)
    clean = {c: max(0, int(v)) for c, v in ratio.items() if c in CATEGORIES and int(v or 0) > 0}
    return clean or dict(DEFAULT_RATIO)


def allocate(total: int, ratio: Dict[str, int]) -> Dict[str, int]:
    """비율 → 실제 개수. 합이 정확히 total 이 되도록 최대 잔여법으로 맞춘다.

    단순 반올림은 100개 요청에 98개가 나오는 일이 생긴다. 남는 자리는
    소수부가 큰 카테고리부터 1개씩 준다.
    """
    total = max(0, int(total))
    weights = {c: v for c, v in (ratio or {}).items() if v > 0}
    if total == 0 or not weights:
        return {}
    weight_sum = sum(weights.values())
    exact = {c: total * v / weight_sum for c, v in weights.items()}
    out = {c: int(v) for c, v in exact.items()}
    left = total - sum(out.values())
    for c, _ in sorted(exact.items(), key=lambda kv: (-(kv[1] - int(kv[1])), kv[0])):
        if left <= 0:
            break
        out[c] += 1
        left -= 1
    return {c: n for c, n in out.items() if n > 0}


def split_by_subject(total: int, subjects: Sequence[str],
                     quota: Optional[Dict[str, int]] = None) -> Dict[str, int]:
    """질환별 개수. quota 를 주면 그대로 쓰고(합이 total 을 넘으면 비례 축소),
    안 주면 균등 배분한다."""
    subjects = [s for s in subjects if s]
    if not subjects or total <= 0:
        return {}
    if quota:
        asked = {s: max(0, int(n)) for s, n in quota.items() if s in subjects and int(n or 0) > 0}
        if asked:
            if sum(asked.values()) <= total:
                return asked
            return allocate(total, asked)      # 넘치면 비율로 보고 줄인다
    return allocate(total, {s: 1 for s in subjects})


# ── 간절함(내원 의도) ────────────────────────────────────────────────────────
# 검색량이 큰 키워드가 곧 환자가 되는 키워드는 아니다. '아토피에좋은음식'은 한 달에
# 수천 번 검색되지만 그 사람들은 병원을 찾는 중이 아니고, '강남역아토피피부과'는
# 검색량이 20이어도 지금 갈 곳을 고르는 중이다. 글은 뒤쪽부터 써야 한다.
#
# 그래서 검색량과 따로, **얼마나 간절한가**를 글자에서 읽어 0~100 으로 매긴다.
# AI 를 쓰지 않는 이유는 분류기와 같다 — 한국어 검색어의 간절함은 어미와 낱말에 그대로 드러난다.

# 카테고리가 정하는 밑점. 글의 성격이 곧 검색한 사람의 처지다.
_INTENT_BASE: Dict[str, int] = {
    "병원": 78,    # 지금 갈 곳을 고르는 중
    "비용": 72,    # 돈을 계산하는 중 — 갈 마음은 이미 먹었다
    "치료": 58,    # 해결책을 찾는 중
    "검사": 46,
    "증상": 40,
    "대표": 34,
    "기타": 24,
    "원인": 26,
    "관리": 22,    # 집에서 해보려는 중
}

# 더하는 신호. (점수, 이름표, 낱말들) — 맞은 것 중 점수가 가장 큰 것이 이름표가 된다.
_INTENT_UP: tuple[tuple[int, str, tuple[str, ...]], ...] = (
    (20, "지금 아파서 급함",
     ("안낫", "안없어", "낫지않", "안나아", "심해", "심함", "악화", "번져", "퍼져",
      "재발", "계속", "지긋지긋", "못참", "미치겠", "밤에", "잠못", "잠을못",
      "응급", "급성", "빨리", "당장", "바로")),
    (14, "지역을 찍어 찾는 중", ("근처", "가까운", "우리동네", "동네")),
    (12, "고를 준비가 된 검색",
     ("추천", "후기", "잘하는", "잘보는", "유명한", "예약", "상담", "문의", "전문의")),
    (10, "가족 때문에 급함", ("아기", "신생아", "소아", "어린이", "아이", "임산부", "임신", "수유")),
)

# 빼는 신호. 같은 질환이라도 '뜻'을 찾는 사람과 '병원'을 찾는 사람은 다르다.
_INTENT_DOWN: tuple[tuple[int, str, tuple[str, ...]], ...] = (
    (14, "뜻·정보만 확인", ("뜻", "이란", "무엇", "영어", "사진", "이미지", "연예인", "유래", "역사")),
    (8, "집에서 해결하려는 중", ("음식", "식단", "먹으면", "민간요법", "집에서", "자연치유", "예방법")),
)

# '3주째', '한달 넘게' — 참다 참다 검색한 사람이다.
_DURATION = re.compile(r"(\d+\s*(일|주|주일|개월|달|년))|((한|두|세|네|몇)\s*(달|주|해))")


def intent(keyword: str, regions: Sequence[str] = (), subjects: Sequence[str] = (),
           category: Optional[str] = None) -> tuple[int, str]:
    """이 키워드를 검색한 사람이 얼마나 간절한가. (0~100 점수, 한 줄 이름표).

    검색량과는 독립이다 — 많이 검색되는 것과 병원을 찾는 것은 다른 일이다.
    """
    k = _norm(keyword)
    if not k:
        return 0, "알 수 없음"
    category = category or classify(keyword, regions, subjects)
    score = _INTENT_BASE.get(category, 24)
    reason, weight = "", 0

    # 우리 진료 지역이 박힌 키워드 — 이 사람은 그 동네에서 갈 곳을 찾고 있다.
    if any(_norm(r) and _norm(r) in k for r in regions if r):
        score += 16
        reason, weight = "우리 지역을 찍어 찾는 중", 16

    for up, label, terms in _INTENT_UP:
        if any(t in k for t in terms):
            score += up
            if up > weight:
                reason, weight = label, up

    if _DURATION.search(keyword or ""):
        score += 12
        if 12 > weight:
            reason, weight = "오래 참다 검색", 12

    for down, label, terms in _INTENT_DOWN:
        if any(t in k for t in terms):
            score -= down
            if not reason:
                reason = label

    if not reason:
        reason = {
            "병원": "갈 곳을 고르는 중", "비용": "비용을 따져 보는 중", "치료": "치료법을 찾는 중",
            "검사": "내 상태를 확인하는 중", "증상": "증상을 확인하는 중", "대표": "질환을 알아보는 중",
            "원인": "원인을 알아보는 중", "관리": "집에서 관리하는 중",
        }.get(category, "정보를 찾는 중")
    return max(5, min(100, score)), reason


def intent_level(score: Optional[int]) -> str:
    """점수를 사람 말로. 화면에는 숫자보다 이 말이 먼저 읽힌다."""
    value = int(score or 0)
    if value >= 75:
        return "높음"
    if value >= 50:
        return "보통"
    return "낮음"
