"""
닥터보이스 프로 - 완전 독립 실행 패키지 생성
Python, Node.js 자동 설치 포함
"""
import os
import shutil
import json
from pathlib import Path
from datetime import datetime

def create_full_portable_package():
    print("=" * 70)
    print("  닥터보이스 프로 - 완전 독립 실행 패키지 생성")
    print("  (Python, Node.js 자동 설치 포함)")
    print("=" * 70)
    print()

    source_dir = Path(__file__).parent
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    package_name = f"DoctorVoicePro_FullPortable_{timestamp}"
    release_dir = source_dir / package_name

    print(f"[*] 패키지 폴더: {package_name}")
    print()

    # 폴더 생성
    if release_dir.exists():
        print("[!] 기존 폴더 삭제 중...")
        shutil.rmtree(release_dir)

    release_dir.mkdir()

    # 하위 폴더 생성
    (release_dir / "runtime").mkdir()
    (release_dir / "app").mkdir()

    print("[+] 애플리케이션 파일 복사 중...")

    # 복사할 파일/폴더
    items_to_copy = {
        'backend': [
            'backend/app',
            'backend/alembic',
            'backend/alembic.ini',
            'backend/requirements.txt',
            'backend/.env',
            'backend/.env.example',
        ],
        'frontend': [
            'frontend/src',
            'frontend/public',
            'frontend/package.json',
            'frontend/package-lock.json',
            'frontend/next.config.js',
            'frontend/tsconfig.json',
            'frontend/tailwind.config.ts',
            'frontend/postcss.config.js',
            'frontend/.env.local',
        ],
    }

    copied_count = 0
    for category, items in items_to_copy.items():
        for item in items:
            source_path = source_dir / item
            if not source_path.exists():
                print(f"  [SKIP] {item}")
                continue

            relative_path = Path(item)
            dest_path = release_dir / "app" / relative_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            if source_path.is_dir():
                if dest_path.exists():
                    shutil.rmtree(dest_path)
                shutil.copytree(source_path, dest_path)
                print(f"  [OK] {item}/")
            else:
                shutil.copy2(source_path, dest_path)
                print(f"  [OK] {item}")

            copied_count += 1

    print(f"\n[OK] {copied_count}개 항목 복사 완료\n")

    # 스크립트 생성
    print("[+] 실행 스크립트 생성 중...")
    create_auto_installer(release_dir)
    create_launcher(release_dir)
    create_readme_full(release_dir, package_name)

    # 패키지 정보
    package_info = {
        "name": "DoctorVoice Pro - Full Portable",
        "version": "1.0.0",
        "created_at": datetime.now().isoformat(),
        "includes": ["Python", "Node.js", "Application"],
        "backend_port": 8000,
        "frontend_port": 3000,
    }

    with open(release_dir / "package_info.json", "w", encoding="utf-8") as f:
        json.dump(package_info, f, indent=2, ensure_ascii=False)

    print("=" * 70)
    print("  [SUCCESS] 완전 독립 실행 패키지 생성 완료!")
    print("=" * 70)
    print()
    print(f"[*] 위치: {release_dir}")
    print()
    print("[*] 사용 방법:")
    print(f"  1. '{package_name}' 폴더를 다른 컴퓨터로 복사")
    print(f"  2. '실행.bat' 더블클릭 (Python, Node.js 자동 설치)")
    print(f"  3. 완료!")
    print()

    return release_dir

