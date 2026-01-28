"""
정기결제 이메일 알림 서비스
결제 예정, 완료, 실패, 해지 등 알림 발송
"""
import logging
from datetime import datetime
from typing import Optional
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

# 이메일 발송 서비스 설정
# console: 로그로 출력 (개발용)
# smtp: SMTP 서버를 통한 발송 (Gmail, Naver 등)
# sendgrid/ses: 외부 이메일 서비스 (추후 구현)
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@platonmarketing.com")
EMAIL_SERVICE = os.getenv("EMAIL_SERVICE", "console")  # console, smtp, sendgrid, ses

# P3 Fix: SMTP 설정
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"


class BillingNotificationService:
    """정기결제 알림 서비스"""

    def __init__(self):
        self.email_from = EMAIL_FROM

    async def _send_email(self, to: str, subject: str, html_content: str):
        """
        이메일 발송

        지원 서비스:
        - console: 개발용 (로그로 출력)
        - smtp: SMTP 서버를 통한 발송 (Gmail, Naver, 회사 메일 등)
        """
        if EMAIL_SERVICE == "console":
            logger.info(f"""
========== 이메일 발송 ==========
To: {to}
Subject: {subject}
--------------------------------
{html_content}
================================
            """)
            return True

        # P3 Fix: SMTP 이메일 발송 구현
        if EMAIL_SERVICE == "smtp":
            try:
                if not SMTP_USER or not SMTP_PASSWORD:
                    logger.error("SMTP credentials not configured (SMTP_USER, SMTP_PASSWORD)")
                    return False

                # MIME 메시지 생성
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = self.email_from
                msg["To"] = to

                # HTML 본문 추가
                html_part = MIMEText(html_content, "html", "utf-8")
                msg.attach(html_part)

                # SMTP 서버 연결 및 발송
                with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                    if SMTP_USE_TLS:
                        server.starttls()
                    server.login(SMTP_USER, SMTP_PASSWORD)
                    server.sendmail(self.email_from, to, msg.as_string())

                logger.info(f"이메일 발송 성공: {to}")
                return True

            except smtplib.SMTPAuthenticationError:
                logger.error(f"SMTP 인증 실패: {SMTP_USER}")
                return False
            except smtplib.SMTPException as e:
                logger.error(f"SMTP 오류: {e}")
                return False
            except Exception as e:
                logger.error(f"이메일 발송 실패: {e}")
                return False

        # 기타 서비스 (sendgrid, ses 등)는 추후 구현
        logger.warning(f"Unsupported email service: {EMAIL_SERVICE}")
        return False

    async def send_renewal_notice(
        self,
        email: str,
        user_name: str,
        plan_name: str,
        amount: int,
        billing_date: datetime,
        card_info: Optional[str] = None
    ):
        """
        결제 예정 알림 (7일 전)
        전자상거래법에 따라 결제 7일 전 안내 필수
        """
        subject = f"[닥터보이스 프로] {plan_name} 플랜 결제 예정 안내"

        html_content = f"""
        <div style="font-family: 'Noto Sans KR', sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2563eb;">결제 예정 안내</h2>

            <p>{user_name}님, 안녕하세요.</p>

            <p>구독 중이신 <strong>{plan_name}</strong> 플랜의 다음 결제일이 다가왔습니다.</p>

            <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p><strong>결제 정보</strong></p>
                <ul style="list-style: none; padding: 0;">
                    <li>플랜: {plan_name}</li>
                    <li>결제 금액: {amount:,}원</li>
                    <li>결제 예정일: {billing_date.strftime('%Y년 %m월 %d일')}</li>
                    {f'<li>결제 수단: {card_info}</li>' if card_info else ''}
                </ul>
            </div>

            <p>구독을 유지하시면 결제 예정일에 자동으로 결제됩니다.</p>

            <div style="background: #fef3c7; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <p style="margin: 0; color: #92400e;">
                    <strong>해지를 원하시나요?</strong><br>
                    결제일 전까지 아래 버튼을 통해 구독을 해지할 수 있습니다.
                </p>
            </div>

            <div style="text-align: center; margin: 30px 0;">
                <a href="https://doctorvoice.pro/subscription/manage"
                   style="background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                    구독 관리하기
                </a>
            </div>

            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">

            <p style="color: #6b7280; font-size: 12px;">
                본 메일은 전자상거래 등에서의 소비자보호에 관한 법률에 따라 발송되었습니다.<br>
                문의: support@platonmarketing.com
            </p>
        </div>
        """

        await self._send_email(email, subject, html_content)

    async def send_payment_success(
        self,
        email: str,
        user_name: str,
        plan_name: str,
        amount: int,
        next_billing_date: datetime
    ):
        """결제 완료 알림"""
        subject = f"[닥터보이스 프로] {plan_name} 플랜 결제 완료"

        html_content = f"""
        <div style="font-family: 'Noto Sans KR', sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #059669;">결제가 완료되었습니다</h2>

            <p>{user_name}님, 안녕하세요.</p>

            <p><strong>{plan_name}</strong> 플랜 결제가 정상적으로 완료되었습니다.</p>

            <div style="background: #ecfdf5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p><strong>결제 내역</strong></p>
                <ul style="list-style: none; padding: 0;">
                    <li>플랜: {plan_name}</li>
                    <li>결제 금액: {amount:,}원</li>
                    <li>결제일: {datetime.utcnow().strftime('%Y년 %m월 %d일')}</li>
                    <li>다음 결제일: {next_billing_date.strftime('%Y년 %m월 %d일')}</li>
                </ul>
            </div>

            <p>감사합니다. 닥터보이스 프로를 이용해 주셔서 감사합니다.</p>

            <div style="text-align: center; margin: 30px 0;">
                <a href="https://doctorvoice.pro/dashboard"
                   style="background: #059669; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                    대시보드 바로가기
                </a>
            </div>

            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">

            <p style="color: #6b7280; font-size: 12px;">
                결제 영수증은 대시보드 > 결제 내역에서 확인하실 수 있습니다.<br>
                문의: support@platonmarketing.com
            </p>
        </div>
        """

        await self._send_email(email, subject, html_content)

    async def send_payment_failed(
        self,
        email: str,
        user_name: str,
        plan_name: str,
        amount: int,
        retry_count: int,
        error_message: Optional[str] = None
    ):
        """결제 실패 알림"""
        subject = f"[닥터보이스 프로] 결제 실패 안내"

        remaining_retry = 3 - retry_count

        html_content = f"""
        <div style="font-family: 'Noto Sans KR', sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #dc2626;">결제에 실패했습니다</h2>

            <p>{user_name}님, 안녕하세요.</p>

            <p><strong>{plan_name}</strong> 플랜의 정기결제가 실패했습니다.</p>

            <div style="background: #fef2f2; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p><strong>결제 정보</strong></p>
                <ul style="list-style: none; padding: 0;">
                    <li>플랜: {plan_name}</li>
                    <li>결제 금액: {amount:,}원</li>
                    {f'<li>실패 사유: {error_message}</li>' if error_message else ''}
                    <li>재시도 횟수: {retry_count}/3회</li>
                </ul>
            </div>

            {f'''
            <div style="background: #fef3c7; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <p style="margin: 0; color: #92400e;">
                    <strong>자동 재시도 예정</strong><br>
                    3일 후 자동으로 결제를 재시도합니다. (남은 재시도: {remaining_retry}회)
                </p>
            </div>
            ''' if remaining_retry > 0 else '''
            <div style="background: #fef2f2; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <p style="margin: 0; color: #dc2626;">
                    <strong>구독이 일시 중지되었습니다</strong><br>
                    결제 수단을 확인하시고 새로운 카드를 등록해 주세요.
                </p>
            </div>
            '''}

            <p>카드 한도, 유효기간 등을 확인해 주세요.</p>

            <div style="text-align: center; margin: 30px 0;">
                <a href="https://doctorvoice.pro/subscription/manage"
                   style="background: #dc2626; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                    결제 수단 변경하기
                </a>
            </div>

            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">

            <p style="color: #6b7280; font-size: 12px;">
                문의: support@platonmarketing.com
            </p>
        </div>
        """

        await self._send_email(email, subject, html_content)

    async def send_subscription_cancelled(
        self,
        email: str,
        user_name: str,
        plan_name: str
    ):
        """구독 해지 완료 알림"""
        subject = f"[닥터보이스 프로] {plan_name} 플랜 구독 해지 완료"

        html_content = f"""
        <div style="font-family: 'Noto Sans KR', sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #6b7280;">구독이 해지되었습니다</h2>

            <p>{user_name}님, 안녕하세요.</p>

            <p><strong>{plan_name}</strong> 플랜 구독이 해지되었습니다.</p>

            <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p>이용해 주셔서 감사합니다.</p>
                <p>계정과 데이터는 30일간 보관됩니다.</p>
            </div>

            <p>언제든 다시 구독하실 수 있습니다.</p>

            <div style="text-align: center; margin: 30px 0;">
                <a href="https://doctorvoice.pro/pricing"
                   style="background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                    다시 구독하기
                </a>
            </div>

            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">

            <p style="color: #6b7280; font-size: 12px;">
                문의: support@platonmarketing.com
            </p>
        </div>
        """

        await self._send_email(email, subject, html_content)

    async def send_subscription_expired(
        self,
        email: str,
        user_name: str,
        plan_name: str
    ):
        """구독 만료 알림 (결제 실패로 인한 만료)"""
        subject = f"[닥터보이스 프로] 구독이 만료되었습니다"

        html_content = f"""
        <div style="font-family: 'Noto Sans KR', sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #dc2626;">구독이 만료되었습니다</h2>

            <p>{user_name}님, 안녕하세요.</p>

            <p>결제 실패로 인해 <strong>{plan_name}</strong> 플랜 구독이 만료되었습니다.</p>

            <div style="background: #fef2f2; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p><strong>서비스 이용이 제한됩니다</strong></p>
                <ul style="padding-left: 20px;">
                    <li>글 생성 기능 제한</li>
                    <li>분석 기능 제한</li>
                    <li>기존 데이터는 30일간 보관</li>
                </ul>
            </div>

            <p>새로운 결제 수단을 등록하시면 바로 서비스를 재개하실 수 있습니다.</p>

            <div style="text-align: center; margin: 30px 0;">
                <a href="https://doctorvoice.pro/subscription/manage"
                   style="background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                    결제 수단 등록하기
                </a>
            </div>

            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">

            <p style="color: #6b7280; font-size: 12px;">
                문의: support@platonmarketing.com
            </p>
        </div>
        """

        await self._send_email(email, subject, html_content)

    async def send_trial_ending_notice(
        self,
        email: str,
        user_name: str,
        plan_name: str,
        amount: int,
        trial_end_date: datetime
    ):
        """트라이얼 종료 예정 알림 (7일 전)"""
        subject = f"[닥터보이스 프로] 무료체험 종료 안내"

        html_content = f"""
        <div style="font-family: 'Noto Sans KR', sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2563eb;">무료체험이 곧 종료됩니다</h2>

            <p>{user_name}님, 안녕하세요.</p>

            <p><strong>{plan_name}</strong> 플랜 무료체험이 곧 종료됩니다.</p>

            <div style="background: #dbeafe; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p><strong>무료체험 정보</strong></p>
                <ul style="list-style: none; padding: 0;">
                    <li>종료일: {trial_end_date.strftime('%Y년 %m월 %d일')}</li>
                    <li>전환 후 금액: 월 {amount:,}원</li>
                </ul>
            </div>

            <p>결제 수단이 등록되어 있다면 무료체험 종료 후 자동으로 유료 구독으로 전환됩니다.</p>

            <div style="background: #fef3c7; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <p style="margin: 0; color: #92400e;">
                    유료 전환을 원하지 않으시면 무료체험 기간 내 해지해 주세요.
                </p>
            </div>

            <div style="text-align: center; margin: 30px 0;">
                <a href="https://doctorvoice.pro/subscription/manage"
                   style="background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                    구독 관리하기
                </a>
            </div>

            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">

            <p style="color: #6b7280; font-size: 12px;">
                본 메일은 전자상거래 등에서의 소비자보호에 관한 법률에 따라 발송되었습니다.<br>
                문의: support@platonmarketing.com
            </p>
        </div>
        """

        await self._send_email(email, subject, html_content)
