"""
대량 분석 서비스
카테고리별 상위글을 대량으로 수집하고 분석하는 백그라운드 작업 관리
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Callable
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.models.analysis_job import AnalysisJob, CollectedKeyword
from app.models.top_post_analysis import TopPostAnalysis, AggregatedPattern
from app.services.keyword_collector import (
    collect_keywords_for_category,
    save_keywords_to_db,
    get_keywords_for_analysis,
    mark_keyword_analyzed,
    CATEGORY_SEEDS
)
from app.services.top_post_analyzer import (
    analyze_top_posts,
    update_aggregated_patterns,
    CATEGORIES
)


# 메모리 기반 작업 상태 저장소 (프로덕션에서는 Redis 사용 권장)
_running_jobs: Dict[str, AnalysisJob] = {}
_job_callbacks: Dict[str, Callable] = {}


class BulkAnalysisService:
    """대량 분석 서비스 클래스"""

    def __init__(self, db: Session):
        self.db = db

    def create_job(
        self,
        category: str,
        target_count: int,
        keywords: Optional[List[str]] = None
    ) -> AnalysisJob:
        """
        새 분석 작업 생성

        Args:
            category: 분석할 카테고리
            target_count: 목표 분석 글 수 (100, 500, 1000)
            keywords: 사전 수집된 키워드 목록 (없으면 자동 수집)

        Returns:
            생성된 AnalysisJob
        """
        job_id = str(uuid.uuid4())

        # 필요한 키워드 수 계산 (글 3개당 키워드 1개)
        keywords_needed = (target_count // 3) + 10  # 여유분 포함

        job = AnalysisJob(
            id=job_id,
            category=category,
            target_count=target_count,
            status='pending',
            progress=0,
            keywords_total=keywords_needed,
            keywords=keywords or []
        )

        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        return job

    def get_job(self, job_id: str) -> Optional[AnalysisJob]:
        """작업 조회"""
        return self.db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()

    def get_jobs(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20
    ) -> List[AnalysisJob]:
        """작업 목록 조회"""
        query = self.db.query(AnalysisJob)

        if category:
            query = query.filter(AnalysisJob.category == category)
        if status:
            query = query.filter(AnalysisJob.status == status)

        return query.order_by(AnalysisJob.created_at.desc()).limit(limit).all()

    def update_job_status(
        self,
        job_id: str,
        status: str,
        progress: int = None,
        posts_analyzed: int = None,
        keywords_collected: int = None,
        error_message: str = None
    ):
        """작업 상태 업데이트"""
        job = self.get_job(job_id)
        if not job:
            return

        job.status = status

        if progress is not None:
            job.progress = progress
        if posts_analyzed is not None:
            job.posts_analyzed = posts_analyzed
        if keywords_collected is not None:
            job.keywords_collected = keywords_collected
        if error_message is not None:
            job.error_message = error_message

        if status == 'running' and not job.started_at:
            job.started_at = datetime.utcnow()
        elif status in ['completed', 'failed', 'cancelled']:
            job.completed_at = datetime.utcnow()

        self.db.commit()

    def cancel_job(self, job_id: str) -> bool:
        """작업 취소"""
        job = self.get_job(job_id)
        if not job:
            return False

        if job.status in ['pending', 'running']:
            job.status = 'cancelled'
            job.completed_at = datetime.utcnow()
            self.db.commit()
            return True

        return False


def get_analyzed_keywords(db: Session, category: str) -> set:
    """
    이미 분석된 키워드 목록 조회
    """
    # CollectedKeyword에서 is_analyzed=1인 것들
    analyzed_from_collected = db.query(CollectedKeyword.keyword).filter(
        CollectedKeyword.category == category,
        CollectedKeyword.is_analyzed == 1
    ).all()

    # TopPostAnalysis에서 분석된 키워드들
    analyzed_from_posts = db.query(TopPostAnalysis.keyword).filter(
        TopPostAnalysis.category == category
    ).distinct().all()

    analyzed_set = set()
    for (kw,) in analyzed_from_collected:
        analyzed_set.add(kw)
    for (kw,) in analyzed_from_posts:
        analyzed_set.add(kw)

    return analyzed_set


async def run_bulk_analysis(
    db: Session,
    job_id: str,
    category: str,
    target_count: int,
    progress_callback: Optional[Callable] = None
):
    """
    대량 분석 실행 (백그라운드)

    Args:
        db: DB 세션
        job_id: 작업 ID
        category: 카테고리
        target_count: 목표 분석 수
        progress_callback: 진행 상황 콜백
    """
    service = BulkAnalysisService(db)

    try:
        # 1. 작업 시작
        service.update_job_status(job_id, 'running', progress=0)

        # 2. 이미 분석된 키워드 조회
        already_analyzed = get_analyzed_keywords(db, category)
        print(f"[대량분석] 이미 분석된 키워드: {len(already_analyzed)}개")

        # 3. 키워드 수집 (이미 분석된 것 고려하여 더 많이 수집)
        keywords_needed = (target_count // 3) + 10 + len(already_analyzed)
        print(f"[대량분석] 키워드 수집 시작: {keywords_needed}개 필요 (중복 제외 위해 추가 수집)")

        keyword_result = await collect_keywords_for_category(category, min(keywords_needed, 500))
        all_keywords = keyword_result.get('keywords', [])

        if not all_keywords:
            service.update_job_status(
                job_id, 'failed',
                error_message="키워드 수집 실패"
            )
            return

        # 4. 이미 분석된 키워드 제외
        new_keywords = [kw for kw in all_keywords if kw not in already_analyzed]
        skipped_count = len(all_keywords) - len(new_keywords)

        print(f"[대량분석] 수집된 키워드: {len(all_keywords)}개, 신규: {len(new_keywords)}개, 스킵: {skipped_count}개")

        if not new_keywords:
            service.update_job_status(
                job_id, 'completed',
                progress=100,
                posts_analyzed=0,
                error_message=f"모든 키워드가 이미 분석되었습니다 ({skipped_count}개 스킵)"
            )
            return

        keywords = new_keywords

        # 키워드 DB 저장
        save_keywords_to_db(db, category, keywords, source='bulk_analysis')

        service.update_job_status(
            job_id, 'running',
            progress=10,
            keywords_collected=len(keywords)
        )

        # 작업 객체에 키워드 저장
        job = service.get_job(job_id)
        if job:
            job.keywords = keywords
            job.keywords_collected = len(keywords)
            job.result_summary = {
                "skipped_keywords": skipped_count,
                "new_keywords": len(keywords)
            }
            db.commit()

        print(f"[대량분석] 신규 키워드 {len(keywords)}개 분석 시작")

        # 5. 상위글 분석
        posts_analyzed = 0
        posts_failed = 0

        for i, keyword in enumerate(keywords):
            # 작업 취소 확인
            job = service.get_job(job_id)
            if job and job.status == 'cancelled':
                print(f"[대량분석] 작업 취소됨: {job_id}")
                return

            # 목표 달성 확인
            if posts_analyzed >= target_count:
                break

            try:
                # 상위 3개 글 분석
                result = await analyze_top_posts(
                    keyword=keyword,
                    top_n=3,
                    db=None  # 비동기 환경에서는 별도 처리
                )

                analyzed_count = result.get('analyzed_count', 0)
                posts_analyzed += analyzed_count

                # 키워드 분석 완료 표시
                mark_keyword_analyzed(db, category, keyword, analyzed_count)

            except Exception as e:
                print(f"[대량분석] 키워드 분석 실패 ({keyword}): {e}")
                posts_failed += 1

            # 진행률 계산 (키워드 수집 10% + 분석 90%)
            analysis_progress = min(90, (posts_analyzed / target_count) * 90)
            total_progress = 10 + int(analysis_progress)

            service.update_job_status(
                job_id, 'running',
                progress=total_progress,
                posts_analyzed=posts_analyzed
            )

            # Rate limiting (네이버 차단 방지)
            await asyncio.sleep(1.0)

        # 4. 패턴 집계 업데이트
        try:
            update_aggregated_patterns(db, category)
        except Exception as e:
            print(f"[대량분석] 패턴 집계 오류: {e}")

        # 5. 작업 완료
        job = service.get_job(job_id)
        if job:
            job.posts_analyzed = posts_analyzed
            job.posts_failed = posts_failed
            job.result_summary = {
                "total_keywords": len(keywords),
                "posts_analyzed": posts_analyzed,
                "posts_failed": posts_failed,
                "category": category
            }
            db.commit()

        service.update_job_status(
            job_id, 'completed',
            progress=100,
            posts_analyzed=posts_analyzed
        )

        print(f"[대량분석] 완료: {posts_analyzed}개 글 분석")

    except Exception as e:
        print(f"[대량분석] 오류: {e}")
        service.update_job_status(
            job_id, 'failed',
            error_message=str(e)
        )


def get_analysis_dashboard(db: Session) -> Dict:
    """
    분석 대시보드 통계 조회
    """
    # 전체 분석 수
    total_posts = db.query(TopPostAnalysis).count()

    # 전체 키워드 수
    total_keywords = db.query(CollectedKeyword).count()

    # 카테고리별 통계
    categories = []
    for cat_id, cat_info in CATEGORIES.items():
        cat_posts = db.query(TopPostAnalysis).filter(
            TopPostAnalysis.category == cat_id
        ).count()

        cat_keywords = db.query(CollectedKeyword).filter(
            CollectedKeyword.category == cat_id
        ).count()

        # 패턴 조회
        pattern = db.query(AggregatedPattern).filter(
            AggregatedPattern.category == cat_id
        ).first()

        if cat_posts > 0 or cat_keywords > 0:
            categories.append({
                "category": cat_id,
                "category_name": cat_info["name"],
                "posts_count": cat_posts,
                "keywords_count": cat_keywords,
                "sample_count": pattern.sample_count if pattern else 0,
                "confidence": min(1.0, (pattern.sample_count / 30) if pattern else 0),
                "last_updated": pattern.updated_at.isoformat() if pattern and pattern.updated_at else None
            })

    # 정렬 (샘플 수 기준)
    categories.sort(key=lambda x: x["sample_count"], reverse=True)

    # 최근 작업
    recent_jobs = db.query(AnalysisJob).order_by(
        AnalysisJob.created_at.desc()
    ).limit(10).all()

    jobs_data = []
    for job in recent_jobs:
        jobs_data.append({
            "id": job.id,
            "category": job.category,
            "category_name": CATEGORIES.get(job.category, {}).get("name", "알 수 없음"),
            "target_count": job.target_count,
            "status": job.status,
            "progress": job.progress,
            "posts_analyzed": job.posts_analyzed,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None
        })

    return {
        "total_posts": total_posts,
        "total_keywords": total_keywords,
        "categories": categories,
        "recent_jobs": jobs_data
    }


def get_category_rules(db: Session, category: str) -> Optional[Dict]:
    """
    카테고리별 분석된 규칙 조회
    """
    pattern = db.query(AggregatedPattern).filter(
        AggregatedPattern.category == category
    ).first()

    if not pattern or pattern.sample_count < 3:
        return None

    confidence = min(1.0, pattern.sample_count / 30)

    # 최적 키워드 위치 결정
    positions = {
        "front": pattern.keyword_position_front,
        "middle": pattern.keyword_position_middle,
        "end": pattern.keyword_position_end
    }
    best_position = max(positions, key=positions.get)

    return {
        "category": category,
        "category_name": CATEGORIES.get(category, {}).get("name", "알 수 없음"),
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
