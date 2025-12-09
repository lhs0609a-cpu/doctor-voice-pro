"""
닥터보이스 프로 - 최종 완성 패키지 생성
모든 기능이 포함된 완전한 배포 패키지
"""
import os
import shutil
import json
from pathlib import Path
from datetime import datetime

def create_final_package():
    print("=" * 70)
    print("  닥터보이스 프로 - 최종 완성 패키지 생성")
    print("=" * 70)
    print()

    source_dir = Path(__file__).parent
    package_name = "DoctorVoicePro_Final_Release"
    release_dir = source_dir / package_name

    print(f"[*] 패키지 폴더: {package_name}")
    print()

    # 기존 폴더 삭제
    if release_dir.exists():
        print("[!] 기존 폴더 삭제 중...")
        shutil.rmtree(release_dir)

    # 폴더 구조 생성
    release_dir.mkdir()
    (release_dir / "docs").mkdir()

    print("[1/7] 애플리케이션 파일 복사 중...")
    print()

    # Backend 복사
    items = [
        ('backend/app', 'backend/app'),
        ('backend/alembic', 'backend/alembic'),
        ('backend/alembic.ini', 'backend/alembic.ini'),
        ('backend/requirements.txt', 'backend/requirements.txt'),
        ('backend/.env', 'backend/.env'),
        ('backend/.env.example', 'backend/.env.example'),
    ]

    copied = 0
    for source, dest in items:
        src_path = source_dir / source
        dst_path = release_dir / dest

        if not src_path.exists():
            print(f"  [SKIP] {source}")
            continue

        dst_path.parent.mkdir(parents=True, exist_ok=True)

        if src_path.is_dir():
            if dst_path.exists():
                shutil.rmtree(dst_path)
            shutil.copytree(src_path, dst_path)
            print(f"  [OK] {source}/")
        else:
            shutil.copy2(src_path, dst_path)
            print(f"  [OK] {source}")
        copied += 1

    # Frontend 복사
    frontend_items = [
        ('frontend/src', 'frontend/src'),
        ('frontend/public', 'frontend/public'),
        ('frontend/package.json', 'frontend/package.json'),
        ('frontend/package-lock.json', 'frontend/package-lock.json'),
        ('frontend/next.config.js', 'frontend/next.config.js'),
        ('frontend/tsconfig.json', 'frontend/tsconfig.json'),
        ('frontend/tailwind.config.ts', 'frontend/tailwind.config.ts'),
        ('frontend/postcss.config.js', 'frontend/postcss.config.js'),
        ('frontend/.env.local', 'frontend/.env.local'),
    ]

    for source, dest in frontend_items:
        src_path = source_dir / source
        dst_path = release_dir / dest

        if not src_path.exists():
            print(f"  [SKIP] {source}")
            continue

        dst_path.parent.mkdir(parents=True, exist_ok=True)

        if src_path.is_dir():
            if dst_path.exists():
                shutil.rmtree(dst_path)
            shutil.copytree(src_path, dst_path)
            print(f"  [OK] {source}/")
        else:
            shutil.copy2(src_path, dst_path)
            print(f"  [OK] {source}")
        copied += 1

    print(f"\n[OK] {copied}개 파일/폴더 복사 완료\n")

    # 유틸리티 스크립트 복사
    print("[2/7] 유틸리티 스크립트 생성 중...")
    create_port_checker(release_dir)
    create_smart_launcher(release_dir)
    create_server_cleanup(release_dir)
    create_simple_launcher(release_dir)
    print("[OK] 스크립트 생성 완료\n")

    # 문서 생성
    print("[3/7] 문서 생성 중...")
    create_main_readme(release_dir)
    create_quick_guide(release_dir)
    create_troubleshooting_guide(release_dir)
    print("[OK] 문서 생성 완료\n")

    # 패키지 정보
    print("[4/7] 패키지 정보 저장 중...")
    package_info = {
        "name": "DoctorVoice Pro",
        "version": "2.0.0",
        "release_date": datetime.now().isoformat(),
        "features": [
            "Smart Port Detection",
            "Auto Configuration",
            "Health Check",
            "Modern UI with Animations",
            "Auto Installation"
        ],
        "default_ports": {
            "backend": 8000,
            "frontend": 3000
        }
    }

    with open(release_dir / "package_info.json", "w", encoding="utf-8") as f:
        json.dump(package_info, f, indent=2, ensure_ascii=False)
    print("[OK] 패키지 정보 저장 완료\n")

    # 버전 파일
    print("[5/7] 버전 파일 생성 중...")
    with open(release_dir / "VERSION.txt", "w", encoding="utf-8") as f:
        f.write(f"DoctorVoice Pro v2.0.0\n")
        f.write(f"Release Date: {datetime.now().strftime('%Y-%m-%d')}\n")
        f.write(f"\nFeatures:\n")
        f.write(f"- Smart Port Auto-Detection\n")
        f.write(f"- Automatic Configuration\n")
        f.write(f"- Health Monitoring\n")
        f.write(f"- Modern Animated UI\n")
    print("[OK] 버전 파일 생성 완료\n")

    # 라이센스
    print("[6/7] 라이센스 파일 생성 중...")
    with open(release_dir / "LICENSE.txt", "w", encoding="utf-8") as f:
        f.write(f"DoctorVoice Pro - Medical Blog Automation Tool\n")
        f.write(f"Copyright (c) 2025 DoctorVoice Pro\n")
        f.write(f"\nAll rights reserved.\n")
    print("[OK] 라이센스 파일 생성 완료\n")

    # .gitignore
    print("[7/7] .gitignore 생성 중...")
    with open(release_dir / ".gitignore", "w") as f:
        f.write("# Dependencies\n")
        f.write("backend/venv/\n")
        f.write("frontend/node_modules/\n")
        f.write("\n# Build\n")
        f.write("frontend/.next/\n")
        f.write("frontend/out/\n")
        f.write("\n# Database\n")
        f.write("*.db\n")
        f.write("*.sqlite\n")
        f.write("\n# Config\n")
        f.write(".installed\n")
        f.write("port_config.json\n")
        f.write("\n# Logs\n")
        f.write("*.log\n")
        f.write("\n# OS\n")
        f.write(".DS_Store\n")
        f.write("Thumbs.db\n")
    print("[OK] .gitignore 생성 완료\n")

    print("=" * 70)
    print("  [SUCCESS] 최종 완성 패키지 생성 완료!")
    print("=" * 70)
    print()
    print(f"[*] 위치: {release_dir}")
    print()
    print("[*] 포함된 내용:")
    print("  - Backend 애플리케이션")
    print("  - Frontend 애플리케이션 (개선된 UI)")
    print("  - 스마트 자동 실행 스크립트")
    print("  - 포트 자동 감지 시스템")
    print("  - 완전한 문서")
    print()
    print("[*] 실행 방법:")
    print("  1. 폴더 진입")
    print("  2. '스마트_실행.bat' 더블클릭")
    print("  3. 완료!")
    print()

    return release_dir

