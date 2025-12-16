"""
포트 9001용 관리자 계정 생성 스크립트
"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import uuid
from datetime import datetime
import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 보안 모듈 import
from app.core.security import get_password_hash

# 데이터베이스 URL (포트 9001용 동일 DB 사용)
DATABASE_URL = "sqlite+aiosqlite:///./doctorvoice.db"

# 관리자 계정 정보
ADMIN_EMAIL = "admin@doctorvoice.com"
ADMIN_PASSWORD = "admin123"
ADMIN_NAME = "관리자"


async def create_admin_for_9001():
    """포트 9001용 관리자 계정 생성"""
    # 엔진 생성
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        try:
            # 1. 기존 관리자 계정 확인
            result = await session.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": ADMIN_EMAIL}
            )
            existing = result.first()

            if existing:
                print(f"관리자 계정이 이미 존재합니다: {ADMIN_EMAIL}")
                print("이미 로그인 가능한 상태입니다!")
                return

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
포트 9001용 관리자 계정이 생성되었습니다!
============================================
이메일: {ADMIN_EMAIL}
비밀번호: {ADMIN_PASSWORD}
============================================
localhost:3010 에서 로그인하세요!
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
    print("포트 9001용 관리자 계정 생성 중...")
    asyncio.run(create_admin_for_9001())
