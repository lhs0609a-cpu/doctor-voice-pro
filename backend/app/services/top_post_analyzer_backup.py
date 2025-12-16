"""
상위 글 분석 서비스
네이버 블로그 검색 결과 상위 1~3위 글들을 크롤링하고 분석
"""

import re
import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.top_post_analysis import TopPostAnalysis, AggregatedPattern


# 카테고리 정의
CATEGORIES = {
    "hospital": {
        "name": "병원/의료",
        "keywords": ["병원", "의원", "클리닉", "치과", "피부과", "성형", "시술", "수술", "치료", "진료", "의사", "간호", "정형외과", "내과", "외과", "안과", "이비인후과", "산부인과", "비뇨기과", "재활의학과"]
    },
    "restaurant": {
        "name": "맛집/음식점",
        "keywords": ["맛집", "식당", "카페", "음식", "메뉴", "배달", "맛있", "먹방", "레스토랑", "베이커리", "디저트", "브런치", "점심", "저녁", "회식"]
    },
    "beauty": {
        "name": "뷰티/화장품",
        "keywords": ["화장품", "뷰티", "스킨케어", "메이크업", "향수", "네일", "헤어", "에스테틱", "피부관리", "미용실", "왁싱", "속눈썹"]
    },
    "parenting": {
        "name": "육아/교육",
        "keywords": ["육아", "아기", "유아", "어린이", "키즈", "유치원", "초등", "학원", "교육", "엄마", "아빠", "임신", "출산"]
    },
    "travel": {
        "name": "여행/숙소",
        "keywords": ["여행", "호텔", "숙소", "펜션", "리조트", "관광", "투어", "항공", "렌트카", "캠핑", "글램핑", "제주", "부산", "해외여행"]
    },
    "tech": {
        "name": "IT/리뷰",
        "keywords": ["리뷰", "전자제품", "스마트폰", "노트북", "가전", "IT", "앱", "소프트웨어", "테크", "아이폰", "갤럭시", "애플워치"]
    },
    "fitness": {
        "name": "운동/헬스",
        "keywords": ["헬스", "피트니스", "PT", "다이어트", "요가", "필라테스", "크로스핏", "러닝", "수영", "운동"]
    },
    "general": {
        "name": "일반",
        "keywords": []
    }
}

# HTML 파싱 셀렉터
SELECTORS = {
    "title": [
        ".se-title-text",
        ".tit_h3",
        "._postTitleText",
        ".post_tit",
        "meta[property='og:title']"
    ],
    "content": [
        ".se-main-container",
        "._postView",
        ".post_ct",
        "#postViewArea",
        ".__viewer_container"
    ],
    "images": [
        ".se-image-resource",
        "img.se_mediaImage",
        "img[src*='blogfiles']",
        "img[src*='postfiles']"
    ],
    "videos": [
        ".se-video",
        "iframe[src*='video']",
        "iframe[src*='youtube']",
        "iframe[src*='tv.naver']"
    ],
    "headings": [
        ".se-section-title",
        ".se-title-text",
        "h2", "h3"
    ],
    "maps": [
        ".se-map",
        "iframe[src*='map']",
        ".map_area"
    ],
    "quotes": [
        ".se-quotation",
        "blockquote",
        ".se-quote"
    ],
    "lists": [
        ".se-list",
        "ul", "ol"
    ]
}


def detect_category(keyword: str) -> str:
    """키워드에서 카테고리 자동 감지"""
    keyword_lower = keyword.lower()

    for category_id, category_info in CATEGORIES.items():
        if category_id == "general":
            continue
        for kw in category_info["keywords"]:
            if kw in keyword_lower:
                return category_id

    return "general"


