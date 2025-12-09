"""
DoctorVoicePro Ultimate Auto-Install Package Creator
아무것도 설치되지 않은 컴퓨터에서도 한 번의 클릭으로 완전 실행
"""
import os
import shutil
import json
from pathlib import Path

def create_ultimate_package():
    """완전 자동화 패키지 생성"""

    source_dir = Path(__file__).parent
    package_name = "DoctorVoicePro_Ultimate_AutoInstall"
    release_dir = source_dir / package_name

    print("=" * 70)
    print("  DoctorVoicePro Ultimate Auto-Install Package Creator")
    print("=" * 70)

    # 기존 폴더 삭제
    if release_dir.exists():
        print(f"\n[1/10] Removing existing folder...")
        shutil.rmtree(release_dir)

    # 새 폴더 생성
    print(f"[2/10] Creating package folder: {package_name}")
    release_dir.mkdir()
    (release_dir / "docs").mkdir()
    (release_dir / "tools").mkdir()

    # 백엔드 복사
    print("[3/10] Copying backend files...")
    backend_items = [
        ('backend/app', 'backend/app'),
        ('backend/alembic', 'backend/alembic'),
        ('backend/requirements.txt', 'backend/requirements.txt'),
        ('backend/.env.example', 'backend/.env.example'),
        ('backend/alembic.ini', 'backend/alembic.ini'),
    ]

    for src, dst in backend_items:
        src_path = source_dir / src
        dst_path = release_dir / dst
        if src_path.exists():
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            if src_path.is_file():
                shutil.copy2(src_path, dst_path)
            else:
                shutil.copytree(src_path, dst_path, dirs_exist_ok=True)

    # .env 파일 생성
    env_content = """# Backend Environment Configuration
DATABASE_URL=sqlite:///./doctor_voice.db
SECRET_KEY=your-secret-key-here-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS
ALLOWED_ORIGINS=http://localhost:3000

# Claude AI
ANTHROPIC_API_KEY=your-anthropic-api-key-here

# Naver Blog API
NAVER_CLIENT_ID=your-naver-client-id
NAVER_CLIENT_SECRET=your-naver-client-secret
NAVER_REDIRECT_URI=http://localhost:3000/api/naver/callback
"""
    (release_dir / "backend" / ".env").write_text(env_content, encoding='utf-8')

    # 프론트엔드 복사
    print("[4/10] Copying frontend files...")
    frontend_items = [
        ('frontend/src', 'frontend/src'),
        ('frontend/public', 'frontend/public'),
        ('frontend/package.json', 'frontend/package.json'),
        ('frontend/next.config.js', 'frontend/next.config.js'),
        ('frontend/tsconfig.json', 'frontend/tsconfig.json'),
        ('frontend/tailwind.config.ts', 'frontend/tailwind.config.ts'),
        ('frontend/postcss.config.js', 'frontend/postcss.config.js'),
        ('frontend/components.json', 'frontend/components.json'),
    ]

    for src, dst in frontend_items:
        src_path = source_dir / src
        dst_path = release_dir / dst
        if src_path.exists():
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            if src_path.is_file():
                shutil.copy2(src_path, dst_path)
            else:
                shutil.copytree(src_path, dst_path, dirs_exist_ok=True)

    # .env.local 파일 생성
    env_local_content = """NEXT_PUBLIC_API_URL=http://localhost:8000
"""
    (release_dir / "frontend" / ".env.local").write_text(env_local_content, encoding='utf-8')

    # 도구 파일 복사
    print("[5/10] Copying utility files...")
    shutil.copy2(source_dir / "port_checker.py", release_dir / "tools" / "port_checker.py")
    shutil.copy2(source_dir / "server_manager.py", release_dir / "tools" / "server_manager.py")

    # 메인 자동 설치 스크립트 생성
    print("[6/10] Creating main auto-install script...")

    main_script = r"""@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title 닥터보이스 프로 - 완전 자동 설치 및 실행

echo.
echo ============================================================
echo.
echo     닥터보이스 프로 v3.0 - Ultimate Auto-Install
echo.
echo ============================================================
echo.

cd /d "%~dp0"

:: 1. Python 확인 및 설치
echo [Step 1/8] Python 확인 중...
python --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] Python이 설치되어 있지 않습니다.
    echo [INFO] Python 설치를 시작합니다...
    call tools\install_python.bat
    if errorlevel 1 (
        echo [ERROR] Python 설치 실패
        pause
        exit /b 1
    )
) else (
    echo [OK] Python이 이미 설치되어 있습니다.
)

:: 2. Node.js 확인 및 설치
echo.
echo [Step 2/8] Node.js 확인 중...
node --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] Node.js가 설치되어 있지 않습니다.
    echo [INFO] Node.js 설치를 시작합니다...
    call tools\install_nodejs.bat
    if errorlevel 1 (
        echo [ERROR] Node.js 설치 실패
        pause
        exit /b 1
    )
) else (
    echo [OK] Node.js가 이미 설치되어 있습니다.
)

:: 3. 포트 충돌 체크
echo.
echo [Step 3/8] 포트 충돌 체크 중...
python tools\port_checker.py
if errorlevel 1 (
    echo [WARNING] 포트 확인 중 문제 발생 (계속 진행)
)

:: 포트 설정 읽기
if exist port_config.json (
    for /f "tokens=*" %%i in ('powershell -Command "$config = Get-Content 'port_config.json' ^| ConvertFrom-Json; Write-Output $config.backend_port"') do set BACKEND_PORT=%%i
    for /f "tokens=*" %%i in ('powershell -Command "$config = Get-Content 'port_config.json' ^| ConvertFrom-Json; Write-Output $config.frontend_port"') do set FRONTEND_PORT=%%i
    echo [OK] Backend Port: !BACKEND_PORT!
    echo [OK] Frontend Port: !FRONTEND_PORT!
) else (
    set BACKEND_PORT=8000
    set FRONTEND_PORT=3000
    echo [INFO] Using default ports: 8000, 3000
)

:: 4. Backend 가상환경 확인 및 설치
echo.
echo [Step 4/8] Backend 설정 중...
cd backend

if not exist venv (
    echo [INFO] Creating Python virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        cd ..
        pause
        exit /b 1
    )
)

echo [INFO] Installing backend dependencies...
call venv\Scripts\activate.bat
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [WARNING] Some packages might have failed to install
)

:: 환경 파일 업데이트
echo [INFO] Updating backend .env file...
powershell -Command "(Get-Content .env) -replace 'ALLOWED_ORIGINS=.*', 'ALLOWED_ORIGINS=http://localhost:!FRONTEND_PORT!' | Set-Content .env"

cd ..

:: 5. Frontend 설정
echo.
echo [Step 5/8] Frontend 설정 중...
cd frontend

if not exist node_modules (
    echo [INFO] Installing frontend dependencies...
    call npm install
    if errorlevel 1 (
        echo [ERROR] Failed to install frontend dependencies
        cd ..
        pause
        exit /b 1
    )
) else (
    echo [INFO] Frontend dependencies already installed
)

:: 환경 파일 업데이트
echo [INFO] Updating frontend .env.local file...
powershell -Command "(Get-Content .env.local) -replace 'NEXT_PUBLIC_API_URL=.*', 'NEXT_PUBLIC_API_URL=http://localhost:!BACKEND_PORT!' | Set-Content .env.local"

cd ..

:: 6. Backend 시작
echo.
echo [Step 6/8] Starting backend server...
cd backend
start "DoctorVoicePro Backend" cmd /k "call venv\Scripts\activate.bat && python -m uvicorn app.main:app --host 0.0.0.0 --port !BACKEND_PORT! --reload"
cd ..

:: 7. Backend 헬스체크
echo.
echo [Step 7/8] Waiting for backend to be ready...
timeout /t 5 /nobreak >nul

set "MAX_RETRIES=30"
set "RETRY_COUNT=0"

:health_check
set /a RETRY_COUNT+=1
python -c "import urllib.request; urllib.request.urlopen('http://localhost:!BACKEND_PORT!/health').read()" >nul 2>&1
if errorlevel 1 (
    if !RETRY_COUNT! lss !MAX_RETRIES! (
        echo [INFO] Attempt !RETRY_COUNT!/!MAX_RETRIES! - Retrying...
        timeout /t 2 /nobreak >nul
        goto health_check
    ) else (
        echo [ERROR] Backend health check failed
        echo [ERROR] Please check the Backend window for errors
        pause
        exit /b 1
    )
)

echo [OK] Backend is healthy!

:: 8. Frontend 시작
echo.
echo [Step 8/8] Starting frontend server...
cd frontend
start "DoctorVoicePro Frontend" cmd /k "set PORT=!FRONTEND_PORT! && npm run dev"
cd ..

:: 완료
echo.
echo ============================================================
echo.
echo     [SUCCESS] 서버가 성공적으로 시작되었습니다!
echo.
echo ============================================================
echo.
echo Frontend: http://localhost:!FRONTEND_PORT!
echo Backend:  http://localhost:!BACKEND_PORT!
echo API Docs: http://localhost:!BACKEND_PORT!/docs
echo.
echo ============================================================
echo.
echo 브라우저가 자동으로 열립니다...
echo.

:: 브라우저 열기
timeout /t 3 /nobreak >nul
start http://localhost:!FRONTEND_PORT!

echo.
echo [INFO] 서버가 실행 중입니다.
echo [INFO] 종료하려면 서버 창들을 닫으세요.
echo.
pause
"""

    (release_dir / "자동설치_및_실행.bat").write_text(main_script, encoding='utf-8')

    # Python 자동 설치 스크립트
    print("[7/10] Creating Python installer...")

    python_installer = r"""@echo off
chcp 65001 >nul
setlocal

echo.
echo ============================================================
echo   Python 자동 설치
echo ============================================================
echo.

:: Python 다운로드 URL (최신 3.11 버전)
set PYTHON_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
set PYTHON_INSTALLER=%TEMP%\python_installer.exe

echo [INFO] Python 다운로더를 실행합니다...
echo [INFO] 다운로드 URL: %PYTHON_URL%
echo.

:: PowerShell로 다운로드
powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_INSTALLER%'}"

if not exist "%PYTHON_INSTALLER%" (
    echo [ERROR] Python 다운로드 실패
    echo.
    echo 수동 설치 방법:
    echo 1. https://www.python.org/downloads/ 방문
    echo 2. Python 3.11 이상 다운로드
    echo 3. 설치 시 "Add Python to PATH" 체크
    echo 4. 이 스크립트 다시 실행
    pause
    exit /b 1
)

echo [OK] Python 다운로드 완료
echo [INFO] Python 설치를 시작합니다...
echo.
echo 설치 과정:
echo 1. "Add Python to PATH" 자동 선택됨
echo 2. 기본 설정으로 설치
echo 3. 완료될 때까지 기다려주세요
echo.

:: Python 설치 (자동, PATH 추가)
"%PYTHON_INSTALLER%" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0

if errorlevel 1 (
    echo [ERROR] Python 설치 실패
    pause
    exit /b 1
)

echo [OK] Python 설치 완료!
echo [INFO] 환경 변수를 새로고침합니다...

:: 환경 변수 새로고침
call refreshenv.cmd >nul 2>&1

:: 설치 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Python이 PATH에 추가되지 않았을 수 있습니다.
    echo [INFO] 컴퓨터를 재시작하거나 명령 프롬프트를 다시 열어주세요.
    pause
    exit /b 1
)

echo [OK] Python이 정상적으로 설치되었습니다!
python --version

exit /b 0
"""

    (release_dir / "tools" / "install_python.bat").write_text(python_installer, encoding='utf-8')

    # Node.js 자동 설치 스크립트
    print("[8/10] Creating Node.js installer...")

    nodejs_installer = r"""@echo off
chcp 65001 >nul
setlocal

echo.
echo ============================================================
echo   Node.js 자동 설치
echo ============================================================
echo.

:: Node.js 다운로드 URL (LTS 버전)
set NODEJS_URL=https://nodejs.org/dist/v20.11.1/node-v20.11.1-x64.msi
set NODEJS_INSTALLER=%TEMP%\nodejs_installer.msi

echo [INFO] Node.js 다운로더를 실행합니다...
echo [INFO] 다운로드 URL: %NODEJS_URL%
echo.

:: PowerShell로 다운로드
powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%NODEJS_URL%' -OutFile '%NODEJS_INSTALLER%'}"

if not exist "%NODEJS_INSTALLER%" (
    echo [ERROR] Node.js 다운로드 실패
    echo.
    echo 수동 설치 방법:
    echo 1. https://nodejs.org/ 방문
    echo 2. LTS 버전 다운로드
    echo 3. 설치
    echo 4. 이 스크립트 다시 실행
    pause
    exit /b 1
)

echo [OK] Node.js 다운로드 완료
echo [INFO] Node.js 설치를 시작합니다...
echo.
echo 설치 과정:
echo 1. 기본 설정으로 설치
echo 2. npm 자동 포함
echo 3. 완료될 때까지 기다려주세요
echo.

:: Node.js 설치 (자동)
msiexec /i "%NODEJS_INSTALLER%" /qn /norestart

if errorlevel 1 (
    echo [ERROR] Node.js 설치 실패
    pause
    exit /b 1
)

echo [OK] Node.js 설치 완료!
echo [INFO] 환경 변수를 새로고침합니다...

:: 환경 변수 새로고침
call refreshenv.cmd >nul 2>&1

:: 설치 확인
node --version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Node.js가 PATH에 추가되지 않았을 수 있습니다.
    echo [INFO] 컴퓨터를 재시작하거나 명령 프롬프트를 다시 열어주세요.
    pause
    exit /b 1
)

echo [OK] Node.js가 정상적으로 설치되었습니다!
node --version
npm --version

exit /b 0
"""

    (release_dir / "tools" / "install_nodejs.bat").write_text(nodejs_installer, encoding='utf-8')

    # 서버 정리 스크립트
    print("[9/10] Creating cleanup script...")

    cleanup_script = r"""@echo off
chcp 65001 >nul
title 서버 정리

echo.
echo ============================================================
echo   서버 프로세스 정리
echo ============================================================
echo.

echo [INFO] Python 프로세스 종료 중...
taskkill /F /IM python.exe >nul 2>&1
if errorlevel 1 (
    echo [INFO] 실행 중인 Python 프로세스 없음
) else (
    echo [OK] Python 프로세스 종료됨
)

echo [INFO] Node.js 프로세스 종료 중...
taskkill /F /IM node.exe >nul 2>&1
if errorlevel 1 (
    echo [INFO] 실행 중인 Node.js 프로세스 없음
) else (
    echo [OK] Node.js 프로세스 종료됨
)

echo.
echo [OK] 정리 완료!
echo.
pause
"""

    (release_dir / "서버정리.bat").write_text(cleanup_script, encoding='utf-8')

    # 문서 작성
    print("[10/10] Creating documentation...")

    readme = """# DoctorVoicePro v3.0 - Ultimate Auto-Install

## 🚀 초간단 실행 방법

### 1단계: 폴더 열기
`DoctorVoicePro_Ultimate_AutoInstall` 폴더로 이동

### 2단계: 실행 파일 클릭
`자동설치_및_실행.bat` 더블클릭

### 3단계: 완료!
- 자동으로 Python, Node.js 설치 (필요한 경우)
- 자동으로 포트 충돌 해결
- 자동으로 백엔드-프론트엔드 연결
- 자동으로 브라우저 오픈

## ✨ 주요 기능

### 완전 자동화
- Python 자동 설치
- Node.js 자동 설치
- 의존성 패키지 자동 설치
- 포트 충돌 자동 감지 및 해결
- 백엔드-프론트엔드 자동 연결
- 헬스체크 및 재시도

### 스마트 포트 관리
- 8000 → 8001 → 8002 자동 시도 (Backend)
- 3000 → 3001 → 3002 자동 시도 (Frontend)
- 환경 파일 자동 동기화

### 로그인 화면 자동 동기화
- 백엔드 서버 상태 실시간 표시
- 자동 동기화 버튼으로 서버 자동 검색
- 수동 URL 설정 가능

## 📋 시스템 요구사항

- Windows 10/11 (64bit)
- 인터넷 연결 (첫 설치 시)
- 4GB RAM 이상 권장
- 2GB 여유 디스크 공간

## 🔧 문제 해결

### 서버 연결 안 됨
1. `서버정리.bat` 실행
2. `자동설치_및_실행.bat` 다시 실행

### Python/Node.js 설치 실패
- 관리자 권한으로 실행
- 인터넷 연결 확인
- 수동 설치: https://python.org, https://nodejs.org

## 📊 접속 정보

실행 후:
- 메인 앱: http://localhost:3000
- Backend: http://localhost:8000
- API 문서: http://localhost:8000/docs

※ 포트 충돌 시 자동으로 다른 포트 사용

## 🎯 완성도

✓ 완전 자동 설치
✓ 포트 충돌 자동 해결
✓ 백엔드-프론트엔드 자동 연결
✓ 헬스체크 및 재시도
✓ 로그인 화면 자동 동기화
✓ 사용자 편의 극대화

---

© 2025 DoctorVoicePro v3.0 Ultimate
"""

    (release_dir / "README.md").write_text(readme, encoding='utf-8')

    # 빠른 시작 가이드
    quick_start = """╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║     닥터보이스 프로 v3.0 - 빠른 시작 가이드                    ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  실행 방법 (30초 완성!)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. "자동설치_및_실행.bat" 더블클릭

2. 완료!

※ Python, Node.js가 없어도 자동으로 설치됩니다


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  자동으로 진행되는 것들
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[1/8] Python 확인 및 자동 설치
[2/8] Node.js 확인 및 자동 설치
[3/8] 포트 충돌 감지 및 해결
[4/8] Backend 설정 및 설치
[5/8] Frontend 설정 및 설치
[6/8] Backend 서버 시작
[7/8] Backend 헬스체크 (자동 재시도)
[8/8] Frontend 서버 시작 + 브라우저 오픈


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  특별 기능
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✨ 로그인 화면 자동 동기화
  → 백엔드 서버 상태 실시간 표시
  → "자동 동기화" 버튼으로 서버 자동 검색
  → 포트 8000~9001 자동 스캔
  → 수동 URL 설정도 가능

✨ 포트 충돌 자동 해결
  → Backend: 8000 → 8001 → 8002 ...
  → Frontend: 3000 → 3001 → 3002 ...
  → 자동으로 사용 가능한 포트 찾기

✨ 백엔드-프론트엔드 자동 연결
  → 환경 파일 자동 업데이트
  → CORS 설정 자동 동기화
  → API URL 자동 설정


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  문제 해결
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q: 서버 연결이 안 돼요
A: 1. "서버정리.bat" 실행
   2. "자동설치_및_실행.bat" 다시 실행

Q: Python/Node.js 설치가 안 돼요
A: 관리자 권한으로 실행하거나 수동 설치
   - Python: https://python.org
   - Node.js: https://nodejs.org

Q: 포트 충돌이 계속 나요
A: 자동으로 해결됩니다! 걱정하지 마세요.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  접속 정보
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

실행 후 자동으로 브라우저가 열립니다!

또는 수동 접속:
  • http://localhost:3000 (메인 앱)
  • http://localhost:8000 (Backend)
  • http://localhost:8000/docs (API 문서)

※ 포트 번호는 자동으로 조정될 수 있습니다


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

© 2025 닥터보이스 프로 v3.0
"""

    (release_dir / "docs" / "빠른시작.txt").write_text(quick_start, encoding='utf-8')

    # 버전 정보
    version_info = """DoctorVoicePro v3.0 Ultimate Auto-Install
Build Date: 2025-10-31

=== VERSION HISTORY ===

v3.0 (2025-10-31) - Ultimate Auto-Install
  ✓ 완전 자동 Python/Node.js 설치
  ✓ 포트 충돌 자동 감지 및 해결
  ✓ 백엔드-프론트엔드 자동 연결
  ✓ 헬스체크 및 자동 재시도
  ✓ 로그인 화면 자동 동기화 버튼
  ✓ 원클릭 실행

v2.0 (Previous)
  ✓ 스마트 포트 감지
  ✓ 환경 설정 자동 업데이트
  ✓ 개선된 GUI

v1.0 (Initial)
  ✓ 기본 기능
"""

    (release_dir / "VERSION.txt").write_text(version_info, encoding='utf-8')

    # package_info.json
    package_info = {
        "name": "DoctorVoicePro",
        "version": "3.0.0",
        "description": "Ultimate Auto-Install Package",
        "features": [
            "Auto Python/Node.js installation",
            "Auto port conflict resolution",
            "Auto backend-frontend connection",
            "Health check with retry",
            "Login page auto-sync button"
        ],
        "build_date": "2025-10-31",
        "requirements": {
            "python": "3.11+",
            "nodejs": "20+",
            "os": "Windows 10/11 64bit"
        }
    }

    with open(release_dir / "package_info.json", 'w', encoding='utf-8') as f:
        json.dump(package_info, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print("  ✓ Package Created Successfully!")
    print("=" * 70)
    print(f"\nPackage Location: {release_dir}")
    print(f"\nTo use:")
    print(f"  1. Open: {release_dir}")
    print(f"  2. Double-click: 자동설치_및_실행.bat")
    print(f"  3. Done!")
    print("\n" + "=" * 70)

if __name__ == '__main__':
    create_ultimate_package()
    print("\n[Press any key to exit...]")
    input()
