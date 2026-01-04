"""
관리자 계정 확인 및 재설정 스크립트
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.core.security import get_password_hash, verify_password

DATABASE_URL = "sqlite+aiosqlite:///./doctorvoice.db"

async def check_and_fix_admin():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            # 1. 모든 사용자 확인
            result = await session.execute(
                text("SELECT id, email, name, is_admin, is_active, is_approved, hashed_password FROM users")
            )
            users = result.fetchall()

            print("\n" + "="*60)
            print("현재 데이터베이스 사용자 목록")
            print("="*60)

            if not users:
                print("사용자가 없습니다!")
            else:
                for user in users:
                    print(f"ID: {user[0][:8]}...")
                    print(f"  이메일: {user[1]}")
                    print(f"  이름: {user[2]}")
                    print(f"  관리자: {user[3]}")
                    print(f"  활성: {user[4]}")
                    print(f"  승인됨: {user[5]}")
                    print(f"  비밀번호 해시: {user[6][:30]}...")
                    print()

            # 2. admin@doctorvoice.com 계정 확인
            result = await session.execute(
                text("SELECT id, hashed_password, is_admin, is_active, is_approved FROM users WHERE email = :email"),
                {"email": "admin@doctorvoice.com"}
            )
            admin = result.first()

            if admin:
                print("="*60)
                print("관리자 계정 발견!")
                print("="*60)

                # 비밀번호 검증 테스트
                test_passwords = ["admin123!@#", "admin123", "Admin123!@#"]
                for pwd in test_passwords:
                    is_valid = verify_password(pwd, admin[1])
                    print(f"비밀번호 '{pwd}' 테스트: {'성공' if is_valid else '실패'}")

                # 계정 상태 확인
                if not admin[2] or not admin[3] or not admin[4]:
                    print("\n계정 상태에 문제가 있습니다. 수정 중...")
                    await session.execute(
                        text("UPDATE users SET is_admin = 1, is_active = 1, is_approved = 1, is_verified = 1 WHERE email = :email"),
                        {"email": "admin@doctorvoice.com"}
                    )
                    await session.commit()
                    print("계정 상태가 수정되었습니다.")
            else:
                print("="*60)
                print("관리자 계정이 없습니다. 새로 생성합니다...")
                print("="*60)

                import uuid
                from datetime import datetime

                new_password = "admin123!@#"
                hashed = get_password_hash(new_password)
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
                        "email": "admin@doctorvoice.com",
                        "hashed_password": hashed,
                        "name": "관리자",
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
                print(f"관리자 계정이 생성되었습니다!")
                print(f"이메일: admin@doctorvoice.com")
                print(f"비밀번호: {new_password}")

        except Exception as e:
            print(f"오류 발생: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_and_fix_admin())