def get_keyword_position(title: str, keyword: str) -> int:
    """
    제목에서 키워드 위치 판단
    Returns:
        0: 앞부분 (0~33%)
        1: 중간 (34~66%)
        2: 끝부분 (67~100%)
        -1: 키워드 없음
    """
    title_normalized = title.lower().replace(" ", "")
    keyword_normalized = keyword.lower().replace(" ", "")

    if keyword_normalized not in title_normalized:
        return -1

    position = title_normalized.find(keyword_normalized)
    title_length = len(title_normalized)

    if title_length == 0:
        return -1

    ratio = position / title_length

    if ratio <= 0.33:
        return 0  # 앞부분
    elif ratio <= 0.66:
        return 1  # 중간
    else:
        return 2  # 끝부분


def calculate_keyword_density(content: str, keyword: str) -> Tuple[int, float]:
    """
    키워드 밀도 계산
    Returns:
        (keyword_count, keyword_density)
        - keyword_count: 키워드 등장 횟수
        - keyword_density: 1000자당 키워드 등장 횟수
    """
    content_normalized = content.lower().replace(" ", "")
    keyword_normalized = keyword.lower().replace(" ", "")

    keyword_count = content_normalized.count(keyword_normalized)
    content_length = len(content_normalized)

    if content_length == 0:
        return (0, 0.0)

    keyword_density = round((keyword_count * 1000) / content_length, 2)

    return (keyword_count, keyword_density)


def assess_data_quality(analysis: dict) -> str:
    """데이터 품질 판단"""
    content_length = analysis.get("content_length", 0)
    image_count = analysis.get("image_count", 0)

    if content_length >= 1000 and image_count >= 3:
        return "high"
    elif content_length >= 500:
        return "medium"
    return "low"


async def search_naver_blog(keyword: str, top_n: int = 3) -> List[Dict]:
    """
    네이버 블로그 검색하여 상위 글 URL 수집
    """
    results = []
    search_url = f"https://search.naver.com/search.naver?where=blog&query={keyword}&sm=tab_opt"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(search_url, headers=headers)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # 블로그 검색 결과 파싱
                blog_items = soup.select('.api_txt_lines.total_tit') or soup.select('.title_link')

                for idx, item in enumerate(blog_items[:top_n]):
                    href = item.get('href', '')

                    # 블로그 URL 추출
                    if 'blog.naver.com' in href:
                        # URL에서 blog_id와 post_no 추출
                        match = re.search(r'blog\.naver\.com/([^/\?]+)/?(\d+)?', href)
                        if match:
                            blog_id = match.group(1)
                            post_no = match.group(2) if match.group(2) else ''

                            results.append({
                                "rank": idx + 1,
                                "blog_id": blog_id,
                                "post_url": href,
                                "title": item.get_text(strip=True)
                            })

    except Exception as e:
        print(f"[상위글 분석] 검색 오류: {e}")

    return results


