"""
관리자 계정 생성 스크립트
"""

import asyncio
import sys
from pathlib import Path

# 백엔드 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.models import User
from app.core.security import get_password_hash


async def create_admin_user():
    """관리자 계정 생성"""
    async with AsyncSessionLocal() as db:
        # 기존 관리자 계정 확인
        result = await db.execute(
            select(User).where(User.email == "admin@doctorvoice.com")
        )
        existing_admin = result.scalar_one_or_none()

        if existing_admin:
            print("관리자 계정이 이미 존재합니다.")
            print(f"이메일: {existing_admin.email}")
            print(f"관리자 여부: {existing_admin.is_admin}")

            # 관리자 권한이 없다면 추가
            if not existing_admin.is_admin:
                existing_admin.is_admin = True
                existing_admin.is_approved = True
                existing_admin.is_active = True
                await db.commit()
                print("관리자 권한이 추가되었습니다.")
            return

        # 새 관리자 계정 생성
        admin_user = User(
            email="admin@doctorvoice.com",
            hashed_password=get_password_hash("admin123!@#"),
            name="관리자",
            hospital_name="닥터보이스 프로",
            specialty="시스템 관리",
            is_active=True,
            is_verified=True,
            is_approved=True,
            is_admin=True,
        )

        db.add(admin_user)
        await db.commit()
        await db.refresh(admin_user)

        print("✓ 관리자 계정이 생성되었습니다!")
        print(f"이메일: admin@doctorvoice.com")
        print(f"비밀번호: admin123!@#")
        print(f"ID: {admin_user.id}")


if __name__ == "__main__":
    asyncio.run(create_admin_user())
