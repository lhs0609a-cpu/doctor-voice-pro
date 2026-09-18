"""
가중치 시스템 — 카테고리 사전값 + 학습값 blend + 클램프 (문서 3장, 13장).

★ 반드시 **한 곳에서만** 가중치를 결정할 것 (resolve_scoring_weights).
  이 함수가 생기기 전에는 경로가 둘로 갈라져 있었다.
    - 키워드 있음 : 카테고리 사전값과 학습값을 70/30 blend
    - 키워드 없음 : DB 학습값을 **그대로** 사용 (blend도 하한도 없음)
  블로그 단위 분석은 항상 후자라, 붕괴한 학습값이 여과 없이 적용됐다.

규칙:
  1) 카테고리 사전값(수동 추정)에서 출발한다.
  2) 학습값은 **현재 SCORING_VERSION 에서 학습된 것만** 반영한다.
     버전 스탬프가 없거나 다르면 = 다른 채점식에 맞춰진 값이므로 버린다.
  3) 반영하더라도 70/30 blend 후 하한/상한으로 자르고 재정규화한다.
  4) _learned 는 '실제로 반영했는지'를 그대로 적는다 (UI 배지가 거짓말하지 않게).
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# 13-1. 카테고리 감지 키워드 사전 (CATEGORY_KEYWORDS) — 원본 그대로
# ──────────────────────────────────────────────────────────────────────────────
CATEGORY_KEYWORDS: Dict[str, list] = {
    "맛집": [
        "맛집", "음식", "식당", "카페", "레스토랑", "베이커리", "디저트", "브런치", "치킨", "피자",
        "삼겹살", "고기", "횟집", "초밥", "라멘", "파스타", "스테이크", "술집", "와인바", "칵테일",
        "이자카야", "소주", "맥주", "막걸리",
    ],
    "의료": [
        "병원", "의원", "치과", "피부과", "성형", "안과", "정형외과", "한의원", "임플란트", "교정",
        "라식", "라섹", "보톡스", "필러", "리프팅", "건강검진", "내시경", "물리치료", "도수치료",
        "추나", "디스크", "아토피", "비염", "여드름", "탈모", "통증", "관절", "척추",
    ],
    "IT": [
        "노트북", "스마트폰", "태블릿", "이어폰", "헤드폰", "키보드", "마우스", "모니터", "아이폰",
        "갤럭시", "맥북", "아이패드", "에어팟", "버즈", "카메라", "드론", "게이밍", "SSD", "NAS",
        "공유기", "전자책",
    ],
    "여행": [
        "여행", "호텔", "숙소", "펜션", "리조트", "항공", "비행기", "관광", "제주", "부산", "강릉",
        "속초", "경주", "전주", "여수", "통영", "일본", "도쿄", "오사카", "베트남", "태국", "발리",
        "유럽", "미국",
    ],
    "뷰티": [
        "화장품", "스킨케어", "메이크업", "선크림", "파운데이션", "립스틱", "샴푸", "헤어", "염색",
        "펌", "네일", "향수", "에센스", "세럼", "클렌징", "마스크팩", "아이크림",
    ],
    "교육": [
        "학원", "과외", "인강", "강의", "토익", "토플", "영어", "수학", "코딩", "자격증", "공무원",
        "유학", "어학연수", "독서실", "스터디",
    ],
    "육아": [
        "출산", "육아", "유모차", "카시트", "분유", "기저귀", "아기", "유아", "어린이집", "유치원",
        "장난감", "아기옷", "이유식", "수면교육", "임신", "신생아", "걸음마", "엄마표", "돌잔치",
    ],
    "반려동물": [
        "강아지", "고양이", "반려동물", "펫", "동물병원", "사료", "간식", "펫호텔", "애견카페",
        "고양이카페", "훈련",
    ],
    "인테리어": [
        "인테리어", "가구", "소파", "침대", "매트리스", "조명", "커튼", "이사", "청소", "냉장고",
        "에어컨", "세탁기", "청소기",
    ],
    "재테크": [
        "주식", "투자", "부동산", "코인", "적금", "예금", "대출", "보험", "카드", "연금", "재테크",
        "절세", "isa", "etf", "청년도약", "청년희망", "퇴직연금", "irp", "연금저축", "통장",
        "환테크", "비트코인",
    ],
    # 리뷰(메타 — 도메인 미매칭 시에만)
    "리뷰": [
        "후기", "리뷰", "사용기", "솔직", "내돈내산", "구매", "추천템", "추천", "비교", "장단점",
        "vs", "어떤", "테스트",
    ],
}

# 메타 카테고리 — 도메인 카테고리에 하나도 안 걸렸을 때만 폴백으로 본다.
_META_CATEGORIES = ("리뷰",)

# ──────────────────────────────────────────────────────────────────────────────
# 13-2. 가중치 프리셋 (CATEGORY_WEIGHTS)
#   c_rank {weight, sub{context, content, chain}}
#   dia    {weight, sub{depth, information, accuracy}}
#   content_factors {weight, sub{content_length, heading_count, paragraph_count,
#                                image_count, keyword_count, keyword_density,
#                                freshness, title_keyword}}
#   bonus_factors  {has_map, has_link, video_count, engagement}
#   ※ 교육·반려동물·인테리어는 감지 사전만 있고 별도 가중치 프리셋이 없다 → default.
#   ★ 프리셋은 _clamp_and_normalize_main 을 거치므로 실제 적용값은 [0.15, 0.55] 로
#     잘리고 합이 1.0 으로 재정규화된다. 예: 맛집 (0.25,0.25,0.60) → (0.238,0.238,0.524)
# ──────────────────────────────────────────────────────────────────────────────
CATEGORY_WEIGHTS: Dict[str, Dict[str, Any]] = {
    # [default] ← B 검증 종합 반영
    #   주가중치 c_rank 0.30 / dia 0.20 / content_factors 0.50
    #   근거: c_rank ρ=+0.032, dia ρ=+0.015, content_factors(외부 실측 raw)가 둘보다 큼
    #   C-Rank sub: B 검증(n=67) context ρ=+0.134, content ρ=+0.153, chain ρ=-0.045
    #   D.I.A. sub: depth +0.022, information -0.090, accuracy -0.054
    "default": {
        "c_rank": {"weight": 0.30, "sub_weights": {"context": 0.40, "content": 0.50, "chain": 0.10}},
        "dia": {"weight": 0.20, "sub_weights": {"depth": 0.20, "information": 0.50, "accuracy": 0.30}},
        "content_factors": {
            "weight": 0.50,
            "sub_weights": {
                "content_length": 0.15, "heading_count": 0.12, "paragraph_count": 0.10,
                "image_count": 0.12, "keyword_count": 0.15, "keyword_density": 0.08,
                "freshness": 0.15, "title_keyword": 0.13,
            },
        },
        "bonus_factors": {"has_map": 0.03, "has_link": 0.02, "video_count": 0.05, "engagement": 0.05},
    },
    # [맛집] B 검증 R8(n=97): 모든 신호 |ρ|<0.18, freshness 0.177이 최강.
    #        R7(n=32) 결과가 큰 샘플에서 무너짐 → 보수적.
    "맛집": {
        "c_rank": {"weight": 0.25, "sub_weights": {"context": 0.40, "content": 0.50, "chain": 0.10}},
        "dia": {"weight": 0.25, "sub_weights": {"depth": 0.20, "information": 0.55, "accuracy": 0.25}},
        "content_factors": {
            "weight": 0.60,
            "sub_weights": {
                "content_length": 0.10, "heading_count": 0.08, "paragraph_count": 0.08,
                "image_count": 0.20,      # 이미지 매우 중요
                "keyword_count": 0.12, "keyword_density": 0.07,
                "freshness": 0.20,        # 최신성 매우 중요
                "title_keyword": 0.15,
            },
        },
        "bonus_factors": {"has_map": 0.08, "has_link": 0.02, "video_count": 0.03, "engagement": 0.07},  # has_map: 위치
    },
    # [의료] 직접 검증 안 됨 — 도메인 추정. 전문성·글 길이·정보 깊이 중심.
    "의료": {
        "c_rank": {"weight": 0.30, "sub_weights": {"context": 0.45, "content": 0.45, "chain": 0.10}},
        "dia": {"weight": 0.35, "sub_weights": {"depth": 0.30, "information": 0.40, "accuracy": 0.30}},
        "content_factors": {
            "weight": 0.40,
            "sub_weights": {
                "content_length": 0.22, "heading_count": 0.15, "paragraph_count": 0.12,
                "image_count": 0.10, "keyword_count": 0.15, "keyword_density": 0.06,
                "freshness": 0.10, "title_keyword": 0.10,
            },
        },
        "bonus_factors": {"has_map": 0.05, "has_link": 0.03, "video_count": 0.04, "engagement": 0.03},
    },
    # [IT] B 검증 R8(n=69): raw_avg_post_length ρ=0.339, post_total 0.316 (안정적 강함)
    #      context는 음의 상관(-0.240) — IT는 한 주제만 다루는 블로그보다 다양성 있는 블로그가 SERP 우위.
    "IT": {
        "c_rank": {"weight": 0.40, "sub_weights": {"context": 0.15, "content": 0.70, "chain": 0.15}},
        "dia": {"weight": 0.20, "sub_weights": {"depth": 0.30, "information": 0.40, "accuracy": 0.30}},
        "content_factors": {
            "weight": 0.45,
            "sub_weights": {
                "content_length": 0.18, "heading_count": 0.15, "paragraph_count": 0.12,
                "image_count": 0.15, "keyword_count": 0.12, "keyword_density": 0.08,
                "freshness": 0.12, "title_keyword": 0.08,
            },
        },
        "bonus_factors": {"has_map": 0.01, "has_link": 0.05, "video_count": 0.06, "engagement": 0.03},
    },
    # [여행] B 검증 R8(n=64): fp_images ρ=0.369 (가장 안정적인 최강 신호) ⭐
    #        post_freshness 는 R7 0.371 → R8 0.144 로 약화. 이미지가 결정적.
    "여행": {
        "c_rank": {"weight": 0.20, "sub_weights": {"context": 0.25, "content": 0.60, "chain": 0.15}},
        "dia": {"weight": 0.25, "sub_weights": {"depth": 0.15, "information": 0.55, "accuracy": 0.30}},
        "content_factors": {
            "weight": 0.55,
            "sub_weights": {
                "content_length": 0.10, "heading_count": 0.08, "paragraph_count": 0.07,
                "image_count": 0.30,      # ⭐
                "keyword_count": 0.10, "keyword_density": 0.05,
                "freshness": 0.12, "title_keyword": 0.18,
            },
        },
        "bonus_factors": {"has_map": 0.08, "has_link": 0.03, "video_count": 0.06, "engagement": 0.05},
    },
    # [뷰티] 직접 검증 안 됨 — 리뷰 카테고리와 유사 가정.
    "뷰티": {
        "c_rank": {"weight": 0.30, "sub_weights": {"context": 0.30, "content": 0.55, "chain": 0.15}},
        "dia": {"weight": 0.25, "sub_weights": {"depth": 0.20, "information": 0.55, "accuracy": 0.25}},
        "content_factors": {
            "weight": 0.55,
            "sub_weights": {
                "content_length": 0.14, "heading_count": 0.10, "paragraph_count": 0.10,
                "image_count": 0.20, "keyword_count": 0.12, "keyword_density": 0.08,
                "freshness": 0.15, "title_keyword": 0.11,
            },
        },
        "bonus_factors": {"has_map": 0.01, "has_link": 0.04, "video_count": 0.06, "engagement": 0.06},
    },
    # [육아] B 검증 R8(n=51): 모든 신호 |ρ|<0.17. R7의 post_total 0.408 은 n=17 노이즈였음.
    #        보수적으로 default 근사.
    "육아": {
        "c_rank": {"weight": 0.30, "sub_weights": {"context": 0.40, "content": 0.50, "chain": 0.10}},
        "dia": {"weight": 0.20, "sub_weights": {"depth": 0.20, "information": 0.50, "accuracy": 0.30}},
        "content_factors": {
            "weight": 0.35,
            "sub_weights": {
                "content_length": 0.13, "heading_count": 0.10, "paragraph_count": 0.10,
                "image_count": 0.13, "keyword_count": 0.13, "keyword_density": 0.07,
                "freshness": 0.18, "title_keyword": 0.16,
            },
        },
        "bonus_factors": {"has_map": 0.02, "has_link": 0.03, "video_count": 0.04, "engagement": 0.06},
    },
    # [리뷰] B 검증(n=29): content ρ=0.376(최강), post_total 0.319, context 0.241
    "리뷰": {
        "c_rank": {"weight": 0.40, "sub_weights": {"context": 0.30, "content": 0.55, "chain": 0.15}},
        "dia": {"weight": 0.20, "sub_weights": {"depth": 0.20, "information": 0.55, "accuracy": 0.25}},
        "content_factors": {
            "weight": 0.40,
            "sub_weights": {
                "content_length": 0.18, "heading_count": 0.12, "paragraph_count": 0.10,
                "image_count": 0.15, "keyword_count": 0.13, "keyword_density": 0.07,
                "freshness": 0.13, "title_keyword": 0.12,
            },
        },
        "bonus_factors": {"has_map": 0.01, "has_link": 0.04, "video_count": 0.05, "engagement": 0.05},
    },
    # [재테크] B 검증 R8(n=69, 금융): 모든 신호 |ρ|<0.13. raw_avg_post_length 0.127 이 최강.
    #          R7의 post_length 0.328 은 노이즈였음.
    "재테크": {
        "c_rank": {"weight": 0.30, "sub_weights": {"context": 0.30, "content": 0.55, "chain": 0.15}},
        "dia": {"weight": 0.25, "sub_weights": {"depth": 0.25, "information": 0.45, "accuracy": 0.30}},
        "content_factors": {
            "weight": 0.35,
            "sub_weights": {
                "content_length": 0.22, "heading_count": 0.13, "paragraph_count": 0.12,
                "image_count": 0.08, "keyword_count": 0.13, "keyword_density": 0.08,
                "freshness": 0.10, "title_keyword": 0.14,
            },
        },
        "bonus_factors": {"has_map": 0.01, "has_link": 0.05, "video_count": 0.03, "engagement": 0.03},
    },
}

# ──────────────────────────────────────────────────────────────────────────────
# 13-3. 카테고리별 최적화 팁 (UI 노출용)
# ──────────────────────────────────────────────────────────────────────────────
CATEGORY_TIPS: Dict[str, Dict[str, Any]] = {
    "맛집": {
        "tips": [
            "고퀄 음식사진 15장+", "지도 필수", "최근 방문정보 갱신",
            "맛·서비스·분위기 상세", '제목에 "지역명+맛집"',
        ],
        "focus": ["이미지", "지도", "최신성", "공감/댓글"],
    },
    "의료": {
        "tips": [
            "3000자+ 상세 정보", "소제목 구조화", "의료진·시설", "치료과정·비용", "정확한 의료정보",
        ],
        "focus": ["글 길이", "정보 깊이", "신뢰도", "구조화"],
    },
    "IT": {
        "tips": [
            "다양한 각도 제품사진", "스펙 비교표", "언박싱 영상", "공식스토어 링크", "장단점 객관 분석",
        ],
        "focus": ["이미지", "영상", "정보 깊이", "링크"],
    },
    "여행": {
        "tips": ["사진 20장+", "위치·경로 지도", "예산·비용", "최신 방문정보", "브이로그"],
        "focus": ["이미지", "지도", "최신성", "영상"],
    },
    "뷰티": {
        "tips": ["비포/애프터", "사용감·지속력", "발색·사용법 영상", "가성비 평가", "공감 유도"],
        "focus": ["이미지", "영상", "최신성", "공감"],
    },
    "default": {
        "tips": ["2000자+", "이미지 10장+", "제목 핵심 키워드", "소제목 구조화", "정기 업데이트"],
        "focus": ["글 길이", "이미지", "키워드", "구조화"],
    },
}

# ──────────────────────────────────────────────────────────────────────────────
# 3-1. 주요 3축 클램프 ★
#   왜 필요한가: 학습기(경사하강)는 정규화도 하한도 없어서 신호가 약한 차원을
#   0 근처까지 밀어버린다. 실제로 2026-01-25 학습 결과가
#   c_rank 0.054 / dia 0.483 / content 0.463 이었고, 이 값이 6개월간 그대로
#   총점을 지배했다. C-Rank가 총점의 5%가 되는 건 학습이 아니라 붕괴다.
#   → 학습값은 '사전값을 조정하는 힘'까지만 허용하고, 축을 없애지는 못하게 한다.
# ──────────────────────────────────────────────────────────────────────────────
_MAIN_DIMENSIONS = ("c_rank", "dia", "content_factors")
_WEIGHT_FLOOR = 0.15
_WEIGHT_CEIL = 0.55
_MAIN_DEFAULTS = {"c_rank": 0.30, "dia": 0.20, "content_factors": 0.50}

# 3-2. (b) data/learned_category_weights.json 카테고리별 학습값 — TTL 300초 캐시
_LEARNED_FILE = Path(__file__).resolve().parents[2] / "data" / "learned_category_weights.json"
_LEARNED_TTL = 300
_learned_cache: Dict[str, Any] = {"loaded_at": 0.0, "data": {}}


def detect_keyword_category(keyword: Optional[str]) -> str:
    """3-4. 카테고리 감지.

    1단계: 도메인 카테고리 우선(리뷰 제외한 전부)를 순회하며 부분문자열 매칭
    2단계: 도메인 실패 시에만 메타 카테고리 "리뷰" 매칭
    3단계: 그래도 없으면 "default"

    ★ 이유: "다이슨 청소기 후기"는 인테리어 도메인이지 리뷰 메타가 아니다.
    ⚠️ 부분문자열 매칭이므로 오탐 주의 (예: '의원'이 '국회의원'에도 걸린다).
       경계 조건을 강화하면 값이 달라지므로 원본 그대로 둔다.
    """
    if not keyword:
        return "default"
    keyword_lower = keyword.lower().replace(" ", "")
    for category, words in CATEGORY_KEYWORDS.items():
        if category in _META_CATEGORIES:
            continue
        for w in words:
            if w.lower() in keyword_lower:
                return category
    for category in _META_CATEGORIES:
        for w in CATEGORY_KEYWORDS.get(category, []):
            if w.lower() in keyword_lower:
                return category
    return "default"


def _load_learned_weights() -> Dict[str, Any]:
    """data/learned_category_weights.json → {category: weights}. 파일이 없으면 {}."""
    now = time.time()
    if now - _learned_cache["loaded_at"] < _LEARNED_TTL:
        return _learned_cache["data"]
    data: Dict[str, Any] = {}
    try:
        if _LEARNED_FILE.exists():
            with open(_LEARNED_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                data = loaded
    except Exception as e:  # noqa: BLE001
        logger.warning("learned_category_weights.json 로드 실패: %s", e)
        data = {}
    _learned_cache["loaded_at"] = now
    _learned_cache["data"] = data
    return data


def _blend_weights(manual: Dict[str, Any], learned: Dict[str, Any], learned_ratio: float = 0.7) -> Dict[str, Any]:
    """3-2. blend 규칙.

    learned_ratio = 0.7 (학습값 우선)
    main weight : blended = learned*0.7 + manual*0.3   (소수 3자리 반올림)
    sub_weights : 키 합집합에 대해 같은 식으로 blend → 합이 1.0 이 되게 재정규화
    """
    out = json.loads(json.dumps(manual))
    manual_ratio = 1.0 - learned_ratio
    for dim in _MAIN_DIMENSIONS:
        m_dim = manual.get(dim) or {}
        l_dim = learned.get(dim) if isinstance(learned.get(dim), dict) else None
        if l_dim is None:
            continue
        out.setdefault(dim, {})
        m_w = m_dim.get("weight")
        l_w = l_dim.get("weight")
        if l_w is not None and m_w is not None:
            out[dim]["weight"] = round(float(l_w) * learned_ratio + float(m_w) * manual_ratio, 3)
        elif l_w is not None:
            out[dim]["weight"] = round(float(l_w), 3)

        m_sub = m_dim.get("sub_weights") or {}
        l_sub = l_dim.get("sub_weights") or {}
        if l_sub:
            keys = set(m_sub.keys()) | set(l_sub.keys())
            blended: Dict[str, float] = {}
            for k in keys:
                mv = m_sub.get(k)
                lv = l_sub.get(k)
                if mv is not None and lv is not None:
                    blended[k] = float(lv) * learned_ratio + float(mv) * manual_ratio
                elif lv is not None:
                    blended[k] = float(lv)
                else:
                    blended[k] = float(mv)
            total = sum(blended.values())
            if total > 0:
                blended = {k: round(v / total, 3) for k, v in blended.items()}
            out[dim]["sub_weights"] = blended
    return out


def _clamp_and_normalize_main(weights: Dict[str, Any]) -> Dict[str, Any]:
    """3-1. 각 축의 weight 를 [0.15, 0.55] 로 clamp 한 뒤 합이 1.0 이 되도록 재정규화."""
    clamped: Dict[str, float] = {}
    for dim in _MAIN_DIMENSIONS:
        block = weights.get(dim)
        if not isinstance(block, dict):
            block = {}
            weights[dim] = block
        w = block.get("weight")
        try:
            w = float(w) if w is not None else _MAIN_DEFAULTS[dim]
        except (TypeError, ValueError):
            w = _MAIN_DEFAULTS[dim]
        clamped[dim] = max(_WEIGHT_FLOOR, min(_WEIGHT_CEIL, w))
    total = sum(clamped.values())
    if total <= 0:
        clamped = dict(_MAIN_DEFAULTS)
        total = sum(clamped.values())
    for dim in _MAIN_DIMENSIONS:
        weights[dim]["weight"] = round(clamped[dim] / total, 3)
    return weights


def resolve_scoring_weights(keyword: Optional[str], learned_weights: Optional[Dict[str, Any]] = None,
                            scoring_version: int = 6) -> Dict[str, Any]:
    """3-3. resolve_scoring_weights (원본 그대로)."""
    category = detect_keyword_category(keyword) if keyword else "default"
    manual = CATEGORY_WEIGHTS.get(category, CATEGORY_WEIGHTS["default"])
    weights = json.loads(json.dumps(manual))  # deep copy

    learned_version = (learned_weights or {}).get("_scoring_version")
    compatible = bool(learned_weights) and learned_version == scoring_version

    if compatible:
        weights = _blend_weights(weights, learned_weights, learned_ratio=0.7)
        weights["_learned"] = True
        weights["_learned_meta"] = {"source": "learning_db",
                                    "scoring_version": learned_version}
    else:
        weights["_learned"] = False
        weights["_learned_meta"] = {
            "source": "category_prior",
            "reason": ("no_learned_weights" if not learned_weights
                       else f"stale_scoring_version({learned_version} != {scoring_version})")}

    if keyword:
        learned_for_cat = _load_learned_weights().get(category)
        if learned_for_cat:
            weights = _blend_weights(weights, learned_for_cat, learned_ratio=0.7)
            weights["_learned"] = True
            meta = weights.get("_learned_meta") or {}
            if meta.get("reason"):
                meta["learning_db_skipped"] = meta.pop("reason")
            meta["source"] = "category_learned"
            meta["category_learned"] = learned_for_cat.get("_meta", {})
            weights["_learned_meta"] = meta

    weights = _clamp_and_normalize_main(weights)   # [0.15, 0.55] → 합 1.0

    # 폴백 sub_weights / extra_factors (원본 그대로 — 프리셋에 없을 때만)
    if "sub_weights" not in weights.get("c_rank", {}):
        weights["c_rank"]["sub_weights"] = {"context": 0.35, "content": 0.40, "chain": 0.25}
    if "sub_weights" not in weights.get("dia", {}):
        weights["dia"]["sub_weights"] = {"depth": 0.33, "information": 0.34, "accuracy": 0.33}
    if not isinstance(weights.get("extra_factors"), dict) or not weights["extra_factors"]:
        # extra_factors 기본값: post_count 0.05 / neighbor_count 0.03 / visitor_count 0.02
        weights["extra_factors"] = {"post_count": 0.05, "neighbor_count": 0.03, "visitor_count": 0.02}

    weights["_category"] = category
    return weights
