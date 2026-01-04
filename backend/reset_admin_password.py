"""
관리자 비밀번호 재설정 스크립트
"""
import sqlite3
import os
from passlib.context import CryptContext

# 비밀번호 해싱 설정 (백엔드와 동일하게)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

db_path = os.path.join(os.path.dirname(__file__), "doctorvoice.db")

# 새 비밀번호
NEW_PASSWORD = "admin123!@#"

print(f"데이터베이스: {db_path}")
print(f"새 비밀번호: {NEW_PASSWORD}")

# 비밀번호 해싱
hashed_password = pwd_context.hash(NEW_PASSWORD)
print(f"해시된 비밀번호: {hashed_password[:50]}...")

# 검증 테스트
is_valid = pwd_context.verify(NEW_PASSWORD, hashed_password)
print(f"해시 검증: {'성공' if is_valid else '실패'}")

# 데이터베이스 업데이트
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute(
        "UPDATE users SET hashed_password = ? WHERE email = ?",
        (hashed_password, "admin@doctorvoice.com")
    )
    conn.commit()

    if cursor.rowcount > 0:
        print("\n" + "="*60)
        print("비밀번호가 성공적으로 업데이트되었습니다!")
        print("="*60)
        print(f"이메일: admin@doctorvoice.com")
        print(f"비밀번호: {NEW_PASSWORD}")
        print("="*60)
    else:
        print("업데이트된 행이 없습니다!")

except Exception as e:
    print(f"오류: {e}")
finally:
    conn.close()
