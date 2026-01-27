"""
이메일 발송 서비스
SMTP를 통한 이메일 발송, 템플릿 렌더링, 추적 기능
"""
import logging
import uuid
import asyncio
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from cryptography.fernet import Fernet
import os
import base64

# 비동기 SMTP 라이브러리 (동기 smtplib 대체)
try:
    import aiosmtplib
    HAS_AIOSMTPLIB = True
except ImportError:
    import smtplib
    HAS_AIOSMTPLIB = False
    import warnings
    warnings.warn("aiosmtplib not installed. Using synchronous smtplib (may cause performance issues).")

from app.models.blog_outreach import (
    NaverBlog, BlogContact, EmailTemplate, EmailCampaign,
    EmailLog, EmailStatus, CampaignStatus, OutreachSetting,
    LeadGrade, BlogStatus
)

logger = logging.getLogger(__name__)


class EmailSenderService:
    """이메일 발송 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db
        # 암호화 키 (환경 변수에서 가져오거나 생성)
        self._encryption_key = os.getenv("ENCRYPTION_KEY", Fernet.generate_key().decode())

    def _get_fernet(self) -> Fernet:
        """Fernet 암호화 객체"""
        key = self._encryption_key
        if isinstance(key, str):
            key = key.encode()
        # 키가 유효한 Fernet 키인지 확인
        try:
            return Fernet(key)
        except Exception:
            # 유효하지 않으면 새 키 생성
            return Fernet(Fernet.generate_key())

    def encrypt_password(self, password: str) -> str:
        """비밀번호 암호화"""
        f = self._get_fernet()
        return f.encrypt(password.encode()).decode()

    def decrypt_password(self, encrypted: str) -> str:
        """비밀번호 복호화"""
        f = self._get_fernet()
        return f.decrypt(encrypted.encode()).decode()

    async def _get_outreach_settings(self, user_id: str) -> Optional[OutreachSetting]:
        """사용자 발송 설정 조회"""
        result = await self.db.execute(
            select(OutreachSetting).where(OutreachSetting.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def _check_daily_limit(self, user_id: str) -> Dict[str, Any]:
        """일일 발송 한도 확인"""
        settings = await self._get_outreach_settings(user_id)
        daily_limit = settings.daily_limit if settings else 50

        # 오늘 발송량 조회
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await self.db.execute(
            select(func.count()).select_from(EmailLog).where(and_(
                EmailLog.user_id == user_id,
                EmailLog.sent_at >= today_start,
                EmailLog.status == EmailStatus.SENT
            ))
        )
        today_sent = result.scalar() or 0

        remaining = max(0, daily_limit - today_sent)

        return {
            "daily_limit": daily_limit,
            "sent_today": today_sent,
            "remaining": remaining,
            "can_send": remaining > 0
        }

    async def _check_hourly_limit(self, user_id: str) -> Dict[str, Any]:
        """시간당 발송 한도 확인"""
        settings = await self._get_outreach_settings(user_id)
        hourly_limit = settings.hourly_limit if settings else 10

        # 최근 1시간 발송량 조회
        hour_ago = datetime.utcnow() - timedelta(hours=1)
        result = await self.db.execute(
            select(func.count()).select_from(EmailLog).where(and_(
                EmailLog.user_id == user_id,
                EmailLog.sent_at >= hour_ago,
                EmailLog.status == EmailStatus.SENT
            ))
        )
        hour_sent = result.scalar() or 0

        remaining = max(0, hourly_limit - hour_sent)

        return {
            "hourly_limit": hourly_limit,
            "sent_this_hour": hour_sent,
            "remaining": remaining,
            "can_send": remaining > 0
        }

    def _render_template(
        self,
        template_text: str,
        variables: Dict[str, str]
    ) -> str:
        """템플릿 변수 치환"""
        result = template_text
        for key, value in variables.items():
            placeholder = "{{" + key + "}}"
            result = result.replace(placeholder, str(value))
        return result

    def _generate_tracking_id(self) -> str:
        """추적 ID 생성"""
        return str(uuid.uuid4())

    def _classify_bounce(self, error_str: str, error_type: str) -> tuple:
        """
        P2: 바운스 유형 분류
        Returns: (bounce_type: str, is_hard_bounce: bool)
        """
        # Hard bounce 패턴 (영구적 - 재시도 불필요)
        hard_bounce_patterns = [
            "550",  # 사용자 없음
            "551",  # 사용자가 로컬 아님
            "553",  # 잘못된 주소 형식
            "user unknown",
            "user not found",
            "mailbox not found",
            "address rejected",
            "no such user",
            "invalid recipient",
            "does not exist",
            "undeliverable",
            "permanently rejected",
        ]

        # Soft bounce 패턴 (일시적 - 재시도 가능)
        soft_bounce_patterns = [
            "552",  # 저장 공간 초과
            "421",  # 서비스 일시 사용 불가
            "450",  # 메일박스 사용 불가
            "451",  # 로컬 오류
            "452",  # 시스템 저장 공간 부족
            "timeout",
            "connection",
            "temporarily",
            "try again",
            "rate limit",
            "too many",
            "quota",
            "mailbox full",
            "over quota",
        ]

        # Hard bounce 체크
        for pattern in hard_bounce_patterns:
            if pattern in error_str:
                return ("hard_bounce", True)

        # Soft bounce 체크
        for pattern in soft_bounce_patterns:
            if pattern in error_str:
                return ("soft_bounce", False)

        # 기본값: unknown (안전하게 soft로 처리)
        return ("unknown", False)

    async def _invalidate_contact(self, contact_id: str, reason: str):
        """
        P2: Hard bounce 시 연락처 무효화
        - 연락처를 무효 상태로 변경
        - 바운스 카운트 증가
        - 블로그 상태 업데이트
        """
        try:
            result = await self.db.execute(
                select(BlogContact).where(BlogContact.id == contact_id)
            )
            contact = result.scalar_one_or_none()

            if contact:
                contact.is_verified = False
                contact.is_primary = False  # Primary에서 제외

                # 바운스 정보 기록
                contact.bounce_count = (contact.bounce_count or 0) + 1
                contact.last_bounce_at = datetime.utcnow()
                contact.bounce_reason = reason[:200] if reason else None

                # 블로그 상태도 업데이트 (연락처가 더 없으면 INVALID로)
                if contact.blog_id:
                    blog_result = await self.db.execute(
                        select(NaverBlog).where(NaverBlog.id == contact.blog_id)
                    )
                    blog = blog_result.scalar_one_or_none()
                    if blog:
                        # 다른 유효한 연락처가 있는지 확인
                        other_contacts_result = await self.db.execute(
                            select(BlogContact).where(
                                and_(
                                    BlogContact.blog_id == contact.blog_id,
                                    BlogContact.id != contact_id,
                                    BlogContact.email.isnot(None),
                                    BlogContact.bounce_count < 3  # 바운스 3회 미만
                                )
                            )
                        )
                        other_valid_contacts = other_contacts_result.scalars().all()

                        if not other_valid_contacts:
                            # 유효한 연락처가 없으면 블로그도 INVALID
                            blog.status = BlogStatus.INVALID
                            blog.notes = f"모든 이메일 바운스: {reason}"
                        else:
                            # 다른 유효한 연락처 중 하나를 primary로 설정
                            other_valid_contacts[0].is_primary = True
                            blog.notes = f"이메일 바운스 발생, 대체 연락처로 전환: {reason}"

                logger.info(f"연락처 무효화: contact_id={contact_id}, bounce_count={contact.bounce_count}, reason={reason}")

        except Exception as e:
            logger.error(f"연락처 무효화 실패: {e}")

    def _send_email_sync(
        self,
        settings: "OutreachSetting",
        smtp_password: str,
        to_email: str,
        msg: MIMEMultipart
    ) -> None:
        """
        동기 SMTP 발송 (aiosmtplib 미설치 시 fallback)
        run_in_executor에서 호출되어 이벤트 루프 블로킹 방지
        """
        import smtplib

        if settings.smtp_use_tls:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30)

        try:
            server.login(settings.smtp_username, smtp_password)
            server.sendmail(settings.sender_email, to_email, msg.as_string())
        finally:
            server.quit()

    def _add_tracking_pixel(
        self,
        html_body: str,
        tracking_id: str,
        base_url: str
    ) -> str:
        """오픈 추적 픽셀 추가"""
        pixel = f'<img src="{base_url}/api/v1/outreach/track/open/{tracking_id}" width="1" height="1" style="display:none;" />'

        # </body> 태그 앞에 삽입
        if "</body>" in html_body:
            return html_body.replace("</body>", f"{pixel}</body>")
        else:
            return html_body + pixel

    def _add_click_tracking(
        self,
        html_body: str,
        tracking_id: str,
        base_url: str
    ) -> str:
        """링크 클릭 추적 추가"""
        # href 속성의 URL을 추적 URL로 래핑
        pattern = r'href=["\']([^"\']+)["\']'

        def replace_link(match):
            original_url = match.group(1)
            # 이미 추적 URL이거나 mailto/tel 링크는 제외
            if "track/click" in original_url or original_url.startswith(("mailto:", "tel:")):
                return match.group(0)

            import urllib.parse
            encoded_url = urllib.parse.quote(original_url, safe='')
            tracking_url = f'{base_url}/api/v1/outreach/track/click/{tracking_id}?url={encoded_url}'
            return f'href="{tracking_url}"'

        return re.sub(pattern, replace_link, html_body)

    def _create_email_html(
        self,
        body: str,
        tracking_id: str,
        settings: Optional[OutreachSetting],
        base_url: str = "https://doctorvoice.ai"
    ) -> str:
        """HTML 이메일 생성 (추적 포함)"""
        # 기본 HTML 래핑
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: 'Malgun Gothic', Arial, sans-serif; line-height: 1.6; color: #333;">
    {body}
    <br><br>
    <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
    <p style="font-size: 12px; color: #999;">
        {settings.unsubscribe_text if settings and settings.unsubscribe_text else "이 이메일 수신을 원치 않으시면 회신해 주세요."}
    </p>
</body>
</html>
"""
        # 추적 기능 추가
        if settings and settings.track_opens:
            html = self._add_tracking_pixel(html, tracking_id, base_url)

        if settings and settings.track_clicks:
            html = self._add_click_tracking(html, tracking_id, base_url)

        return html

    async def send_email(
        self,
        user_id: str,
        to_email: str,
        to_name: Optional[str],
        subject: str,
        body: str,
        blog_id: Optional[str] = None,
        campaign_id: Optional[str] = None,
        template_id: Optional[str] = None,
        contact_id: Optional[str] = None,
        sequence_number: int = 1
    ) -> Dict[str, Any]:
        """이메일 발송"""
        try:
            # 한도 확인 (await 추가 - P0 버그 수정)
            daily_check = await self._check_daily_limit(user_id)
            if not daily_check["can_send"]:
                return {
                    "success": False,
                    "error": f"일일 발송 한도 초과 ({daily_check['daily_limit']}건)"
                }

            hourly_check = await self._check_hourly_limit(user_id)
            if not hourly_check["can_send"]:
                return {
                    "success": False,
                    "error": f"시간당 발송 한도 초과 ({hourly_check['hourly_limit']}건)"
                }

            # 설정 조회 (await 추가 - P0 버그 수정)
            settings = await self._get_outreach_settings(user_id)
            if not settings or not settings.smtp_host:
                return {
                    "success": False,
                    "error": "SMTP 설정이 필요합니다"
                }

            # 추적 ID 생성
            tracking_id = self._generate_tracking_id()

            # HTML 이메일 생성
            html_body = self._create_email_html(body, tracking_id, settings)

            # 이메일 로그 생성
            email_log = EmailLog(
                user_id=user_id,
                campaign_id=campaign_id,
                blog_id=blog_id,
                contact_id=contact_id,
                template_id=template_id,
                to_email=to_email,
                to_name=to_name,
                subject=subject,
                body=html_body,
                from_email=settings.sender_email,
                from_name=settings.sender_name,
                tracking_id=tracking_id,
                status=EmailStatus.PENDING,
                sequence_number=sequence_number
            )
            self.db.add(email_log)
            self.db.flush()

            # SMTP 발송 (비동기로 변경 - P0 성능 개선)
            try:
                # 이메일 메시지 구성
                msg = MIMEMultipart('alternative')
                msg['From'] = f"{settings.sender_name} <{settings.sender_email}>"
                msg['To'] = f"{to_name} <{to_email}>" if to_name else to_email
                msg['Subject'] = subject

                # 텍스트 버전 (HTML 태그 제거)
                text_body = re.sub(r'<[^>]+>', '', body)
                msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
                msg.attach(MIMEText(html_body, 'html', 'utf-8'))

                # SMTP 연결 및 발송
                smtp_password = self.decrypt_password(settings.smtp_password_encrypted) if settings.smtp_password_encrypted else ""

                # 비동기 SMTP 발송 (aiosmtplib 사용)
                if HAS_AIOSMTPLIB:
                    if settings.smtp_use_tls:
                        # STARTTLS 방식
                        await aiosmtplib.send(
                            msg,
                            hostname=settings.smtp_host,
                            port=settings.smtp_port,
                            username=settings.smtp_username,
                            password=smtp_password,
                            start_tls=True,
                            timeout=30
                        )
                    else:
                        # SSL 방식
                        await aiosmtplib.send(
                            msg,
                            hostname=settings.smtp_host,
                            port=settings.smtp_port,
                            username=settings.smtp_username,
                            password=smtp_password,
                            use_tls=True,
                            timeout=30
                        )
                else:
                    # Fallback: 동기 smtplib (aiosmtplib 미설치 시)
                    # run_in_executor로 이벤트 루프 블로킹 방지
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None,
                        self._send_email_sync,
                        settings,
                        smtp_password,
                        to_email,
                        msg
                    )

                # 발송 성공 업데이트
                email_log.status = EmailStatus.SENT
                email_log.sent_at = datetime.utcnow()

                # 블로그 상태 업데이트
                if blog_id:
                    blog_result = await self.db.execute(
                        select(NaverBlog).where(NaverBlog.id == blog_id)
                    )
                    blog = blog_result.scalar_one_or_none()
                    if blog:
                        blog.status = BlogStatus.CONTACTED
                        blog.updated_at = datetime.utcnow()

                await self.db.commit()

                return {
                    "success": True,
                    "email_log_id": email_log.id,
                    "tracking_id": tracking_id
                }

            except Exception as smtp_error:
                # P2: 개선된 바운스 감지 - Hard/Soft bounce 구분
                error_str = str(smtp_error).lower()
                error_type = type(smtp_error).__name__.lower()

                # 바운스 유형 분류
                bounce_type, is_hard_bounce = self._classify_bounce(error_str, error_type)

                email_log.status = EmailStatus.BOUNCED
                email_log.error_message = f"[{bounce_type}] {str(smtp_error)}"
                email_log.bounced_at = datetime.utcnow()

                # P2: Hard bounce인 경우 연락처 자동 무효화
                if is_hard_bounce and contact_id:
                    await self._invalidate_contact(contact_id, bounce_type)

                await self.db.commit()

                # 인증 오류 (Soft bounce - 발신자 문제)
                if "auth" in error_str or "authentication" in error_str or "login" in error_str:
                    return {
                        "success": False,
                        "error": "SMTP 인증 실패",
                        "error_code": "SMTP_AUTH_ERROR",
                        "bounce_type": "soft",
                        "user_message": "SMTP 로그인에 실패했습니다. 이메일 주소와 비밀번호(앱 비밀번호)를 확인해주세요.",
                        "action_required": "설정 > 이메일 설정에서 SMTP 정보를 확인해주세요.",
                        "help_url": "/dashboard/outreach/smtp-guide"
                    }

                # 연결 오류 (Soft bounce - 일시적 문제)
                elif "connect" in error_str or "connection" in error_str or "refused" in error_type:
                    return {
                        "success": False,
                        "error": "SMTP 서버 연결 실패",
                        "error_code": "SMTP_CONNECT_ERROR",
                        "bounce_type": "soft",
                        "user_message": "SMTP 서버에 연결할 수 없습니다. 호스트 주소와 포트를 확인해주세요.",
                        "action_required": "SMTP 호스트: smtp.gmail.com (Gmail), smtp.naver.com (네이버) 등을 확인하세요.",
                        "help_url": "/dashboard/outreach/smtp-guide"
                    }

                # 수신자 거부 - Hard bounce 케이스 분류
                elif "550" in error_str or "551" in error_str or "552" in error_str or "553" in error_str or "554" in error_str:
                    # 550: 사용자 없음 (Hard)
                    # 551: 사용자가 로컬 아님 (Hard)
                    # 552: 저장 공간 초과 (Soft)
                    # 553: 잘못된 주소 형식 (Hard)
                    # 554: 트랜잭션 실패 (상황에 따라 다름)
                    if "550" in error_str or "551" in error_str or "553" in error_str:
                        return {
                            "success": False,
                            "error": "수신자 이메일 주소 없음",
                            "error_code": "HARD_BOUNCE_USER_NOT_FOUND",
                            "bounce_type": "hard",
                            "is_permanent": True,
                            "contact_invalidated": is_hard_bounce and contact_id is not None,
                            "user_message": f"수신자 이메일 주소({to_email})가 존재하지 않습니다. 이 연락처는 자동으로 무효 처리됩니다.",
                            "action_required": "다른 연락처를 사용하거나 이 블로그를 목록에서 제외해주세요."
                        }
                    else:
                        return {
                            "success": False,
                            "error": "수신자 메일함 문제",
                            "error_code": "SOFT_BOUNCE_MAILBOX",
                            "bounce_type": "soft",
                            "user_message": f"수신자({to_email})의 메일함에 일시적 문제가 있습니다. 나중에 다시 시도해주세요.",
                            "action_required": "1-2일 후 다시 시도해주세요."
                        }

                # 수신자 거부 (일반)
                elif "recipient" in error_str or "rcpt" in error_str:
                    return {
                        "success": False,
                        "error": "수신자 이메일 거부",
                        "error_code": "RECIPIENT_REFUSED",
                        "bounce_type": "hard",
                        "is_permanent": True,
                        "contact_invalidated": is_hard_bounce and contact_id is not None,
                        "user_message": f"수신자 이메일 주소({to_email})가 유효하지 않거나 수신을 거부했습니다.",
                        "action_required": "수신자 이메일 주소를 확인하거나 다른 연락처를 시도해주세요."
                    }

                # 타임아웃 (Soft bounce)
                elif "timeout" in error_str or "timed out" in error_str:
                    return {
                        "success": False,
                        "error": "SMTP 서버 응답 시간 초과",
                        "error_code": "SMTP_TIMEOUT",
                        "bounce_type": "soft",
                        "user_message": "SMTP 서버가 응답하지 않습니다. 잠시 후 다시 시도해주세요.",
                        "action_required": "네트워크 연결을 확인하고 잠시 후 다시 시도해주세요."
                    }

                # Rate limit (Soft bounce)
                elif "rate limit" in error_str or "too many" in error_str or "quota" in error_str:
                    return {
                        "success": False,
                        "error": "발송 한도 초과 (SMTP 서버)",
                        "error_code": "SMTP_RATE_LIMIT",
                        "bounce_type": "soft",
                        "user_message": "SMTP 서버의 발송 한도를 초과했습니다. 잠시 후 다시 시도해주세요.",
                        "action_required": "1시간 정도 후에 다시 시도하거나, 일일 발송량을 줄여주세요."
                    }

                # 기타 SMTP 오류
                else:
                    return {
                        "success": False,
                        "error": f"SMTP 발송 오류: {str(smtp_error)}",
                        "error_code": "SMTP_ERROR",
                        "bounce_type": bounce_type,
                        "user_message": "이메일 발송 중 오류가 발생했습니다.",
                        "action_required": "SMTP 설정을 확인하고 다시 시도해주세요.",
                        "technical_detail": str(smtp_error)
                    }

        except Exception as e:
            logger.error(f"이메일 발송 오류: {e}")
            await self.db.rollback()
            return {
                "success": False,
                "error": "이메일 발송 중 예기치 않은 오류",
                "error_code": "UNEXPECTED_ERROR",
                "user_message": "이메일 발송 중 예기치 않은 오류가 발생했습니다.",
                "action_required": "잠시 후 다시 시도하거나, 관리자에게 문의해주세요.",
                "technical_detail": str(e)
            }

    async def send_with_template(
        self,
        user_id: str,
        blog_id: str,
        template_id: str,
        campaign_id: Optional[str] = None,
        custom_variables: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """템플릿으로 이메일 발송"""
        try:
            # 블로그 및 연락처 조회
            blog_result = await self.db.execute(
                select(NaverBlog).where(and_(
                    NaverBlog.id == blog_id,
                    NaverBlog.user_id == user_id
                ))
            )
            blog = blog_result.scalar_one_or_none()

            if not blog:
                return {"success": False, "error": "블로그를 찾을 수 없습니다"}

            # 기본 연락처 조회
            contact_result = await self.db.execute(
                select(BlogContact).where(and_(
                    BlogContact.blog_id == blog_id,
                    BlogContact.is_primary == True
                ))
            )
            contact = contact_result.scalar_one_or_none()

            if not contact:
                contact_result2 = await self.db.execute(
                    select(BlogContact).where(and_(
                        BlogContact.blog_id == blog_id,
                        BlogContact.email.isnot(None)
                    ))
                )
                contact = contact_result2.scalar_one_or_none()

            if not contact or not contact.email:
                return {"success": False, "error": "이메일 연락처가 없습니다"}

            # 템플릿 조회
            template_result = await self.db.execute(
                select(EmailTemplate).where(and_(
                    EmailTemplate.id == template_id,
                    EmailTemplate.user_id == user_id
                ))
            )
            template = template_result.scalar_one_or_none()

            if not template:
                return {"success": False, "error": "템플릿을 찾을 수 없습니다"}

            # 설정 조회
            settings = await self._get_outreach_settings(user_id)

            # 변수 준비
            variables = {
                "blog_name": blog.blog_name or blog.owner_nickname or "블로거",
                "blog_nickname": blog.owner_nickname or "블로거",
                "blog_url": blog.blog_url,
                "sender_name": settings.sender_name if settings else "",
                "company_name": settings.company_name if settings else "",
                "service_name": settings.service_name if settings else "",
                "service_description": settings.service_description if settings else ""
            }

            # 사용자 정의 변수 추가
            if custom_variables:
                variables.update(custom_variables)

            # 템플릿 렌더링
            rendered_subject = self._render_template(template.subject, variables)
            rendered_body = self._render_template(template.body, variables)

            # 이메일 발송
            result = await self.send_email(
                user_id=user_id,
                to_email=contact.email,
                to_name=blog.owner_nickname,
                subject=rendered_subject,
                body=rendered_body,
                blog_id=blog_id,
                campaign_id=campaign_id,
                template_id=template_id,
                contact_id=contact.id
            )

            # 템플릿 사용 횟수 증가
            if result["success"]:
                template.usage_count = (template.usage_count or 0) + 1
                await self.db.commit()

            return result

        except Exception as e:
            logger.error(f"템플릿 이메일 발송 오류: {e}")
            await self.db.rollback()
            return {"success": False, "error": str(e)}

    async def send_campaign_batch(
        self,
        user_id: str,
        campaign_id: str,
        batch_size: int = 10
    ) -> Dict[str, Any]:
        """캠페인 배치 발송"""
        try:
            # 캠페인 조회
            campaign_result = await self.db.execute(
                select(EmailCampaign).where(and_(
                    EmailCampaign.id == campaign_id,
                    EmailCampaign.user_id == user_id
                ))
            )
            campaign = campaign_result.scalar_one_or_none()

            if not campaign:
                return {"success": False, "error": "캠페인을 찾을 수 없습니다"}

            if campaign.status != CampaignStatus.ACTIVE:
                return {"success": False, "error": "활성 상태의 캠페인이 아닙니다"}

            # 한도 확인
            daily_check = await self._check_daily_limit(user_id)
            batch_size = min(batch_size, daily_check["remaining"])

            if batch_size <= 0:
                return {
                    "success": False,
                    "error": "일일 발송 한도 초과"
                }

            # 이미 발송된 블로그 ID 목록 조회
            sent_result = await self.db.execute(
                select(EmailLog.blog_id).where(EmailLog.campaign_id == campaign_id)
            )
            sent_blog_ids = [row[0] for row in sent_result.all()]

            # 타겟 블로그 조회 조건
            conditions = [
                NaverBlog.user_id == user_id,
                NaverBlog.has_contact == True,
                NaverBlog.status.notin_([BlogStatus.CONTACTED, BlogStatus.NOT_INTERESTED, BlogStatus.INVALID])
            ]

            if sent_blog_ids:
                conditions.append(NaverBlog.id.notin_(sent_blog_ids))

            # 등급 필터
            if campaign.target_grades:
                target_grades = [LeadGrade(g) for g in campaign.target_grades]
                conditions.append(NaverBlog.lead_grade.in_(target_grades))

            # 최소 점수 필터
            if campaign.min_score:
                conditions.append(NaverBlog.lead_score >= campaign.min_score)

            # 정렬 및 제한
            blogs_result = await self.db.execute(
                select(NaverBlog).where(and_(*conditions)).order_by(
                    NaverBlog.lead_score.desc()
                ).limit(batch_size)
            )
            blogs = blogs_result.scalars().all()

            if not blogs:
                return {
                    "success": True,
                    "message": "발송 대상이 없습니다",
                    "sent": 0
                }

            # 템플릿 시퀀스에서 첫 번째 템플릿 가져오기
            templates = campaign.templates or []
            if not templates:
                return {"success": False, "error": "캠페인에 템플릿이 없습니다"}

            first_template_id = templates[0].get("template_id")
            if not first_template_id:
                return {"success": False, "error": "템플릿 ID가 없습니다"}

            # 배치 발송
            results = {
                "sent": 0,
                "failed": 0,
                "errors": []
            }

            settings = await self._get_outreach_settings(user_id)
            min_interval = settings.min_interval_seconds if settings else 300

            for blog in blogs:
                result = await self.send_with_template(
                    user_id=user_id,
                    blog_id=blog.id,
                    template_id=first_template_id,
                    campaign_id=campaign_id
                )

                if result["success"]:
                    results["sent"] += 1
                    campaign.total_sent = (campaign.total_sent or 0) + 1
                else:
                    results["failed"] += 1
                    results["errors"].append({
                        "blog_id": blog.id,
                        "error": result.get("error")
                    })

                # 발송 간격 대기
                if min_interval > 0 and results["sent"] < len(blogs):
                    await asyncio.sleep(min_interval)

            await self.db.commit()

            return {
                "success": True,
                "results": results
            }

        except Exception as e:
            logger.error(f"캠페인 배치 발송 오류: {e}")
            await self.db.rollback()
            return {"success": False, "error": str(e)}

    async def track_open(self, tracking_id: str) -> bool:
        """오픈 추적"""
        try:
            result = await self.db.execute(
                select(EmailLog).where(EmailLog.tracking_id == tracking_id)
            )
            email_log = result.scalar_one_or_none()

            if email_log and email_log.status == EmailStatus.SENT:
                email_log.status = EmailStatus.OPENED
                email_log.opened_at = datetime.utcnow()

                # 캠페인 통계 업데이트
                if email_log.campaign_id:
                    campaign_result = await self.db.execute(
                        select(EmailCampaign).where(EmailCampaign.id == email_log.campaign_id)
                    )
                    campaign = campaign_result.scalar_one_or_none()
                    if campaign:
                        campaign.total_opened = (campaign.total_opened or 0) + 1

                await self.db.commit()
                return True

            return False

        except Exception as e:
            logger.error(f"오픈 추적 오류: {e}")
            return False

    async def track_click(self, tracking_id: str, url: str) -> bool:
        """클릭 추적"""
        try:
            result = await self.db.execute(
                select(EmailLog).where(EmailLog.tracking_id == tracking_id)
            )
            email_log = result.scalar_one_or_none()

            if email_log:
                if email_log.status in [EmailStatus.SENT, EmailStatus.OPENED]:
                    email_log.status = EmailStatus.CLICKED
                email_log.clicked_at = datetime.utcnow()

                # 캠페인 통계 업데이트
                if email_log.campaign_id:
                    campaign_result = await self.db.execute(
                        select(EmailCampaign).where(EmailCampaign.id == email_log.campaign_id)
                    )
                    campaign = campaign_result.scalar_one_or_none()
                    if campaign:
                        campaign.total_clicked = (campaign.total_clicked or 0) + 1

                await self.db.commit()
                return True

            return False

        except Exception as e:
            logger.error(f"클릭 추적 오류: {e}")
            return False

    async def mark_replied(self, email_log_id: str) -> bool:
        """회신 마킹"""
        try:
            result = await self.db.execute(
                select(EmailLog).where(EmailLog.id == email_log_id)
            )
            email_log = result.scalar_one_or_none()

            if email_log:
                email_log.status = EmailStatus.REPLIED
                email_log.replied_at = datetime.utcnow()

                # 블로그 상태 업데이트
                if email_log.blog_id:
                    blog_result = await self.db.execute(
                        select(NaverBlog).where(NaverBlog.id == email_log.blog_id)
                    )
                    blog = blog_result.scalar_one_or_none()
                    if blog:
                        blog.status = BlogStatus.RESPONDED
                        blog.updated_at = datetime.utcnow()

                # 캠페인 통계 업데이트
                if email_log.campaign_id:
                    campaign_result = await self.db.execute(
                        select(EmailCampaign).where(EmailCampaign.id == email_log.campaign_id)
                    )
                    campaign = campaign_result.scalar_one_or_none()
                    if campaign:
                        campaign.total_replied = (campaign.total_replied or 0) + 1

                await self.db.commit()
                return True

            return False

        except Exception as e:
            logger.error(f"회신 마킹 오류: {e}")
            return False

    async def get_sending_stats(self, user_id: str) -> Dict[str, Any]:
        """발송 통계"""
        settings = await self._get_outreach_settings(user_id)

        # 오늘 통계
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_result = await self.db.execute(
            select(EmailLog).where(and_(
                EmailLog.user_id == user_id,
                EmailLog.created_at >= today_start
            ))
        )
        today_logs = today_result.scalars().all()

        today_stats = {
            "sent": 0,
            "opened": 0,
            "clicked": 0,
            "replied": 0,
            "bounced": 0
        }

        for log in today_logs:
            if log.status == EmailStatus.SENT:
                today_stats["sent"] += 1
            elif log.status == EmailStatus.OPENED:
                today_stats["sent"] += 1
                today_stats["opened"] += 1
            elif log.status == EmailStatus.CLICKED:
                today_stats["sent"] += 1
                today_stats["opened"] += 1
                today_stats["clicked"] += 1
            elif log.status == EmailStatus.REPLIED:
                today_stats["sent"] += 1
                today_stats["opened"] += 1
                today_stats["replied"] += 1
            elif log.status == EmailStatus.BOUNCED:
                today_stats["bounced"] += 1

        # 전체 통계
        all_result = await self.db.execute(
            select(EmailLog).where(EmailLog.user_id == user_id)
        )
        all_logs = all_result.scalars().all()

        total_stats = {
            "total": len(all_logs),
            "sent": sum(1 for l in all_logs if l.status not in [EmailStatus.PENDING, EmailStatus.BOUNCED]),
            "opened": sum(1 for l in all_logs if l.status in [EmailStatus.OPENED, EmailStatus.CLICKED, EmailStatus.REPLIED]),
            "clicked": sum(1 for l in all_logs if l.status in [EmailStatus.CLICKED, EmailStatus.REPLIED]),
            "replied": sum(1 for l in all_logs if l.status == EmailStatus.REPLIED),
            "bounced": sum(1 for l in all_logs if l.status == EmailStatus.BOUNCED)
        }

        # 비율 계산
        if total_stats["sent"] > 0:
            total_stats["open_rate"] = round(total_stats["opened"] / total_stats["sent"] * 100, 1)
            total_stats["click_rate"] = round(total_stats["clicked"] / total_stats["sent"] * 100, 1)
            total_stats["reply_rate"] = round(total_stats["replied"] / total_stats["sent"] * 100, 1)
        else:
            total_stats["open_rate"] = 0
            total_stats["click_rate"] = 0
            total_stats["reply_rate"] = 0

        return {
            "today": today_stats,
            "total": total_stats,
            "limits": {
                "daily": await self._check_daily_limit(user_id),
                "hourly": await self._check_hourly_limit(user_id)
            }
        }
