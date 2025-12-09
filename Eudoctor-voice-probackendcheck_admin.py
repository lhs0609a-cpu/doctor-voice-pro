"""
관리자 계정 확인 스크립트
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.models import User


async def check_admin():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.email == "admin@doctorvoice.com")
        )
        admin = result.scalar_one_or_none()

        if not admin:
            print("❌ 관리자 계정이 존재하지 않습니다.")
            return

        print("✅ 관리자 계정 정보:")
        print(f"  - ID: {admin.id}")
        print(f"  - 이메일: {admin.email}")
        print(f"  - 이름: {admin.name}")
        print(f"  - 활성화: {admin.is_active}")
        print(f"  - 승인됨: {admin.is_approved}")
        print(f"  - 관리자: {admin.is_admin}")
        print(f"  - 생성일: {admin.created_at}")

        if not admin.is_admin:
            print("\n⚠️  is_admin이 False입니다. True로 변경합니다...")
            admin.is_admin = True
            admin.is_approved = True
            admin.is_active = True
            await db.commit()
            print("✅ 관리자 권한이 설정되었습니다.")


if __name__ == "__main__":
    asyncio.run(check_admin())
