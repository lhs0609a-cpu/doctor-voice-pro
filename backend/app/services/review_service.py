"""
플레이스 리뷰 관리 서비스
"""

import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc, or_
from sqlalchemy.orm import selectinload
import uuid

from app.models.place_review import (
    PlaceReview, ReviewAlert, ReviewReplyTemplate, ReviewAnalytics, GeneratedReply,
    Sentiment
)
from app.models.naver_place import NaverPlace
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)


class ReviewService:
    """플레이스 리뷰 관리 서비스"""

    def __init__(self):
        self.ai_service = AIService()

    async def get_reviews(
        self,
        db: AsyncSession,
        place_db_id: str,
        sentiment: Optional[Sentiment] = None,
        is_replied: Optional[bool] = None,
        is_urgent: Optional[bool] = None,
        min_rating: Optional[int] = None,
        max_rating: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[PlaceReview]:
        """리뷰 목록 조회"""
        query = select(PlaceReview).where(PlaceReview.place_id == place_db_id)

        if sentiment:
            query = query.where(PlaceReview.sentiment == sentiment)
        if is_replied is not None:
            query = query.where(PlaceReview.is_replied == is_replied)
        if is_urgent is not None:
            query = query.where(PlaceReview.is_urgent == is_urgent)
        if min_rating:
            query = query.where(PlaceReview.rating >= min_rating)
        if max_rating:
            query = query.where(PlaceReview.rating <= max_rating)
        if start_date:
            query = query.where(PlaceReview.written_at >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.where(PlaceReview.written_at <= datetime.combine(end_date, datetime.max.time()))
        if search:
            query = query.where(
                or_(
                    PlaceReview.content.ilike(f"%{search}%"),
                    PlaceReview.author_name.ilike(f"%{search}%"),
                )
            )

        query = query.order_by(desc(PlaceReview.written_at)).offset(offset).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_review(
        self,
        db: AsyncSession,
        review_db_id: str,
    ) -> Optional[PlaceReview]:
        """리뷰 상세 조회"""
        query = select(PlaceReview).where(PlaceReview.id == review_db_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def create_review(
        self,
        db: AsyncSession,
        place_db_id: str,
        review_id: str,
        **kwargs,
    ) -> PlaceReview:
        """리뷰 생성 (동기화용)"""
        # 중복 체크
        query = select(PlaceReview).where(PlaceReview.review_id == review_id)
        result = await db.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            # 업데이트
            for key, value in kwargs.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            await db.commit()
            await db.refresh(existing)
            return existing

        review = PlaceReview(
            place_id=place_db_id,
            review_id=review_id,
            **kwargs,
        )

        # 감성 분석
        if review.content and not review.sentiment:
            sentiment, score = await self._analyze_sentiment(review.content)
            review.sentiment = sentiment
            review.sentiment_score = score

            # 부정 리뷰 긴급 플래그
            if sentiment == Sentiment.NEGATIVE and score < -0.5:
                review.is_urgent = True
                review.needs_attention = True

        db.add(review)
        await db.commit()
        await db.refresh(review)

        return review

    async def _analyze_sentiment(self, content: str) -> tuple:
        """감성 분석"""
        # 간단한 키워드 기반 감성 분석
        positive_keywords = ["좋", "만족", "친절", "깨끗", "추천", "감사", "최고", "훌륭", "편안", "전문"]
        negative_keywords = ["불친절", "비추", "실망", "불만", "최악", "나쁘", "아쉬", "후회", "답답", "오래"]

        positive_count = sum(1 for kw in positive_keywords if kw in content)
        negative_count = sum(1 for kw in negative_keywords if kw in content)

        if positive_count > negative_count + 1:
            score = min(0.5 + (positive_count * 0.1), 1.0)
            return Sentiment.POSITIVE, score
        elif negative_count > positive_count + 1:
            score = max(-0.5 - (negative_count * 0.1), -1.0)
            return Sentiment.NEGATIVE, score
        else:
            return Sentiment.NEUTRAL, 0.0

    async def reply_to_review(
        self,
        db: AsyncSession,
        review_db_id: str,
        reply_content: str,
        reply_by: Optional[str] = None,
    ) -> PlaceReview:
        """리뷰 답변 등록"""
        query = select(PlaceReview).where(PlaceReview.id == review_db_id)
        result = await db.execute(query)
        review = result.scalar_one_or_none()

        if not review:
            raise ValueError("Review not found")

        review.is_replied = True
        review.reply_content = reply_content
        review.replied_at = datetime.utcnow()
        review.reply_by = reply_by
        review.needs_attention = False

        await db.commit()
        await db.refresh(review)

        return review

    async def generate_reply(
        self,
        db: AsyncSession,
        review_db_id: str,
        user_id: str,
        tone: str = "professional",
    ) -> GeneratedReply:
        """AI 답변 생성"""
        query = select(PlaceReview).where(PlaceReview.id == review_db_id)
        result = await db.execute(query)
        review = result.scalar_one_or_none()

        if not review:
            raise ValueError("Review not found")

        # 플레이스 정보 조회
        place_query = select(NaverPlace).where(NaverPlace.id == review.place_id)
        place_result = await db.execute(place_query)
        place = place_result.scalar_one_or_none()

        # AI 답변 생성
        sentiment_guide = {
            Sentiment.POSITIVE: "감사의 마음을 전하고, 재방문을 유도",
            Sentiment.NEGATIVE: "진심으로 사과하고, 개선 의지를 표현",
            Sentiment.NEUTRAL: "피드백에 감사하고, 더 나은 서비스를 약속",
        }

        prompt = f"""
네이버 플레이스 리뷰에 대한 답변을 작성해주세요.

병원명: {place.place_name if place else '병원'}
리뷰 내용: {review.content}
리뷰 평점: {review.rating}점
감성: {review.sentiment.value if review.sentiment else 'neutral'}

답변 작성 지침:
- 톤: {'전문적이고 정중하게' if tone == 'professional' else '친근하고 따뜻하게' if tone == 'friendly' else '공감하며 진심으로'}
- 방향: {sentiment_guide.get(review.sentiment, sentiment_guide[Sentiment.NEUTRAL])}
- 길이: 2-4문장
- 고객 이름 호칭 사용 (고객님, 환자분 등)
- 병원명 포함

답변만 출력해주세요:
"""

        try:
            reply_text = await self.ai_service.generate_text(prompt)
        except Exception as e:
            logger.error(f"AI reply generation failed: {e}")
            if review.sentiment == Sentiment.POSITIVE:
                reply_text = f"소중한 후기 감사드립니다. 앞으로도 {place.place_name if place else '저희 병원'}은 최선의 진료로 보답하겠습니다."
            elif review.sentiment == Sentiment.NEGATIVE:
                reply_text = f"불편을 드려 진심으로 사과드립니다. 말씀해주신 부분 개선하여 더 나은 서비스를 제공하겠습니다."
            else:
                reply_text = f"소중한 의견 감사드립니다. {place.place_name if place else '저희 병원'}은 항상 환자분의 건강을 최우선으로 생각합니다."

        # 저장
        generated_reply = GeneratedReply(
            review_id=review_db_id,
            user_id=user_id,
            generated_content=reply_text,
            tone=tone,
        )

        db.add(generated_reply)
        await db.commit()
        await db.refresh(generated_reply)

        return generated_reply

    async def get_analytics(
        self,
        db: AsyncSession,
        place_db_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """리뷰 분석 통계"""
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()

        # 기본 통계
        query = select(
            func.count(PlaceReview.id).label("total"),
            func.avg(PlaceReview.rating).label("avg_rating"),
            func.sum(func.cast(PlaceReview.is_replied, Integer)).label("replied"),
        ).where(
            and_(
                PlaceReview.place_id == place_db_id,
                PlaceReview.written_at >= datetime.combine(start_date, datetime.min.time()),
                PlaceReview.written_at <= datetime.combine(end_date, datetime.max.time()),
            )
        )

        result = await db.execute(query)
        row = result.one()

        total = row.total or 0
        avg_rating = round(row.avg_rating or 0, 1)
        replied = row.replied or 0

        # 감성별 통계
        sentiment_query = select(
            PlaceReview.sentiment,
            func.count(PlaceReview.id).label("count"),
        ).where(
            and_(
                PlaceReview.place_id == place_db_id,
                PlaceReview.written_at >= datetime.combine(start_date, datetime.min.time()),
                PlaceReview.written_at <= datetime.combine(end_date, datetime.max.time()),
            )
        ).group_by(PlaceReview.sentiment)

        sentiment_result = await db.execute(sentiment_query)
        sentiment_rows = sentiment_result.all()

        sentiment_breakdown = {
            "positive": 0,
            "negative": 0,
            "neutral": 0,
        }
        for s_row in sentiment_rows:
            if s_row.sentiment:
                sentiment_breakdown[s_row.sentiment.value] = s_row.count

        # 평점별 통계
        rating_query = select(
            PlaceReview.rating,
            func.count(PlaceReview.id).label("count"),
        ).where(
            and_(
                PlaceReview.place_id == place_db_id,
                PlaceReview.written_at >= datetime.combine(start_date, datetime.min.time()),
                PlaceReview.written_at <= datetime.combine(end_date, datetime.max.time()),
            )
        ).group_by(PlaceReview.rating)

        rating_result = await db.execute(rating_query)
        rating_rows = rating_result.all()

        rating_breakdown = {i: 0 for i in range(1, 6)}
        for r_row in rating_rows:
            if r_row.rating:
                rating_breakdown[r_row.rating] = r_row.count

        # 일별 트렌드
        daily_query = select(
            func.date(PlaceReview.written_at).label("date"),
            func.count(PlaceReview.id).label("count"),
            func.avg(PlaceReview.rating).label("avg_rating"),
        ).where(
            and_(
                PlaceReview.place_id == place_db_id,
                PlaceReview.written_at >= datetime.combine(start_date, datetime.min.time()),
                PlaceReview.written_at <= datetime.combine(end_date, datetime.max.time()),
            )
        ).group_by(func.date(PlaceReview.written_at)).order_by("date")

        daily_result = await db.execute(daily_query)
        daily_rows = daily_result.all()

        daily_trend = [
            {
                "date": str(d_row.date),
                "count": d_row.count,
                "avg_rating": round(d_row.avg_rating or 0, 1),
            }
            for d_row in daily_rows
        ]

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "summary": {
                "total_reviews": total,
                "avg_rating": avg_rating,
                "replied_count": replied,
                "reply_rate": round(replied / total * 100, 1) if total > 0 else 0,
            },
            "sentiment_breakdown": sentiment_breakdown,
            "rating_breakdown": rating_breakdown,
            "daily_trend": daily_trend,
        }

    async def get_alert_settings(
        self,
        db: AsyncSession,
        user_id: str,
        place_db_id: Optional[str] = None,
    ) -> List[ReviewAlert]:
        """알림 설정 조회"""
        query = select(ReviewAlert).where(ReviewAlert.user_id == user_id)
        if place_db_id:
            query = query.where(ReviewAlert.place_id == place_db_id)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def update_alert_settings(
        self,
        db: AsyncSession,
        user_id: str,
        place_db_id: str,
        alert_type: str,
        is_active: bool = True,
        channels: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        rating_threshold: int = 3,
    ) -> ReviewAlert:
        """알림 설정 업데이트"""
        query = select(ReviewAlert).where(
            and_(
                ReviewAlert.user_id == user_id,
                ReviewAlert.place_id == place_db_id,
                ReviewAlert.alert_type == alert_type,
            )
        )
        result = await db.execute(query)
        alert = result.scalar_one_or_none()

        if alert:
            alert.is_active = is_active
            alert.channels = channels or []
            alert.keywords = keywords or []
            alert.rating_threshold = rating_threshold
        else:
            alert = ReviewAlert(
                user_id=user_id,
                place_id=place_db_id,
                alert_type=alert_type,
                is_active=is_active,
                channels=channels or [],
                keywords=keywords or [],
                rating_threshold=rating_threshold,
            )
            db.add(alert)

        await db.commit()
        await db.refresh(alert)

        return alert

    async def get_templates(
        self,
        db: AsyncSession,
        user_id: str,
        sentiment_type: Optional[Sentiment] = None,
    ) -> List[ReviewReplyTemplate]:
        """답변 템플릿 조회"""
        query = select(ReviewReplyTemplate).where(
            and_(
                ReviewReplyTemplate.user_id == user_id,
                ReviewReplyTemplate.is_active == True,
            )
        )

        if sentiment_type:
            query = query.where(ReviewReplyTemplate.sentiment_type == sentiment_type)

        query = query.order_by(desc(ReviewReplyTemplate.usage_count))

        result = await db.execute(query)
        return list(result.scalars().all())

    async def create_template(
        self,
        db: AsyncSession,
        user_id: str,
        name: str,
        template_content: str,
        sentiment_type: Optional[Sentiment] = None,
        category: Optional[str] = None,
        variables: Optional[List[str]] = None,
    ) -> ReviewReplyTemplate:
        """답변 템플릿 생성"""
        template = ReviewReplyTemplate(
            user_id=user_id,
            name=name,
            template_content=template_content,
            sentiment_type=sentiment_type,
            category=category,
            variables=variables or [],
        )

        db.add(template)
        await db.commit()
        await db.refresh(template)

        return template


# Integer 임포트
from sqlalchemy import Integer
