"""
사용자 비밀번호 재설정 스크립트
"""

import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from passlib.context import CryptContext

# 직접 import
sys.path.insert(0, '.')
from app.models import User

# 데이터베이스 URL
DATABASE_URL = "sqlite+aiosqlite:///./doctorvoice.db"

# 비밀번호 해시 컨텍스트
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def reset_password(email: str, new_password: str):
    """사용자 비밀번호 재설정"""

    # 비동기 엔진 생성
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 사용자 조회
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user:
            print(f"[ERROR] User not found: {email}")
            return False

        # 비밀번호 해시 생성
        hashed_password = pwd_context.hash(new_password)

        # 비밀번호 및 승인 상태 업데이트
        user.hashed_password = hashed_password
        user.is_approved = True
        user.is_active = True

        await session.commit()

        print(f"[OK] Password reset successfully!")
        print(f"   Email: {email}")
        print(f"   New Password: {new_password}")
        print(f"   Approved: {user.is_approved}")

        return True

    await engine.dispose()


async def main():
    """메인 함수"""
    print("=" * 60)
    print("사용자 비밀번호 재설정")
    print("=" * 60)
    print()

    # lhs0609c@naver.com 계정 비밀번호 재설정
    email = "lhs0609c@naver.com"
    password = "pascal1623!"

    success = await reset_password(email, password)

    if success:
        print()
        print("=" * 60)
        print("재설정 완료!")
        print("=" * 60)
        print()
        print("이제 다음 정보로 로그인할 수 있습니다:")
        print(f"  이메일: {email}")
        print(f"  비밀번호: {password}")
        print()
    else:
        print()
        print("재설정에 실패했습니다.")


if __name__ == "__main__":
    asyncio.run(main())
