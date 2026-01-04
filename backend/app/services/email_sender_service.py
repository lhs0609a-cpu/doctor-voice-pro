"""
이메일 발송 서비스
SMTP를 통한 이메일 발송, 템플릿 렌더링, 추적 기능
"""
import logging
import smtplib
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
            # 한도 확인
            daily_check = self._check_daily_limit(user_id)
            if not daily_check["can_send"]:
                return {
                    "success": False,
                    "error": f"일일 발송 한도 초과 ({daily_check['daily_limit']}건)"
                }

            hourly_check = self._check_hourly_limit(user_id)
            if not hourly_check["can_send"]:
                return {
                    "success": False,
                    "error": f"시간당 발송 한도 초과 ({hourly_check['hourly_limit']}건)"
                }

            # 설정 조회
            settings = self._get_outreach_settings(user_id)
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

            # SMTP 발송
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

                if settings.smtp_use_tls:
                    server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
                    server.starttls()
                else:
                    server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port)

                server.login(settings.smtp_username, smtp_password)
                server.sendmail(settings.sender_email, to_email, msg.as_string())
                server.quit()

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

            except smtplib.SMTPException as e:
                email_log.status = EmailStatus.BOUNCED
                email_log.error_message = str(e)
                email_log.bounced_at = datetime.utcnow()
                await self.db.commit()

                return {
                    "success": False,
                    "error": f"SMTP 발송 오류: {str(e)}"
                }

        except Exception as e:
            logger.error(f"이메일 발송 오류: {e}")
            await self.db.rollback()
            return {"success": False, "error": str(e)}

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
