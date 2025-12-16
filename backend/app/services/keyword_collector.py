"""
키워드 수집 서비스
네이버 연관검색어 및 자동완성 키워드를 수집하여 분석용 키워드 풀을 생성
"""

import re
import json
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Set, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.analysis_job import CollectedKeyword


# 카테고리별 시드 키워드
CATEGORY_SEEDS = {
    "hospital": {
        "name": "병원/의료",
        "seeds": [
            "피부과", "정형외과", "치과", "한의원", "성형외과",
            "내과", "산부인과", "안과", "이비인후과", "비뇨기과",
            "재활의학과", "신경외과", "외과", "정신건강의학과",
            "시술", "수술", "진료", "치료", "검진", "주사"
        ]
    },
    "restaurant": {
        "name": "맛집/음식점",
        "seeds": [
            "맛집", "카페", "식당", "레스토랑", "브런치",
            "디저트", "베이커리", "치킨", "피자", "삼겹살",
            "회", "스시", "파스타", "한식", "중식", "일식",
            "배달", "포장", "맛있는", "추천"
        ]
    },
    "beauty": {
        "name": "뷰티/화장품",
        "seeds": [
            "화장품", "스킨케어", "메이크업", "향수", "네일",
            "헤어", "미용실", "피부관리", "에스테틱", "속눈썹",
            "왁싱", "제모", "토너", "세럼", "크림", "클렌징"
        ]
    },
    "parenting": {
        "name": "육아/교육",
        "seeds": [
            "육아", "아기", "유아", "어린이", "키즈",
            "유치원", "어린이집", "초등학교", "학원", "과외",
            "임신", "출산", "이유식", "장난감", "교구", "책"
        ]
    },
    "travel": {
        "name": "여행/숙소",
        "seeds": [
            "여행", "호텔", "숙소", "펜션", "리조트",
            "캠핑", "글램핑", "항공", "렌트카", "관광",
            "투어", "제주도", "부산", "강원도", "해외여행"
        ]
    },
    "tech": {
        "name": "IT/리뷰",
        "seeds": [
            "리뷰", "스마트폰", "노트북", "태블릿", "이어폰",
            "스마트워치", "카메라", "모니터", "키보드", "마우스",
            "아이폰", "갤럭시", "맥북", "게이밍", "앱"
        ]
    },
    "fitness": {
        "name": "운동/헬스",
        "seeds": [
            "헬스장", "피트니스", "PT", "다이어트", "요가",
            "필라테스", "크로스핏", "러닝", "수영", "골프",
            "홈트", "운동", "헬스", "식단", "보충제"
        ]
    },
    "general": {
        "name": "일반",
        "seeds": [
            "후기", "추천", "비교", "정보", "방법",
            "가격", "비용", "효과", "장단점", "꿀팁"
        ]
    }
}

# User-Agent 헤더
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


async def get_naver_related_keywords(keyword: str) -> List[str]:
    """
    네이버 연관검색어 수집
    """
    related = []
    search_url = f"https://search.naver.com/search.naver?where=nexearch&query={keyword}"

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(search_url, headers=HEADERS)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # 연관 검색어 영역 찾기
                related_area = soup.select('.related_srch .keyword')
                for item in related_area:
                    text = item.get_text(strip=True)
                    if text and text != keyword:
                        related.append(text)

                # 추가 연관검색어 영역
                related_area2 = soup.select('.related_srch_area .lst_related_srch a')
                for item in related_area2:
                    text = item.get_text(strip=True)
                    if text and text != keyword and text not in related:
                        related.append(text)

    except Exception as e:
        print(f"[키워드 수집] 연관검색어 오류 ({keyword}): {e}")

    return related[:10]  # 최대 10개


async def get_naver_autocomplete(keyword: str) -> List[str]:
    """
    네이버 자동완성 키워드 수집
    """
    suggestions = []
    autocomplete_url = f"https://ac.search.naver.com/nx/ac?q={keyword}&con=1&frm=nv&ans=2&r_format=json&r_enc=UTF-8&r_unicode=0&t_koreng=1&run=2&rev=4&q_enc=UTF-8"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(autocomplete_url, headers=HEADERS)

            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [[]])[0]

                for item in items:
                    if isinstance(item, list) and len(item) > 0:
                        suggestion = item[0]
                        if suggestion and suggestion != keyword:
                            suggestions.append(suggestion)

    except Exception as e:
        print(f"[키워드 수집] 자동완성 오류 ({keyword}): {e}")

    return suggestions[:10]


