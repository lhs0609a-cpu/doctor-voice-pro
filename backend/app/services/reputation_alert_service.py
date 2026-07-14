"""
평판 모니터링 - 알림 서비스
위험도 기반 알림 라우팅 + 쿨다운 관리
"""
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, List

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reputation import (
    Mention, ReputationAlertRule, ReputationAlertLog,
    MentionPlatform, MentionSentiment, RiskLevel, AlertSeverity
)
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class ReputationAlertService:
    """평판 알림 서비스"""

    def __init__(self):
        self.notification_service = NotificationService()

    async def check_and_alert(self, db: AsyncSession, mention: Mention):
        """멘션에 대해 알림 규칙을 확인하고 알림 발송"""
        # 해당 프로필의 활성 알림 규칙 조회
        result = await db.execute(
            select(ReputationAlertRule).where(and_(
                ReputationAlertRule.profile_id == mention.profile_id,
                ReputationAlertRule.is_active == True,
            ))
        )
        rules = result.scalars().all()

        for rule in rules:
            if self._matches_rule(mention, rule):
                await self._send_alert(db, rule, mention)

    def _matches_rule(self, mention: Mention, rule: ReputationAlertRule) -> bool:
        """멘션이 알림 규칙에 매칭되는지 확인"""
        # 쿨다운 확인
        if rule.last_triggered_at and rule.cooldown_minutes:
            cooldown_end = rule.last_triggered_at + timedelta(minutes=rule.cooldown_minutes)
            if datetime.utcnow() < cooldown_end:
                return False

        # 플랫폼 필터
        if rule.platforms:
            if mention.platform and mention.platform.value not in rule.platforms:
                return False

        # 감성 필터
        if rule.sentiment_filter:
            if mention.sentiment and mention.sentiment.value not in rule.sentiment_filter:
                return False

        # 위험도 점수 필터
        if rule.min_risk_score is not None:
            if (mention.risk_score or 0) < rule.min_risk_score:
                return False

        # 별점 필터
        if rule.max_rating is not None and mention.rating is not None:
            if mention.rating > rule.max_rating:
                return False

        if rule.min_rating is not None and mention.rating is not None:
            if mention.rating < rule.min_rating:
                return False

        # 키워드 필터
        if rule.keyword_contains:
            content = (mention.content or "") + " " + (mention.title or "")
            content_lower = content.lower()
            if not any(kw.lower() in content_lower for kw in rule.keyword_contains):
                return False

        return True

    async def _send_alert(self, db: AsyncSession, rule: ReputationAlertRule, mention: Mention):
        """알림 발송"""
        # 알림 제목/메시지 생성
        platform_name = mention.platform.value if mention.platform else "알 수 없음"
        risk_emoji = {
            AlertSeverity.CRITICAL: "[긴급]",
            AlertSeverity.WARNING: "[주의]",
            AlertSeverity.INFO: "[알림]",
        }.get(rule.severity, "[알림]")

        title = f"{risk_emoji} {platform_name}에서 새로운 멘션이 감지되었습니다"

        content_preview = (mention.content or "")[:100]
        rating_info = f"별점: {mention.rating}/5\n" if mention.rating else ""
        message = (
            f"플랫폼: {platform_name}\n"
            f"{rating_info}"
            f"작성자: {mention.author_name or '익명'}\n"
            f"위험도: {mention.risk_level.value if mention.risk_level else 'N/A'} "
            f"(점수: {mention.risk_score or 0})\n"
            f"내용: {content_preview}...\n"
            f"URL: {mention.source_url or 'N/A'}"
        )

        # 각 채널로 알림 발송
        channels_to_send = []
        if rule.notify_email:
            channels_to_send.append("email")
        if rule.notify_sms:
            channels_to_send.append("sms")
        if rule.notify_kakao:
            channels_to_send.append("kakao")
        if rule.notify_webhook_url:
            channels_to_send.append("webhook")

        for channel in channels_to_send:
            log = ReputationAlertLog(
                id=str(uuid.uuid4()),
                rule_id=rule.id,
                mention_id=mention.id,
                user_id=rule.user_id,
                severity=rule.severity,
                title=title,
                message=message,
                channel=channel,
            )

            try:
                await self._dispatch_notification(
                    channel=channel,
                    title=title,
                    message=message,
                    rule=rule,
                    mention=mention,
                )
                log.is_sent = True
                log.sent_at = datetime.utcnow()
            except Exception as e:
                log.is_sent = False
                log.error_message = str(e)
                logger.error(f"알림 발송 실패 ({channel}): {e}")

            db.add(log)

        # 쿨다운 업데이트
        rule.last_triggered_at = datetime.utcnow()
        await db.commit()

    async def _dispatch_notification(
        self,
        channel: str,
        title: str,
        message: str,
        rule: ReputationAlertRule,
        mention: Mention,
    ):
        """채널별 알림 디스패치"""
        if channel == "email":
            # 이메일 발송 (기존 NotificationService 또는 EmailSenderService 활용)
            logger.info(f"이메일 알림 발송: {title}")
            # TODO: 실제 이메일 발송 연동

        elif channel == "sms":
            logger.info(f"SMS 알림 발송: {title}")
            # TODO: SMS API 연동

        elif channel == "kakao":
            logger.info(f"카카오톡 알림 발송: {title}")
            # TODO: 카카오 알림톡 API 연동

        elif channel == "webhook":
            if rule.notify_webhook_url:
                import aiohttp
                payload = {
                    "title": title,
                    "message": message,
                    "severity": rule.severity.value if rule.severity else "info",
                    "mention_id": mention.id,
                    "platform": mention.platform.value if mention.platform else None,
                    "source_url": mention.source_url,
                    "risk_score": mention.risk_score,
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        rule.notify_webhook_url,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        if resp.status >= 400:
                            raise Exception(f"Webhook 응답 오류: {resp.status}")

    async def send_daily_digest(self, db: AsyncSession, profile_id: str, user_id: str):
        """일일 다이제스트 발송"""
        since = datetime.utcnow() - timedelta(hours=24)

        # 24시간 내 멘션 통계
        from sqlalchemy import func
        stats = await db.execute(
            select(
                func.count(Mention.id).label("total"),
                func.count().filter(Mention.sentiment == MentionSentiment.POSITIVE).label("positive"),
                func.count().filter(Mention.sentiment == MentionSentiment.NEGATIVE).label("negative"),
                func.count().filter(Mention.risk_level == RiskLevel.CRITICAL).label("critical"),
                func.avg(Mention.rating).label("avg_rating"),
            ).where(and_(
                Mention.profile_id == profile_id,
                Mention.created_at >= since,
            ))
        )
        row = stats.one()

        if row.total == 0:
            return  # 멘션 없으면 스킵

        digest = (
            f"[일일 평판 리포트]\n"
            f"기간: 최근 24시간\n"
            f"총 멘션: {row.total}건\n"
            f"긍정: {row.positive}건 | 부정: {row.negative}건\n"
            f"긴급 대응 필요: {row.critical}건\n"
            f"평균 별점: {round(float(row.avg_rating or 0), 1)}\n"
        )

        logger.info(f"일일 다이제스트: {digest}")
        # TODO: 실제 발송
