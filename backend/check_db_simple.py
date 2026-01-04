"""
SQLite로 직접 관리자 계정 확인
"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "doctorvoice.db")

print(f"데이터베이스 경로: {db_path}")
print(f"파일 존재: {os.path.exists(db_path)}")

if not os.path.exists(db_path):
    print("데이터베이스 파일이 없습니다!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 테이블 목록 확인
print("\n" + "="*60)
print("테이블 목록")
print("="*60)
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
for table in tables:
    print(f"  - {table[0]}")

# users 테이블 확인
print("\n" + "="*60)
print("사용자 목록")
print("="*60)

try:
    cursor.execute("SELECT id, email, name, is_admin, is_active, is_approved, is_verified FROM users")
    users = cursor.fetchall()

    if not users:
        print("사용자가 없습니다!")
    else:
        for user in users:
            print(f"\nID: {user[0][:8] if user[0] else 'N/A'}...")
            print(f"  이메일: {user[1]}")
            print(f"  이름: {user[2]}")
            print(f"  관리자: {user[3]}")
            print(f"  활성: {user[4]}")
            print(f"  승인됨: {user[5]}")
            print(f"  인증됨: {user[6]}")

    # admin 계정 확인
    cursor.execute("SELECT * FROM users WHERE email = 'admin@doctorvoice.com'")
    admin = cursor.fetchone()

    if admin:
        print("\n" + "="*60)
        print("관리자 계정 상세")
        print("="*60)
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        for i, col in enumerate(columns):
            if i < len(admin):
                val = admin[i]
                if col == 'hashed_password' and val:
                    val = val[:50] + "..."
                print(f"  {col}: {val}")
    else:
        print("\n관리자 계정(admin@doctorvoice.com)이 없습니다!")

except Exception as e:
    print(f"오류: {e}")

conn.close()