def create_port_checker(release_dir):
    """포트 체커 스크립트"""
    script = '''"""
포트 사용 여부 확인 및 사용 가능한 포트 찾기
"""
import socket
import json
import sys

def is_port_available(port, host='127.0.0.1'):
    """포트가 사용 가능한지 확인"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex((host, port))
            return result != 0
    except Exception:
        return False

def find_available_port(start_port, max_attempts=50):
    """사용 가능한 포트 찾기"""
    for port in range(start_port, start_port + max_attempts):
        if is_port_available(port):
            return port
    return None

def check_and_find_ports():
    """백엔드와 프론트엔드용 포트 확인 및 찾기"""
    default_backend_port = 8000
    default_frontend_port = 3000

    # 백엔드 포트
    backend_port = default_backend_port
    if not is_port_available(backend_port):
        print(f"[!] 포트 {backend_port} 사용 중, 대체 포트 검색...")
        backend_port = find_available_port(8000)
        if backend_port:
            print(f"[OK] 백엔드 포트: {backend_port}")
        else:
            print(f"[ERROR] 사용 가능한 포트 없음")
            sys.exit(1)
    else:
        print(f"[OK] 백엔드 포트: {backend_port}")

    # 프론트엔드 포트
    frontend_port = default_frontend_port
    if not is_port_available(frontend_port):
        print(f"[!] 포트 {frontend_port} 사용 중, 대체 포트 검색...")
        frontend_port = find_available_port(3000)
        if frontend_port:
            print(f"[OK] 프론트엔드 포트: {frontend_port}")
        else:
            print(f"[ERROR] 사용 가능한 포트 없음")
            sys.exit(1)
    else:
        print(f"[OK] 프론트엔드 포트: {frontend_port}")

    result = {
        "backend_port": backend_port,
        "frontend_port": frontend_port,
        "backend_url": f"http://localhost:{backend_port}",
        "frontend_url": f"http://localhost:{frontend_port}"
    }

    with open('port_config.json', 'w') as f:
        json.dump(result, f, indent=2)

    return result

if __name__ == "__main__":
    try:
        check_and_find_ports()
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
'''

    with open(release_dir / "port_checker.py", "w", encoding="utf-8") as f:
        f.write(script)