async def analyze_post(post_url: str, keyword: str) -> Dict:
    """
    블로그 포스트 분석
    """
    result = {
        "post_url": post_url,
        "keyword": keyword,
        "title": "",
        "title_length": 0,
        "title_has_keyword": False,
        "title_keyword_position": -1,
        "content_length": 0,
        "image_count": 0,
        "video_count": 0,
        "keyword_count": 0,
        "keyword_density": 0.0,
        "heading_count": 0,
        "paragraph_count": 0,
        "has_map": False,
        "has_link": False,
        "has_quote": False,
        "has_list": False,
        "like_count": 0,
        "comment_count": 0,
        "post_date": None,
        "post_age_days": None,
        "data_fetched": False
    }

    # URL에서 blog_id, post_no 추출
    match = re.search(r'blog\.naver\.com/([^/\?]+)/?(\d+)?', post_url)
    if not match:
        return result

    blog_id = match.group(1)
    post_no = match.group(2) if match.group(2) else ''

    # 모바일 버전 URL로 요청 (더 간단한 구조)
    mobile_url = f"https://m.blog.naver.com/{blog_id}/{post_no}" if post_no else f"https://m.blog.naver.com/{blog_id}"

    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(mobile_url, headers=headers)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # 제목 추출
                title = None
                for selector in SELECTORS["title"]:
                    if selector.startswith("meta"):
                        meta = soup.select_one(selector)
                        if meta:
                            title = meta.get('content', '')
                            break
                    else:
                        el = soup.select_one(selector)
                        if el:
                            title = el.get_text(strip=True)
                            break

                if title:
                    result["title"] = title
                    result["title_length"] = len(title)
                    result["title_has_keyword"] = keyword.lower() in title.lower()
                    result["title_keyword_position"] = get_keyword_position(title, keyword)

                # 본문 추출
                content = ""
                for selector in SELECTORS["content"]:
                    el = soup.select_one(selector)
                    if el:
                        content = el.get_text(separator="\n", strip=True)
                        break

                if content:
                    result["content_length"] = len(content)
                    kw_count, kw_density = calculate_keyword_density(content, keyword)
                    result["keyword_count"] = kw_count
                    result["keyword_density"] = kw_density
                    result["data_fetched"] = True

                    # 문단 개수 (줄바꿈 기준)
                    paragraphs = [p for p in content.split('\n') if p.strip() and len(p.strip()) > 20]
                    result["paragraph_count"] = len(paragraphs)

                # 이미지 개수
                images = []
                for selector in SELECTORS["images"]:
                    images.extend(soup.select(selector))
                result["image_count"] = len(set([img.get('src', '') for img in images if img.get('src')]))

                # 동영상 개수
                videos = []
                for selector in SELECTORS["videos"]:
                    videos.extend(soup.select(selector))
                result["video_count"] = len(videos)

                # 소제목 개수
                headings = []
                for selector in SELECTORS["headings"]:
                    headings.extend(soup.select(selector))
                result["heading_count"] = len(headings)

                # 지도 여부
                maps = []
                for selector in SELECTORS["maps"]:
                    maps.extend(soup.select(selector))
                result["has_map"] = len(maps) > 0

                # 외부 링크 여부
                links = soup.select('a[href*="http"]')
                external_links = [l for l in links if 'naver.com' not in l.get('href', '')]
                result["has_link"] = len(external_links) > 0

                # 인용구 여부
                quotes = []
                for selector in SELECTORS["quotes"]:
                    quotes.extend(soup.select(selector))
                result["has_quote"] = len(quotes) > 0

                # 목록 여부
                lists = []
                for selector in SELECTORS["lists"]:
                    lists.extend(soup.select(selector))
                result["has_list"] = len(lists) > 0

    except Exception as e:
        print(f"[상위글 분석] 포스트 분석 오류 ({post_url}): {e}")

    return result


async def analyze_top_posts(keyword: str, top_n: int = 3, db: Session = None) -> Dict:
    """
    키워드에 대한 상위 글 전체 분석
    """
    category = detect_category(keyword)

    # 1. 검색하여 상위 글 URL 수집
    search_results = await search_naver_blog(keyword, top_n)

    if not search_results:
        return {
            "keyword": keyword,
            "category": category,
            "analyzed_count": 0,
            "results": [],
            "summary": None,
            "error": "검색 결과를 찾을 수 없습니다"
        }

    # 2. 각 글 분석
    analysis_results = []
    for result in search_results:
        analysis = await analyze_post(result["post_url"], keyword)
        analysis["rank"] = result["rank"]
        analysis["blog_id"] = result["blog_id"]
        analysis["category"] = category
        analysis["data_quality"] = assess_data_quality(analysis)
        analysis_results.append(analysis)

        # DB 저장
        if db:
            try:
                save_post_analysis(db, analysis)
            except Exception as e:
                print(f"[상위글 분석] DB 저장 오류: {e}")

    # 3. 요약 통계 계산
    summary = calculate_summary(analysis_results)

    # 4. 패턴 집계 업데이트
    if db:
        try:
            update_aggregated_patterns(db, category)
        except Exception as e:
            print(f"[상위글 분석] 패턴 집계 오류: {e}")

    return {
        "keyword": keyword,
        "category": category,
        "category_name": CATEGORIES.get(category, {}).get("name", "일반"),
        "analyzed_count": len(analysis_results),
        "results": analysis_results,
        "summary": summary
    }


