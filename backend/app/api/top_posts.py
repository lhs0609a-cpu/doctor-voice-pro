"""
상위 글 분석 API 엔드포인트
네이버 블로그 검색 결과 상위 1~3위 글들을 분석하고 글쓰기 가이드 제공
"""

import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List
from pydantic import BaseModel

from app.api.deps import get_db
from app.models.top_post_analysis import TopPostAnalysis, AggregatedPattern
from app.models.analysis_job import AnalysisJob, CollectedKeyword
from app.services.top_post_analyzer import (
    analyze_top_posts,
    generate_writing_guide,
    generate_ai_prompt_guide,
    CATEGORIES,
    detect_category
)
from app.services.keyword_collector import (
    collect_keywords_for_category,
    get_all_categories,
    get_category_keyword_stats,
    CATEGORY_SEEDS
)
from app.services.bulk_analysis_service import (
    BulkAnalysisService,
    run_bulk_analysis,
    get_analysis_dashboard,
    get_category_rules
)

router = APIRouter()


class AnalyzeRequest(BaseModel):
    """분석 요청 스키마"""
    keyword: str
    top_n: int = 3


class AnalyzeResponse(BaseModel):
    """분석 응답 스키마"""
    keyword: str
    category: str
    category_name: str
    analyzed_count: int
    results: list
    summary: Optional[dict] = None
    error: Optional[str] = None


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_keyword(
    request: AnalyzeRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    키워드에 대한 상위 글 분석

    - 네이버 블로그 검색 결과 상위 1~3위 글을 수집
    - 각 글의 제목, 본문, 이미지 등 분석
    - 결과를 DB에 저장하고 요약 통계 반환
    """
    try:
        # 동기 DB 세션으로 변환 필요 - 일단 None으로 전달
        result = await analyze_top_posts(
            keyword=request.keyword,
            top_n=request.top_n,
            db=None  # 비동기 환경에서는 별도 처리 필요
        )

        return AnalyzeResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/patterns/{category}")
async def get_patterns(
    category: str,
    db: AsyncSession = Depends(get_db)
):
    """
    카테고리별 축적된 패턴 조회
    """
    result = await db.execute(
        select(AggregatedPattern).where(AggregatedPattern.category == category)
    )
    patterns = result.scalar_one_or_none()

    if not patterns:
        return {
            "category": category,
            "sample_count": 0,
            "message": "해당 카테고리의 분석 데이터가 없습니다"
        }

    return {
        "category": category,
        "category_name": CATEGORIES.get(category, {}).get("name", "일반"),
        "sample_count": patterns.sample_count,
        "patterns": {
            "title": {
                "avg_length": round(patterns.avg_title_length),
                "keyword_rate": round(patterns.title_keyword_rate * 100, 1),
                "keyword_position": {
                    "front": round(patterns.keyword_position_front * 100, 1),
                    "middle": round(patterns.keyword_position_middle * 100, 1),
                    "end": round(patterns.keyword_position_end * 100, 1)
                }
            },
            "content": {
                "avg_length": round(patterns.avg_content_length),
                "min_length": patterns.min_content_length,
                "max_length": patterns.max_content_length,
                "avg_headings": round(patterns.avg_heading_count, 1),
                "avg_keyword_count": round(patterns.avg_keyword_count, 1),
                "avg_keyword_density": round(patterns.avg_keyword_density, 2)
            },
            "media": {
                "avg_images": round(patterns.avg_image_count, 1),
                "min_images": patterns.min_image_count,
                "max_images": patterns.max_image_count,
                "video_usage_rate": round(patterns.video_usage_rate * 100, 1)
            },
            "extras": {
                "map_usage_rate": round(patterns.map_usage_rate * 100, 1)
            }
        },
        "updated_at": patterns.updated_at.isoformat() if patterns.updated_at else None
    }


@router.get("/writing-guide")
async def get_writing_guide(
    category: str = Query(default="general", description="카테고리"),
    keyword: Optional[str] = Query(default=None, description="키워드 (카테고리 자동 감지)"),
    db: AsyncSession = Depends(get_db)
):
    """
    글쓰기 가이드 조회

    - 축적된 데이터 기반으로 최적화된 글쓰기 규칙 반환
    - 데이터 부족 시 기본값 반환
    """
    # 키워드가 있으면 카테고리 자동 감지
    if keyword:
        category = detect_category(keyword)

    # 패턴 조회
    result = await db.execute(
        select(AggregatedPattern).where(AggregatedPattern.category == category)
    )
    patterns = result.scalar_one_or_none()

    # 기본 규칙
    DEFAULT_RULES = {
        "title": {
            "length": {"optimal": 30, "min": 20, "max": 45},
            "keyword_placement": {
                "include_keyword": True,
                "rate": 80,
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

    if not patterns or patterns.sample_count < 3:
        return {
            "status": "insufficient_data",
            "confidence": 0,
            "sample_count": patterns.sample_count if patterns else 0,
            "category": category,
            "category_name": CATEGORIES.get(category, {}).get("name", "일반"),
            "message": "분석 데이터가 부족합니다. '네이버 상위노출' 버튼을 클릭하여 데이터를 수집하세요.",
            "rules": DEFAULT_RULES
        }

    sample_count = patterns.sample_count
    confidence = min(1.0, sample_count / 30)

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
                "quote": {"usage_rate": 30, "recommended": True},
                "list": {"usage_rate": 40, "recommended": True}
            }
        }
    }


@router.get("/writing-guide/prompt")
async def get_writing_guide_prompt(
    category: str = Query(default="general", description="카테고리"),
    keyword: Optional[str] = Query(default=None, description="키워드"),
    db: AsyncSession = Depends(get_db)
):
    """
    AI 프롬프트용 글쓰기 가이드 텍스트 반환

    - 블로그 생성 시 AI 프롬프트에 포함할 최적화 규칙 텍스트
    """
    # 가이드 조회
    guide = await get_writing_guide(category=category, keyword=keyword, db=db)

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

이 규칙을 따라 글을 작성해주세요."""

    return {
        "category": category,
        "category_name": guide.get("category_name", "일반"),
        "sample_count": guide.get("sample_count", 0),
        "confidence": guide.get("confidence", 0),
        "prompt": prompt
    }


@router.get("/stats")
async def get_analysis_stats(db: AsyncSession = Depends(get_db)):
    """
    전체 분석 통계 조회
    """
    # 전체 분석 수
    total_result = await db.execute(
        select(func.count(TopPostAnalysis.id))
    )
    total_count = total_result.scalar() or 0

    # 카테고리별 분석 수
    category_stats = {}
    for cat_id in CATEGORIES.keys():
        cat_result = await db.execute(
            select(func.count(TopPostAnalysis.id)).where(
                TopPostAnalysis.category == cat_id
            )
        )
        count = cat_result.scalar() or 0
        if count > 0:
            category_stats[cat_id] = {
                "name": CATEGORIES[cat_id]["name"],
                "count": count
            }

    # 최근 분석 (최근 10개)
    recent_result = await db.execute(
        select(TopPostAnalysis)
        .order_by(TopPostAnalysis.analyzed_at.desc())
        .limit(10)
    )
    recent_analyses = recent_result.scalars().all()

    recent_list = []
    for analysis in recent_analyses:
        recent_list.append({
            "keyword": analysis.keyword,
            "rank": analysis.rank,
            "title": analysis.title[:50] + "..." if analysis.title and len(analysis.title) > 50 else analysis.title,
            "category": analysis.category,
            "analyzed_at": analysis.analyzed_at.isoformat() if analysis.analyzed_at else None
        })

    return {
        "total_analyses": total_count,
        "category_breakdown": category_stats,
        "recent_analyses": recent_list
    }


@router.get("/categories")
async def get_categories():
    """
    사용 가능한 카테고리 목록 조회
    """
    return {
        "categories": [
            {"id": cat_id, "name": cat_info["name"], "keywords": cat_info["keywords"][:5]}
            for cat_id, cat_info in CATEGORIES.items()
        ]
    }


# ============================================================
# 대량 분석 API 엔드포인트
# ============================================================

class BulkAnalyzeRequest(BaseModel):
    """대량 분석 요청 스키마"""
    category: str
    target_count: int = 100  # 100, 500, 1000
    keywords: Optional[List[str]] = None


class BulkAnalyzeResponse(BaseModel):
    """대량 분석 응답 스키마"""
    job_id: str
    category: str
    target_count: int
    status: str
    message: str


@router.post("/bulk-analyze", response_model=BulkAnalyzeResponse)
async def start_bulk_analysis(
    request: BulkAnalyzeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    대량 분석 작업 시작

    - 카테고리와 목표 분석 수를 지정하여 대량 분석 시작
    - 백그라운드에서 키워드 수집 및 상위글 분석 실행
    - 작업 ID를 반환하여 진행 상황 조회 가능
    """
    # 유효한 카테고리인지 확인
    if request.category not in CATEGORY_SEEDS:
        raise HTTPException(status_code=400, detail=f"Invalid category: {request.category}")

    # 목표 수 검증
    if request.target_count not in [100, 500, 1000]:
        raise HTTPException(status_code=400, detail="target_count must be 100, 500, or 1000")

    try:
        # 동기 세션 생성 (SQLite는 동기 작업 필요)
        from app.db.database import SessionLocal
        sync_db = SessionLocal()

        try:
            # 작업 생성
            service = BulkAnalysisService(sync_db)
            job = service.create_job(
                category=request.category,
                target_count=request.target_count,
                keywords=request.keywords
            )

            # 백그라운드 작업 시작
            background_tasks.add_task(
                run_bulk_analysis_wrapper,
                job.id,
                request.category,
                request.target_count
            )

            return BulkAnalyzeResponse(
                job_id=job.id,
                category=request.category,
                target_count=request.target_count,
                status="pending",
                message=f"분석 작업이 시작되었습니다. 작업 ID: {job.id}"
            )
        finally:
            sync_db.close()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def run_bulk_analysis_wrapper(job_id: str, category: str, target_count: int):
    """백그라운드 분석 실행 래퍼"""
    from app.db.database import SessionLocal
    db = SessionLocal()
    try:
        await run_bulk_analysis(db, job_id, category, target_count)
    finally:
        db.close()


@router.get("/jobs")
async def get_analysis_jobs(
    category: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    분석 작업 목록 조회
    """
    query = select(AnalysisJob)

    if category:
        query = query.where(AnalysisJob.category == category)
    if status:
        query = query.where(AnalysisJob.status == status)

    query = query.order_by(AnalysisJob.created_at.desc()).limit(limit)

    result = await db.execute(query)
    jobs = result.scalars().all()

    return {
        "jobs": [
            {
                "id": job.id,
                "category": job.category,
                "category_name": CATEGORY_SEEDS.get(job.category, {}).get("name", "알 수 없음"),
                "target_count": job.target_count,
                "status": job.status,
                "progress": job.progress,
                "keywords_collected": job.keywords_collected,
                "posts_analyzed": job.posts_analyzed,
                "error_message": job.error_message,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None
            }
            for job in jobs
        ]
    }


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    분석 작업 상태 조회
    """
    result = await db.execute(
        select(AnalysisJob).where(AnalysisJob.id == job_id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "id": job.id,
        "category": job.category,
        "category_name": CATEGORY_SEEDS.get(job.category, {}).get("name", "알 수 없음"),
        "target_count": job.target_count,
        "status": job.status,
        "progress": job.progress,
        "keywords_collected": job.keywords_collected,
        "keywords_total": job.keywords_total,
        "posts_analyzed": job.posts_analyzed,
        "posts_failed": job.posts_failed,
        "keywords": job.keywords[:20] if job.keywords else [],  # 최대 20개만 반환
        "error_message": job.error_message,
        "result_summary": job.result_summary,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None
    }


@router.delete("/jobs/{job_id}")
async def cancel_job(
    job_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    분석 작업 취소
    """
    result = await db.execute(
        select(AnalysisJob).where(AnalysisJob.id == job_id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in ['pending', 'running']:
        raise HTTPException(status_code=400, detail="Cannot cancel completed or failed job")

    job.status = 'cancelled'
    await db.commit()

    return {"message": "Job cancelled successfully", "job_id": job_id}


@router.post("/collect-keywords")
async def collect_keywords(
    category: str = Query(..., description="카테고리 ID"),
    max_keywords: int = Query(default=100, le=500, description="최대 수집 키워드 수")
):
    """
    연관검색어 수집

    - 카테고리의 시드 키워드에서 연관검색어를 수집
    - 수집된 키워드 목록 반환
    """
    if category not in CATEGORY_SEEDS:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")

    try:
        result = await collect_keywords_for_category(category, max_keywords)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/keywords/{category}")
async def get_category_keywords(
    category: str,
    limit: int = Query(default=100, le=500),
    only_unanalyzed: bool = Query(default=False),
    db: AsyncSession = Depends(get_db)
):
    """
    카테고리별 수집된 키워드 조회
    """
    if category not in CATEGORY_SEEDS:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")

    query = select(CollectedKeyword).where(CollectedKeyword.category == category)

    if only_unanalyzed:
        query = query.where(CollectedKeyword.is_analyzed == 0)

    query = query.order_by(CollectedKeyword.created_at.desc()).limit(limit)

    result = await db.execute(query)
    keywords = result.scalars().all()

    return {
        "category": category,
        "category_name": CATEGORY_SEEDS[category]["name"],
        "total": len(keywords),
        "keywords": [
            {
                "keyword": kw.keyword,
                "source": kw.source,
                "is_analyzed": kw.is_analyzed == 1,
                "analysis_count": kw.analysis_count,
                "created_at": kw.created_at.isoformat() if kw.created_at else None
            }
            for kw in keywords
        ]
    }


@router.get("/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    """
    분석 대시보드 통계

    - 전체 분석 현황
    - 카테고리별 통계
    - 최근 작업 목록
    """
    # 전체 분석 수
    total_result = await db.execute(select(func.count(TopPostAnalysis.id)))
    total_posts = total_result.scalar() or 0

    # 전체 키워드 수
    keywords_result = await db.execute(select(func.count(CollectedKeyword.id)))
    total_keywords = keywords_result.scalar() or 0

    # 카테고리별 통계
    categories = []
    for cat_id, cat_info in CATEGORY_SEEDS.items():
        # 분석된 글 수
        posts_result = await db.execute(
            select(func.count(TopPostAnalysis.id)).where(TopPostAnalysis.category == cat_id)
        )
        posts_count = posts_result.scalar() or 0

        # 키워드 수
        kw_result = await db.execute(
            select(func.count(CollectedKeyword.id)).where(CollectedKeyword.category == cat_id)
        )
        kw_count = kw_result.scalar() or 0

        # 패턴 조회
        pattern_result = await db.execute(
            select(AggregatedPattern).where(AggregatedPattern.category == cat_id)
        )
        pattern = pattern_result.scalar_one_or_none()

        categories.append({
            "category": cat_id,
            "category_name": cat_info["name"],
            "posts_count": posts_count,
            "keywords_count": kw_count,
            "sample_count": pattern.sample_count if pattern else 0,
            "confidence": round(min(1.0, (pattern.sample_count / 30)) if pattern else 0, 2),
            "last_updated": pattern.updated_at.isoformat() if pattern and pattern.updated_at else None
        })

    # 샘플 수 기준 정렬
    categories.sort(key=lambda x: x["sample_count"], reverse=True)

    # 최근 작업
    jobs_result = await db.execute(
        select(AnalysisJob).order_by(AnalysisJob.created_at.desc()).limit(10)
    )
    jobs = jobs_result.scalars().all()

    return {
        "total_posts": total_posts,
        "total_keywords": total_keywords,
        "categories": categories,
        "recent_jobs": [
            {
                "id": job.id,
                "category": job.category,
                "category_name": CATEGORY_SEEDS.get(job.category, {}).get("name", "알 수 없음"),
                "target_count": job.target_count,
                "status": job.status,
                "progress": job.progress,
                "posts_analyzed": job.posts_analyzed,
                "created_at": job.created_at.isoformat() if job.created_at else None
            }
            for job in jobs
        ]
    }


@router.get("/rules/{category}")
async def get_rules(
    category: str,
    db: AsyncSession = Depends(get_db)
):
    """
    카테고리별 분석된 규칙 조회

    - 해당 카테고리의 상위글 패턴 기반 최적화 규칙 반환
    - 글 생성 시 자동으로 적용됨
    """
    if category not in CATEGORY_SEEDS:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")

    # 패턴 조회
    result = await db.execute(
        select(AggregatedPattern).where(AggregatedPattern.category == category)
    )
    pattern = result.scalar_one_or_none()

    if not pattern or pattern.sample_count < 3:
        return {
            "status": "insufficient_data",
            "category": category,
            "category_name": CATEGORY_SEEDS[category]["name"],
            "sample_count": pattern.sample_count if pattern else 0,
            "message": "분석 데이터가 부족합니다. 대량 분석을 실행해주세요.",
            "rules": None
        }

    confidence = min(1.0, pattern.sample_count / 30)

    # 최적 키워드 위치 결정
    positions = {
        "front": pattern.keyword_position_front,
        "middle": pattern.keyword_position_middle,
        "end": pattern.keyword_position_end
    }
    best_position = max(positions, key=positions.get)

    return {
        "status": "data_driven",
        "category": category,
        "category_name": CATEGORY_SEEDS[category]["name"],
        "sample_count": pattern.sample_count,
        "confidence": round(confidence, 2),
        "rules": {
            "title": {
                "length": {
                    "optimal": round(pattern.avg_title_length),
                    "min": max(15, round(pattern.avg_title_length * 0.7)),
                    "max": min(60, round(pattern.avg_title_length * 1.3))
                },
                "keyword_placement": {
                    "include_keyword": pattern.title_keyword_rate > 0.5,
                    "rate": round(pattern.title_keyword_rate * 100, 1),
                    "best_position": best_position,
                    "position_distribution": {
                        "front": round(pattern.keyword_position_front * 100, 1),
                        "middle": round(pattern.keyword_position_middle * 100, 1),
                        "end": round(pattern.keyword_position_end * 100, 1)
                    }
                }
            },
            "content": {
                "length": {
                    "optimal": round(pattern.avg_content_length),
                    "min": max(500, round(pattern.avg_content_length * 0.7)),
                    "max": round(pattern.avg_content_length * 1.3)
                },
                "structure": {
                    "heading_count": {
                        "optimal": round(pattern.avg_heading_count),
                        "min": max(2, round(pattern.avg_heading_count * 0.6)),
                        "max": round(pattern.avg_heading_count * 1.5)
                    },
                    "keyword_density": {
                        "optimal": round(pattern.avg_keyword_density, 2),
                        "min": max(0.3, round(pattern.avg_keyword_density * 0.5, 2)),
                        "max": min(3.0, round(pattern.avg_keyword_density * 1.5, 2))
                    },
                    "keyword_count": {
                        "optimal": round(pattern.avg_keyword_count),
                        "min": max(3, round(pattern.avg_keyword_count * 0.6)),
                        "max": round(pattern.avg_keyword_count * 1.4)
                    }
                }
            },
            "media": {
                "images": {
                    "optimal": round(pattern.avg_image_count),
                    "min": max(3, pattern.min_image_count),
                    "max": pattern.max_image_count
                },
                "videos": {
                    "usage_rate": round(pattern.video_usage_rate * 100, 1),
                    "recommended": pattern.video_usage_rate > 0.3
                }
            }
        }
    }


@router.get("/analyzed-posts")
async def get_analyzed_posts(
    category: Optional[str] = Query(default=None, description="카테고리 필터"),
    keyword: Optional[str] = Query(default=None, description="키워드 검색"),
    limit: int = Query(default=50, le=200, description="조회 개수"),
    offset: int = Query(default=0, description="오프셋"),
    db: AsyncSession = Depends(get_db)
):
    """
    분석된 글 목록 조회

    - 최근 분석된 상위글 목록과 상세 정보 반환
    - 카테고리, 키워드로 필터링 가능
    """
    query = select(TopPostAnalysis)

    if category:
        query = query.where(TopPostAnalysis.category == category)
    if keyword:
        query = query.where(TopPostAnalysis.keyword.contains(keyword))

    # 전체 개수
    count_query = select(func.count(TopPostAnalysis.id))
    if category:
        count_query = count_query.where(TopPostAnalysis.category == category)
    if keyword:
        count_query = count_query.where(TopPostAnalysis.keyword.contains(keyword))

    total_result = await db.execute(count_query)
    total_count = total_result.scalar() or 0

    # 목록 조회
    query = query.order_by(TopPostAnalysis.analyzed_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    posts = result.scalars().all()

    # 키워드별 그룹화 통계
    keyword_stats = {}
    for post in posts:
        kw = post.keyword
        if kw not in keyword_stats:
            keyword_stats[kw] = {
                "keyword": kw,
                "category": post.category,
                "posts_count": 0,
                "avg_content_length": 0,
                "avg_image_count": 0,
                "keyword_in_title_rate": 0,
                "posts": []
            }
        keyword_stats[kw]["posts_count"] += 1
        keyword_stats[kw]["avg_content_length"] += post.content_length
        keyword_stats[kw]["avg_image_count"] += post.image_count
        if post.title_has_keyword:
            keyword_stats[kw]["keyword_in_title_rate"] += 1
        keyword_stats[kw]["posts"].append({
            "id": post.id,
            "rank": post.rank,
            "title": post.title,
            "post_url": post.post_url,
            "content_length": post.content_length,
            "image_count": post.image_count,
            "video_count": post.video_count,
            "heading_count": post.heading_count,
            "keyword_count": post.keyword_count,
            "keyword_density": post.keyword_density,
            "has_map": post.has_map,
            "data_quality": post.data_quality,
            "analyzed_at": post.analyzed_at.isoformat() if post.analyzed_at else None
        })

    # 평균 계산
    for kw, stats in keyword_stats.items():
        n = stats["posts_count"]
        if n > 0:
            stats["avg_content_length"] = round(stats["avg_content_length"] / n)
            stats["avg_image_count"] = round(stats["avg_image_count"] / n, 1)
            stats["keyword_in_title_rate"] = round(stats["keyword_in_title_rate"] / n * 100, 1)

    return {
        "total_count": total_count,
        "returned_count": len(posts),
        "offset": offset,
        "limit": limit,
        "by_keyword": list(keyword_stats.values()),
        "posts": [
            {
                "id": post.id,
                "keyword": post.keyword,
                "rank": post.rank,
                "title": post.title,
                "post_url": post.post_url,
                "blog_id": post.blog_id,
                "category": post.category,
                "category_name": CATEGORY_SEEDS.get(post.category, {}).get("name", "일반"),
                "content_length": post.content_length,
                "image_count": post.image_count,
                "video_count": post.video_count,
                "heading_count": post.heading_count,
                "keyword_count": post.keyword_count,
                "keyword_density": round(post.keyword_density, 2),
                "title_has_keyword": post.title_has_keyword,
                "title_keyword_position": post.title_keyword_position,
                "has_map": post.has_map,
                "has_quote": post.has_quote,
                "has_list": post.has_list,
                "data_quality": post.data_quality,
                "analyzed_at": post.analyzed_at.isoformat() if post.analyzed_at else None
            }
            for post in posts
        ]
    }


@router.get("/patterns-summary/{category}")
async def get_patterns_summary(
    category: str,
    db: AsyncSession = Depends(get_db)
):
    """
    카테고리별 발견된 공통점 요약

    - 상위글들의 공통 패턴을 자연어로 요약
    - 데이터 기반 인사이트 제공
    """
    if category not in CATEGORY_SEEDS:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")

    # 패턴 조회
    result = await db.execute(
        select(AggregatedPattern).where(AggregatedPattern.category == category)
    )
    pattern = result.scalar_one_or_none()

    if not pattern or pattern.sample_count < 3:
        return {
            "status": "insufficient_data",
            "category": category,
            "category_name": CATEGORY_SEEDS[category]["name"],
            "sample_count": pattern.sample_count if pattern else 0,
            "summary": None,
            "insights": []
        }

    # 최적 위치 결정
    positions = {
        "앞부분": pattern.keyword_position_front,
        "중간": pattern.keyword_position_middle,
        "뒷부분": pattern.keyword_position_end
    }
    best_position = max(positions, key=positions.get)

    # 인사이트 생성
    insights = []

    # 제목 길이 인사이트
    insights.append({
        "category": "제목",
        "finding": f"평균 {round(pattern.avg_title_length)}자",
        "recommendation": f"제목은 {max(15, round(pattern.avg_title_length * 0.7))}~{min(60, round(pattern.avg_title_length * 1.3))}자가 적당합니다",
        "confidence": min(1.0, pattern.sample_count / 30)
    })

    # 키워드 위치 인사이트
    if pattern.title_keyword_rate > 0.5:
        insights.append({
            "category": "제목",
            "finding": f"상위글의 {round(pattern.title_keyword_rate * 100)}%가 제목에 키워드 포함",
            "recommendation": f"키워드를 제목의 {best_position}에 배치하세요",
            "confidence": min(1.0, pattern.sample_count / 30)
        })

    # 본문 길이 인사이트
    insights.append({
        "category": "본문",
        "finding": f"평균 {round(pattern.avg_content_length)}자 ({round(pattern.avg_content_length / 500)}분 분량)",
        "recommendation": f"본문은 {max(500, round(pattern.avg_content_length * 0.7))}~{round(pattern.avg_content_length * 1.3)}자가 적당합니다",
        "confidence": min(1.0, pattern.sample_count / 30)
    })

    # 소제목 인사이트
    if pattern.avg_heading_count > 0:
        insights.append({
            "category": "구조",
            "finding": f"평균 {round(pattern.avg_heading_count)}개의 소제목 사용",
            "recommendation": f"소제목을 {max(2, round(pattern.avg_heading_count * 0.6))}~{round(pattern.avg_heading_count * 1.5)}개 사용하세요",
            "confidence": min(1.0, pattern.sample_count / 30)
        })

    # 이미지 인사이트
    insights.append({
        "category": "이미지",
        "finding": f"평균 {round(pattern.avg_image_count)}장 사용",
        "recommendation": f"이미지를 {max(3, pattern.min_image_count)}~{pattern.max_image_count}장 삽입하세요",
        "confidence": min(1.0, pattern.sample_count / 30)
    })

    # 키워드 밀도 인사이트
    insights.append({
        "category": "키워드",
        "finding": f"1000자당 평균 {round(pattern.avg_keyword_density, 1)}회 등장",
        "recommendation": f"키워드를 본문에 {round(pattern.avg_keyword_count)}회 정도 자연스럽게 포함하세요",
        "confidence": min(1.0, pattern.sample_count / 30)
    })

    # 지도 인사이트
    if pattern.map_usage_rate > 0.2:
        insights.append({
            "category": "부가요소",
            "finding": f"상위글의 {round(pattern.map_usage_rate * 100)}%가 지도 사용",
            "recommendation": "위치 정보가 있다면 네이버 지도를 삽입하세요",
            "confidence": min(1.0, pattern.sample_count / 30)
        })

    # 동영상 인사이트
    if pattern.video_usage_rate > 0.1:
        insights.append({
            "category": "부가요소",
            "finding": f"상위글의 {round(pattern.video_usage_rate * 100)}%가 동영상 사용",
            "recommendation": "관련 동영상이 있다면 삽입을 고려하세요",
            "confidence": min(1.0, pattern.sample_count / 30)
        })

    # 요약 텍스트 생성
    summary = f"""【{CATEGORY_SEEDS[category]['name']} 카테고리 상위글 분석 결과】
분석 샘플: {pattern.sample_count}개 글

📝 제목: 평균 {round(pattern.avg_title_length)}자, 키워드는 {best_position}에 배치
📄 본문: 평균 {round(pattern.avg_content_length)}자
🖼️ 이미지: 평균 {round(pattern.avg_image_count)}장
📑 소제목: 평균 {round(pattern.avg_heading_count)}개
🔑 키워드: 본문에 평균 {round(pattern.avg_keyword_count)}회 등장

이 패턴을 따르면 상위노출 확률이 높아집니다."""

    return {
        "status": "data_driven",
        "category": category,
        "category_name": CATEGORY_SEEDS[category]["name"],
        "sample_count": pattern.sample_count,
        "confidence": round(min(1.0, pattern.sample_count / 30), 2),
        "summary": summary,
        "insights": insights,
        "raw_patterns": {
            "title": {
                "avg_length": round(pattern.avg_title_length),
                "keyword_rate": round(pattern.title_keyword_rate * 100, 1),
                "best_position": best_position
            },
            "content": {
                "avg_length": round(pattern.avg_content_length),
                "avg_headings": round(pattern.avg_heading_count, 1),
                "avg_keyword_count": round(pattern.avg_keyword_count, 1),
                "avg_keyword_density": round(pattern.avg_keyword_density, 2)
            },
            "media": {
                "avg_images": round(pattern.avg_image_count, 1),
                "video_rate": round(pattern.video_usage_rate * 100, 1),
                "map_rate": round(pattern.map_usage_rate * 100, 1)
            }
        },
        "updated_at": pattern.updated_at.isoformat() if pattern.updated_at else None
    }


@router.get("/categories-with-stats")
async def get_categories_with_stats(db: AsyncSession = Depends(get_db)):
    """
    카테고리 목록 및 통계 조회
    """
    categories = []

    for cat_id, cat_info in CATEGORY_SEEDS.items():
        # 분석된 글 수
        posts_result = await db.execute(
            select(func.count(TopPostAnalysis.id)).where(TopPostAnalysis.category == cat_id)
        )
        posts_count = posts_result.scalar() or 0

        # 패턴 조회
        pattern_result = await db.execute(
            select(AggregatedPattern).where(AggregatedPattern.category == cat_id)
        )
        pattern = pattern_result.scalar_one_or_none()

        categories.append({
            "id": cat_id,
            "name": cat_info["name"],
            "seeds": cat_info["seeds"][:5],
            "posts_count": posts_count,
            "sample_count": pattern.sample_count if pattern else 0,
            "confidence": round(min(1.0, (pattern.sample_count / 30)) if pattern else 0, 2),
            "has_rules": pattern is not None and pattern.sample_count >= 3
        })

    return {"categories": categories}