def create_auto_installer(release_dir):
    """Python과 Node.js를 자동으로 다운로드하고 설치하는 스크립트"""

    script = """@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

cd /d "%~dp0"

cls
echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║                                                            ║
echo ║          닥터보이스 프로 - 자동 설치                        ║
echo ║          (Python, Node.js 포함)                            ║
echo ║                                                            ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
echo.

REM 설치 완료 확인
if exist ".installed" (
    echo [*] 이미 설치되어 있습니다.
    echo [*] 서버를 시작합니다...
    echo.
    goto :start_servers
)

echo [단계 1/4] Python 설치 확인 중...
echo.

REM Python 확인
set "PYTHON_DIR=%~dp0runtime\\python"
set "PYTHON_EXE=%PYTHON_DIR%\\python.exe"

if not exist "%PYTHON_EXE%" (
    echo [*] Python Portable 다운로드 중...
    echo [*] Python 3.11 embedded 버전
    echo.

    REM Python embeddable 다운로드
    powershell -Command "& { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip' -OutFile 'python.zip' }"

    if !errorlevel! neq 0 (
        echo [ERROR] Python 다운로드 실패
        echo.
        echo 수동 설치가 필요합니다:
        echo 1. Python 3.9+ 설치: https://www.python.org/downloads/
        echo 2. "Add Python to PATH" 옵션 체크
        echo.
        pause
        exit /b 1
    )

    echo [*] Python 압축 해제 중...
    powershell -Command "Expand-Archive -Path 'python.zip' -DestinationPath '%PYTHON_DIR%' -Force"
    del python.zip

    REM get-pip.py 다운로드
    echo [*] pip 설치 중...
    powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%PYTHON_DIR%\\get-pip.py'"

    REM pip 설치
    "%PYTHON_EXE%" "%PYTHON_DIR%\\get-pip.py" --no-warn-script-location

    REM pth 파일 수정 (site-packages 활성화)
    echo import site > "%PYTHON_DIR%\\python311._pth"

    echo [OK] Python 설치 완료
) else (
    echo [OK] Python 이미 설치됨
)
echo.

echo [단계 2/4] Node.js 설치 확인 중...
echo.

REM Node.js 확인
set "NODE_DIR=%~dp0runtime\\nodejs"
set "NODE_EXE=%NODE_DIR%\\node.exe"
set "NPM_CMD=%NODE_DIR%\\npm.cmd"

if not exist "%NODE_EXE%" (
    echo [*] Node.js Portable 다운로드 중...
    echo [*] Node.js v20 LTS
    echo.

    REM Node.js 다운로드
    powershell -Command "& { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://nodejs.org/dist/v20.11.0/node-v20.11.0-win-x64.zip' -OutFile 'nodejs.zip' }"

    if !errorlevel! neq 0 (
        echo [ERROR] Node.js 다운로드 실패
        echo.
        echo 수동 설치가 필요합니다:
        echo 1. Node.js 18+ 설치: https://nodejs.org/
        echo.
        pause
        exit /b 1
    )

    echo [*] Node.js 압축 해제 중...
    powershell -Command "Expand-Archive -Path 'nodejs.zip' -DestinationPath 'runtime' -Force"
    move "runtime\\node-v20.11.0-win-x64" "%NODE_DIR%" >nul 2>&1
    del nodejs.zip

    echo [OK] Node.js 설치 완료
) else (
    echo [OK] Node.js 이미 설치됨
)
echo.

echo [단계 3/4] Backend 의존성 설치 중...
echo.

cd app\\backend

REM Python 가상환경 생성
if not exist "venv" (
    echo [*] 가상환경 생성 중...
    "%PYTHON_EXE%" -m venv venv
)

REM 가상환경 활성화 및 패키지 설치
call venv\\Scripts\\activate.bat
pip install -r requirements.txt --quiet

if !errorlevel! neq 0 (
    echo [ERROR] Backend 설치 실패
    pause
    exit /b 1
)

cd ..\..
echo [OK] Backend 설치 완료
echo.

echo [단계 4/4] Frontend 의존성 설치 중...
echo.

cd app\\frontend

REM PATH에 Node.js 추가
set "PATH=%NODE_DIR%;%PATH%"

REM npm 설치
call "%NPM_CMD%" install --loglevel=error

if !errorlevel! neq 0 (
    echo [ERROR] Frontend 설치 실패
    pause
    exit /b 1
)

cd ..\..
echo [OK] Frontend 설치 완료
echo.

REM 설치 완료 표시
echo installed > .installed

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║                  설치 완료!                                 ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
echo 서버를 시작합니다...
timeout /t 3 /nobreak > nul

:start_servers
cls
echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║                                                            ║
echo ║          닥터보이스 프로 시작                               ║
echo ║                                                            ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

echo [1/3] Backend 서버 시작 중... (Port: 8000)
start "DoctorVoice - Backend" cmd /k "cd /d %~dp0\\app\\backend && call venv\\Scripts\\activate.bat && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo [2/3] 대기 중... (5초)
timeout /t 5 /nobreak > nul

echo [3/3] Frontend 서버 시작 중... (Port: 3000)
set "PATH=%NODE_DIR%;%PATH%"
start "DoctorVoice - Frontend" cmd /k "cd /d %~dp0\\app\\frontend && %NPM_CMD% run dev"

timeout /t 8 /nobreak > nul

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║              서버가 시작되었습니다!                          ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
echo   Frontend: http://localhost:3000
echo   Backend:  http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo.
echo   브라우저를 여는 중...
echo.

start http://localhost:3000

timeout /t 3 /nobreak > nul
cls
echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║            서버가 백그라운드에서 실행 중                     ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
echo   이 창은 닫아도 됩니다.
echo   서버를 종료하려면 서버 창을 닫으세요.
echo.
pause
"""

    with open(release_dir / "설치및실행.bat", "w", encoding="utf-8") as f:
        f.write(script)