def calculate_summary(results: List[Dict]) -> Dict:
    """분석 결과 요약 통계 계산"""
    if not results:
        return None

    valid_results = [r for r in results if r.get("data_fetched")]
    if not valid_results:
        return None

    n = len(valid_results)

    # 평균 계산
    avg_title_length = sum(r["title_length"] for r in valid_results) / n
    avg_content_length = sum(r["content_length"] for r in valid_results) / n
    avg_image_count = sum(r["image_count"] for r in valid_results) / n
    avg_heading_count = sum(r["heading_count"] for r in valid_results) / n
    avg_keyword_count = sum(r["keyword_count"] for r in valid_results) / n
    avg_keyword_density = sum(r["keyword_density"] for r in valid_results) / n

    # 범위 계산
    content_lengths = [r["content_length"] for r in valid_results]
    image_counts = [r["image_count"] for r in valid_results]

    # 키워드 위치 분포
    positions = [r["title_keyword_position"] for r in valid_results]
    pos_front = positions.count(0) / n * 100 if n > 0 else 0
    pos_middle = positions.count(1) / n * 100 if n > 0 else 0
    pos_end = positions.count(2) / n * 100 if n > 0 else 0

    # 비율 계산
    title_keyword_rate = sum(1 for r in valid_results if r["title_has_keyword"]) / n * 100
    map_rate = sum(1 for r in valid_results if r["has_map"]) / n * 100
    video_rate = sum(1 for r in valid_results if r["video_count"] > 0) / n * 100
    quote_rate = sum(1 for r in valid_results if r["has_quote"]) / n * 100
    list_rate = sum(1 for r in valid_results if r["has_list"]) / n * 100

    return {
        "sample_count": n,
        "title": {
            "avg_length": round(avg_title_length),
            "min_length": min(r["title_length"] for r in valid_results),
            "max_length": max(r["title_length"] for r in valid_results),
            "keyword_rate": round(title_keyword_rate, 1),
            "position_distribution": {
                "front": round(pos_front, 1),
                "middle": round(pos_middle, 1),
                "end": round(pos_end, 1)
            }
        },
        "content": {
            "avg_length": round(avg_content_length),
            "min_length": min(content_lengths),
            "max_length": max(content_lengths),
            "avg_headings": round(avg_heading_count, 1),
            "avg_keyword_count": round(avg_keyword_count, 1),
            "avg_keyword_density": round(avg_keyword_density, 2)
        },
        "media": {
            "avg_images": round(avg_image_count, 1),
            "min_images": min(image_counts),
            "max_images": max(image_counts),
            "video_usage_rate": round(video_rate, 1)
        },
        "extras": {
            "map_usage_rate": round(map_rate, 1),
            "quote_usage_rate": round(quote_rate, 1),
            "list_usage_rate": round(list_rate, 1)
        }
    }


def save_post_analysis(db: Session, analysis: Dict):
    """분석 결과 DB 저장"""
    existing = db.query(TopPostAnalysis).filter(
        TopPostAnalysis.keyword == analysis["keyword"],
        TopPostAnalysis.post_url == analysis["post_url"]
    ).first()

    if existing:
        # 업데이트
        for key, value in analysis.items():
            if hasattr(existing, key) and key not in ["id", "analyzed_at"]:
                setattr(existing, key, value)
        existing.analyzed_at = datetime.utcnow()
    else:
        # 새로 생성
        new_analysis = TopPostAnalysis(
            keyword=analysis.get("keyword"),
            rank=analysis.get("rank", 0),
            blog_id=analysis.get("blog_id", ""),
            post_url=analysis.get("post_url"),
            title=analysis.get("title", ""),
            title_length=analysis.get("title_length", 0),
            title_has_keyword=analysis.get("title_has_keyword", False),
            title_keyword_position=analysis.get("title_keyword_position", -1),
            content_length=analysis.get("content_length", 0),
            image_count=analysis.get("image_count", 0),
            video_count=analysis.get("video_count", 0),
            heading_count=analysis.get("heading_count", 0),
            paragraph_count=analysis.get("paragraph_count", 0),
            keyword_count=analysis.get("keyword_count", 0),
            keyword_density=analysis.get("keyword_density", 0.0),
            has_map=analysis.get("has_map", False),
            has_link=analysis.get("has_link", False),
            has_quote=analysis.get("has_quote", False),
            has_list=analysis.get("has_list", False),
            like_count=analysis.get("like_count", 0),
            comment_count=analysis.get("comment_count", 0),
            category=analysis.get("category", "general"),
            data_quality=analysis.get("data_quality", "low")
        )
        db.add(new_analysis)

    db.commit()


