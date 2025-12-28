"""
A/B 테스트 서비스
- 테스트 생성/관리
- 변형 할당
- 결과 분석
"""

import uuid
import random
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.viral_common import ABTest, ABTestResult, ABTestStatus


class ABTestService:
    """A/B 테스트 서비스"""

    async def create_test(
        self,
        db: AsyncSession,
        user_id: str,
        name: str,
        description: str,
        test_type: str,  # tone, length, structure, promotion, timing
        platform: str,   # knowledge / cafe
        variants: List[Dict[str, Any]],
        traffic_split: Optional[Dict[str, float]] = None,
        target_sample_size: int = 100
    ) -> ABTest:
        """A/B 테스트 생성"""
        # 기본 트래픽 분할 (균등)
        if not traffic_split:
            variant_names = [v["name"] for v in variants]
            split = 1.0 / len(variant_names)
            traffic_split = {name: split for name in variant_names}

        test = ABTest(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            description=description,
            test_type=test_type,
            platform=platform,
            variants=variants,
            traffic_split=traffic_split,
            target_sample_size=target_sample_size
        )
        db.add(test)
        await db.commit()
        await db.refresh(test)
        return test

    async def get_tests(
        self,
        db: AsyncSession,
        user_id: str,
        status: Optional[ABTestStatus] = None,
        platform: Optional[str] = None
    ) -> List[ABTest]:
        """테스트 목록 조회"""
        query = select(ABTest).where(ABTest.user_id == user_id)

        if status:
            query = query.where(ABTest.status == status.value)

        if platform:
            query = query.where(ABTest.platform == platform)

        query = query.order_by(ABTest.created_at.desc())

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_test(
        self,
        db: AsyncSession,
        test_id: str,
        user_id: str
    ) -> Optional[ABTest]:
        """테스트 상세 조회"""
        result = await db.execute(
            select(ABTest).where(
                and_(
                    ABTest.id == test_id,
                    ABTest.user_id == user_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def start_test(
        self,
        db: AsyncSession,
        test_id: str,
        user_id: str
    ) -> Optional[ABTest]:
        """테스트 시작"""
        test = await self.get_test(db, test_id, user_id)
        if test and test.status == ABTestStatus.DRAFT.value:
            test.status = ABTestStatus.RUNNING.value
            test.started_at = datetime.utcnow()
            await db.commit()
            await db.refresh(test)
        return test

    async def stop_test(
        self,
        db: AsyncSession,
        test_id: str,
        user_id: str
    ) -> Optional[ABTest]:
        """테스트 중지"""
        test = await self.get_test(db, test_id, user_id)
        if test and test.status == ABTestStatus.RUNNING.value:
            test.status = ABTestStatus.PAUSED.value
            await db.commit()
            await db.refresh(test)
        return test

    async def complete_test(
        self,
        db: AsyncSession,
        test_id: str,
        user_id: str,
        winner_variant: Optional[str] = None
    ) -> Optional[ABTest]:
        """테스트 완료"""
        test = await self.get_test(db, test_id, user_id)
        if test:
            test.status = ABTestStatus.COMPLETED.value
            test.completed_at = datetime.utcnow()
            if winner_variant:
                test.winner_variant = winner_variant
            await db.commit()
            await db.refresh(test)
        return test

    async def assign_variant(
        self,
        db: AsyncSession,
        test_id: str,
        user_id: str
    ) -> Optional[str]:
        """변형 할당 (가중 랜덤)"""
        test = await self.get_test(db, test_id, user_id)

        if not test or test.status != ABTestStatus.RUNNING.value:
            return None

        # 가중치 기반 랜덤 선택
        traffic_split = test.traffic_split or {}
        variants = list(traffic_split.keys())
        weights = list(traffic_split.values())

        if not variants:
            return None

        selected = random.choices(variants, weights=weights, k=1)[0]
        return selected

    async def record_result(
        self,
        db: AsyncSession,
        test_id: str,
        variant: str,
        content_id: str,
        content_type: str,  # answer / comment / post
        metadata: Optional[Dict[str, Any]] = None
    ) -> ABTestResult:
        """결과 기록"""
        result = await db.execute(
            select(ABTest).where(ABTest.id == test_id)
        )
        test = result.scalar_one_or_none()

        if test:
            test.current_sample_size += 1

            # 목표 달성 시 자동 완료
            if test.current_sample_size >= test.target_sample_size:
                test.status = ABTestStatus.COMPLETED.value
                test.completed_at = datetime.utcnow()

        ab_result = ABTestResult(
            id=str(uuid.uuid4()),
            test_id=test_id,
            variant=variant,
            content_id=content_id,
            content_type=content_type,
            metadata=metadata
        )
        db.add(ab_result)
        await db.commit()
        await db.refresh(ab_result)

        return ab_result

    async def update_result_metrics(
        self,
        db: AsyncSession,
        result_id: str,
        is_success: Optional[bool] = None,
        is_adopted: Optional[bool] = None,
        likes: Optional[int] = None,
        replies: Optional[int] = None,
        clicks: Optional[int] = None,
        conversion: Optional[bool] = None
    ):
        """결과 메트릭 업데이트"""
        result = await db.execute(
            select(ABTestResult).where(ABTestResult.id == result_id)
        )
        ab_result = result.scalar_one_or_none()

        if ab_result:
            if is_success is not None:
                ab_result.is_success = is_success
            if is_adopted is not None:
                ab_result.is_adopted = is_adopted
            if likes is not None:
                ab_result.likes = likes
            if replies is not None:
                ab_result.replies = replies
            if clicks is not None:
                ab_result.clicks = clicks
            if conversion is not None:
                ab_result.conversion = conversion

            ab_result.updated_at = datetime.utcnow()
            await db.commit()

    async def get_test_results(
        self,
        db: AsyncSession,
        test_id: str
    ) -> List[ABTestResult]:
        """테스트 결과 목록"""
        result = await db.execute(
            select(ABTestResult).where(
                ABTestResult.test_id == test_id
            ).order_by(ABTestResult.created_at.desc())
        )
        return list(result.scalars().all())

    async def analyze_test(
        self,
        db: AsyncSession,
        test_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """테스트 분석"""
        test = await self.get_test(db, test_id, user_id)
        if not test:
            return {}

        results = await self.get_test_results(db, test_id)

        # 변형별 집계
        variant_stats = {}
        for result in results:
            variant = result.variant
            if variant not in variant_stats:
                variant_stats[variant] = {
                    "count": 0,
                    "success": 0,
                    "adopted": 0,
                    "total_likes": 0,
                    "total_replies": 0,
                    "total_clicks": 0,
                    "conversions": 0
                }

            stats = variant_stats[variant]
            stats["count"] += 1

            if result.is_success:
                stats["success"] += 1
            if result.is_adopted:
                stats["adopted"] += 1
            stats["total_likes"] += result.likes or 0
            stats["total_replies"] += result.replies or 0
            stats["total_clicks"] += result.clicks or 0
            if result.conversion:
                stats["conversions"] += 1

        # 변형별 지표 계산
        for variant, stats in variant_stats.items():
            count = stats["count"]
            if count > 0:
                stats["success_rate"] = stats["success"] / count
                stats["adoption_rate"] = stats["adopted"] / count
                stats["avg_likes"] = stats["total_likes"] / count
                stats["avg_replies"] = stats["total_replies"] / count
                stats["avg_clicks"] = stats["total_clicks"] / count
                stats["conversion_rate"] = stats["conversions"] / count
            else:
                stats["success_rate"] = 0
                stats["adoption_rate"] = 0
                stats["avg_likes"] = 0
                stats["avg_replies"] = 0
                stats["avg_clicks"] = 0
                stats["conversion_rate"] = 0

        # 우승자 결정 (종합 점수 기반)
        def calculate_score(stats):
            return (
                stats.get("success_rate", 0) * 0.2 +
                stats.get("adoption_rate", 0) * 0.3 +
                stats.get("avg_likes", 0) * 0.1 +
                stats.get("avg_replies", 0) * 0.1 +
                stats.get("avg_clicks", 0) * 0.15 +
                stats.get("conversion_rate", 0) * 0.15
            )

        winner = None
        max_score = -1

        for variant, stats in variant_stats.items():
            score = calculate_score(stats)
            stats["score"] = round(score, 4)

            if score > max_score:
                max_score = score
                winner = variant

        # 통계적 유의성 (간단한 계산)
        total_samples = sum(s["count"] for s in variant_stats.values())
        is_significant = total_samples >= test.target_sample_size

        return {
            "test_id": test_id,
            "test_name": test.name,
            "status": test.status,
            "platform": test.platform,
            "test_type": test.test_type,
            "total_samples": total_samples,
            "target_samples": test.target_sample_size,
            "progress": round(total_samples / test.target_sample_size * 100, 1),
            "variants": variant_stats,
            "winner": winner,
            "is_significant": is_significant,
            "started_at": test.started_at.isoformat() if test.started_at else None,
            "completed_at": test.completed_at.isoformat() if test.completed_at else None
        }

    async def get_variant_config(
        self,
        db: AsyncSession,
        test_id: str,
        variant: str
    ) -> Optional[Dict[str, Any]]:
        """변형 설정 가져오기"""
        result = await db.execute(
            select(ABTest).where(ABTest.id == test_id)
        )
        test = result.scalar_one_or_none()

        if not test or not test.variants:
            return None

        for v in test.variants:
            if v.get("name") == variant:
                return v.get("config", {})

        return None

    async def delete_test(
        self,
        db: AsyncSession,
        test_id: str,
        user_id: str
    ) -> bool:
        """테스트 삭제"""
        test = await self.get_test(db, test_id, user_id)
        if test:
            # 결과도 함께 삭제
            await db.execute(
                select(ABTestResult).where(ABTestResult.test_id == test_id)
            )
            # Note: cascade delete 설정에 따라 자동 삭제될 수 있음

            await db.delete(test)
            await db.commit()
            return True
        return False


# 미리 정의된 테스트 템플릿
AB_TEST_TEMPLATES = {
    "tone": {
        "name": "어조 테스트",
        "description": "다양한 어조 스타일 비교",
        "variants": [
            {"name": "friendly", "config": {"tone": "friendly"}},
            {"name": "professional", "config": {"tone": "professional"}},
            {"name": "empathetic", "config": {"tone": "empathetic"}}
        ]
    },
    "length": {
        "name": "길이 테스트",
        "description": "콘텐츠 길이 비교",
        "variants": [
            {"name": "short", "config": {"max_length": 200}},
            {"name": "medium", "config": {"max_length": 400}},
            {"name": "long", "config": {"max_length": 800}}
        ]
    },
    "promotion": {
        "name": "홍보 테스트",
        "description": "홍보 포함 여부 비교",
        "variants": [
            {"name": "no_promotion", "config": {"include_promotion": False}},
            {"name": "subtle", "config": {"include_promotion": True, "promotion_style": "subtle"}},
            {"name": "direct", "config": {"include_promotion": True, "promotion_style": "direct"}}
        ]
    },
    "emoji": {
        "name": "이모지 테스트",
        "description": "이모지 사용 여부 비교",
        "variants": [
            {"name": "no_emoji", "config": {"include_emoji": False}},
            {"name": "minimal", "config": {"include_emoji": True, "emoji_level": "minimal"}},
            {"name": "rich", "config": {"include_emoji": True, "emoji_level": "rich"}}
        ]
    }
}


# 싱글톤 인스턴스
ab_test_service = ABTestService()
