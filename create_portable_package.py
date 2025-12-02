"""
다른 컴퓨터에서 실행 가능한 배포 패키지 생성
"""
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

def create_portable_package():
    """배포용 패키지 생성"""
    print("=" * 60)
    print("Doctor Voice Pro - 배포 패키지 생성")
    print("=" * 60)

    # 패키지 이름
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    package_name = f"DoctorVoicePro_Portable_{timestamp}"
    package_dir = Path(package_name)

    # 제외할 항목들
    exclude_items = {
        '__pycache__',
        'node_modules',
        'venv',
        '.git',
        '.next',
        '*.pyc',
        '*.pyo',
        '*.db',
        '*.db.backup',
        'logs',
        'error_reports',
        'backups',
        '.env',
        'nul',
    }

    # 포함할 폴더/파일
    include_items = [
        'backend',
        'frontend',
        'install.bat',
        'run.bat',
        'install.sh',
        'run.sh',
        'auto_install_prerequisites.bat',
        'auto_install_nodejs.bat',
        'find_available_port.py',
        'server_manager.py',
        'cleanup_all_ports.bat',
        'START.bat',
        'AUTOINSTALL.bat',
        '완전자동설치.bat',
        'README.md',
        'README_INSTALL.md',
        'README_SIMPLE.md',
        '사용법_간단버전.txt',
        '사용법_최종버전.txt',
        'docker-compose.yml',
        'health_check.py',
    ]

    print(f"\nPackage: {package_name}")
    print(f"Location: {package_dir.absolute()}\n")

    # 패키지 디렉토리 생성
    if package_dir.exists():
        print(f"Removing existing package directory...")
        shutil.rmtree(package_dir)

    package_dir.mkdir()
    print("Created package directory")

    # 파일 복사
    print("\nCopying files...")
    for item in include_items:
        src = Path(item)
        if not src.exists():
            print(f"  Skip (not found): {item}")
            continue

        dst = package_dir / item

        if src.is_dir():
            print(f"  Copying directory: {item}")
            shutil.copytree(
                src,
                dst,
                ignore=shutil.ignore_patterns(*exclude_items)
            )
        else:
            print(f"  Copying file: {item}")
            shutil.copy2(src, dst)

    # README 파일 생성
    print("\nCreating INSTALL_GUIDE.txt...")
    install_guide = package_dir / "INSTALL_GUIDE.txt"
    install_guide.write_text("""
╔════════════════════════════════════════════════════════════════╗
║          Doctor Voice Pro - 설치 가이드                         ║
╚════════════════════════════════════════════════════════════════╝

다른 컴퓨터에 설치하는 방법 (각 컴퓨터에서 독립 실행)

【 방법 1: 완전 자동 설치 (권장 ⭐) 】
  ✅ Python과 Node.js가 없어도 자동으로 설치됩니다!

  1. 이 폴더 전체를 원하는 위치에 복사
  2. "완전자동설치.bat"를 마우스 우클릭
  3. "관리자 권한으로 실행" 선택
  4. 끝! 모든 것이 자동으로 설치되고 실행됩니다.

【 방법 2: 수동 설치 】
  ⚠️ 먼저 Python 3.8 이상과 Node.js 16.0 이상이 설치되어 있어야 합니다.

  1. 이 폴더 전체를 원하는 위치에 복사
  2. install.bat 더블클릭
  3. 설치 완료 후 run.bat 더블클릭

【 Python/Node.js만 자동 설치 】
  1. "auto_install_prerequisites.bat"를 마우스 우클릭
  2. "관리자 권한으로 실행" 선택
  3. 컴퓨터 재시작
  4. install.bat → run.bat 실행

【 Mac/Linux 설치 】
  1. 터미널 열기
  2. 이 폴더로 이동: cd [폴더경로]
  3. 권한 부여: chmod +x install.sh run.sh
  4. 설치: ./install.sh
  5. 실행: ./run.sh

【 접속 주소 】
  프론트엔드: http://localhost:3000
  백엔드 API: http://localhost:8010/docs

【 기본 계정 】
  이메일: admin@doctorvoice.com
  비밀번호: admin123!@#

【 문제 해결 】

  ⚠️ 포트가 사용 중이라는 오류 발생 시:
  → port_cleanup.bat 더블클릭 (Windows)

  ⚠️ 로그인이 안 되거나 DB 오류 발생 시:
  → python recreate_db.py 실행

  ⚠️ 기타 문제:
  → python health_check.py 실행 (자동 진단)

【 각 컴퓨터에서 독립 실행 】
  - 각 컴퓨터는 자신만의 데이터베이스를 가집니다
  - 데이터는 다른 컴퓨터와 공유되지 않습니다
  - 각각 admin 계정으로 로그인 필요

【 API 키 설정 (선택) 】
  AI 기능을 사용하려면:
  1. backend/.env 파일 열기
  2. ANTHROPIC_API_KEY 입력
  3. 서버 재시작

【 포함된 유틸리티 】
  - 완전자동설치.bat: Python/Node.js 포함 완전 자동 설치 ⭐
  - auto_install_prerequisites.bat: Python/Node.js 자동 설치
  - auto_install_nodejs.bat: Node.js만 자동 설치
  - install.bat: 애플리케이션 설치
  - run.bat: 서버 실행 (포트 자동 탐지, Node.js 자동 설치 포함) ✨
  - port_cleanup.bat: 포트 충돌 해결
  - find_available_port.py: 사용 가능한 포트 자동 찾기
  - recreate_db.py: 데이터베이스 초기화
  - health_check.py: 시스템 진단

【 새로운 자동화 기능 ✨ 】
  ✅ 포트 자동 탐지: 8010/3000 포트가 사용 중이면 자동으로 다른 포트 사용
  ✅ Node.js 자동 설치: Node.js가 없으면 자동 설치 제안
  ✅ 설정 자동 업데이트: 포트 변경 시 설정 파일 자동 업데이트

【 지원 】
  - README.md 파일 참고
  - README_INSTALL.md 상세 가이드

""", encoding='utf-8')

    # 데이터베이스 재생성 스크립트 생성
    print("Creating recreate_db.py...")
    recreate_db_script = package_dir / "recreate_db.py"
    recreate_db_script.write_text('''"""
Database recreation script
Recreates all tables with the latest schema and creates default admin user
"""
import asyncio
import sys
from pathlib import Path

# Add the parent directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from backend.app.db.database import Base
from backend.app.models.user import User
from backend.app.models.post import Post, PostVersion, PostAnalytics
from backend.app.models.doctor_profile import DoctorProfile
from backend.app.models.tag import Tag
from backend.app.models.naver_connection import NaverConnection
from backend.app.models.medical_law import MedicalLawRule
from backend.app.core.config import settings
from passlib.context import CryptContext
import uuid

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def recreate_database():
    """Recreate all database tables"""
    print("Recreating database...")

    # Use sync engine for table creation
    sync_db_url = settings.DATABASE_URL_SYNC
    engine = create_engine(sync_db_url, echo=False)

    # Drop all tables
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)

    # Create all tables
    print("Creating all tables...")
    Base.metadata.create_all(bind=engine)

    print("Database tables created successfully!")

    # Create default admin user
    print("Creating default admin user...")
    with Session(engine) as session:
        admin_user = User(
            id=uuid.uuid4(),
            email="admin@doctorvoice.com",
            hashed_password=pwd_context.hash("admin123!@#"),
            name="관리자",
            hospital_name="닥터보이스 프로",
            specialty="일반의",
            subscription_tier="PRO",
            is_active=True,
            is_verified=True,
            is_approved=True,
            is_admin=True,
        )
        session.add(admin_user)
        session.commit()
        print(f"Admin user created: {admin_user.email}")
        print(f"Password: admin123!@#")

    engine.dispose()
    print("\\nDatabase recreation completed!")


if __name__ == "__main__":
    recreate_database()
''', encoding='utf-8')

    # 포트 종료 스크립트 생성
    print("Creating port_cleanup.bat...")
    port_cleanup = package_dir / "port_cleanup.bat"
    port_cleanup.write_text('''@echo off
chcp 65001 > nul
echo ================================================================
echo   포트 8010 및 3000 프로세스 종료
echo ================================================================
echo.

echo 포트 8010 사용 프로세스 확인 중...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8010.*LISTENING"') do (
    echo 포트 8010 프로세스 종료: %%a
    taskkill /F /PID %%a 2>nul
)

echo.
echo 포트 3000 사용 프로세스 확인 중...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000.*LISTENING"') do (
    echo 포트 3000 프로세스 종료: %%a
    taskkill /F /PID %%a 2>nul
)

echo.
echo ================================================================
echo   완료!
echo ================================================================
pause
''', encoding='utf-8')

    # 환경 설정 예제 파일 생성
    print("Creating .env.example...")
    backend_dir = package_dir / "backend"
    env_example = backend_dir / ".env.example"
    env_example.write_text("""# Application
APP_NAME=DoctorVoice Pro
APP_VERSION=1.0.0
DEBUG=True
SECRET_KEY=dev-secret-key-change-in-production-12345678

# Database (SQLite for local development)
DATABASE_URL=sqlite+aiosqlite:///./doctorvoice.db
DATABASE_URL_SYNC=sqlite:///./doctorvoice.db

# Redis
REDIS_URL=redis://localhost:6379/0

# AI APIs
ANTHROPIC_API_KEY=your-api-key-here
OPENAI_API_KEY=

# AWS S3
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=ap-northeast-2
S3_BUCKET_NAME=doctorvoice-files

# JWT Settings
JWT_SECRET_KEY=dev-jwt-secret-key-change-in-production-12345678
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Email (SendGrid)
SENDGRID_API_KEY=
FROM_EMAIL=noreply@doctorvoice.com

# Naver Blog API
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=
""")

    # ZIP 압축
    print(f"\nCreating ZIP archive...")
    zip_filename = f"{package_name}.zip"

    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(package_dir):
            # 제외 항목 필터링
            dirs[:] = [d for d in dirs if d not in exclude_items]

            for file in files:
                if file.endswith(('.pyc', '.pyo')):
                    continue

                file_path = Path(root) / file
                arcname = file_path.relative_to(package_dir.parent)
                zipf.write(file_path, arcname)

    zip_size = os.path.getsize(zip_filename) / (1024 * 1024)
    print(f"  Created: {zip_filename} ({zip_size:.2f} MB)")

    # 임시 폴더 삭제
    print(f"\nCleaning up temporary directory...")
    shutil.rmtree(package_dir)

    print("\n" + "=" * 60)
    print("Package created successfully!")
    print("=" * 60)
    print(f"\nPackage file: {zip_filename}")
    print(f"Size: {zip_size:.2f} MB")
    print("\nTo deploy:")
    print("1. Copy the ZIP file to target computer")
    print("2. Extract the ZIP file")
    print("3. Run install.bat (Windows) or ./install.sh (Mac/Linux)")
    print("4. Run run.bat (Windows) or ./run.sh (Mac/Linux)")
    print("\n" + "=" * 60)

if __name__ == "__main__":
    try:
        create_portable_package()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