def create_smart_launcher(release_dir):
    """스마트 실행 스크립트 - 계속"""

    script = """@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

cd /d "%~dp0"

cls
echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║                                                            ║
echo ║          닥터보이스 프로 v2.0                               ║
echo ║          스마트 자동 실행                                   ║
echo ║                                                            ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

REM 포트 체크
echo [1/6] 포트 충돌 체크...
python port_checker.py
if %errorlevel% neq 0 (
    echo [ERROR] 포트 체크 실패
    pause
    exit /b 1
)

REM 포트 설정 읽기
for /f "tokens=*" %%i in ('powershell -Command "$config = Get-Content 'port_config.json' | ConvertFrom-Json; Write-Output $config.backend_port"') do set BACKEND_PORT=%%i
for /f "tokens=*" %%i in ('powershell -Command "$config = Get-Content 'port_config.json' | ConvertFrom-Json; Write-Output $config.frontend_port"') do set FRONTEND_PORT=%%i

echo [OK] Backend: %BACKEND_PORT%, Frontend: %FRONTEND_PORT%
echo.

REM 설치 확인
if exist ".installed" goto :start_servers

echo [2/6] Python 확인...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 미설치
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python 확인
echo.

echo [3/6] Node.js 확인...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js 미설치
    echo https://nodejs.org/
    pause
    exit /b 1
)
echo [OK] Node.js 확인
echo.

echo [4/6] Backend 설치...
cd backend
if not exist "venv" python -m venv venv
call venv\\Scripts\\activate.bat

REM .env 업데이트
powershell -Command "(Get-Content .env) -replace 'ALLOWED_ORIGINS=.*', 'ALLOWED_ORIGINS=http://localhost:%FRONTEND_PORT%' | Set-Content .env"

pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Backend 설치 실패
    pause
    exit /b 1
)
cd ..
echo [OK] Backend 설치 완료
echo.

echo [5/6] Frontend 설치...
cd frontend
echo NEXT_PUBLIC_API_URL=http://localhost:%BACKEND_PORT% > .env.local
call npm install --loglevel=error
if %errorlevel% neq 0 (
    echo [ERROR] Frontend 설치 실패
    pause
    exit /b 1
)
cd ..
echo [OK] Frontend 설치 완료
echo.

echo installed > .installed

:start_servers
cls
echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║              서버 시작 중...                                ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

echo [6/6] 서버 시작...
echo.
echo Backend (Port %BACKEND_PORT%) 시작 중...
start "DoctorVoice - Backend [%BACKEND_PORT%]" cmd /k "cd /d %~dp0\\backend && call venv\\Scripts\\activate.bat && python -m uvicorn app.main:app --host 0.0.0.0 --port %BACKEND_PORT% --reload"

timeout /t 10 /nobreak > nul

echo Frontend (Port %FRONTEND_PORT%) 시작 중...
start "DoctorVoice - Frontend [%FRONTEND_PORT%]" cmd /k "cd /d %~dp0\\frontend && npm run dev"

timeout /t 8 /nobreak > nul

cls
echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║              ✓ 서버 실행 완료!                              ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
echo   Frontend: http://localhost:%FRONTEND_PORT%
echo   Backend:  http://localhost:%BACKEND_PORT%
echo   API Docs: http://localhost:%BACKEND_PORT%/docs
echo.
echo   브라우저를 여는 중...
echo.

start http://localhost:%FRONTEND_PORT%

timeout /t 3 /nobreak > nul
echo   이 창은 닫아도 됩니다.
pause
"""

    with open(release_dir / "스마트_실행.bat", "w", encoding="utf-8") as f:
        f.write(script)

def create_server_cleanup(release_dir):
    """서버 정리 스크립트"""
    script = """@echo off
chcp 65001 > nul
echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║              서버 프로세스 정리                              ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

taskkill /F /IM python.exe /T >nul 2>&1
taskkill /F /IM node.exe /T >nul 2>&1

echo [OK] 모든 서버 프로세스가 종료되었습니다.
echo.
pause
"""

    with open(release_dir / "서버정리.bat", "w", encoding="utf-8") as f:
        f.write(script)