def update_aggregated_patterns(db: Session, category: str):
    """카테고리별 패턴 집계 업데이트"""
    # 상위 1~3위 글만 집계 (rank <= 3)
    stats = db.query(
        func.count(TopPostAnalysis.id).label('sample_count'),
        func.avg(TopPostAnalysis.title_length).label('avg_title_length'),
        func.avg(TopPostAnalysis.content_length).label('avg_content_length'),
        func.avg(TopPostAnalysis.image_count).label('avg_image_count'),
        func.avg(TopPostAnalysis.video_count).label('avg_video_count'),
        func.avg(TopPostAnalysis.heading_count).label('avg_heading_count'),
        func.avg(TopPostAnalysis.paragraph_count).label('avg_paragraph_count'),
        func.avg(TopPostAnalysis.keyword_count).label('avg_keyword_count'),
        func.avg(TopPostAnalysis.keyword_density).label('avg_keyword_density'),
        func.min(TopPostAnalysis.content_length).label('min_content_length'),
        func.max(TopPostAnalysis.content_length).label('max_content_length'),
        func.min(TopPostAnalysis.image_count).label('min_image_count'),
        func.max(TopPostAnalysis.image_count).label('max_image_count'),
    ).filter(
        TopPostAnalysis.category == category,
        TopPostAnalysis.rank <= 3,
        TopPostAnalysis.content_length > 100
    ).first()

    if not stats or stats.sample_count == 0:
        return

    # 비율 계산
    total = db.query(TopPostAnalysis).filter(
        TopPostAnalysis.category == category,
        TopPostAnalysis.rank <= 3,
        TopPostAnalysis.content_length > 100
    ).count()

    title_keyword_count = db.query(TopPostAnalysis).filter(
        TopPostAnalysis.category == category,
        TopPostAnalysis.rank <= 3,
        TopPostAnalysis.title_has_keyword == True
    ).count()

    map_count = db.query(TopPostAnalysis).filter(
        TopPostAnalysis.category == category,
        TopPostAnalysis.rank <= 3,
        TopPostAnalysis.has_map == True
    ).count()

    video_count = db.query(TopPostAnalysis).filter(
        TopPostAnalysis.category == category,
        TopPostAnalysis.rank <= 3,
        TopPostAnalysis.video_count > 0
    ).count()

    # 키워드 위치 분포
    pos_front = db.query(TopPostAnalysis).filter(
        TopPostAnalysis.category == category,
        TopPostAnalysis.rank <= 3,
        TopPostAnalysis.title_keyword_position == 0
    ).count()

    pos_middle = db.query(TopPostAnalysis).filter(
        TopPostAnalysis.category == category,
        TopPostAnalysis.rank <= 3,
        TopPostAnalysis.title_keyword_position == 1
    ).count()

    pos_end = db.query(TopPostAnalysis).filter(
        TopPostAnalysis.category == category,
        TopPostAnalysis.rank <= 3,
        TopPostAnalysis.title_keyword_position == 2
    ).count()

    # 저장
    existing = db.query(AggregatedPattern).filter(
        AggregatedPattern.category == category
    ).first()

    pattern_data = {
        "category": category,
        "sample_count": stats.sample_count,
        "avg_title_length": stats.avg_title_length or 0,
        "avg_content_length": stats.avg_content_length or 0,
        "avg_image_count": stats.avg_image_count or 0,
        "avg_video_count": stats.avg_video_count or 0,
        "avg_heading_count": stats.avg_heading_count or 0,
        "avg_paragraph_count": stats.avg_paragraph_count or 0,
        "avg_keyword_count": stats.avg_keyword_count or 0,
        "avg_keyword_density": stats.avg_keyword_density or 0,
        "min_content_length": stats.min_content_length or 0,
        "max_content_length": stats.max_content_length or 0,
        "min_image_count": stats.min_image_count or 0,
        "max_image_count": stats.max_image_count or 0,
        "title_keyword_rate": title_keyword_count / total if total > 0 else 0,
        "map_usage_rate": map_count / total if total > 0 else 0,
        "video_usage_rate": video_count / total if total > 0 else 0,
        "keyword_position_front": pos_front / total if total > 0 else 0,
        "keyword_position_middle": pos_middle / total if total > 0 else 0,
        "keyword_position_end": pos_end / total if total > 0 else 0,
    }

    if existing:
        for key, value in pattern_data.items():
            if hasattr(existing, key):
                setattr(existing, key, value)
        existing.updated_at = datetime.utcnow()
    else:
        new_pattern = AggregatedPattern(**pattern_data)
        db.add(new_pattern)

    db.commit()