def create_launcher(release_dir):
    """간단한 실행 스크립트"""
    script = """@echo off
chcp 65001 > nul
cd /d "%~dp0"

REM 설치되어 있지 않으면 설치 실행
if not exist ".installed" (
    call "설치및실행.bat"
    exit /b 0
)

cls
echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║          닥터보이스 프로 시작                               ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

set "NODE_DIR=%~dp0runtime\\nodejs"
set "NPM_CMD=%NODE_DIR%\\npm.cmd"

echo [1/3] Backend 서버 시작 중...
start "DoctorVoice - Backend" cmd /k "cd /d %~dp0\\app\\backend && call venv\\Scripts\\activate.bat && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 5 /nobreak > nul

echo [2/3] Frontend 서버 시작 중...
set "PATH=%NODE_DIR%;%PATH%"
start "DoctorVoice - Frontend" cmd /k "cd /d %~dp0\\app\\frontend && %NPM_CMD% run dev"

timeout /t 8 /nobreak > nul

echo [3/3] 브라우저 열기...
start http://localhost:3000

echo.
echo 서버가 시작되었습니다!
echo Frontend: http://localhost:3000
echo Backend:  http://localhost:8000
echo.
pause
"""

    with open(release_dir / "실행.bat", "w", encoding="utf-8") as f:
        f.write(script)

def create_readme_full(release_dir, package_name):
    """README 파일"""
    readme = f"""# 닥터보이스 프로 - 완전 독립 실행 패키지

## 패키지 정보

- **버전**: 1.0.0 Full Portable
- **생성일**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **포함**: Python 3.11 + Node.js 20 + Application

---

## 빠른 시작 (3단계)

### 1. 폴더 복사
이 폴더를 원하는 컴퓨터로 복사하세요.

### 2. 실행
```
실행.bat
```
또는
```
설치및실행.bat
```
파일을 더블클릭하세요!

### 3. 완료!
- 첫 실행 시 Python과 Node.js를 자동으로 다운로드합니다 (5-10분)
- 인터넷 연결이 필요합니다
- 두 번째 실행부터는 즉시 시작됩니다

---

## 특징

### 완전 독립 실행
- Python 설치 불필요 (자동 다운로드)
- Node.js 설치 불필요 (자동 다운로드)
- 관리자 권한 불필요
- 레지스트리 수정 없음

### 자동 설치
- Python 3.11 Embedded 자동 다운로드
- Node.js 20 LTS Portable 자동 다운로드
- 모든 의존성 자동 설치

### 원클릭 실행
- 한 번의 클릭으로 모든 것이 실행됩니다
- Backend와 Frontend 자동 연결
- 브라우저 자동 오픈

---

## 폴더 구조

```
{package_name}/
│
├── 실행.bat                  ← 빠른 실행 (설치 후)
├── 설치및실행.bat             ← 첫 실행 (자동 설치)
├── README.txt
│
├── runtime/                  (런타임 환경)
│   ├── python/              (자동 다운로드됨)
│   └── nodejs/              (자동 다운로드됨)
│
└── app/                     (애플리케이션)
    ├── backend/             (백엔드)
    └── frontend/            (프론트엔드)
```

---

## 시스템 요구사항

- **OS**: Windows 10/11 (64bit)
- **메모리**: 4GB 이상 권장
- **디스크**: 2GB 여유 공간
- **인터넷**: 첫 설치 시에만 필요

---

## 사용 방법

### 첫 실행
1. `설치및실행.bat` 더블클릭
2. Python 다운로드 중... (약 30MB)
3. Node.js 다운로드 중... (약 50MB)
4. 의존성 설치 중... (약 5분)
5. 서버 시작!

### 이후 실행
1. `실행.bat` 더블클릭
2. 즉시 시작!

---

## 접속 정보

- **메인 앱**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API 문서**: http://localhost:8000/docs

---

## 문제 해결

### 다운로드 실패
- 인터넷 연결을 확인하세요
- 방화벽 설정을 확인하세요

### 포트 충돌
- 작업 관리자에서 python.exe, node.exe 종료

### 설치 실패
- `설치및실행.bat`을 다시 실행하세요
- `.installed` 파일을 삭제하고 재시도

---

## 장점

✓ 시스템에 아무것도 설치하지 않음
✓ USB에서 바로 실행 가능
✓ 여러 버전 동시 실행 가능
✓ 삭제가 간단 (폴더만 삭제)
✓ 다른 컴퓨터로 이동 가능

---

## 배포

이 폴더를 압축(ZIP)해서 공유하면:
1. 받은 사람이 압축 해제
2. `설치및실행.bat` 실행
3. 완료!

---

© 2025 닥터보이스 프로. All rights reserved.
"""

    with open(release_dir / "README.txt", "w", encoding="utf-8") as f:
        f.write(readme)

if __name__ == "__main__":
    try:
        release_dir = create_full_portable_package()
        print(f"[OK] 완료! 폴더: {release_dir.name}")
    except Exception as e:
        print(f"[ERROR] 에러: {e}")
        import traceback
        traceback.print_exc()
        input("\nEnter를 눌러 종료...")
