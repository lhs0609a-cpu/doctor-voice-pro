"""
알림 서비스
- Slack / Telegram / Discord / Kakao / Email / Webhook 지원
- 다양한 이벤트 알림
"""

import uuid
import json
import aiohttp
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.viral_common import (
    NotificationChannel, NotificationLog, NotificationType
)


class NotificationService:
    """알림 서비스"""

    async def create_channel(
        self,
        db: AsyncSession,
        user_id: str,
        channel_type: str,  # slack, telegram, discord, kakao, email, webhook
        channel_name: str,
        config: Dict[str, Any],
        notify_types: Optional[List[str]] = None
    ) -> NotificationChannel:
        """알림 채널 생성"""
        channel = NotificationChannel(
            id=str(uuid.uuid4()),
            user_id=user_id,
            channel_type=channel_type,
            channel_name=channel_name,
            config=config,
            notify_types=notify_types or [
                NotificationType.ADOPTION.value,
                NotificationType.DAILY_REPORT.value,
                NotificationType.ERROR.value
            ]
        )
        db.add(channel)
        await db.commit()
        await db.refresh(channel)
        return channel

    async def get_channels(
        self,
        db: AsyncSession,
        user_id: str,
        channel_type: Optional[str] = None
    ) -> List[NotificationChannel]:
        """채널 목록 조회"""
        query = select(NotificationChannel).where(
            NotificationChannel.user_id == user_id
        )

        if channel_type:
            query = query.where(NotificationChannel.channel_type == channel_type)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def update_channel(
        self,
        db: AsyncSession,
        channel_id: str,
        user_id: str,
        **updates
    ) -> Optional[NotificationChannel]:
        """채널 업데이트"""
        result = await db.execute(
            select(NotificationChannel).where(
                and_(
                    NotificationChannel.id == channel_id,
                    NotificationChannel.user_id == user_id
                )
            )
        )
        channel = result.scalar_one_or_none()

        if channel:
            for key, value in updates.items():
                if hasattr(channel, key):
                    setattr(channel, key, value)
            channel.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(channel)

        return channel

    async def delete_channel(
        self,
        db: AsyncSession,
        channel_id: str,
        user_id: str
    ) -> bool:
        """채널 삭제"""
        result = await db.execute(
            select(NotificationChannel).where(
                and_(
                    NotificationChannel.id == channel_id,
                    NotificationChannel.user_id == user_id
                )
            )
        )
        channel = result.scalar_one_or_none()

        if channel:
            await db.delete(channel)
            await db.commit()
            return True
        return False

    async def send_notification(
        self,
        db: AsyncSession,
        user_id: str,
        notification_type: NotificationType,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> List[NotificationLog]:
        """알림 전송"""
        # 해당 타입 알림을 받는 활성 채널 조회
        channels = await self.get_channels(db, user_id)
        active_channels = [
            ch for ch in channels
            if ch.is_active and notification_type.value in (ch.notify_types or [])
        ]

        logs = []
        for channel in active_channels:
            log = await self._send_to_channel(
                db, channel, notification_type, title, message, data
            )
            logs.append(log)

        return logs

    async def _send_to_channel(
        self,
        db: AsyncSession,
        channel: NotificationChannel,
        notification_type: NotificationType,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> NotificationLog:
        """개별 채널로 전송"""
        log = NotificationLog(
            id=str(uuid.uuid4()),
            user_id=channel.user_id,
            channel_id=channel.id,
            notification_type=notification_type.value,
            title=title,
            message=message,
            data=data
        )

        try:
            if channel.channel_type == "slack":
                await self._send_slack(channel.config, title, message, data)
            elif channel.channel_type == "telegram":
                await self._send_telegram(channel.config, title, message, data)
            elif channel.channel_type == "discord":
                await self._send_discord(channel.config, title, message, data)
            elif channel.channel_type == "kakao":
                await self._send_kakao(channel.config, title, message, data)
            elif channel.channel_type == "email":
                await self._send_email(channel.config, title, message, data)
            elif channel.channel_type == "webhook":
                await self._send_webhook(channel.config, title, message, data)

            log.is_sent = True
            log.sent_at = datetime.utcnow()

            # 채널 통계 업데이트
            channel.total_sent += 1
            channel.last_sent_at = datetime.utcnow()

        except Exception as e:
            log.is_sent = False
            log.error_message = str(e)
            channel.fail_count += 1
            channel.last_error = str(e)
            channel.last_error_at = datetime.utcnow()

        db.add(log)
        await db.commit()
        await db.refresh(log)

        return log

    async def _send_slack(
        self,
        config: Dict[str, Any],
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ):
        """Slack 웹훅 전송"""
        webhook_url = config.get("webhook_url")
        if not webhook_url:
            raise ValueError("Slack webhook URL not configured")

        payload = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": title,
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message
                    }
                }
            ]
        }

        if data:
            fields = []
            for key, value in data.items():
                fields.append({
                    "type": "mrkdwn",
                    "text": f"*{key}:*\n{value}"
                })
            if fields:
                payload["blocks"].append({
                    "type": "section",
                    "fields": fields[:10]  # Slack 필드 제한
                })

        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as resp:
                if resp.status != 200:
                    raise Exception(f"Slack API error: {resp.status}")

    async def _send_telegram(
        self,
        config: Dict[str, Any],
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ):
        """Telegram 봇 메시지 전송"""
        bot_token = config.get("bot_token")
        chat_id = config.get("chat_id")

        if not bot_token or not chat_id:
            raise ValueError("Telegram bot_token and chat_id required")

        # HTML 형식 메시지
        text = f"<b>{title}</b>\n\n{message}"

        if data:
            text += "\n\n<b>상세 정보:</b>"
            for key, value in data.items():
                text += f"\n• {key}: {value}"

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    result = await resp.json()
                    raise Exception(f"Telegram API error: {result}")

    async def _send_discord(
        self,
        config: Dict[str, Any],
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ):
        """Discord 웹훅 전송"""
        webhook_url = config.get("webhook_url")
        if not webhook_url:
            raise ValueError("Discord webhook URL not configured")

        embed = {
            "title": title,
            "description": message,
            "color": 5814783,  # 파란색
            "timestamp": datetime.utcnow().isoformat()
        }

        if data:
            embed["fields"] = [
                {"name": key, "value": str(value), "inline": True}
                for key, value in list(data.items())[:25]
            ]

        payload = {"embeds": [embed]}

        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as resp:
                if resp.status not in [200, 204]:
                    raise Exception(f"Discord API error: {resp.status}")

    async def _send_kakao(
        self,
        config: Dict[str, Any],
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ):
        """카카오톡 메시지 전송 (카카오워크 웹훅)"""
        webhook_url = config.get("webhook_url")
        if not webhook_url:
            raise ValueError("Kakao webhook URL not configured")

        text = f"[{title}]\n{message}"
        if data:
            for key, value in data.items():
                text += f"\n• {key}: {value}"

        payload = {"text": text}

        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as resp:
                if resp.status != 200:
                    raise Exception(f"Kakao API error: {resp.status}")

    async def _send_email(
        self,
        config: Dict[str, Any],
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ):
        """이메일 전송 (구현 필요)"""
        # SMTP 또는 외부 이메일 서비스 연동
        # 현재는 placeholder
        email = config.get("email")
        if not email:
            raise ValueError("Email address not configured")

        # TODO: 실제 이메일 전송 구현
        # import smtplib 또는 SendGrid/Mailgun API 사용
        pass

    async def _send_webhook(
        self,
        config: Dict[str, Any],
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ):
        """커스텀 웹훅 전송"""
        webhook_url = config.get("webhook_url")
        if not webhook_url:
            raise ValueError("Webhook URL not configured")

        headers = config.get("headers", {})
        method = config.get("method", "POST").upper()

        payload = {
            "title": title,
            "message": message,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }

        async with aiohttp.ClientSession() as session:
            if method == "POST":
                async with session.post(
                    webhook_url, json=payload, headers=headers
                ) as resp:
                    if resp.status >= 400:
                        raise Exception(f"Webhook error: {resp.status}")
            elif method == "GET":
                async with session.get(
                    webhook_url, params=payload, headers=headers
                ) as resp:
                    if resp.status >= 400:
                        raise Exception(f"Webhook error: {resp.status}")

    async def test_channel(
        self,
        db: AsyncSession,
        channel_id: str,
        user_id: str
    ) -> bool:
        """채널 테스트"""
        result = await db.execute(
            select(NotificationChannel).where(
                and_(
                    NotificationChannel.id == channel_id,
                    NotificationChannel.user_id == user_id
                )
            )
        )
        channel = result.scalar_one_or_none()

        if not channel:
            return False

        try:
            log = await self._send_to_channel(
                db,
                channel,
                NotificationType.SYSTEM,
                "테스트 알림",
                "Doctor Voice Pro 알림 테스트입니다.",
                {"테스트 시간": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}
            )
            return log.is_sent
        except:
            return False

    async def get_notification_logs(
        self,
        db: AsyncSession,
        user_id: str,
        channel_id: Optional[str] = None,
        notification_type: Optional[NotificationType] = None,
        limit: int = 50
    ) -> List[NotificationLog]:
        """알림 로그 조회"""
        query = select(NotificationLog).where(
            NotificationLog.user_id == user_id
        )

        if channel_id:
            query = query.where(NotificationLog.channel_id == channel_id)

        if notification_type:
            query = query.where(
                NotificationLog.notification_type == notification_type.value
            )

        query = query.order_by(NotificationLog.created_at.desc()).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    # 편의 메서드들
    async def notify_adoption(
        self,
        db: AsyncSession,
        user_id: str,
        question_title: str,
        answer_preview: str,
        reward_points: int = 0
    ):
        """채택 알림"""
        await self.send_notification(
            db,
            user_id,
            NotificationType.ADOPTION,
            "🎉 답변이 채택되었습니다!",
            f"질문: {question_title}\n\n답변: {answer_preview[:100]}...",
            {"내공": reward_points} if reward_points else None
        )

    async def notify_like(
        self,
        db: AsyncSession,
        user_id: str,
        content_type: str,  # answer / comment / post
        content_preview: str,
        like_count: int
    ):
        """좋아요 알림"""
        type_names = {
            "answer": "답변",
            "comment": "댓글",
            "post": "게시글"
        }
        await self.send_notification(
            db,
            user_id,
            NotificationType.LIKE,
            f"👍 {type_names.get(content_type, content_type)}에 좋아요가 추가되었습니다",
            content_preview[:100],
            {"총 좋아요": like_count}
        )

    async def notify_reply(
        self,
        db: AsyncSession,
        user_id: str,
        original_content: str,
        reply_content: str,
        reply_author: str
    ):
        """댓글/대댓글 알림"""
        await self.send_notification(
            db,
            user_id,
            NotificationType.REPLY,
            "💬 새 댓글이 달렸습니다",
            f"원글: {original_content[:50]}...\n\n댓글: {reply_content}",
            {"작성자": reply_author}
        )

    async def notify_daily_report(
        self,
        db: AsyncSession,
        user_id: str,
        report_data: Dict[str, Any]
    ):
        """일일 리포트 알림"""
        summary = []
        if report_data.get("answers_posted", 0):
            summary.append(f"답변 {report_data['answers_posted']}건")
        if report_data.get("comments_posted", 0):
            summary.append(f"댓글 {report_data['comments_posted']}건")
        if report_data.get("adoptions", 0):
            summary.append(f"채택 {report_data['adoptions']}건")

        await self.send_notification(
            db,
            user_id,
            NotificationType.DAILY_REPORT,
            "📊 일일 활동 리포트",
            ", ".join(summary) if summary else "오늘 활동이 없습니다.",
            report_data
        )

    async def notify_error(
        self,
        db: AsyncSession,
        user_id: str,
        error_type: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """에러 알림"""
        await self.send_notification(
            db,
            user_id,
            NotificationType.ERROR,
            f"⚠️ 오류 발생: {error_type}",
            error_message,
            context
        )

    async def notify_account_blocked(
        self,
        db: AsyncSession,
        user_id: str,
        account_name: str,
        reason: str
    ):
        """계정 차단 알림"""
        await self.send_notification(
            db,
            user_id,
            NotificationType.ACCOUNT_BLOCKED,
            "🚫 계정 차단 감지",
            f"계정 '{account_name}'이(가) 차단되었을 수 있습니다.",
            {"사유": reason}
        )


# 싱글톤 인스턴스
notification_service = NotificationService()