def generate_writing_guide(db: Session, category: str) -> Dict:
    """
    축적된 데이터 기반 글쓰기 가이드 생성
    """
    patterns = db.query(AggregatedPattern).filter(
        AggregatedPattern.category == category
    ).first()

    # 기본 규칙
    DEFAULT_RULES = {
        "title": {
            "length": {"optimal": 30, "min": 20, "max": 45},
            "keyword_placement": {
                "include_keyword": True,
                "best_position": "front",
                "position_distribution": {"front": 60, "middle": 30, "end": 10}
            }
        },
        "content": {
            "length": {"optimal": 2000, "min": 1500, "max": 3500},
            "structure": {
                "heading_count": {"optimal": 5, "min": 3, "max": 8},
                "keyword_density": {"optimal": 1.2, "min": 0.8, "max": 2.0},
                "keyword_count": {"optimal": 8, "min": 5, "max": 15}
            }
        },
        "media": {
            "images": {"optimal": 10, "min": 5, "max": 15},
            "videos": {"usage_rate": 20, "recommended": False}
        },
        "extras": {
            "map": {"usage_rate": 15, "recommended": False},
            "quote": {"usage_rate": 30, "recommended": True},
            "list": {"usage_rate": 40, "recommended": True}
        }
    }

    # 데이터 부족 시 기본값 사용
    if not patterns or patterns.sample_count < 3:
        return {
            "status": "insufficient_data",
            "confidence": 0,
            "sample_count": patterns.sample_count if patterns else 0,
            "message": "분석 데이터가 부족합니다. 더 많은 키워드를 검색해주세요.",
            "rules": DEFAULT_RULES
        }

    sample_count = patterns.sample_count
    confidence = min(1.0, sample_count / 30)  # 30개 이상이면 100% 신뢰도

    # 최적 키워드 위치 결정
    positions = {
        "front": patterns.keyword_position_front,
        "middle": patterns.keyword_position_middle,
        "end": patterns.keyword_position_end
    }
    best_position = max(positions, key=positions.get)

    return {
        "status": "data_driven",
        "confidence": round(confidence, 2),
        "sample_count": sample_count,
        "category": category,
        "category_name": CATEGORIES.get(category, {}).get("name", "일반"),
        "rules": {
            "title": {
                "length": {
                    "optimal": round(patterns.avg_title_length),
                    "min": max(15, round(patterns.avg_title_length * 0.7)),
                    "max": min(60, round(patterns.avg_title_length * 1.3))
                },
                "keyword_placement": {
                    "include_keyword": patterns.title_keyword_rate > 0.5,
                    "rate": round(patterns.title_keyword_rate * 100, 1),
                    "best_position": best_position,
                    "position_distribution": {
                        "front": round(patterns.keyword_position_front * 100, 1),
                        "middle": round(patterns.keyword_position_middle * 100, 1),
                        "end": round(patterns.keyword_position_end * 100, 1)
                    }
                }
            },
            "content": {
                "length": {
                    "optimal": round(patterns.avg_content_length),
                    "min": max(500, round(patterns.avg_content_length * 0.7)),
                    "max": round(patterns.avg_content_length * 1.3)
                },
                "structure": {
                    "heading_count": {
                        "optimal": round(patterns.avg_heading_count),
                        "min": max(2, round(patterns.avg_heading_count * 0.6)),
                        "max": round(patterns.avg_heading_count * 1.5)
                    },
                    "keyword_density": {
                        "optimal": round(patterns.avg_keyword_density, 2),
                        "min": max(0.3, round(patterns.avg_keyword_density * 0.5, 2)),
                        "max": min(3.0, round(patterns.avg_keyword_density * 1.5, 2))
                    },
                    "keyword_count": {
                        "optimal": round(patterns.avg_keyword_count),
                        "min": max(3, round(patterns.avg_keyword_count * 0.6)),
                        "max": round(patterns.avg_keyword_count * 1.4)
                    }
                }
            },
            "media": {
                "images": {
                    "optimal": round(patterns.avg_image_count),
                    "min": max(3, patterns.min_image_count),
                    "max": patterns.max_image_count
                },
                "videos": {
                    "usage_rate": round(patterns.video_usage_rate * 100, 1),
                    "recommended": patterns.video_usage_rate > 0.3
                }
            },
            "extras": {
                "map": {
                    "usage_rate": round(patterns.map_usage_rate * 100, 1),
                    "recommended": patterns.map_usage_rate > 0.2
                },
                "quote": {
                    "usage_rate": round(patterns.quote_usage_rate * 100, 1) if hasattr(patterns, 'quote_usage_rate') else 30,
                    "recommended": True
                },
                "list": {
                    "usage_rate": round(patterns.list_usage_rate * 100, 1) if hasattr(patterns, 'list_usage_rate') else 40,
                    "recommended": True
                }
            }
        }
    }


