"""
리드 스코어링 서비스
블로그의 영향력, 활동성, 관련성을 분석하여 리드 점수 계산
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.blog_outreach import (
    NaverBlog, BlogContact, LeadGrade, BlogCategory,
    OutreachSetting, BlogStatus
)

logger = logging.getLogger(__name__)


class LeadScoringService:
    """리드 스코어링 서비스"""

    # 기본 가중치
    DEFAULT_WEIGHTS = {
        "influence": 0.4,   # 영향력 (방문자, 이웃)
        "activity": 0.3,    # 활동성 (최근 포스팅)
        "relevance": 0.3    # 관련성 (카테고리, 키워드)
    }

    # 영향력 점수 기준
    INFLUENCE_TIERS = {
        "visitor_daily": [
            (10000, 100),   # 일일 1만 이상: 100점
            (5000, 80),     # 5천 이상: 80점
            (1000, 60),     # 1천 이상: 60점
            (500, 40),      # 500 이상: 40점
            (100, 20),      # 100 이상: 20점
            (0, 10)         # 그 외: 10점
        ],
        "neighbor_count": [
            (10000, 100),   # 이웃 1만 이상: 100점
            (5000, 80),
            (1000, 60),
            (500, 40),
            (100, 20),
            (0, 10)
        ]
    }

    # 활동성 점수 기준 (최근 포스팅 날짜)
    ACTIVITY_TIERS = [
        (1, 100),       # 1일 이내: 100점
        (3, 90),        # 3일 이내: 90점
        (7, 80),        # 1주 이내: 80점
        (14, 60),       # 2주 이내: 60점
        (30, 40),       # 1달 이내: 40점
        (90, 20),       # 3달 이내: 20점
        (float('inf'), 5)  # 그 외: 5점
    ]

    # 등급 기준
    GRADE_THRESHOLDS = {
        "A": 80,    # 80점 이상
        "B": 60,    # 60-79점
        "C": 40,    # 40-59점
        "D": 0      # 40점 미만
    }

    # 카테고리별 기본 관련성 점수
    CATEGORY_RELEVANCE = {
        BlogCategory.HEALTH: 100,       # 건강/의료 - 최우선
        BlogCategory.PARENTING: 80,     # 육아 - 높음
        BlogCategory.BEAUTY: 70,        # 뷰티 - 보통
        BlogCategory.LIFESTYLE: 60,     # 라이프스타일 - 보통
        BlogCategory.FOOD: 50,          # 맛집 - 관련있음
        BlogCategory.LIVING: 40,        # 리빙 - 관련있음
        BlogCategory.TRAVEL: 30,        # 여행 - 관련있음
        BlogCategory.IT: 20,            # IT - 낮음
        BlogCategory.FINANCE: 20,       # 금융 - 낮음
        BlogCategory.OTHER: 30          # 기타
    }

    def __init__(self, db: Session):
        self.db = db

    def _get_user_weights(self, user_id: str) -> Dict[str, float]:
        """사용자 설정 가중치 가져오기"""
        settings = self.db.query(OutreachSetting).filter(
            OutreachSetting.user_id == user_id
        ).first()

        if settings:
            return {
                "influence": settings.weight_influence or self.DEFAULT_WEIGHTS["influence"],
                "activity": settings.weight_activity or self.DEFAULT_WEIGHTS["activity"],
                "relevance": settings.weight_relevance or self.DEFAULT_WEIGHTS["relevance"]
            }
        return self.DEFAULT_WEIGHTS.copy()

    def _calculate_influence_score(self, blog: NaverBlog) -> float:
        """영향력 점수 계산"""
        visitor_score = 0
        neighbor_score = 0

        # 일일 방문자 점수
        daily_visitors = blog.visitor_daily or 0
        for threshold, score in self.INFLUENCE_TIERS["visitor_daily"]:
            if daily_visitors >= threshold:
                visitor_score = score
                break

        # 이웃 수 점수
        neighbors = blog.neighbor_count or 0
        for threshold, score in self.INFLUENCE_TIERS["neighbor_count"]:
            if neighbors >= threshold:
                neighbor_score = score
                break

        # 인플루언서 보너스
        influencer_bonus = 20 if blog.is_influencer else 0

        # 평균 + 보너스
        base_score = (visitor_score + neighbor_score) / 2
        return min(100, base_score + influencer_bonus)

    def _calculate_activity_score(self, blog: NaverBlog) -> float:
        """활동성 점수 계산"""
        if not blog.last_post_date:
            return 10  # 정보 없음

        days_since_post = (datetime.utcnow() - blog.last_post_date).days

        for days, score in self.ACTIVITY_TIERS:
            if days_since_post <= days:
                return score

        return 5  # 기본값

    def _calculate_relevance_score(
        self,
        blog: NaverBlog,
        target_categories: Optional[List[BlogCategory]] = None,
        target_keywords: Optional[List[str]] = None
    ) -> float:
        """관련성 점수 계산"""
        # 카테고리 점수
        category_score = self.CATEGORY_RELEVANCE.get(blog.category, 30)

        # 타겟 카테고리가 지정된 경우
        if target_categories:
            if blog.category in target_categories:
                category_score = 100  # 타겟 카테고리면 최고점
            else:
                category_score = category_score * 0.5  # 타겟이 아니면 감점

        # 키워드 매칭 점수
        keyword_score = 0
        if target_keywords and blog.keywords:
            blog_keywords = blog.keywords if isinstance(blog.keywords, list) else []
            matched_keywords = set(target_keywords) & set(blog_keywords)
            if matched_keywords:
                # 매칭 비율에 따른 점수
                match_ratio = len(matched_keywords) / len(target_keywords)
                keyword_score = match_ratio * 100

        # 연락처 보유 보너스
        contact_bonus = 20 if blog.has_contact else 0

        # 가중 평균
        if target_keywords:
            relevance = (category_score * 0.6 + keyword_score * 0.4)
        else:
            relevance = category_score

        return min(100, relevance + contact_bonus)

    def calculate_lead_score(
        self,
        blog: NaverBlog,
        user_id: str,
        target_categories: Optional[List[BlogCategory]] = None,
        target_keywords: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """리드 점수 종합 계산"""
        # 가중치 가져오기
        weights = self._get_user_weights(user_id)

        # 개별 점수 계산
        influence_score = self._calculate_influence_score(blog)
        activity_score = self._calculate_activity_score(blog)
        relevance_score = self._calculate_relevance_score(
            blog, target_categories, target_keywords
        )

        # 종합 점수 계산
        total_score = (
            influence_score * weights["influence"] +
            activity_score * weights["activity"] +
            relevance_score * weights["relevance"]
        )

        # 등급 결정
        grade = LeadGrade.D
        for g, threshold in self.GRADE_THRESHOLDS.items():
            if total_score >= threshold:
                grade = LeadGrade(g)
                break

        return {
            "lead_score": round(total_score, 2),
            "lead_grade": grade,
            "influence_score": round(influence_score, 2),
            "activity_score": round(activity_score, 2),
            "relevance_score": round(relevance_score, 2),
            "weights": weights
        }

    async def score_blog(
        self,
        blog_id: str,
        user_id: str,
        target_categories: Optional[List[BlogCategory]] = None,
        target_keywords: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """블로그 스코어링 및 저장"""
        try:
            blog = self.db.query(NaverBlog).filter(
                NaverBlog.id == blog_id,
                NaverBlog.user_id == user_id
            ).first()

            if not blog:
                return {"success": False, "error": "블로그를 찾을 수 없습니다"}

            # 점수 계산
            scores = self.calculate_lead_score(
                blog, user_id, target_categories, target_keywords
            )

            # DB 업데이트
            blog.lead_score = scores["lead_score"]
            blog.lead_grade = scores["lead_grade"]
            blog.influence_score = scores["influence_score"]
            blog.activity_score = scores["activity_score"]
            blog.relevance_score = scores["relevance_score"]
            blog.updated_at = datetime.utcnow()

            self.db.commit()

            return {
                "success": True,
                "blog_id": blog_id,
                "scores": scores
            }

        except Exception as e:
            logger.error(f"블로그 스코어링 오류: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    async def score_blogs_batch(
        self,
        user_id: str,
        target_categories: Optional[List[BlogCategory]] = None,
        target_keywords: Optional[List[str]] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """배치 스코어링"""
        try:
            # 스코어링 필요한 블로그 조회
            blogs = self.db.query(NaverBlog).filter(
                NaverBlog.user_id == user_id,
                NaverBlog.lead_score == 0  # 아직 스코어링 안된 블로그
            ).limit(limit).all()

            results = {
                "total": len(blogs),
                "scored": 0,
                "grades": {"A": 0, "B": 0, "C": 0, "D": 0},
                "errors": []
            }

            for blog in blogs:
                try:
                    scores = self.calculate_lead_score(
                        blog, user_id, target_categories, target_keywords
                    )

                    blog.lead_score = scores["lead_score"]
                    blog.lead_grade = scores["lead_grade"]
                    blog.influence_score = scores["influence_score"]
                    blog.activity_score = scores["activity_score"]
                    blog.relevance_score = scores["relevance_score"]
                    blog.updated_at = datetime.utcnow()

                    results["scored"] += 1
                    results["grades"][scores["lead_grade"].value] += 1

                except Exception as e:
                    results["errors"].append({
                        "blog_id": blog.id,
                        "error": str(e)
                    })

            self.db.commit()

            return {
                "success": True,
                "results": results
            }

        except Exception as e:
            logger.error(f"배치 스코어링 오류: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    async def rescore_all(
        self,
        user_id: str,
        target_categories: Optional[List[BlogCategory]] = None,
        target_keywords: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """전체 재스코어링"""
        try:
            blogs = self.db.query(NaverBlog).filter(
                NaverBlog.user_id == user_id
            ).all()

            results = {
                "total": len(blogs),
                "scored": 0,
                "grades": {"A": 0, "B": 0, "C": 0, "D": 0}
            }

            for blog in blogs:
                scores = self.calculate_lead_score(
                    blog, user_id, target_categories, target_keywords
                )

                blog.lead_score = scores["lead_score"]
                blog.lead_grade = scores["lead_grade"]
                blog.influence_score = scores["influence_score"]
                blog.activity_score = scores["activity_score"]
                blog.relevance_score = scores["relevance_score"]
                blog.updated_at = datetime.utcnow()

                results["scored"] += 1
                results["grades"][scores["lead_grade"].value] += 1

            self.db.commit()

            return {
                "success": True,
                "results": results
            }

        except Exception as e:
            logger.error(f"재스코어링 오류: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    async def get_top_leads(
        self,
        user_id: str,
        grade: Optional[LeadGrade] = None,
        category: Optional[BlogCategory] = None,
        has_contact: Optional[bool] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """상위 리드 조회"""
        query = self.db.query(NaverBlog).filter(
            NaverBlog.user_id == user_id,
            NaverBlog.status.notin_([BlogStatus.INVALID, BlogStatus.NOT_INTERESTED])
        )

        if grade:
            query = query.filter(NaverBlog.lead_grade == grade)

        if category:
            query = query.filter(NaverBlog.category == category)

        if has_contact is not None:
            query = query.filter(NaverBlog.has_contact == has_contact)

        blogs = query.order_by(
            NaverBlog.lead_score.desc()
        ).limit(limit).all()

        results = []
        for blog in blogs:
            # 연락처 정보 조회
            contacts = self.db.query(BlogContact).filter(
                BlogContact.blog_id == blog.id
            ).all()

            results.append({
                "id": blog.id,
                "blog_id": blog.blog_id,
                "blog_url": blog.blog_url,
                "blog_name": blog.blog_name,
                "owner_nickname": blog.owner_nickname,
                "category": blog.category.value if blog.category else None,
                "lead_score": blog.lead_score,
                "lead_grade": blog.lead_grade.value if blog.lead_grade else None,
                "influence_score": blog.influence_score,
                "activity_score": blog.activity_score,
                "relevance_score": blog.relevance_score,
                "visitor_daily": blog.visitor_daily,
                "neighbor_count": blog.neighbor_count,
                "is_influencer": blog.is_influencer,
                "has_contact": blog.has_contact,
                "contacts": [
                    {
                        "email": c.email,
                        "instagram": c.instagram,
                        "phone": c.phone
                    } for c in contacts
                ],
                "status": blog.status.value if blog.status else None,
                "last_post_date": blog.last_post_date.isoformat() if blog.last_post_date else None
            })

        return results

    async def get_scoring_stats(self, user_id: str) -> Dict[str, Any]:
        """스코어링 통계"""
        from sqlalchemy import select

        # 비동기 쿼리로 수정
        stmt = select(NaverBlog).where(NaverBlog.user_id == user_id)
        result = await self.db.execute(stmt)
        blogs = result.scalars().all()

        stats = {
            "total_blogs": len(blogs),
            "scored_blogs": 0,
            "unscored_blogs": 0,
            "grades": {"A": 0, "B": 0, "C": 0, "D": 0},
            "with_contact": 0,
            "influencers": 0,
            "avg_lead_score": 0,
            "avg_influence_score": 0,
            "avg_activity_score": 0,
            "avg_relevance_score": 0,
            "categories": {}
        }

        total_lead = 0
        total_influence = 0
        total_activity = 0
        total_relevance = 0
        scored_count = 0

        for blog in blogs:
            if blog.lead_score and blog.lead_score > 0:
                stats["scored_blogs"] += 1
                scored_count += 1
                total_lead += blog.lead_score
                total_influence += blog.influence_score or 0
                total_activity += blog.activity_score or 0
                total_relevance += blog.relevance_score or 0

                if blog.lead_grade:
                    grade_val = blog.lead_grade.value if hasattr(blog.lead_grade, 'value') else blog.lead_grade
                    if grade_val in stats["grades"]:
                        stats["grades"][grade_val] += 1
            else:
                stats["unscored_blogs"] += 1

            if blog.has_contact:
                stats["with_contact"] += 1

            if blog.is_influencer:
                stats["influencers"] += 1

            # 카테고리별 통계
            cat = blog.category.value if blog.category and hasattr(blog.category, 'value') else (blog.category or "other")
            if cat not in stats["categories"]:
                stats["categories"][cat] = 0
            stats["categories"][cat] += 1

        if scored_count > 0:
            stats["avg_lead_score"] = round(total_lead / scored_count, 2)
            stats["avg_influence_score"] = round(total_influence / scored_count, 2)
            stats["avg_activity_score"] = round(total_activity / scored_count, 2)
            stats["avg_relevance_score"] = round(total_relevance / scored_count, 2)

        return stats
