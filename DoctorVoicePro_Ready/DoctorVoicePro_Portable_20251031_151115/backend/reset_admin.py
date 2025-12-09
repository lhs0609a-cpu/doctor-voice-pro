"""
관리자 계정 초기화 및 재생성 스크립트
"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import uuid
from datetime import datetime

# 보안 모듈 import
from app.core.security import get_password_hash

# 데이터베이스 URL
DATABASE_URL = "sqlite+aiosqlite:///./doctorvoice.db"

# 관리자 계정 정보
ADMIN_EMAIL = "admin@doctorvoice.com"
ADMIN_PASSWORD = "admin123"
ADMIN_NAME = "관리자"


async def reset_admin_user():
    """관리자 계정 초기화 및 재생성"""
    # 엔진 생성
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        try:
            # 1. 기존 관리자 계정 삭제
            await session.execute(
                text("DELETE FROM users WHERE email = :email"),
                {"email": ADMIN_EMAIL}
            )
            await session.commit()
            print(f"기존 관리자 계정 삭제 완료: {ADMIN_EMAIL}")

            # 2. passlib을 사용해서 비밀번호 해싱
            hashed_password = get_password_hash(ADMIN_PASSWORD)
            print(f"비밀번호 해싱 완료 (passlib 사용)")

            # 3. 새 관리자 계정 생성
            user_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()

            await session.execute(
                text("""
                    INSERT INTO users (
                        id, email, hashed_password, name, hospital_name, specialty,
                        subscription_tier, is_active, is_verified, is_approved, is_admin,
                        created_at, updated_at
                    ) VALUES (
                        :id, :email, :hashed_password, :name, :hospital_name, :specialty,
                        :subscription_tier, :is_active, :is_verified, :is_approved, :is_admin,
                        :created_at, :updated_at
                    )
                """),
                {
                    "id": user_id,
                    "email": ADMIN_EMAIL,
                    "hashed_password": hashed_password,
                    "name": ADMIN_NAME,
                    "hospital_name": "닥터보이스 프로 관리팀",
                    "specialty": "관리",
                    "subscription_tier": "ENTERPRISE",
                    "is_active": 1,
                    "is_verified": 1,
                    "is_approved": 1,
                    "is_admin": 1,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            await session.commit()

            print(f"""
============================================
관리자 계정이 재생성되었습니다!
============================================
이메일: {ADMIN_EMAIL}
비밀번호: {ADMIN_PASSWORD}
============================================
passlib bcrypt를 사용하여 생성되었습니다.
이제 로그인이 정상적으로 작동합니다.
============================================
            """)

        except Exception as e:
            print(f"오류 발생: {e}")
            import traceback
            traceback.print_exc()
            await session.rollback()
        finally:
            await engine.dispose()


if __name__ == "__main__":
    print("관리자 계정 초기화 및 재생성 중...")
    asyncio.run(reset_admin_user())