def generate_ai_prompt_guide(guide: Dict) -> str:
    """AI 프롬프트용 가이드 텍스트 생성"""
    rules = guide["rules"]

    prompt = f"""[상위노출 최적화 규칙 - {guide.get('sample_count', 0)}개 글 분석 기반, 신뢰도 {guide.get('confidence', 0) * 100:.0f}%]

## 제목 규칙
- 글자 수: {rules['title']['length']['min']}~{rules['title']['length']['max']}자 (최적: {rules['title']['length']['optimal']}자)
- 키워드 위치: {rules['title']['keyword_placement']['best_position']} (앞:{rules['title']['keyword_placement']['position_distribution']['front']}% 중간:{rules['title']['keyword_placement']['position_distribution']['middle']}% 끝:{rules['title']['keyword_placement']['position_distribution']['end']}%)
- 키워드 포함률: {rules['title']['keyword_placement']['rate']}%

## 본문 규칙
- 글자 수: {rules['content']['length']['min']}~{rules['content']['length']['max']}자 (최적: {rules['content']['length']['optimal']}자)
- 소제목: {rules['content']['structure']['heading_count']['min']}~{rules['content']['structure']['heading_count']['max']}개
- 키워드 등장: {rules['content']['structure']['keyword_count']['min']}~{rules['content']['structure']['keyword_count']['max']}회
- 키워드 밀도: {rules['content']['structure']['keyword_density']['min']}~{rules['content']['structure']['keyword_density']['max']}/1000자

## 이미지 규칙
- 이미지: {rules['media']['images']['min']}~{rules['media']['images']['max']}장 (최적: {rules['media']['images']['optimal']}장)
- 동영상 사용률: {rules['media']['videos']['usage_rate']}%

이 규칙을 따라 글을 작성해주세요."""

    return prompt
