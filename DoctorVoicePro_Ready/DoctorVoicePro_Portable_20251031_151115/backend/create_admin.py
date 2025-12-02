"""
관리자 계정 생성 스크립트
"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.models import User
from app.core.security import get_password_hash
import uuid
from datetime import datetime

# 데이터베이스 URL (환경에 맞게 수정)
DATABASE_URL = "sqlite+aiosqlite:///./doctorvoice.db"

# 관리자 계정 정보
ADMIN_EMAIL = "admin@doctorvoice.com"
ADMIN_PASSWORD = "admin123"  # 실제 운영 시 변경 필요
ADMIN_NAME = "관리자"


async def create_admin_user():
    """관리자 계정 생성"""
    # 엔진 생성
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        try:
            # 기존 관리자 계정 확인
            from sqlalchemy import select
            result = await session.execute(
                select(User).where(User.email == ADMIN_EMAIL)
            )
            existing_user = result.scalar_one_or_none()

            if existing_user:
                print(f"관리자 계정이 이미 존재합니다: {ADMIN_EMAIL}")
                if not existing_user.is_admin:
                    existing_user.is_admin = True
                    existing_user.is_approved = True
                    existing_user.is_active = True
                    await session.commit()
                    print("기존 계정을 관리자로 업데이트했습니다.")
                return

            # 새 관리자 계정 생성
            admin_user = User(
                id=uuid.uuid4(),
                email=ADMIN_EMAIL,
                hashed_password=get_password_hash(ADMIN_PASSWORD),
                name=ADMIN_NAME,
                hospital_name="닥터보이스 프로 관리팀",
                specialty="관리",
                subscription_tier="enterprise",
                is_active=True,
                is_verified=True,
                is_approved=True,
                is_admin=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            session.add(admin_user)
            await session.commit()

            print(f"""
============================================
관리자 계정이 생성되었습니다!
============================================
이메일: {ADMIN_EMAIL}
비밀번호: {ADMIN_PASSWORD}
============================================
보안을 위해 최초 로그인 후 비밀번호를 변경하세요.
============================================
            """)

        except Exception as e:
            print(f"오류 발생: {e}")
            await session.rollback()
        finally:
            await engine.dispose()


if __name__ == "__main__":
    print("관리자 계정 생성 중...")
    asyncio.run(create_admin_user())