def create_simple_launcher(release_dir):
    """간단 실행 스크립트"""
    script = """@echo off
chcp 65001 > nul
cd /d "%~dp0"

if not exist ".installed" (
    call "스마트_실행.bat"
) else (
    start "Backend" cmd /k "cd backend && call venv\\Scripts\\activate.bat && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
    timeout /t 5 /nobreak > nul
    start "Frontend" cmd /k "cd frontend && npm run dev"
    timeout /t 8 /nobreak > nul
    start http://localhost:3000
)
"""

    with open(release_dir / "빠른실행.bat", "w", encoding="utf-8") as f:
        f.write(script)

def create_main_readme(release_dir):
    """메인 README"""
    content = """# 닥터보이스 프로 v2.0

AI 기반 의료 블로그 자동 각색 시스템

## 빠른 시작

```
스마트_실행.bat
```

위 파일을 더블클릭하세요!

## 주요 기능

- 🤖 AI 기반 의료 정보 자동 각색
- 🛡️ 의료법 자동 검증
- 📊 SEO 자동 최적화
- 🎨 현대적인 UI/UX
- ⚡ 스마트 포트 자동 감지
- 🔧 자동 환경 설정

## 시스템 요구사항

- Python 3.9+
- Node.js 18+
- Windows 10/11

## 설치

첫 실행 시 자동으로 설치됩니다.

## 문서

- `docs/빠른시작가이드.txt` - 빠른 시작 가이드
- `docs/문제해결.txt` - 문제 해결 가이드
- `README.md` - 이 파일

## 라이센스

Copyright (c) 2025 DoctorVoice Pro. All rights reserved.
"""

    with open(release_dir / "README.md", "w", encoding="utf-8") as f:
        f.write(content)

def create_quick_guide(release_dir):
    """빠른 시작 가이드"""
    content = """╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║     닥터보이스 프로 v2.0 - 빠른 시작 가이드                     ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝

🚀 3단계로 시작하기

1. 스마트_실행.bat 더블클릭
2. 자동 설치 및 실행 대기 (첫 실행 시 5-10분)
3. 브라우저에서 http://localhost:3000 접속

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✨ 주요 기능

• 스마트 포트 감지
  → 포트 충돌 자동 해결
  → 8000, 3000이 사용 중이면 8001, 3001 자동 사용

• 자동 환경 설정
  → Backend-Frontend 자동 연결
  → .env 파일 자동 업데이트

• 헬스 체크
  → Backend 정상 작동 확인
  → 연결 상태 자동 테스트

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 실행 파일 설명

• 스마트_실행.bat ⭐
  → 추천! 모든 기능 포함

• 빠른실행.bat
  → 설치 후 빠른 실행

• 서버정리.bat
  → 프로세스 정리

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔧 문제 발생 시

1. 서버정리.bat 실행
2. 스마트_실행.bat 다시 실행

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

© 2025 DoctorVoice Pro
"""

    docs_dir = release_dir / "docs"
    with open(docs_dir / "빠른시작가이드.txt", "w", encoding="utf-8") as f:
        f.write(content)

def create_troubleshooting_guide(release_dir):
    """문제 해결 가이드"""
    content = """╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║     문제 해결 가이드                                           ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ ERR_CONNECTION_REFUSED

원인: 서버가 시작되지 않음

해결:
1. 서버정리.bat 실행
2. Backend 창 확인 (에러 메시지)
3. Frontend 창 확인
4. 스마트_실행.bat 다시 실행

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ 포트가 이미 사용 중

원인: 다른 프로그램이 포트 사용

해결:
→ 스마트_실행.bat 사용 (자동 해결!)
→ 다른 포트를 자동으로 찾아서 사용

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ Python/Node.js 미설치

원인: 필수 프로그램 없음

해결:
1. Python 3.9+ 설치
   https://www.python.org/downloads/
   ⚠️ "Add Python to PATH" 체크!

2. Node.js 18+ 설치
   https://nodejs.org/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ 설치 실패

원인: 네트워크 또는 의존성 문제

해결:
1. 인터넷 연결 확인
2. .installed 파일 삭제
3. 스마트_실행.bat 다시 실행

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ Backend 헬스 체크 실패

원인: Backend 시작 지연

해결:
→ Backend 창에서 "Application startup complete" 확인
→ 10초 더 기다리기

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 추가 도움말

port_config.json 파일을 확인하면
현재 사용 중인 포트를 알 수 있습니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

© 2025 DoctorVoice Pro
"""

    docs_dir = release_dir / "docs"
    with open(docs_dir / "문제해결.txt", "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    try:
        release_dir = create_final_package()
        print(f"\n[SUCCESS] 완료! 폴더: {release_dir.name}\n")
    except Exception as e:
        print(f"\n[ERROR] 에러: {e}\n")
        import traceback
        traceback.print_exc()
        input("\nEnter를 눌러 종료...")
