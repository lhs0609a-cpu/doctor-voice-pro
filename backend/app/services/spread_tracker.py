"""
평판 모니터링 - 확산 추적 서비스
동일 이슈가 여러 플랫폼으로 확산되는 것을 추적
"""
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reputation import (
    Mention, SpreadIncident,
    MentionSentiment, RiskLevel, SpreadStatus
)

logger = logging.getLogger(__name__)


class SpreadTracker:
    """확산 추적 서비스"""

    # 유사도 임계값 (간단한 키워드 매칭 기반)
    SIMILARITY_THRESHOLD = 0.3

    async def check_spread(self, db: AsyncSession, mention: Mention):
        """새 멘션이 기존 확산 사건과 관련되는지 확인"""
        if mention.risk_level not in (RiskLevel.CRITICAL, RiskLevel.WARNING):
            return

        profile_id = mention.profile_id

        # 최근 7일간 유사한 부정적 멘션 조회
        since = datetime.utcnow() - timedelta(days=7)
        result = await db.execute(
            select(Mention).where(and_(
                Mention.profile_id == profile_id,
                Mention.id != mention.id,
                Mention.risk_level.in_([RiskLevel.CRITICAL, RiskLevel.WARNING]),
                Mention.created_at >= since,
            ))
        )
        recent_negative = result.scalars().all()

        if not recent_negative:
            return

        # 키워드 기반 유사도 확인
        mention_keywords = set(mention.issues or [])
        mention_words = set((mention.content or "").split()[:50])

        related_mentions = []
        for other in recent_negative:
            other_keywords = set(other.issues or [])
            other_words = set((other.content or "").split()[:50])

            # 이슈 키워드 겹침 확인
            if mention_keywords and other_keywords:
                overlap = mention_keywords & other_keywords
                if overlap:
                    related_mentions.append(other)
                    continue

            # 단어 유사도
            all_words = mention_words | other_words
            if all_words:
                common = mention_words & other_words
                similarity = len(common) / len(all_words)
                if similarity >= self.SIMILARITY_THRESHOLD:
                    related_mentions.append(other)

        if not related_mentions:
            return

        # 다른 플랫폼에서도 발견되었는지 확인
        platforms = {mention.platform}
        for m in related_mentions:
            platforms.add(m.platform)

        if len(platforms) < 2:
            return  # 동일 플랫폼만이면 확산 아님

        # 기존 확산 사건에 연결하거나 새 사건 생성
        existing_incident = None
        for m in related_mentions:
            if m.spread_incident_id:
                result = await db.execute(
                    select(SpreadIncident).where(
                        SpreadIncident.id == m.spread_incident_id
                    )
                )
                existing_incident = result.scalar_one_or_none()
                if existing_incident:
                    break

        if existing_incident:
            # 기존 사건에 멘션 추가
            mention.spread_incident_id = existing_incident.id
            existing_incident.mention_count = (existing_incident.mention_count or 0) + 1
            existing_incident.platform_count = len(platforms)

            # 타임라인 업데이트
            timeline = existing_incident.timeline or []
            timeline.append({
                "time": datetime.utcnow().isoformat(),
                "platform": mention.platform.value if mention.platform else "unknown",
                "event": "새 멘션 감지",
                "url": mention.source_url,
                "mention_id": mention.id,
            })
            existing_incident.timeline = timeline
            existing_incident.status = SpreadStatus.SPREADING

        else:
            # 새 확산 사건 생성
            incident = SpreadIncident(
                id=str(uuid.uuid4()),
                user_id=mention.user_id,
                profile_id=profile_id,
                title=f"확산 감지: {', '.join(mention.issues or ['부정적 멘션'])}",
                description=f"{len(platforms)}개 플랫폼에서 유사한 부정적 멘션 {len(related_mentions) + 1}건 감지",
                status=SpreadStatus.MONITORING,
                platform_count=len(platforms),
                mention_count=len(related_mentions) + 1,
                timeline=[
                    {
                        "time": m.created_at.isoformat() if m.created_at else datetime.utcnow().isoformat(),
                        "platform": m.platform.value if m.platform else "unknown",
                        "event": "멘션 감지",
                        "url": m.source_url,
                        "mention_id": m.id,
                    }
                    for m in [*related_mentions, mention]
                ],
            )
            db.add(incident)
            await db.flush()

            # 관련 멘션들에 사건 ID 연결
            mention.spread_incident_id = incident.id
            for m in related_mentions:
                m.spread_incident_id = incident.id

        await db.commit()
        logger.info(f"확산 사건 {'업데이트' if existing_incident else '생성'}: {len(platforms)}개 플랫폼")

    async def update_incident_stats(self, db: AsyncSession, incident_id: str):
        """확산 사건 통계 업데이트"""
        result = await db.execute(
            select(SpreadIncident).where(SpreadIncident.id == incident_id)
        )
        incident = result.scalar_one_or_none()
        if not incident:
            return

        # 관련 멘션 통계
        stats = await db.execute(
            select(
                func.count(Mention.id),
                func.count(func.distinct(Mention.platform)),
            ).where(Mention.spread_incident_id == incident_id)
        )
        row = stats.one()

        incident.mention_count = row[0]
        incident.platform_count = row[1]

        # 추정 노출 수 (간단한 추정)
        views = await db.execute(
            select(Mention.platform_data).where(
                Mention.spread_incident_id == incident_id
            )
        )
        total_views = 0
        for (pdata,) in views.all():
            if pdata and isinstance(pdata, dict):
                total_views += pdata.get("view_count", 0)
                total_views += pdata.get("like_count", 0) * 10

        incident.estimated_reach = total_views or incident.mention_count * 100
        await db.commit()
