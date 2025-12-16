"""
리뷰 캠페인 관리 서비스
"""

import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from sqlalchemy.orm import selectinload
import uuid
import hashlib
import secrets

from app.models.review_campaign import (
    ReviewCampaign, CampaignParticipation, CampaignTemplate, CampaignAnalytics, ReviewRewardHistory,
    CampaignStatus, RewardType
)

logger = logging.getLogger(__name__)


class CampaignService:
    """리뷰 캠페인 관리 서비스"""

    async def create_campaign(
        self,
        db: AsyncSession,
        user_id: str,
        name: str,
        reward_type: RewardType,
        reward_description: str,
        start_date: date,
        end_date: date,
        place_db_id: Optional[str] = None,
        description: Optional[str] = None,
        terms: Optional[str] = None,
        reward_value: Optional[int] = None,
        target_count: int = 0,
        min_rating: int = 1,
        min_content_length: int = 0,
        require_photo: bool = False,
        total_budget: int = 0,
    ) -> ReviewCampaign:
        """캠페인 생성"""
        campaign = ReviewCampaign(
            user_id=user_id,
            place_id=place_db_id,
            name=name,
            description=description,
            terms=terms,
            reward_type=reward_type,
            reward_description=reward_description,
            reward_value=reward_value,
            start_date=start_date,
            end_date=end_date,
            target_count=target_count,
            min_rating=min_rating,
            min_content_length=min_content_length,
            require_photo=require_photo,
            total_budget=total_budget,
            status=CampaignStatus.DRAFT,
        )

        # 짧은 URL 생성
        short_code = secrets.token_urlsafe(6)
        campaign.short_url = f"/c/{short_code}"

        db.add(campaign)
        await db.commit()
        await db.refresh(campaign)

        logger.info(f"Created campaign {campaign.id} for user {user_id}")
        return campaign

    async def get_campaigns(
        self,
        db: AsyncSession,
        user_id: str,
        status: Optional[CampaignStatus] = None,
        place_db_id: Optional[str] = None,
    ) -> List[ReviewCampaign]:
        """캠페인 목록 조회"""
        query = select(ReviewCampaign).where(ReviewCampaign.user_id == user_id)

        if status:
            query = query.where(ReviewCampaign.status == status)
        if place_db_id:
            query = query.where(ReviewCampaign.place_id == place_db_id)

        query = query.order_by(desc(ReviewCampaign.created_at))

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_campaign(
        self,
        db: AsyncSession,
        campaign_id: str,
    ) -> Optional[ReviewCampaign]:
        """캠페인 상세 조회"""
        query = select(ReviewCampaign).where(ReviewCampaign.id == campaign_id).options(
            selectinload(ReviewCampaign.participations)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def update_campaign(
        self,
        db: AsyncSession,
        campaign_id: str,
        **kwargs,
    ) -> Optional[ReviewCampaign]:
        """캠페인 수정"""
        query = select(ReviewCampaign).where(ReviewCampaign.id == campaign_id)
        result = await db.execute(query)
        campaign = result.scalar_one_or_none()

        if not campaign:
            return None

        for key, value in kwargs.items():
            if hasattr(campaign, key):
                setattr(campaign, key, value)

        campaign.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(campaign)

        return campaign

    async def update_status(
        self,
        db: AsyncSession,
        campaign_id: str,
        status: CampaignStatus,
    ) -> Optional[ReviewCampaign]:
        """캠페인 상태 변경"""
        return await self.update_campaign(db, campaign_id, status=status)

    async def delete_campaign(
        self,
        db: AsyncSession,
        campaign_id: str,
    ) -> bool:
        """캠페인 삭제"""
        query = select(ReviewCampaign).where(ReviewCampaign.id == campaign_id)
        result = await db.execute(query)
        campaign = result.scalar_one_or_none()

        if campaign:
            await db.delete(campaign)
            await db.commit()
            return True

        return False

    async def generate_qr_code(
        self,
        db: AsyncSession,
        campaign_id: str,
        base_url: str,
    ) -> Dict[str, Any]:
        """QR 코드 생성"""
        query = select(ReviewCampaign).where(ReviewCampaign.id == campaign_id)
        result = await db.execute(query)
        campaign = result.scalar_one_or_none()

        if not campaign:
            return {"error": "Campaign not found"}

        # QR 코드 URL
        qr_url = f"{base_url}/c/{campaign.short_url.split('/')[-1]}"

        # 여기서는 QR 코드 이미지 생성 로직 필요 (qrcode 라이브러리 등)
        # 단순화를 위해 URL만 반환
        campaign.qr_code_url = qr_url
        campaign.landing_page_url = qr_url

        await db.commit()

        return {
            "qr_url": qr_url,
            "short_url": campaign.short_url,
            "landing_page_url": qr_url,
        }

    async def participate(
        self,
        db: AsyncSession,
        campaign_id: str,
        customer_name: Optional[str] = None,
        customer_phone: Optional[str] = None,
        customer_email: Optional[str] = None,
        source: str = "link",
    ) -> CampaignParticipation:
        """캠페인 참여"""
        # 참여 코드 생성
        participation_code = secrets.token_urlsafe(8).upper()

        # 전화번호/이메일 해시
        phone_hash = hashlib.sha256(customer_phone.encode()).hexdigest() if customer_phone else None
        email_hash = hashlib.sha256(customer_email.encode()).hexdigest() if customer_email else None

        participation = CampaignParticipation(
            campaign_id=campaign_id,
            customer_name=customer_name,
            customer_phone_hash=phone_hash,
            customer_email_hash=email_hash,
            participation_code=participation_code,
            source=source,
            status="pending",
        )

        db.add(participation)

        # 캠페인 통계 업데이트
        campaign_query = select(ReviewCampaign).where(ReviewCampaign.id == campaign_id)
        campaign_result = await db.execute(campaign_query)
        campaign = campaign_result.scalar_one_or_none()

        if campaign:
            campaign.current_count += 1

        await db.commit()
        await db.refresh(participation)

        return participation

    async def verify_participation(
        self,
        db: AsyncSession,
        participation_id: str,
        review_url: Optional[str] = None,
        review_content: Optional[str] = None,
        review_rating: Optional[int] = None,
        verification_method: str = "manual",
    ) -> CampaignParticipation:
        """참여 검증"""
        query = select(CampaignParticipation).where(CampaignParticipation.id == participation_id)
        result = await db.execute(query)
        participation = result.scalar_one_or_none()

        if not participation:
            raise ValueError("Participation not found")

        participation.review_url = review_url
        participation.review_content = review_content
        participation.review_rating = review_rating
        participation.review_date = datetime.utcnow()
        participation.is_verified = True
        participation.verified_at = datetime.utcnow()
        participation.verification_method = verification_method
        participation.status = "verified"

        # 캠페인 통계 업데이트
        campaign_query = select(ReviewCampaign).where(ReviewCampaign.id == participation.campaign_id)
        campaign_result = await db.execute(campaign_query)
        campaign = campaign_result.scalar_one_or_none()

        if campaign:
            campaign.verified_count += 1

        await db.commit()
        await db.refresh(participation)

        return participation

    async def give_reward(
        self,
        db: AsyncSession,
        user_id: str,
        participation_id: str,
        reward_amount: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> CampaignParticipation:
        """보상 지급"""
        query = select(CampaignParticipation).where(CampaignParticipation.id == participation_id)
        result = await db.execute(query)
        participation = result.scalar_one_or_none()

        if not participation:
            raise ValueError("Participation not found")

        participation.reward_given = True
        participation.reward_given_at = datetime.utcnow()
        participation.reward_amount = reward_amount
        participation.reward_notes = notes
        participation.status = "rewarded"

        # 캠페인 예산 업데이트
        campaign_query = select(ReviewCampaign).where(ReviewCampaign.id == participation.campaign_id)
        campaign_result = await db.execute(campaign_query)
        campaign = campaign_result.scalar_one_or_none()

        if campaign and reward_amount:
            campaign.spent_budget += reward_amount

        # 보상 이력 기록
        reward_history = ReviewRewardHistory(
            user_id=user_id,
            campaign_id=participation.campaign_id,
            participation_id=participation_id,
            reward_type=campaign.reward_type if campaign else RewardType.GIFT,
            reward_description=campaign.reward_description if campaign else "",
            reward_value=reward_amount,
            recipient_name=participation.customer_name,
            status="completed",
            completed_at=datetime.utcnow(),
            cost=reward_amount or 0,
            notes=notes,
        )
        db.add(reward_history)

        await db.commit()
        await db.refresh(participation)

        return participation

    async def get_stats(
        self,
        db: AsyncSession,
        campaign_id: str,
    ) -> Dict[str, Any]:
        """캠페인 통계"""
        query = select(ReviewCampaign).where(ReviewCampaign.id == campaign_id)
        result = await db.execute(query)
        campaign = result.scalar_one_or_none()

        if not campaign:
            return {"error": "Campaign not found"}

        # 참여 통계
        participation_query = select(
            func.count(CampaignParticipation.id).label("total"),
            func.sum(func.cast(CampaignParticipation.is_verified, Integer)).label("verified"),
            func.sum(func.cast(CampaignParticipation.reward_given, Integer)).label("rewarded"),
            func.avg(CampaignParticipation.review_rating).label("avg_rating"),
        ).where(CampaignParticipation.campaign_id == campaign_id)

        participation_result = await db.execute(participation_query)
        row = participation_result.one()

        total = row.total or 0
        verified = row.verified or 0
        rewarded = row.rewarded or 0
        avg_rating = round(row.avg_rating or 0, 1)

        # 소스별 분포
        source_query = select(
            CampaignParticipation.source,
            func.count(CampaignParticipation.id).label("count"),
        ).where(
            CampaignParticipation.campaign_id == campaign_id
        ).group_by(CampaignParticipation.source)

        source_result = await db.execute(source_query)
        source_breakdown = {row.source: row.count for row in source_result.all()}

        # 진행률
        progress = round(verified / campaign.target_count * 100, 1) if campaign.target_count > 0 else 0

        # 예산 사용률
        budget_usage = round(campaign.spent_budget / campaign.total_budget * 100, 1) if campaign.total_budget > 0 else 0

        return {
            "campaign": {
                "id": str(campaign.id),
                "name": campaign.name,
                "status": campaign.status.value,
                "start_date": campaign.start_date.isoformat(),
                "end_date": campaign.end_date.isoformat(),
            },
            "participation": {
                "total": total,
                "verified": verified,
                "rewarded": rewarded,
                "pending": total - verified,
                "verification_rate": round(verified / total * 100, 1) if total > 0 else 0,
            },
            "progress": {
                "target_count": campaign.target_count,
                "current_count": verified,
                "progress_percentage": progress,
            },
            "budget": {
                "total": campaign.total_budget,
                "spent": campaign.spent_budget,
                "remaining": campaign.total_budget - campaign.spent_budget,
                "usage_percentage": budget_usage,
            },
            "reviews": {
                "avg_rating": avg_rating,
            },
            "source_breakdown": source_breakdown,
            "traffic": {
                "views": campaign.total_views,
                "clicks": campaign.total_clicks,
                "conversion_rate": round(total / campaign.total_clicks * 100, 1) if campaign.total_clicks > 0 else 0,
            },
        }

    async def get_participations(
        self,
        db: AsyncSession,
        campaign_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[CampaignParticipation]:
        """참여 목록 조회"""
        query = select(CampaignParticipation).where(
            CampaignParticipation.campaign_id == campaign_id
        )

        if status:
            query = query.where(CampaignParticipation.status == status)

        query = query.order_by(desc(CampaignParticipation.participated_at)).offset(offset).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_templates(
        self,
        db: AsyncSession,
        user_id: Optional[str] = None,
    ) -> List[CampaignTemplate]:
        """캠페인 템플릿 조회"""
        query = select(CampaignTemplate).where(CampaignTemplate.is_active == True)

        if user_id:
            query = query.where(
                (CampaignTemplate.user_id == user_id) | (CampaignTemplate.is_public == True)
            )
        else:
            query = query.where(CampaignTemplate.is_public == True)

        query = query.order_by(desc(CampaignTemplate.usage_count))

        result = await db.execute(query)
        return list(result.scalars().all())

    async def record_view(
        self,
        db: AsyncSession,
        campaign_id: str,
    ):
        """캠페인 조회 기록"""
        query = select(ReviewCampaign).where(ReviewCampaign.id == campaign_id)
        result = await db.execute(query)
        campaign = result.scalar_one_or_none()

        if campaign:
            campaign.total_views += 1
            await db.commit()

    async def record_click(
        self,
        db: AsyncSession,
        campaign_id: str,
    ):
        """캠페인 클릭 기록"""
        query = select(ReviewCampaign).where(ReviewCampaign.id == campaign_id)
        result = await db.execute(query)
        campaign = result.scalar_one_or_none()

        if campaign:
            campaign.total_clicks += 1
            await db.commit()


# Integer 임포트
from sqlalchemy import Integer
