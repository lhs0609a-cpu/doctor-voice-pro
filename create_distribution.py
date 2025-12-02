"""
DoctorVoice Pro 배포판 생성 스크립트
"""
import os
import shutil
from pathlib import Path
from datetime import datetime

# 버전 정보
VERSION = "1.0.0"
BUILD_DATE = datetime.now().strftime("%Y%m%d")
BUILD_TIME = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 경로 설정
SOURCE_DIR = Path(r"C:\Users\u\doctor-voice-pro")
DIST_DIR = Path(r"C:\Users\u\DoctorVoicePro-v1.0.0")

print(f"====================================")
print(f"  DoctorVoice Pro v{VERSION}")
print(f"  배포판 생성 스크립트")
print(f"  빌드: {BUILD_TIME}")
print(f"====================================")
print()
print(f"DoctorVoice Pro v{VERSION} 배포판 생성 시작...")

# 1. 프론트엔드 복사
print("\n[1] 프론트엔드 파일 복사 중...")
frontend_files = [
    (".next", ".next"),
    ("public", "public"),
    ("package.json", "package.json"),
    ("next.config.js", "next.config.js"),
]

for src, dst in frontend_files:
    src_path = SOURCE_DIR / "frontend" / src
    dst_path = DIST_DIR / "frontend" / dst

    if src_path.exists():
        if src_path.is_dir():
            if dst_path.exists():
                shutil.rmtree(dst_path)
            shutil.copytree(src_path, dst_path)
            print(f"   OK {src} 복사 완료")
        else:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dst_path)
            print(f"   OK {src} 복사 완료")

# 2. 백엔드 복사
print("\n[2] 백엔드 파일 복사 중...")
backend_dirs = ["app", "alembic"]
backend_files = ["requirements.txt", "alembic.ini"]

for dir_name in backend_dirs:
    src_path = SOURCE_DIR / "backend" / dir_name
    dst_path = DIST_DIR / "backend" / dir_name
    if src_path.exists():
        if dst_path.exists():
            shutil.rmtree(dst_path)
        shutil.copytree(src_path, dst_path)
        print(f"   OK {dir_name}/ 복사 완료")

for file_name in backend_files:
    src_path = SOURCE_DIR / "backend" / file_name
    dst_path = DIST_DIR / "backend" / file_name
    if src_path.exists():
        shutil.copy2(src_path, dst_path)
        print(f"   OK {file_name} 복사 완료")

# 3. 환경 변수 템플릿 생성
print("\n[3] 환경 변수 템플릿 생성 중...")
env_template = """# Application
APP_NAME=DoctorVoice Pro
APP_VERSION=1.0.0
DEBUG=True
SECRET_KEY=your-secret-key-change-this

# Database (SQLite for local development)
DATABASE_URL=sqlite+aiosqlite:///./doctorvoice.db
DATABASE_URL_SYNC=sqlite:///./doctorvoice.db

# Redis (선택사항 - 없어도 작동합니다)
REDIS_URL=redis://localhost:6379/0

# AI APIs (필수!)
ANTHROPIC_API_KEY=여기에_API_키를_입력하세요

# CORS
ALLOWED_ORIGINS=http://localhost:3002,http://127.0.0.1:3002

# JWT Settings
JWT_SECRET_KEY=your-jwt-secret-key-change-this
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
"""

with open(DIST_DIR / "backend" / ".env.template", "w", encoding="utf-8") as f:
    f.write(env_template)
print("   OK .env.template 생성 완료")

# 4. 프론트엔드 환경 변수
with open(DIST_DIR / "frontend" / ".env.local", "w", encoding="utf-8") as f:
    f.write("NEXT_PUBLIC_API_URL=http://localhost:8000\n")
print("   OK frontend/.env.local 생성 완료")

# 5. 실행 스크립트 복사
print("\n[4] 실행 스크립트 복사 중...")
startup_files = ["start.bat", "start-dev.bat"]
for file_name in startup_files:
    src_path = SOURCE_DIR / file_name
    dst_path = DIST_DIR / file_name
    if src_path.exists():
        shutil.copy2(src_path, dst_path)
        print(f"   OK {file_name} 복사 완료")

