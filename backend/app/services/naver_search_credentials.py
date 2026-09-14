"""Resolve the requesting user's existing search keys without exposing them."""
from sqlalchemy import select
from app.core.config import settings
from app.models.blog_outreach import OutreachSetting
from app.services.email_sender_service import EmailSenderService
from cryptography.fernet import InvalidToken


async def resolve(db, user_id):
    row = (await db.execute(select(OutreachSetting).where(
        OutreachSetting.user_id == user_id))).scalar_one_or_none()
    if row and row.naver_client_id and row.naver_client_secret_encrypted:
        try:
            secret = EmailSenderService(db).decrypt_password(row.naver_client_secret_encrypted)
        except (InvalidToken, ValueError, TypeError):
            secret = None
        if secret:
            return row.naver_client_id, secret
    if settings.NAVER_CLIENT_ID and settings.NAVER_CLIENT_SECRET:
        return settings.NAVER_CLIENT_ID, settings.NAVER_CLIENT_SECRET
    return None
