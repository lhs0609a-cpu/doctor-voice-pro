"""
플레이스 검색 순위 추적 서비스
"""

import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from sqlalchemy.orm import selectinload
import uuid

from app.models.place_ranking import (
    PlaceKeyword, PlaceRanking, RankingAlert, KeywordRecommendation, RankingSummary
)
from app.models.naver_place import NaverPlace

logger = logging.getLogger(__name__)


class RankingService:
    """플레이스 검색 순위 추적 서비스"""

    async def add_keyword(
        self,
        db: AsyncSession,
        user_id: str,
        place_db_id: str,
        keyword: str,
        category: Optional[str] = None,
        priority: int = 0,
    ) -> PlaceKeyword:
        """추적 키워드 추가"""
        # 중복 체크
        query = select(PlaceKeyword).where(
            and_(
                PlaceKeyword.user_id == user_id,
                PlaceKeyword.place_id == place_db_id,
                PlaceKeyword.keyword == keyword,
            )
        )
        result = await db.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            existing.is_active = True
            existing.priority = priority
            existing.category = category
            await db.commit()
            await db.refresh(existing)
            return existing

        kw = PlaceKeyword(
            user_id=user_id,
            place_id=place_db_id,
            keyword=keyword,
            category=category,
            priority=priority,
            is_active=True,
        )

        db.add(kw)
        await db.commit()
        await db.refresh(kw)

        logger.info(f"Added keyword '{keyword}' for user {user_id}")
        return kw

    async def get_keywords(
        self,
        db: AsyncSession,
        user_id: str,
        place_db_id: Optional[str] = None,
        is_active: Optional[bool] = True,
    ) -> List[PlaceKeyword]:
        """추적 키워드 목록 조회"""
        query = select(PlaceKeyword).where(PlaceKeyword.user_id == user_id)

        if place_db_id:
            query = query.where(PlaceKeyword.place_id == place_db_id)
        if is_active is not None:
            query = query.where(PlaceKeyword.is_active == is_active)

        query = query.order_by(desc(PlaceKeyword.priority), PlaceKeyword.keyword)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def remove_keyword(
        self,
        db: AsyncSession,
        keyword_id: str,
    ) -> bool:
        """추적 키워드 제거"""
        query = select(PlaceKeyword).where(PlaceKeyword.id == keyword_id)
        result = await db.execute(query)
        kw = result.scalar_one_or_none()

        if kw:
            kw.is_active = False
            await db.commit()
            return True

        return False

    async def check_ranking(
        self,
        db: AsyncSession,
        keyword_id: str,
        rank: Optional[int] = None,
        total_results: int = 0,
        top_competitors: Optional[List[Dict[str, Any]]] = None,
    ) -> PlaceRanking:
        """순위 체크 및 기록"""
        # 키워드 정보 조회
        kw_query = select(PlaceKeyword).where(PlaceKeyword.id == keyword_id)
        kw_result = await db.execute(kw_query)
        keyword = kw_result.scalar_one_or_none()

        if not keyword:
            raise ValueError("Keyword not found")

        # 이전 순위 조회
        prev_query = select(PlaceRanking).where(
            PlaceRanking.keyword_id == keyword_id
        ).order_by(desc(PlaceRanking.checked_at)).limit(1)

        prev_result = await db.execute(prev_query)
        prev_ranking = prev_result.scalar_one_or_none()

        previous_rank = prev_ranking.rank if prev_ranking else None

        # 새 순위 기록
        ranking = PlaceRanking(
            keyword_id=keyword_id,
            rank=rank,
            total_results=total_results,
            top_competitors=top_competitors or [],
        )

        db.add(ranking)

        # 키워드 정보 업데이트
        keyword.current_rank = rank
        keyword.last_checked_at = datetime.utcnow()

        # 순위 변동 계산 및 트렌드 업데이트
        if rank and previous_rank:
            change = previous_rank - rank  # 양수면 순위 상승
            keyword.rank_change = change

            if change > 0:
                keyword.trend = "up"
            elif change < 0:
                keyword.trend = "down"
            else:
                keyword.trend = "stable"

            # 베스트/워스트 순위 업데이트
            if keyword.best_rank is None or rank < keyword.best_rank:
                keyword.best_rank = rank
            if keyword.worst_rank is None or rank > keyword.worst_rank:
                keyword.worst_rank = rank

            # 중요한 변동 시 알림 생성
            if abs(change) >= 5:
                await self._create_ranking_alert(
                    db, keyword_id, previous_rank, rank, change
                )
        elif rank and not previous_rank:
            keyword.trend = "new"
            keyword.rank_change = 0
            keyword.best_rank = rank
            keyword.worst_rank = rank
        elif not rank and previous_rank:
            keyword.trend = "down"

        await db.commit()
        await db.refresh(ranking)

        return ranking

    async def _create_ranking_alert(
        self,
        db: AsyncSession,
        keyword_id: str,
        previous_rank: int,
        current_rank: int,
        change: int,
    ):
        """순위 변동 알림 생성"""
        if change > 0:
            alert_type = "rank_up"
            if current_rank <= 10 and previous_rank > 10:
                message = f"TOP 10 진입! ({previous_rank}위 → {current_rank}위)"
            else:
                message = f"순위 상승 ({previous_rank}위 → {current_rank}위, +{change})"
        else:
            alert_type = "rank_down"
            if previous_rank <= 10 and current_rank > 10:
                message = f"TOP 10 이탈 ({previous_rank}위 → {current_rank}위)"
            else:
                message = f"순위 하락 ({previous_rank}위 → {current_rank}위, {change})"

        alert = RankingAlert(
            keyword_id=keyword_id,
            previous_rank=previous_rank,
            current_rank=current_rank,
            change=change,
            alert_type=alert_type,
            message=message,
        )

        db.add(alert)

    async def get_ranking_history(
        self,
        db: AsyncSession,
        keyword_id: str,
        days: int = 30,
    ) -> List[PlaceRanking]:
        """순위 히스토리 조회"""
        start_date = datetime.utcnow() - timedelta(days=days)

        query = select(PlaceRanking).where(
            and_(
                PlaceRanking.keyword_id == keyword_id,
                PlaceRanking.checked_at >= start_date,
            )
        ).order_by(PlaceRanking.checked_at)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_current_rankings(
        self,
        db: AsyncSession,
        user_id: str,
        place_db_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """현재 순위 조회"""
        kw_query = select(PlaceKeyword).where(
            and_(
                PlaceKeyword.user_id == user_id,
                PlaceKeyword.is_active == True,
            )
        )

        if place_db_id:
            kw_query = kw_query.where(PlaceKeyword.place_id == place_db_id)

        kw_result = await db.execute(kw_query)
        keywords = list(kw_result.scalars().all())

        results = []
        for kw in keywords:
            results.append({
                "id": str(kw.id),
                "keyword": kw.keyword,
                "category": kw.category,
                "current_rank": kw.current_rank,
                "rank_change": kw.rank_change,
                "trend": kw.trend,
                "best_rank": kw.best_rank,
                "worst_rank": kw.worst_rank,
                "last_checked_at": kw.last_checked_at.isoformat() if kw.last_checked_at else None,
            })

        return results

    async def get_recommendations(
        self,
        db: AsyncSession,
        user_id: str,
        place_db_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """키워드 추천"""
        # 플레이스 정보 조회
        place_query = select(NaverPlace).where(NaverPlace.id == place_db_id)
        place_result = await db.execute(place_query)
        place = place_result.scalar_one_or_none()

        if not place:
            return []

        # 이미 추적 중인 키워드
        tracked_query = select(PlaceKeyword.keyword).where(
            and_(
                PlaceKeyword.user_id == user_id,
                PlaceKeyword.place_id == place_db_id,
                PlaceKeyword.is_active == True,
            )
        )
        tracked_result = await db.execute(tracked_query)
        tracked_keywords = set(row[0] for row in tracked_result.all())

        recommendations = []

        # 카테고리 기반 추천
        category_keywords = {
            "피부과": ["강남피부과", "여드름치료", "피부레이저", "미백", "주름치료", "탄력관리", "모공치료"],
            "성형외과": ["강남성형외과", "쌍꺼풀", "눈성형", "코성형", "지방흡입", "안면윤곽", "리프팅"],
            "치과": ["강남치과", "임플란트", "치아교정", "치아미백", "충치치료", "발치", "신경치료"],
            "한의원": ["강남한의원", "다이어트한의원", "통증치료", "추나요법", "침치료", "한방다이어트"],
        }

        # 지역 추출
        location = ""
        if place.address:
            parts = place.address.split()
            if len(parts) >= 2:
                location = parts[1] if "구" in parts[1] else parts[0]

        # 카테고리 매칭
        for cat, keywords in category_keywords.items():
            if place.category and cat in place.category:
                for kw in keywords:
                    if kw not in tracked_keywords:
                        # 지역 키워드로 변환
                        local_kw = kw.replace("강남", location) if "강남" in kw else kw

                        recommendations.append({
                            "keyword": local_kw,
                            "category": "specialty",
                            "estimated_search_volume": 1000 + len(recommendations) * 100,
                            "estimated_competition": "medium",
                            "relevance_score": 0.85,
                            "source": "category_based",
                            "recommendation_reason": f"{cat} 관련 인기 키워드",
                        })

        # 지역 + 카테고리 조합
        if location and place.category:
            base_category = place.category.split(">")[-1].strip() if ">" in place.category else place.category
            location_kw = f"{location} {base_category}"

            if location_kw not in tracked_keywords:
                recommendations.append({
                    "keyword": location_kw,
                    "category": "location",
                    "estimated_search_volume": 2000,
                    "estimated_competition": "high",
                    "relevance_score": 0.95,
                    "source": "location_based",
                    "recommendation_reason": "지역 + 진료과 핵심 키워드",
                })

        # 일반 추천
        general_keywords = ["야간진료병원", "주말진료", "당일예약가능"]
        for gk in general_keywords:
            if location:
                local_gk = f"{location} {gk}"
            else:
                local_gk = gk

            if local_gk not in tracked_keywords:
                recommendations.append({
                    "keyword": local_gk,
                    "category": "service",
                    "estimated_search_volume": 500,
                    "estimated_competition": "low",
                    "relevance_score": 0.6,
                    "source": "general",
                    "recommendation_reason": "서비스 관련 검색어",
                })

        return recommendations[:limit]

    async def get_summary(
        self,
        db: AsyncSession,
        user_id: str,
        place_db_id: str,
        summary_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """순위 요약 조회"""
        if not summary_date:
            summary_date = datetime.utcnow()

        # 활성 키워드 조회
        kw_query = select(PlaceKeyword).where(
            and_(
                PlaceKeyword.user_id == user_id,
                PlaceKeyword.place_id == place_db_id,
                PlaceKeyword.is_active == True,
            )
        )

        kw_result = await db.execute(kw_query)
        keywords = list(kw_result.scalars().all())

        total_keywords = len(keywords)
        keywords_in_top10 = sum(1 for kw in keywords if kw.current_rank and kw.current_rank <= 10)
        keywords_in_top30 = sum(1 for kw in keywords if kw.current_rank and kw.current_rank <= 30)
        keywords_out_of_rank = sum(1 for kw in keywords if kw.current_rank is None)

        ranks = [kw.current_rank for kw in keywords if kw.current_rank]
        avg_rank = round(sum(ranks) / len(ranks), 1) if ranks else None
        best_rank = min(ranks) if ranks else None
        worst_rank = max(ranks) if ranks else None

        improved_count = sum(1 for kw in keywords if kw.rank_change and kw.rank_change > 0)
        declined_count = sum(1 for kw in keywords if kw.rank_change and kw.rank_change < 0)
        stable_count = sum(1 for kw in keywords if kw.rank_change == 0)

        return {
            "summary_date": summary_date.isoformat(),
            "total_keywords": total_keywords,
            "keywords_in_top10": keywords_in_top10,
            "keywords_in_top30": keywords_in_top30,
            "keywords_out_of_rank": keywords_out_of_rank,
            "avg_rank": avg_rank,
            "best_rank": best_rank,
            "worst_rank": worst_rank,
            "improved_count": improved_count,
            "declined_count": declined_count,
            "stable_count": stable_count,
            "keywords": [
                {
                    "keyword": kw.keyword,
                    "rank": kw.current_rank,
                    "change": kw.rank_change,
                    "trend": kw.trend,
                }
                for kw in keywords
            ]
        }

    async def get_alerts(
        self,
        db: AsyncSession,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
    ) -> List[RankingAlert]:
        """순위 변동 알림 조회"""
        query = select(RankingAlert).join(PlaceKeyword).where(
            PlaceKeyword.user_id == user_id
        )

        if unread_only:
            query = query.where(RankingAlert.is_read == False)

        query = query.order_by(desc(RankingAlert.created_at)).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())
