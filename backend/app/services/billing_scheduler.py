"""
정기결제 스케줄러 서비스
매일 실행되어 구독 갱신, 결제 재시도, 알림 발송을 처리합니다.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.subscription import (
    Subscription, SubscriptionStatus, Payment, PaymentStatus
)
from app.services.toss_payments import TossPaymentsService
from app.services.billing_notification import BillingNotificationService

logger = logging.getLogger(__name__)


class BillingSchedulerService:
    """정기결제 스케줄러"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.toss_service = TossPaymentsService()
        self.notification_service = BillingNotificationService()
        self._running = False

    async def run_all_jobs(self):
        """모든 정기결제 작업 실행 (매일 1회 실행 권장)"""
        logger.info("정기결제 스케줄러 시작")

        try:
            # 1. 결제 7일 전 알림 발송
            await self.send_renewal_notices()

            # 2. 만료 예정 구독 자동 결제
            await self.process_renewals()

            # 3. 실패한 결제 재시도
            await self.retry_failed_payments()

            # 4. 해지 예정 구독 처리
            await self.process_cancellations()

            # 5. 만료된 트라이얼 처리
            await self.process_expired_trials()

            logger.info("정기결제 스케줄러 완료")
        except Exception as e:
            logger.error(f"정기결제 스케줄러 오류: {e}")

    async def send_renewal_notices(self):
        """
        결제 7일 전 이메일 알림 발송
        전자상거래법에 따라 결제 7일 전 안내 필수
        """
        logger.info("결제 예정 알림 발송 시작")

        now = datetime.utcnow()
        seven_days_later = now + timedelta(days=7)

        # 7일 후 만료되고, 아직 알림 안 보낸 구독 조회
        stmt = select(Subscription).where(
            and_(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.cancel_at_period_end == False,
                Subscription.billing_key != None,
                Subscription.renewal_notice_sent == False,
                Subscription.current_period_end <= seven_days_later,
                Subscription.current_period_end > now
            )
        )
        result = await self.db.execute(stmt)
        subscriptions = result.scalars().all()

        sent_count = 0
        for sub in subscriptions:
            try:
                # 사용자, 플랜 정보 로드
                await self.db.refresh(sub, ["user", "plan"])

                if sub.user and sub.user.email and sub.plan:
                    # 이메일 발송
                    await self.notification_service.send_renewal_notice(
                        email=sub.user.email,
                        user_name=sub.user.name or sub.user.email,
                        plan_name=sub.plan.name,
                        amount=sub.plan.price_monthly,
                        billing_date=sub.current_period_end,
                        card_info=f"{sub.card_company} ****{sub.card_number_last4}" if sub.card_company else None
                    )

                    # 알림 발송 기록
                    sub.renewal_notice_sent = True
                    sub.renewal_notice_sent_at = now
                    sent_count += 1

            except Exception as e:
                logger.error(f"알림 발송 실패 (subscription_id={sub.id}): {e}")

        await self.db.commit()
        logger.info(f"결제 예정 알림 발송 완료: {sent_count}건")

    async def process_renewals(self):
        """
        만료 예정 구독 자동 결제
        현재 기간 종료일이 오늘이거나 지난 구독 처리
        """
        logger.info("구독 갱신 처리 시작")

        now = datetime.utcnow()

        # 오늘 또는 이미 만료된 활성 구독 (해지 예정 아닌 것)
        stmt = select(Subscription).where(
            and_(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.cancel_at_period_end == False,
                Subscription.billing_key != None,
                Subscription.current_period_end <= now
            )
        )
        result = await self.db.execute(stmt)
        subscriptions = result.scalars().all()

        success_count = 0
        fail_count = 0

        for sub in subscriptions:
            try:
                await self.db.refresh(sub, ["plan"])

                if not sub.plan:
                    continue

                # 결제 실행
                order_id = f"renewal_{sub.id}_{int(now.timestamp())}"

                charge_result = await self.toss_service.billing_payment(
                    billing_key=sub.billing_key,
                    customer_key=sub.customer_key,
                    amount=sub.plan.price_monthly,
                    order_id=order_id,
                    order_name=f"{sub.plan.name} 플랜 정기결제"
                )

                if charge_result.get("success"):
                    # 결제 성공 - 구독 기간 갱신
                    sub.current_period_start = now
                    sub.current_period_end = now + timedelta(days=30)
                    sub.retry_count = 0
                    sub.renewal_notice_sent = False

                    # 결제 기록
                    payment = Payment(
                        id=uuid.uuid4(),
                        user_id=sub.user_id,
                        subscription_id=sub.id,
                        amount=sub.plan.price_monthly,
                        status=PaymentStatus.COMPLETED,
                        payment_method="card",
                        payment_method_detail=f"{sub.card_company} {sub.card_number_last4}",
                        pg_provider="tosspayments",
                        pg_payment_key=charge_result.get("payment_key"),
                        pg_order_id=order_id,
                        description=f"{sub.plan.name} 플랜 정기결제",
                        paid_at=now
                    )
                    self.db.add(payment)

                    # 결제 완료 알림
                    await self.db.refresh(sub, ["user"])
                    if sub.user and sub.user.email:
                        await self.notification_service.send_payment_success(
                            email=sub.user.email,
                            user_name=sub.user.name or sub.user.email,
                            plan_name=sub.plan.name,
                            amount=sub.plan.price_monthly,
                            next_billing_date=sub.current_period_end
                        )

                    success_count += 1
                else:
                    # 결제 실패
                    sub.retry_count += 1
                    sub.last_retry_at = now

                    if sub.retry_count >= 3:
                        sub.status = SubscriptionStatus.PAST_DUE

                    # 결제 실패 알림
                    await self.db.refresh(sub, ["user"])
                    if sub.user and sub.user.email:
                        await self.notification_service.send_payment_failed(
                            email=sub.user.email,
                            user_name=sub.user.name or sub.user.email,
                            plan_name=sub.plan.name,
                            amount=sub.plan.price_monthly,
                            retry_count=sub.retry_count,
                            error_message=charge_result.get("error")
                        )

                    fail_count += 1

            except Exception as e:
                logger.error(f"구독 갱신 실패 (subscription_id={sub.id}): {e}")
                fail_count += 1

        await self.db.commit()
        logger.info(f"구독 갱신 완료: 성공 {success_count}건, 실패 {fail_count}건")

    async def retry_failed_payments(self):
        """
        실패한 결제 재시도 (3일 간격, 최대 3회)
        """
        logger.info("결제 재시도 처리 시작")

        now = datetime.utcnow()
        three_days_ago = now - timedelta(days=3)

        # PAST_DUE 상태이고, 마지막 재시도가 3일 이상 전인 구독
        stmt = select(Subscription).where(
            and_(
                Subscription.status == SubscriptionStatus.PAST_DUE,
                Subscription.billing_key != None,
                Subscription.retry_count < 3,
                (Subscription.last_retry_at == None) | (Subscription.last_retry_at <= three_days_ago)
            )
        )
        result = await self.db.execute(stmt)
        subscriptions = result.scalars().all()

        for sub in subscriptions:
            try:
                await self.db.refresh(sub, ["plan"])

                if not sub.plan:
                    continue

                # 재시도
                order_id = f"retry_{sub.id}_{int(now.timestamp())}"

                charge_result = await self.toss_service.billing_payment(
                    billing_key=sub.billing_key,
                    customer_key=sub.customer_key,
                    amount=sub.plan.price_monthly,
                    order_id=order_id,
                    order_name=f"{sub.plan.name} 플랜 정기결제 (재시도)"
                )

                if charge_result.get("success"):
                    # 성공 - 구독 재활성화
                    sub.status = SubscriptionStatus.ACTIVE
                    sub.current_period_start = now
                    sub.current_period_end = now + timedelta(days=30)
                    sub.retry_count = 0
                    sub.renewal_notice_sent = False

                    # 결제 기록
                    payment = Payment(
                        id=uuid.uuid4(),
                        user_id=sub.user_id,
                        subscription_id=sub.id,
                        amount=sub.plan.price_monthly,
                        status=PaymentStatus.COMPLETED,
                        payment_method="card",
                        pg_provider="tosspayments",
                        pg_payment_key=charge_result.get("payment_key"),
                        pg_order_id=order_id,
                        description=f"{sub.plan.name} 플랜 정기결제 (재시도 성공)",
                        paid_at=now
                    )
                    self.db.add(payment)

                    logger.info(f"결제 재시도 성공: subscription_id={sub.id}")
                else:
                    # 실패
                    sub.retry_count += 1
                    sub.last_retry_at = now

                    if sub.retry_count >= 3:
                        # 3회 모두 실패 - 구독 만료 처리
                        sub.status = SubscriptionStatus.EXPIRED

                        # 최종 실패 알림
                        await self.db.refresh(sub, ["user"])
                        if sub.user and sub.user.email:
                            await self.notification_service.send_subscription_expired(
                                email=sub.user.email,
                                user_name=sub.user.name or sub.user.email,
                                plan_name=sub.plan.name
                            )

                    logger.warning(f"결제 재시도 실패: subscription_id={sub.id}, retry_count={sub.retry_count}")

            except Exception as e:
                logger.error(f"결제 재시도 오류 (subscription_id={sub.id}): {e}")

        await self.db.commit()

    async def process_cancellations(self):
        """해지 예정 구독 처리 (기간 종료 시 해지)"""
        logger.info("해지 예정 구독 처리 시작")

        now = datetime.utcnow()

        # 기간 종료되고, 해지 예정인 구독
        stmt = select(Subscription).where(
            and_(
                Subscription.cancel_at_period_end == True,
                Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]),
                Subscription.current_period_end <= now
            )
        )
        result = await self.db.execute(stmt)
        subscriptions = result.scalars().all()

        for sub in subscriptions:
            try:
                sub.status = SubscriptionStatus.CANCELLED

                # 해지 완료 알림
                await self.db.refresh(sub, ["user", "plan"])
                if sub.user and sub.user.email and sub.plan:
                    await self.notification_service.send_subscription_cancelled(
                        email=sub.user.email,
                        user_name=sub.user.name or sub.user.email,
                        plan_name=sub.plan.name
                    )

                logger.info(f"구독 해지 완료: subscription_id={sub.id}")

            except Exception as e:
                logger.error(f"구독 해지 처리 오류 (subscription_id={sub.id}): {e}")

        await self.db.commit()

    async def process_expired_trials(self):
        """만료된 트라이얼 처리"""
        logger.info("만료된 트라이얼 처리 시작")

        now = datetime.utcnow()

        # 트라이얼 기간이 종료된 구독
        stmt = select(Subscription).where(
            and_(
                Subscription.status == SubscriptionStatus.TRIALING,
                Subscription.trial_end != None,
                Subscription.trial_end <= now
            )
        )
        result = await self.db.execute(stmt)
        subscriptions = result.scalars().all()

        for sub in subscriptions:
            try:
                if sub.billing_key and not sub.cancel_at_period_end:
                    # 빌링키가 있으면 유료 전환
                    sub.status = SubscriptionStatus.ACTIVE
                    sub.current_period_start = now
                    sub.current_period_end = now + timedelta(days=30)

                    # 첫 정기결제 실행
                    await self.db.refresh(sub, ["plan"])
                    if sub.plan:
                        order_id = f"trial_end_{sub.id}_{int(now.timestamp())}"

                        charge_result = await self.toss_service.billing_payment(
                            billing_key=sub.billing_key,
                            customer_key=sub.customer_key,
                            amount=sub.plan.price_monthly,
                            order_id=order_id,
                            order_name=f"{sub.plan.name} 플랜 첫 결제"
                        )

                        if charge_result.get("success"):
                            payment = Payment(
                                id=uuid.uuid4(),
                                user_id=sub.user_id,
                                subscription_id=sub.id,
                                amount=sub.plan.price_monthly,
                                status=PaymentStatus.COMPLETED,
                                payment_method="card",
                                pg_provider="tosspayments",
                                pg_payment_key=charge_result.get("payment_key"),
                                pg_order_id=order_id,
                                description=f"{sub.plan.name} 플랜 첫 결제 (트라이얼 종료)",
                                paid_at=now
                            )
                            self.db.add(payment)
                        else:
                            sub.status = SubscriptionStatus.PAST_DUE
                            sub.retry_count = 1
                            sub.last_retry_at = now
                else:
                    # 빌링키가 없거나 해지 예정이면 만료
                    sub.status = SubscriptionStatus.EXPIRED

                logger.info(f"트라이얼 종료 처리: subscription_id={sub.id}")

            except Exception as e:
                logger.error(f"트라이얼 처리 오류 (subscription_id={sub.id}): {e}")

        await self.db.commit()


# 스케줄러 인스턴스 (싱글톤)
_scheduler: Optional[BillingSchedulerService] = None


async def get_billing_scheduler(db: AsyncSession) -> BillingSchedulerService:
    """빌링 스케줄러 인스턴스 반환"""
    global _scheduler
    if _scheduler is None:
        _scheduler = BillingSchedulerService(db)
    else:
        _scheduler.db = db
    return _scheduler
