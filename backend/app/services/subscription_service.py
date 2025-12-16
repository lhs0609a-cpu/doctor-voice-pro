"""
구독 관리 서비스
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
import uuid

from app.models.subscription import (
    Plan, Subscription, UsageLog, UsageSummary,
    Payment, CreditTransaction, UserCredit,
    PlanType, PaymentStatus, SubscriptionStatus, UsageType
)
from app.models.user import User


# 기본 플랜 정의
DEFAULT_PLANS = [
    {
        "id": "free",
        "name": "무료",
        "description": "기본 기능을 무료로 체험하세요",
        "price_monthly": 0,
        "price_yearly": 0,
        "posts_per_month": 3,
        "analysis_per_month": 10,
        "keywords_per_month": 20,
        "has_api_access": False,
        "has_priority_support": False,
        "has_advanced_analytics": False,
        "has_team_features": False,
        "extra_post_price": 500,
        "extra_analysis_price": 100,
        "sort_order": 0
    },
    {
        "id": "starter",
        "name": "스타터",
        "description": "개인 블로거를 위한 플랜",
        "price_monthly": 9900,
        "price_yearly": 99000,
        "posts_per_month": 30,
        "analysis_per_month": 100,
        "keywords_per_month": 200,
        "has_api_access": False,
        "has_priority_support": False,
        "has_advanced_analytics": True,
        "has_team_features": False,
        "extra_post_price": 400,
        "extra_analysis_price": 80,
        "sort_order": 1
    },
    {
        "id": "pro",
        "name": "프로",
        "description": "전업 블로거 및 마케터를 위한 플랜",
        "price_monthly": 19900,
        "price_yearly": 199000,
        "posts_per_month": 100,
        "analysis_per_month": -1,  # 무제한
        "keywords_per_month": -1,  # 무제한
        "has_api_access": False,
        "has_priority_support": True,
        "has_advanced_analytics": True,
        "has_team_features": False,
        "extra_post_price": 300,
        "extra_analysis_price": 0,
        "sort_order": 2
    },
    {
        "id": "business",
        "name": "비즈니스",
        "description": "마케팅 대행사 및 팀을 위한 플랜",
        "price_monthly": 49900,
        "price_yearly": 499000,
        "posts_per_month": 300,
        "analysis_per_month": -1,  # 무제한
        "keywords_per_month": -1,  # 무제한
        "has_api_access": True,
        "has_priority_support": True,
        "has_advanced_analytics": True,
        "has_team_features": True,
        "extra_post_price": 200,
        "extra_analysis_price": 0,
        "sort_order": 3
    }
]


class SubscriptionService:
    """구독 관리 서비스"""

    def __init__(self, db: Session):
        self.db = db

    # ==================== 플랜 관리 ====================

    def init_plans(self) -> List[Plan]:
        """기본 플랜 초기화"""
        plans = []
        for plan_data in DEFAULT_PLANS:
            existing = self.db.query(Plan).filter(Plan.id == plan_data["id"]).first()
            if not existing:
                plan = Plan(**plan_data)
                self.db.add(plan)
                plans.append(plan)
            else:
                # 기존 플랜 업데이트
                for key, value in plan_data.items():
                    setattr(existing, key, value)
                plans.append(existing)

        self.db.commit()
        return plans

    def get_plans(self, include_inactive: bool = False) -> List[Plan]:
        """모든 플랜 조회"""
        query = self.db.query(Plan)
        if not include_inactive:
            query = query.filter(Plan.is_active == True)
        return query.order_by(Plan.sort_order).all()

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        """플랜 조회"""
        return self.db.query(Plan).filter(Plan.id == plan_id).first()

    # ==================== 구독 관리 ====================

    def get_user_subscription(self, user_id: str) -> Optional[Subscription]:
        """사용자의 현재 활성 구독 조회"""
        return self.db.query(Subscription).filter(
            and_(
                Subscription.user_id == user_id,
                Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING])
            )
        ).first()

    def create_subscription(
        self,
        user_id: str,
        plan_id: str,
        billing_cycle: str = "monthly",  # monthly or yearly
        trial_days: int = 0
    ) -> Subscription:
        """새 구독 생성"""
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Invalid plan: {plan_id}")

        # 기존 활성 구독 확인
        existing = self.get_user_subscription(user_id)
        if existing:
            raise ValueError("User already has an active subscription")

        now = datetime.utcnow()

        # 트라이얼 기간 설정
        if trial_days > 0:
            trial_start = now
            trial_end = now + timedelta(days=trial_days)
            period_start = trial_end
            status = SubscriptionStatus.TRIALING
        else:
            trial_start = None
            trial_end = None
            period_start = now
            status = SubscriptionStatus.ACTIVE

        # 구독 기간 설정
        if billing_cycle == "yearly":
            period_end = period_start + timedelta(days=365)
        else:
            period_end = period_start + timedelta(days=30)

        subscription = Subscription(
            user_id=user_id,
            plan_id=plan_id,
            status=status,
            current_period_start=period_start,
            current_period_end=period_end,
            trial_start=trial_start,
            trial_end=trial_end,
            metadata={"billing_cycle": billing_cycle}
        )

        self.db.add(subscription)

        # 사용량 요약 초기화
        self._init_usage_summary(user_id, subscription.id, plan)

        # 크레딧 초기화
        self._init_user_credits(user_id)

        self.db.commit()
        self.db.refresh(subscription)

        return subscription

    def cancel_subscription(
        self,
        subscription_id: str,
        immediate: bool = False
    ) -> Subscription:
        """구독 취소"""
        subscription = self.db.query(Subscription).filter(
            Subscription.id == subscription_id
        ).first()

        if not subscription:
            raise ValueError("Subscription not found")

        subscription.cancelled_at = datetime.utcnow()

        if immediate:
            subscription.status = SubscriptionStatus.CANCELLED
        else:
            subscription.cancel_at_period_end = True

        self.db.commit()
        self.db.refresh(subscription)

        return subscription

    def change_plan(
        self,
        subscription_id: str,
        new_plan_id: str,
        immediate: bool = True
    ) -> Subscription:
        """플랜 변경"""
        subscription = self.db.query(Subscription).filter(
            Subscription.id == subscription_id
        ).first()

        if not subscription:
            raise ValueError("Subscription not found")

        new_plan = self.get_plan(new_plan_id)
        if not new_plan:
            raise ValueError(f"Invalid plan: {new_plan_id}")

        if immediate:
            subscription.plan_id = new_plan_id
            # 사용량 제한 업데이트
            self._update_usage_limits(subscription.user_id, new_plan)
        else:
            # 다음 결제 주기에 변경
            if not subscription.metadata:
                subscription.metadata = {}
            subscription.metadata["pending_plan_change"] = new_plan_id

        self.db.commit()
        self.db.refresh(subscription)

        return subscription

    def renew_subscription(self, subscription_id: str) -> Subscription:
        """구독 갱신"""
        subscription = self.db.query(Subscription).filter(
            Subscription.id == subscription_id
        ).first()

        if not subscription:
            raise ValueError("Subscription not found")

        billing_cycle = subscription.metadata.get("billing_cycle", "monthly") if subscription.metadata else "monthly"

        # 기간 연장
        subscription.current_period_start = subscription.current_period_end
        if billing_cycle == "yearly":
            subscription.current_period_end = subscription.current_period_start + timedelta(days=365)
        else:
            subscription.current_period_end = subscription.current_period_start + timedelta(days=30)

        subscription.status = SubscriptionStatus.ACTIVE

        # 사용량 초기화
        plan = self.get_plan(subscription.plan_id)
        self._init_usage_summary(subscription.user_id, subscription.id, plan)

        self.db.commit()
        self.db.refresh(subscription)

        return subscription

    # ==================== 사용량 관리 ====================

    def get_usage_summary(self, user_id: str, year: int = None, month: int = None) -> Optional[UsageSummary]:
        """사용량 요약 조회"""
        if not year or not month:
            now = datetime.utcnow()
            year = now.year
            month = now.month

        return self.db.query(UsageSummary).filter(
            and_(
                UsageSummary.user_id == user_id,
                UsageSummary.year == year,
                UsageSummary.month == month
            )
        ).first()

    def record_usage(
        self,
        user_id: str,
        usage_type: UsageType,
        quantity: int = 1,
        resource_id: str = None,
        resource_type: str = None
    ) -> Dict:
        """사용량 기록"""
        subscription = self.get_user_subscription(user_id)
        plan = self.get_plan(subscription.plan_id) if subscription else self.get_plan("free")

        now = datetime.utcnow()
        summary = self.get_usage_summary(user_id, now.year, now.month)

        if not summary:
            summary = self._init_usage_summary(
                user_id,
                subscription.id if subscription else None,
                plan
            )

        # 사용량 확인 및 업데이트
        is_extra = False
        cost = 0

        if usage_type == UsageType.POST_GENERATION:
            if plan.posts_per_month != -1:  # -1은 무제한
                if summary.posts_used >= summary.posts_limit:
                    is_extra = True
                    cost = plan.extra_post_price * quantity
                    summary.extra_posts += quantity
                    summary.extra_cost += cost
            summary.posts_used += quantity

        elif usage_type == UsageType.TOP_POST_ANALYSIS:
            if plan.analysis_per_month != -1:
                if summary.analysis_used >= summary.analysis_limit:
                    is_extra = True
                    cost = plan.extra_analysis_price * quantity
                    summary.extra_analysis += quantity
                    summary.extra_cost += cost
            summary.analysis_used += quantity

        elif usage_type == UsageType.KEYWORD_RESEARCH:
            if plan.keywords_per_month != -1:
                if summary.keywords_used >= summary.keywords_limit:
                    is_extra = True
            summary.keywords_used += quantity

        # 사용량 로그 기록
        usage_log = UsageLog(
            user_id=user_id,
            subscription_id=subscription.id if subscription else None,
            usage_type=usage_type,
            quantity=quantity,
            resource_id=resource_id,
            resource_type=resource_type,
            cost=cost,
            is_extra=is_extra,
            period_start=datetime(now.year, now.month, 1),
            period_end=datetime(now.year, now.month + 1, 1) if now.month < 12 else datetime(now.year + 1, 1, 1)
        )
        self.db.add(usage_log)
        self.db.commit()

        return {
            "success": True,
            "is_extra": is_extra,
            "cost": cost,
            "usage": {
                "posts": {"used": summary.posts_used, "limit": summary.posts_limit},
                "analysis": {"used": summary.analysis_used, "limit": summary.analysis_limit},
                "keywords": {"used": summary.keywords_used, "limit": summary.keywords_limit}
            }
        }

    def check_usage_limit(self, user_id: str, usage_type: UsageType) -> Dict:
        """사용량 한도 확인"""
        subscription = self.get_user_subscription(user_id)
        plan = self.get_plan(subscription.plan_id) if subscription else self.get_plan("free")

        now = datetime.utcnow()
        summary = self.get_usage_summary(user_id, now.year, now.month)

        if not summary:
            summary = self._init_usage_summary(
                user_id,
                subscription.id if subscription else None,
                plan
            )

        if usage_type == UsageType.POST_GENERATION:
            used = summary.posts_used
            limit = summary.posts_limit
            extra_price = plan.extra_post_price
        elif usage_type == UsageType.TOP_POST_ANALYSIS:
            used = summary.analysis_used
            limit = summary.analysis_limit
            extra_price = plan.extra_analysis_price
        elif usage_type == UsageType.KEYWORD_RESEARCH:
            used = summary.keywords_used
            limit = summary.keywords_limit
            extra_price = 0
        else:
            return {"allowed": True, "remaining": -1}

        remaining = limit - used if limit != -1 else -1
        allowed = remaining > 0 or limit == -1

        return {
            "allowed": allowed,
            "used": used,
            "limit": limit,
            "remaining": remaining,
            "is_unlimited": limit == -1,
            "extra_price": extra_price if not allowed and extra_price > 0 else 0,
            "can_use_extra": extra_price > 0
        }

    # ==================== 크레딧 관리 ====================

    def get_user_credits(self, user_id: str) -> UserCredit:
        """사용자 크레딧 조회"""
        credits = self.db.query(UserCredit).filter(UserCredit.user_id == user_id).first()
        if not credits:
            credits = self._init_user_credits(user_id)
        return credits

    def add_credits(
        self,
        user_id: str,
        credit_type: str,  # post, analysis
        amount: int,
        payment_id: str = None,
        description: str = None,
        expires_days: int = 365
    ) -> CreditTransaction:
        """크레딧 충전"""
        credits = self.get_user_credits(user_id)

        if credit_type == "post":
            credits.post_credits += amount
            balance_after = credits.post_credits
        elif credit_type == "analysis":
            credits.analysis_credits += amount
            balance_after = credits.analysis_credits
        else:
            raise ValueError(f"Invalid credit type: {credit_type}")

        transaction = CreditTransaction(
            user_id=user_id,
            payment_id=payment_id,
            transaction_type="purchase",
            credit_type=credit_type,
            amount=amount,
            balance_after=balance_after,
            description=description or f"{credit_type} 크레딧 {amount}개 충전",
            expires_at=datetime.utcnow() + timedelta(days=expires_days)
        )

        self.db.add(transaction)
        self.db.commit()

        return transaction

    def use_credits(
        self,
        user_id: str,
        credit_type: str,
        amount: int,
        description: str = None
    ) -> Optional[CreditTransaction]:
        """크레딧 사용"""
        credits = self.get_user_credits(user_id)

        if credit_type == "post":
            if credits.post_credits < amount:
                return None
            credits.post_credits -= amount
            balance_after = credits.post_credits
        elif credit_type == "analysis":
            if credits.analysis_credits < amount:
                return None
            credits.analysis_credits -= amount
            balance_after = credits.analysis_credits
        else:
            raise ValueError(f"Invalid credit type: {credit_type}")

        transaction = CreditTransaction(
            user_id=user_id,
            transaction_type="use",
            credit_type=credit_type,
            amount=-amount,
            balance_after=balance_after,
            description=description or f"{credit_type} 크레딧 {amount}개 사용"
        )

        self.db.add(transaction)
        self.db.commit()

        return transaction

    # ==================== 헬퍼 메서드 ====================

    def _init_usage_summary(self, user_id: str, subscription_id: str, plan: Plan) -> UsageSummary:
        """사용량 요약 초기화"""
        now = datetime.utcnow()

        # 기존 요약 확인
        existing = self.get_usage_summary(user_id, now.year, now.month)
        if existing:
            return existing

        summary = UsageSummary(
            user_id=user_id,
            subscription_id=subscription_id,
            year=now.year,
            month=now.month,
            posts_limit=plan.posts_per_month if plan else 3,
            analysis_limit=plan.analysis_per_month if plan else 10,
            keywords_limit=plan.keywords_per_month if plan else 20
        )

        self.db.add(summary)
        self.db.commit()
        self.db.refresh(summary)

        return summary

    def _init_user_credits(self, user_id: str) -> UserCredit:
        """사용자 크레딧 초기화"""
        existing = self.db.query(UserCredit).filter(UserCredit.user_id == user_id).first()
        if existing:
            return existing

        credits = UserCredit(user_id=user_id)
        self.db.add(credits)
        self.db.commit()
        self.db.refresh(credits)

        return credits

    def _update_usage_limits(self, user_id: str, plan: Plan):
        """사용량 제한 업데이트"""
        now = datetime.utcnow()
        summary = self.get_usage_summary(user_id, now.year, now.month)

        if summary:
            summary.posts_limit = plan.posts_per_month
            summary.analysis_limit = plan.analysis_per_month
            summary.keywords_limit = plan.keywords_per_month
            self.db.commit()


def get_subscription_service(db: Session) -> SubscriptionService:
    """서비스 인스턴스 생성"""
    return SubscriptionService(db)