# 6. README 생성
print("\n[5] README 생성 중...")
readme_content = f"""# DoctorVoice Pro v{VERSION}

의료 음성 전사 시스템 - 배포판

빌드: {BUILD_TIME}

## 📋 시스템 요구사항

### 필수 설치 프로그램
1. **Python 3.8 이상**
   - 다운로드: https://www.python.org/downloads/
   - 설치 시 "Add Python to PATH" 체크 필수

2. **Node.js 18 이상**
   - 다운로드: https://nodejs.org/
   - LTS 버전 권장

## 🚀 빠른 시작

### 1단계: 필수 설정
백엔드 폴더의 `.env.template` 파일을 `.env`로 복사하고 API 키를 설정하세요:

```
ANTHROPIC_API_KEY=여기에_실제_API_키_입력
```

### 2단계: 실행
`start.bat` 파일을 더블클릭하면 자동으로:
- 백엔드 서버 시작 (포트: 8000)
- 프론트엔드 서버 시작 (포트: 3002)
- 브라우저 자동 실행

## 🔧 실행 모드

### 프로덕션 모드 (권장)
```
start.bat
```
- 최적화된 빌드로 실행
- 안정적이고 빠른 성능

### 개발 모드
```
start-dev.bat
```
- 코드 변경 시 자동 리로드
- 디버깅 정보 출력

## 📍 접속 주소

- **프론트엔드**: http://localhost:3002
- **백엔드 API**: http://localhost:8000
- **API 문서**: http://localhost:8000/docs

⚠️ 주의: 0.0.0.0:8000은 서버 바인딩 주소입니다.
브라우저에서는 반드시 localhost로 접속하세요!

## 🔑 관리자 계정

최초 실행 시 자동으로 생성되거나, backend 폴더에서:
```
python create_admin_simple.py
```

## ❓ 문제 해결

### Python/Node.js가 설치되어 있지 않다고 나옵니다
- Python과 Node.js를 설치한 후 컴퓨터를 재부팅하세요
- 명령 프롬프트에서 `python --version` 및 `node --version`으로 확인

### 포트가 이미 사용 중입니다
- 8000번 또는 3000번 포트를 사용하는 다른 프로그램을 종료하세요
- 또는 backend/.env 파일에서 포트를 변경하세요

### API 키 오류
- backend/.env 파일에 올바른 ANTHROPIC_API_KEY가 설정되어 있는지 확인하세요

## 📞 지원

- 문서: ./QUICKSTART.md 참조
- 관리자 정보: ./ADMIN_ACCOUNT_INFO.md 참조

---

© 2024 DoctorVoice Pro v{VERSION}
빌드: {BUILD_TIME}
"""

with open(DIST_DIR / "README.md", "w", encoding="utf-8") as f:
    f.write(readme_content)
print("   OK README.md 생성 완료")

# 7. 버전 정보 파일
print("\n[6] 버전 정보 파일 생성 중...")
version_info = f"""DoctorVoice Pro
Version: {VERSION}
Build: {BUILD_TIME}
Build Type: Production Distribution

Components:
- Frontend: Next.js 14.0.4
- Backend: FastAPI + Python
- Database: SQLite (기본) / PostgreSQL (선택)

System Requirements:
- Python 3.8+
- Node.js 18+
"""

with open(DIST_DIR / "VERSION.txt", "w", encoding="utf-8") as f:
    f.write(version_info)
print("   OK VERSION.txt 생성 완료")

print("\n" + "="*50)
print("배포판 생성 완료!")
print("="*50)
print(f"\n패키지 정보:")
print(f"   버전: v{VERSION}")
print(f"   빌드: {BUILD_TIME}")
print(f"   위치: {DIST_DIR}")
print(f"\n다음 단계:")
print(f"   1. {DIST_DIR} 폴더를 원하는 컴퓨터에 복사")
print(f"   2. start.bat 실행")
print(f"   3. 브라우저에서 http://localhost:3002 접속")
print(f"\n주의:")
print(f"   - 프론트엔드: localhost:3002")
print(f"   - 백엔드 API: localhost:8000")
print(f"   - 0.0.0.0:8000은 서버 바인딩 주소입니다")
print()