async def collect_keywords_for_category(
    category: str,
    max_keywords: int = 100
) -> Dict:
    """
    카테고리별 키워드 대량 수집

    Args:
        category: 카테고리 ID
        max_keywords: 최대 수집 키워드 수

    Returns:
        {
            "category": str,
            "keywords": List[str],
            "count": int
        }
    """
    if category not in CATEGORY_SEEDS:
        return {"category": category, "keywords": [], "count": 0, "error": "Invalid category"}

    seeds = CATEGORY_SEEDS[category]["seeds"]
    collected: Set[str] = set(seeds)  # 시드 키워드로 시작

    # 1단계: 시드 키워드에서 연관검색어 수집
    for seed in seeds:
        if len(collected) >= max_keywords:
            break

        related = await get_naver_related_keywords(seed)
        for kw in related:
            if len(collected) < max_keywords:
                collected.add(kw)

        autocomplete = await get_naver_autocomplete(seed)
        for kw in autocomplete:
            if len(collected) < max_keywords:
                collected.add(kw)

    # 2단계: 수집된 키워드에서 추가 확장 (아직 목표에 미달인 경우)
    if len(collected) < max_keywords:
        expansion_candidates = list(collected - set(seeds))[:20]  # 상위 20개만

        for candidate in expansion_candidates:
            if len(collected) >= max_keywords:
                break

            related = await get_naver_related_keywords(candidate)
            for kw in related:
                if len(collected) < max_keywords:
                    collected.add(kw)

    keywords_list = list(collected)[:max_keywords]

    return {
        "category": category,
        "category_name": CATEGORY_SEEDS[category]["name"],
        "keywords": keywords_list,
        "count": len(keywords_list)
    }


def save_keywords_to_db(
    db: Session,
    category: str,
    keywords: List[str],
    source: str = "collected"
) -> int:
    """
    수집된 키워드를 DB에 저장

    Returns:
        저장된 키워드 수
    """
    saved_count = 0

    for keyword in keywords:
        # 이미 존재하는지 확인
        existing = db.query(CollectedKeyword).filter(
            CollectedKeyword.category == category,
            CollectedKeyword.keyword == keyword
        ).first()

        if not existing:
            new_keyword = CollectedKeyword(
                category=category,
                keyword=keyword,
                source=source
            )
            db.add(new_keyword)
            saved_count += 1

    db.commit()
    return saved_count


def get_keywords_for_analysis(
    db: Session,
    category: str,
    limit: int = 100,
    only_unanalyzed: bool = True
) -> List[str]:
    """
    분석용 키워드 목록 조회

    Args:
        category: 카테고리
        limit: 최대 개수
        only_unanalyzed: 미분석 키워드만 조회

    Returns:
        키워드 목록
    """
    query = db.query(CollectedKeyword).filter(
        CollectedKeyword.category == category
    )

    if only_unanalyzed:
        query = query.filter(CollectedKeyword.is_analyzed == 0)

    query = query.order_by(CollectedKeyword.created_at).limit(limit)

    keywords = query.all()
    return [kw.keyword for kw in keywords]


def mark_keyword_analyzed(
    db: Session,
    category: str,
    keyword: str,
    analyzed_count: int = 1
):
    """
    키워드를 분석 완료로 표시
    """
    existing = db.query(CollectedKeyword).filter(
        CollectedKeyword.category == category,
        CollectedKeyword.keyword == keyword
    ).first()

    if existing:
        existing.is_analyzed = 1
        existing.analysis_count = (existing.analysis_count or 0) + analyzed_count
        existing.last_analyzed_at = datetime.utcnow()
        db.commit()


def get_category_keyword_stats(db: Session, category: str) -> Dict:
    """
    카테고리별 키워드 통계 조회
    """
    total = db.query(CollectedKeyword).filter(
        CollectedKeyword.category == category
    ).count()

    analyzed = db.query(CollectedKeyword).filter(
        CollectedKeyword.category == category,
        CollectedKeyword.is_analyzed == 1
    ).count()

    return {
        "category": category,
        "category_name": CATEGORY_SEEDS.get(category, {}).get("name", "알 수 없음"),
        "total_keywords": total,
        "analyzed_keywords": analyzed,
        "pending_keywords": total - analyzed
    }


def get_all_categories() -> List[Dict]:
    """
    모든 카테고리 정보 반환
    """
    return [
        {
            "id": cat_id,
            "name": cat_info["name"],
            "seed_count": len(cat_info["seeds"]),
            "sample_seeds": cat_info["seeds"][:5]
        }
        for cat_id, cat_info in CATEGORY_SEEDS.items()
    ]
