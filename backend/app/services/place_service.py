"""
네이버 플레이스 관리 서비스
"""

import logging
from typing import Optional, Dict, List, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import selectinload
import uuid

from app.models.naver_place import (
    NaverPlace, PlaceOptimizationCheck, PlaceDescription, PlaceTag,
    OptimizationStatus
)
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)


# 최적화 체크 항목 정의
OPTIMIZATION_CHECKS = [
    {"type": "basic_info", "name": "기본 정보 완성도", "priority": 10, "weight": 15},
    {"type": "photos", "name": "사진 등록", "priority": 9, "weight": 15},
    {"type": "description", "name": "소개글", "priority": 8, "weight": 15},
    {"type": "business_hours", "name": "영업시간", "priority": 7, "weight": 10},
    {"type": "tags", "name": "태그", "priority": 6, "weight": 10},
    {"type": "phone", "name": "전화번호", "priority": 5, "weight": 5},
    {"type": "address", "name": "주소 정보", "priority": 5, "weight": 10},
    {"type": "category", "name": "카테고리", "priority": 4, "weight": 10},
    {"type": "reviews", "name": "리뷰 관리", "priority": 8, "weight": 10},
]


class PlaceService:
    """네이버 플레이스 관리 서비스"""

    def __init__(self):
        self.ai_service = AIService()

    async def connect_place(
        self,
        db: AsyncSession,
        user_id: str,
        place_id: str,
        place_name: str,
        place_url: Optional[str] = None,
        **kwargs,
    ) -> NaverPlace:
        """플레이스 연동"""
        # 기존 연결 확인
        query = select(NaverPlace).where(
            and_(
                NaverPlace.user_id == user_id,
                NaverPlace.place_id == place_id,
            )
        )
        result = await db.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            # 기존 연결 업데이트
            existing.place_name = place_name
            existing.place_url = place_url
            existing.is_connected = True
            existing.last_synced_at = datetime.utcnow()
            for key, value in kwargs.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            await db.commit()
            await db.refresh(existing)
            return existing

        # 새 연결 생성
        place = NaverPlace(
            user_id=user_id,
            place_id=place_id,
            place_name=place_name,
            place_url=place_url,
            is_connected=True,
            connection_method="manual",
            last_synced_at=datetime.utcnow(),
            **kwargs,
        )

        db.add(place)
        await db.commit()
        await db.refresh(place)

        # 최적화 체크 초기 실행
        await self.run_optimization_check(db, place.id)

        logger.info(f"Connected place {place_id} for user {user_id}")
        return place

    async def get_place(
        self,
        db: AsyncSession,
        user_id: str,
        place_db_id: Optional[str] = None,
    ) -> Optional[NaverPlace]:
        """플레이스 정보 조회"""
        query = select(NaverPlace).where(NaverPlace.user_id == user_id)

        if place_db_id:
            query = query.where(NaverPlace.id == place_db_id)

        query = query.options(selectinload(NaverPlace.optimization_checks))

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_places(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> List[NaverPlace]:
        """사용자의 모든 플레이스 조회"""
        query = select(NaverPlace).where(
            NaverPlace.user_id == user_id
        ).order_by(desc(NaverPlace.created_at))

        result = await db.execute(query)
        return list(result.scalars().all())

    async def update_place(
        self,
        db: AsyncSession,
        place_db_id: str,
        **kwargs,
    ) -> Optional[NaverPlace]:
        """플레이스 정보 업데이트"""
        query = select(NaverPlace).where(NaverPlace.id == place_db_id)
        result = await db.execute(query)
        place = result.scalar_one_or_none()

        if not place:
            return None

        for key, value in kwargs.items():
            if hasattr(place, key):
                setattr(place, key, value)

        place.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(place)

        return place

    async def run_optimization_check(
        self,
        db: AsyncSession,
        place_db_id: str,
    ) -> Dict[str, Any]:
        """최적화 점수 계산 및 체크리스트 생성"""
        query = select(NaverPlace).where(NaverPlace.id == place_db_id)
        result = await db.execute(query)
        place = result.scalar_one_or_none()

        if not place:
            return {"error": "Place not found"}

        # 기존 체크리스트 삭제
        delete_query = select(PlaceOptimizationCheck).where(
            PlaceOptimizationCheck.place_id == place_db_id
        )
        delete_result = await db.execute(delete_query)
        for check in delete_result.scalars().all():
            await db.delete(check)

        total_score = 0
        total_weight = 0
        checks = []

        for check_def in OPTIMIZATION_CHECKS:
            check_type = check_def["type"]
            weight = check_def["weight"]
            total_weight += weight

            status, score, message, suggestion = await self._evaluate_check(place, check_type)

            check = PlaceOptimizationCheck(
                place_id=place_db_id,
                check_type=check_type,
                check_name=check_def["name"],
                status=status,
                score=score,
                message=message,
                suggestion=suggestion,
                priority=check_def["priority"],
            )
            db.add(check)
            checks.append(check)

            total_score += score * weight

        # 전체 점수 계산 (100점 만점)
        optimization_score = int(total_score / total_weight) if total_weight > 0 else 0
        place.optimization_score = optimization_score
        place.optimization_details = {
            "total_score": optimization_score,
            "checks_passed": sum(1 for c in checks if c.status == OptimizationStatus.PASS),
            "checks_warning": sum(1 for c in checks if c.status == OptimizationStatus.WARNING),
            "checks_failed": sum(1 for c in checks if c.status == OptimizationStatus.FAIL),
            "last_checked": datetime.utcnow().isoformat(),
        }

        await db.commit()

        return {
            "optimization_score": optimization_score,
            "checks": [
                {
                    "type": c.check_type,
                    "name": c.check_name,
                    "status": c.status.value,
                    "score": c.score,
                    "message": c.message,
                    "suggestion": c.suggestion,
                    "priority": c.priority,
                }
                for c in checks
            ]
        }

    async def _evaluate_check(
        self,
        place: NaverPlace,
        check_type: str,
    ) -> tuple:
        """개별 체크 항목 평가"""
        if check_type == "basic_info":
            filled_count = sum([
                bool(place.place_name),
                bool(place.category),
                bool(place.address),
                bool(place.phone),
            ])
            if filled_count >= 4:
                return OptimizationStatus.PASS, 100, "기본 정보가 완벽하게 입력되었습니다.", None
            elif filled_count >= 2:
                return OptimizationStatus.WARNING, 50, f"기본 정보 {filled_count}/4 입력됨", "병원명, 카테고리, 주소, 전화번호를 모두 입력하세요."
            else:
                return OptimizationStatus.FAIL, 0, "기본 정보가 부족합니다.", "필수 정보를 입력해주세요."

        elif check_type == "photos":
            images = place.images or []
            if len(images) >= 10:
                return OptimizationStatus.PASS, 100, f"사진 {len(images)}개 등록됨", None
            elif len(images) >= 5:
                return OptimizationStatus.WARNING, 60, f"사진 {len(images)}개 등록됨", "10장 이상의 고품질 사진을 등록하면 더 좋습니다."
            elif len(images) >= 1:
                return OptimizationStatus.WARNING, 30, f"사진 {len(images)}개 등록됨", "더 많은 사진을 등록해주세요."
            else:
                return OptimizationStatus.FAIL, 0, "사진이 없습니다.", "병원 내외부, 시술 전후 사진 등을 등록해주세요."

        elif check_type == "description":
            desc = place.description or ""
            if len(desc) >= 200:
                return OptimizationStatus.PASS, 100, f"소개글 {len(desc)}자", None
            elif len(desc) >= 100:
                return OptimizationStatus.WARNING, 60, f"소개글 {len(desc)}자", "200자 이상의 상세한 소개글을 작성해주세요."
            elif len(desc) > 0:
                return OptimizationStatus.WARNING, 30, f"소개글 {len(desc)}자", "소개글이 너무 짧습니다."
            else:
                return OptimizationStatus.FAIL, 0, "소개글이 없습니다.", "병원 특장점을 담은 소개글을 작성해주세요."

        elif check_type == "business_hours":
            hours = place.business_hours or {}
            if len(hours) >= 5:
                return OptimizationStatus.PASS, 100, "영업시간 설정 완료", None
            elif len(hours) >= 1:
                return OptimizationStatus.WARNING, 50, f"영업시간 {len(hours)}일 설정", "모든 요일의 영업시간을 설정해주세요."
            else:
                return OptimizationStatus.FAIL, 0, "영업시간 미설정", "영업시간을 설정해주세요."

        elif check_type == "tags":
            tags = place.tags or []
            if len(tags) >= 5:
                return OptimizationStatus.PASS, 100, f"태그 {len(tags)}개", None
            elif len(tags) >= 2:
                return OptimizationStatus.WARNING, 50, f"태그 {len(tags)}개", "5개 이상의 관련 태그를 추가해주세요."
            else:
                return OptimizationStatus.FAIL, 0, "태그 부족", "진료과목, 특화분야 등 태그를 추가해주세요."

        elif check_type == "phone":
            if place.phone:
                return OptimizationStatus.PASS, 100, "전화번호 등록됨", None
            else:
                return OptimizationStatus.FAIL, 0, "전화번호 미등록", "상담 전화번호를 등록해주세요."

        elif check_type == "address":
            if place.address and place.road_address:
                return OptimizationStatus.PASS, 100, "주소 완전 등록", None
            elif place.address or place.road_address:
                return OptimizationStatus.WARNING, 70, "주소 일부 등록", "지번주소와 도로명주소 모두 등록해주세요."
            else:
                return OptimizationStatus.FAIL, 0, "주소 미등록", "정확한 주소를 등록해주세요."

        elif check_type == "category":
            if place.category and place.sub_category:
                return OptimizationStatus.PASS, 100, "카테고리 설정 완료", None
            elif place.category:
                return OptimizationStatus.WARNING, 70, "대분류만 설정됨", "세부 카테고리도 설정해주세요."
            else:
                return OptimizationStatus.FAIL, 0, "카테고리 미설정", "적합한 카테고리를 선택해주세요."

        elif check_type == "reviews":
            review_count = place.review_count or 0
            avg_rating = place.avg_rating or 0
            if review_count >= 50 and avg_rating >= 4.5:
                return OptimizationStatus.PASS, 100, f"리뷰 {review_count}개, 평점 {avg_rating}", None
            elif review_count >= 20 and avg_rating >= 4.0:
                return OptimizationStatus.WARNING, 70, f"리뷰 {review_count}개, 평점 {avg_rating}", "더 많은 리뷰를 확보하세요."
            elif review_count >= 1:
                return OptimizationStatus.WARNING, 40, f"리뷰 {review_count}개, 평점 {avg_rating}", "리뷰 이벤트를 진행해보세요."
            else:
                return OptimizationStatus.FAIL, 0, "리뷰 없음", "리뷰 캠페인을 시작하세요."

        return OptimizationStatus.WARNING, 50, "체크 불가", None

    async def generate_description(
        self,
        db: AsyncSession,
        place_db_id: str,
        user_id: str,
        tone: str = "professional",
        keywords: Optional[List[str]] = None,
        specialty_focus: Optional[str] = None,
    ) -> PlaceDescription:
        """AI 소개글 생성"""
        query = select(NaverPlace).where(NaverPlace.id == place_db_id)
        result = await db.execute(query)
        place = result.scalar_one_or_none()

        if not place:
            raise ValueError("Place not found")

        # AI로 소개글 생성
        prompt = f"""
네이버 플레이스에 등록할 병원 소개글을 작성해주세요.

병원 정보:
- 병원명: {place.place_name}
- 카테고리: {place.category or '미지정'}
- 주소: {place.address or '미지정'}
- 전화번호: {place.phone or '미지정'}

요청 사항:
- 톤: {'전문적이고 신뢰감 있게' if tone == 'professional' else '친근하고 편안하게' if tone == 'friendly' else '간결하게'}
- 강조할 분야: {specialty_focus or '일반 진료'}
- 포함할 키워드: {', '.join(keywords) if keywords else '없음'}

작성 지침:
1. 200자 이상 300자 이하로 작성
2. 병원의 강점과 특화 분야 강조
3. 환자 입장에서 신뢰가 가는 내용
4. 핵심 키워드를 자연스럽게 포함
5. 마지막에 내원을 유도하는 문구 포함

소개글만 출력해주세요:
"""

        try:
            description_text = await self.ai_service.generate_text(prompt)
        except Exception as e:
            logger.error(f"AI description generation failed: {e}")
            description_text = f"{place.place_name}은(는) 환자분들의 건강을 최우선으로 생각하는 의료기관입니다. 친절한 상담과 정확한 진료로 최선의 치료를 제공합니다."

        # 저장
        description = PlaceDescription(
            place_id=place_db_id,
            user_id=user_id,
            description=description_text,
            tone=tone,
            keywords_used=keywords or [],
            specialty_focus=specialty_focus,
        )

        db.add(description)
        await db.commit()
        await db.refresh(description)

        return description

    async def get_tag_recommendations(
        self,
        db: AsyncSession,
        place_db_id: str,
    ) -> List[Dict[str, Any]]:
        """태그 추천"""
        query = select(NaverPlace).where(NaverPlace.id == place_db_id)
        result = await db.execute(query)
        place = result.scalar_one_or_none()

        if not place:
            return []

        # 기본 추천 태그 (카테고리 기반)
        recommendations = []

        # 카테고리 기반 태그
        category_tags = {
            "피부과": ["피부관리", "레이저", "여드름치료", "미백", "주름개선", "탄력관리"],
            "성형외과": ["쌍꺼풀", "코성형", "지방흡입", "안면윤곽", "리프팅", "필러"],
            "치과": ["임플란트", "치아교정", "충치치료", "스케일링", "치아미백", "잇몸치료"],
            "한의원": ["한방치료", "침", "추나", "다이어트", "통증치료", "체질개선"],
            "내과": ["건강검진", "만성질환", "당뇨", "고혈압", "내시경", "예방접종"],
        }

        for category, tags in category_tags.items():
            if place.category and category in place.category:
                for tag in tags:
                    recommendations.append({
                        "tag": tag,
                        "category": "specialty",
                        "relevance_score": 0.9,
                        "source": "category_based",
                    })

        # 지역 기반 태그
        if place.address:
            address_parts = place.address.split()
            for part in address_parts[:3]:
                if len(part) >= 2:
                    recommendations.append({
                        "tag": f"{part}병원",
                        "category": "location",
                        "relevance_score": 0.7,
                        "source": "location_based",
                    })

        # 일반 태그
        general_tags = ["야간진료", "주말진료", "주차가능", "예약필수", "당일예약", "초진환영"]
        for tag in general_tags:
            recommendations.append({
                "tag": tag,
                "category": "service",
                "relevance_score": 0.5,
                "source": "general",
            })

        return recommendations[:20]  # 상위 20개만 반환

    async def get_optimization_checks(
        self,
        db: AsyncSession,
        place_db_id: str,
    ) -> List[PlaceOptimizationCheck]:
        """최적화 체크리스트 조회"""
        query = select(PlaceOptimizationCheck).where(
            PlaceOptimizationCheck.place_id == place_db_id
        ).order_by(desc(PlaceOptimizationCheck.priority))

        result = await db.execute(query)
        return list(result.scalars().all())
