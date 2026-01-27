"""
FastAPI Main Application
닥터보이스 프로 백엔드
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.api import api_router
from contextlib import asynccontextmanager
import traceback


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작 시 실행"""
    # 1. 먼저 데이터베이스 테이블 생성
    try:
        from app.db.database import engine, Base
        # 모든 모델 임포트하여 테이블 메타데이터 등록
        from app.models import (
            User, APIKey, AIUsage,
            # 구독 관련 모델
            Plan, Subscription, UsageLog, UsageSummary,
            Payment, CreditTransaction, UserCredit,
        )
        # 블로그 아웃리치 모델
        from app.models.blog_outreach import (
            NaverBlog, BlogContact, EmailTemplate, EmailCampaign,
            EmailLog, BlogSearchKeyword, OutreachSetting, OutreachStats
        )
        # 공공데이터 리드 모델
        from app.models.public_leads import PublicLeadDB

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[OK] Database tables created/verified")
    except Exception as e:
        print(f"[ERROR] Failed to create database tables: {e}")

    # 1.5. 데이터베이스 마이그레이션 (새 컬럼 추가)
    try:
        from app.db.database import engine
        from sqlalchemy import text

        migrations = [
            # User 테이블 마이그레이션
            "ALTER TABLE users ADD COLUMN has_unlimited_posts BOOLEAN DEFAULT 0",
            "ALTER TABLE users ADD COLUMN unlimited_granted_at DATETIME",
            "ALTER TABLE users ADD COLUMN unlimited_granted_by VARCHAR(255)",
            # Subscriptions 테이블 마이그레이션
            "ALTER TABLE subscriptions ADD COLUMN customer_key VARCHAR(255)",
            "ALTER TABLE subscriptions ADD COLUMN card_company VARCHAR(50)",
            "ALTER TABLE subscriptions ADD COLUMN card_number_last4 VARCHAR(4)",
            "ALTER TABLE subscriptions ADD COLUMN retry_count INTEGER DEFAULT 0",
            "ALTER TABLE subscriptions ADD COLUMN last_retry_at DATETIME",
            "ALTER TABLE subscriptions ADD COLUMN renewal_notice_sent BOOLEAN DEFAULT 0",
            "ALTER TABLE subscriptions ADD COLUMN renewal_notice_sent_at DATETIME",
            "ALTER TABLE subscriptions ADD COLUMN extra_data TEXT",
            # Knowledge answers 테이블 마이그레이션
            "ALTER TABLE knowledge_answers ADD COLUMN posted_account_id VARCHAR(36)",
            # Outreach settings 테이블 - 네이버 API 설정
            "ALTER TABLE outreach_settings ADD COLUMN naver_client_id VARCHAR(100)",
            "ALTER TABLE outreach_settings ADD COLUMN naver_client_secret_encrypted TEXT",
        ]

        async with engine.begin() as conn:
            for migration in migrations:
                try:
                    await conn.execute(text(migration))
                    print(f"[OK] Migration: {migration[:50]}...")
                except Exception as e:
                    # 이미 컬럼이 존재하면 무시
                    if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                        pass
                    else:
                        print(f"[SKIP] Migration skipped: {str(e)[:50]}")
        print("[OK] Database migrations completed")
    except Exception as e:
        print(f"[WARNING] Migration error (may be normal): {e}")

    # 2. 기본 계정들 자동 생성
    try:
        from app.db.database import get_db
        from app.models import User
        from app.core.security import get_password_hash
        from sqlalchemy import select
        import uuid
        from datetime import datetime

        # 기본 계정 목록 (서버 재시작해도 유지됨)
        DEFAULT_ACCOUNTS = [
            {
                "email": "admin@doctorvoice.com",
                "password": "admin123!@#",
                "name": "관리자",
                "hospital_name": "닥터보이스 프로 관리팀",
                "specialty": "관리",
                "is_admin": True,
            },
            {
                "email": "test@test.com",
                "password": "test1234",
                "name": "테스트",
                "hospital_name": "테스트병원",
                "specialty": "내과",
                "is_admin": False,
            },
            {
                "email": "user@doctorvoice.com",
                "password": "user1234!",
                "name": "사용자",
                "hospital_name": "닥터보이스",
                "specialty": "피부과",
                "is_admin": False,
            },
            {
                "email": "demo@demo.com",
                "password": "demo1234",
                "name": "데모",
                "hospital_name": "데모병원",
                "specialty": "성형외과",
                "is_admin": False,
            },
        ]

        async for db in get_db():
            for account in DEFAULT_ACCOUNTS:
                # 기존 계정 확인
                result = await db.execute(
                    select(User).where(User.email == account["email"])
                )
                existing_user = result.scalar_one_or_none()

                if not existing_user:
                    # 계정 생성
                    new_user = User(
                        id=uuid.uuid4(),
                        email=account["email"],
                        hashed_password=get_password_hash(account["password"]),
                        name=account["name"],
                        hospital_name=account["hospital_name"],
                        specialty=account["specialty"],
                        subscription_tier="enterprise",
                        is_active=True,
                        is_verified=True,
                        is_approved=True,
                        is_admin=account["is_admin"],
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                    db.add(new_user)
                    await db.commit()
                    print(f"[OK] Account created: {account['email']}")
                else:
                    # 기존 계정 활성화 확인
                    if not existing_user.is_approved or not existing_user.is_active:
                        existing_user.is_approved = True
                        existing_user.is_active = True
                        existing_user.is_verified = True
                        if account["is_admin"]:
                            existing_user.is_admin = True
                        await db.commit()
                        print(f"[OK] Account activated: {account['email']}")
                    else:
                        print(f"[OK] Account exists: {account['email']}")
            break
    except Exception as e:
        print(f"[WARNING] Error creating default accounts: {e}")

    # 3. 기본 구독 플랜 생성
    try:
        from app.db.database import get_db
        from app.models.subscription import Plan
        from sqlalchemy import select

        # 플랜 정의 (스크린샷 기준)
        DEFAULT_PLANS = [
            {
                "id": "free",
                "name": "Free",
                "description": "서비스를 체험해보세요",
                "price_monthly": 0,
                "price_yearly": 0,
                "posts_per_month": 10,  # 3 → 10: 가치 체험을 위한 충분한 사용량 제공
                "analysis_per_month": 30,  # 10 → 30: 분석 기능도 충분히 체험
                "keywords_per_month": 50,  # 20 → 50: 키워드 연구 체험
                "has_api_access": False,
                "has_priority_support": False,
                "has_advanced_analytics": False,
                "has_team_features": False,
                "extra_post_price": 1000,
                "extra_analysis_price": 200,
                "sort_order": 0,
            },
            {
                "id": "starter",
                "name": "Starter",
                "description": "본격적인 블로그 운영",
                "price_monthly": 29000,
                "price_yearly": 290000,
                "posts_per_month": 30,
                "analysis_per_month": 100,
                "keywords_per_month": 200,
                "has_api_access": False,
                "has_priority_support": False,
                "has_advanced_analytics": False,
                "has_team_features": False,
                "extra_post_price": 800,
                "extra_analysis_price": 150,
                "sort_order": 1,
            },
            {
                "id": "pro",
                "name": "Pro",
                "description": "전문 마케터를 위한 플랜",
                "price_monthly": 79000,
                "price_yearly": 790000,
                "posts_per_month": -1,  # 무제한
                "analysis_per_month": -1,  # 무제한
                "keywords_per_month": -1,  # 무제한
                "has_api_access": False,
                "has_priority_support": True,
                "has_advanced_analytics": True,
                "has_team_features": False,
                "extra_post_price": 0,
                "extra_analysis_price": 0,
                "sort_order": 2,
            },
            {
                "id": "business",
                "name": "Business",
                "description": "마케팅 대행사 & 다점포 의료기관용",
                "price_monthly": 199000,
                "price_yearly": 1990000,
                "posts_per_month": -1,  # 무제한
                "analysis_per_month": -1,  # 무제한
                "keywords_per_month": -1,  # 무제한
                "has_api_access": True,  # REST API 접근
                "has_priority_support": True,  # 전담 매니저 + 우선 지원
                "has_advanced_analytics": True,  # 고급 분석 + 경쟁사 분석
                "has_team_features": True,  # 팀 5명 + 역할 관리
                "extra_post_price": 0,
                "extra_analysis_price": 0,
                "sort_order": 3,
            },
        ]

        async for db in get_db():
            for plan_data in DEFAULT_PLANS:
                result = await db.execute(
                    select(Plan).where(Plan.id == plan_data["id"])
                )
                existing_plan = result.scalar_one_or_none()

                if not existing_plan:
                    new_plan = Plan(**plan_data)
                    db.add(new_plan)
                    await db.commit()
                    print(f"[OK] Plan created: {plan_data['name']}")
                else:
                    # 기존 플랜 업데이트
                    for key, value in plan_data.items():
                        setattr(existing_plan, key, value)
                    await db.commit()
                    print(f"[OK] Plan updated: {plan_data['name']}")
            break
    except Exception as e:
        print(f"[WARNING] Error creating default plans: {e}")

    yield

    # 애플리케이션 종료 시 실행
    pass


# FastAPI 앱 생성
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="의료 블로그 자동 각색 API",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS 설정
# 프로덕션: 모든 origin 허용 (Vercel 동적 URL 지원)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # allow_origins=["*"]일 때는 False
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터 등록
app.include_router(api_router, prefix="/api/v1")


# 전역 예외 핸들러 - 500 오류에도 CORS 헤더 포함
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """모든 예외를 처리하고 CORS 헤더를 포함한 응답 반환"""
    error_detail = str(exc)
    print(f"[ERROR] Unhandled exception: {error_detail}")
    print(f"[ERROR] Traceback: {traceback.format_exc()}")

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "error": error_detail},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT",
            "Access-Control-Allow-Headers": "*",
        }
    )


@app.get("/")
async def root():
    """
    루트 엔드포인트
    """
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """
    헬스 체크 엔드포인트
    """
    # AI 연동 상태 확인
    ai_status = {
        "connected": bool(settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.startswith("sk-")),
        "model": "gpt-4o-mini" if settings.OPENAI_API_KEY else None
    }

    return {
        "status": "healthy",
        "ai": ai_status
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
