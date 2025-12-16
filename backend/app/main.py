"""
FastAPI Main Application
닥터보이스 프로 백엔드
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import api_router
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작 시 실행"""
    # 1. 먼저 데이터베이스 테이블 생성
    try:
        from app.db.database import engine, Base
        # 모든 모델 임포트하여 테이블 메타데이터 등록
        from app.models import User, APIKey, AIUsage

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[OK] Database tables created/verified")
    except Exception as e:
        print(f"[ERROR] Failed to create database tables: {e}")

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
