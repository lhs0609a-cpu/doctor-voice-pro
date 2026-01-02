"""
기본 플랜 데이터 초기화 스크립트
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal
from app.models.subscription import Plan


DEFAULT_PLANS = [
    {
        "id": "free",
        "name": "무료",
        "description": "유료 플랜으로 업그레이드하여 모든 기능을 이용하세요",
        "price_monthly": 0,
        "price_yearly": 0,
        "posts_per_month": 0,
        "analysis_per_month": 0,
        "keywords_per_month": 0,
        "has_api_access": False,
        "has_priority_support": False,
        "has_advanced_analytics": False,
        "has_team_features": False,
        "extra_post_price": 500,
        "extra_analysis_price": 100,
        "sort_order": 0,
    },
    {
        "id": "starter",
        "name": "스타터",
        "description": "소규모 병원에 적합한 플랜",
        "price_monthly": 9900,
        "price_yearly": 99000,  # 2개월 무료
        "posts_per_month": 30,
        "analysis_per_month": 100,
        "keywords_per_month": 200,
        "has_api_access": False,
        "has_priority_support": False,
        "has_advanced_analytics": True,
        "has_team_features": False,
        "extra_post_price": 400,
        "extra_analysis_price": 80,
        "sort_order": 1,
    },
    {
        "id": "pro",
        "name": "프로",
        "description": "성장하는 병원을 위한 전문가 플랜",
        "price_monthly": 19900,
        "price_yearly": 199000,  # 2개월 무료
        "posts_per_month": 100,
        "analysis_per_month": -1,  # 무제한
        "keywords_per_month": -1,  # 무제한
        "has_api_access": False,
        "has_priority_support": True,
        "has_advanced_analytics": True,
        "has_team_features": False,
        "extra_post_price": 300,
        "extra_analysis_price": 0,  # 무제한이므로 의미없음
        "sort_order": 2,
    },
    {
        "id": "business",
        "name": "비즈니스",
        "description": "대형 병원 및 에이전시를 위한 엔터프라이즈 플랜",
        "price_monthly": 49900,
        "price_yearly": 499000,  # 2개월 무료
        "posts_per_month": 300,
        "analysis_per_month": -1,  # 무제한
        "keywords_per_month": -1,  # 무제한
        "has_api_access": True,
        "has_priority_support": True,
        "has_advanced_analytics": True,
        "has_team_features": True,
        "extra_post_price": 200,
        "extra_analysis_price": 0,
        "sort_order": 3,
    },
]


def init_plans():
    """기본 플랜 데이터 초기화"""
    db = SessionLocal()
    try:
        for plan_data in DEFAULT_PLANS:
            existing = db.query(Plan).filter(Plan.id == plan_data["id"]).first()

            if existing:
                # 기존 플랜 업데이트
                for key, value in plan_data.items():
                    setattr(existing, key, value)
                print(f"Updated plan: {plan_data['id']}")
            else:
                # 새 플랜 생성
                plan = Plan(**plan_data)
                db.add(plan)
                print(f"Created plan: {plan_data['id']}")

        db.commit()
        print("\nPlans initialized successfully!")

        # 확인
        plans = db.query(Plan).order_by(Plan.sort_order).all()
        print("\nCurrent plans:")
        for plan in plans:
            print(f"  - {plan.id}: {plan.name} (₩{plan.price_monthly}/월)")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_plans()
