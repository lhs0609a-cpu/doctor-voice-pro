"""
닥터보이스 프로 - Portable 배포 패키지 생성 스크립트
다른 컴퓨터에서도 실행 가능한 패키지를 만듭니다.
"""
import os
import shutil
import json
from pathlib import Path
from datetime import datetime

def create_portable_package():
    print("=" * 70)
    print("  닥터보이스 프로 - Portable 패키지 생성")
    print("=" * 70)
    print()

    # 현재 디렉토리
    source_dir = Path(__file__).parent

    # 배포 폴더 이름
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    package_name = f"DoctorVoicePro_Portable_{timestamp}"
    release_dir = source_dir / package_name

    print(f"[*] 배포 폴더: {package_name}")
    print()

    # 폴더 생성
    if release_dir.exists():
        print("[!] 기존 폴더를 삭제합니다...")
        shutil.rmtree(release_dir)

    release_dir.mkdir()

    # 복사할 파일/폴더 목록
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
        'scripts': [
            'find_ports.py',
        ],
        'docs': [
            'README.md',
        ]
    }

    # 파일 복사
    print("[+] 파일 복사 중...")
    copied_count = 0

    for category, items in items_to_copy.items():
        for item in items:
            source_path = source_dir / item

            if not source_path.exists():
                print(f"  [SKIP] {item} (파일 없음)")
                continue

            # 상대 경로 유지
            relative_path = Path(item)
            dest_path = release_dir / relative_path

            # 대상 디렉토리 생성
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # 파일 복사
            if source_path.is_dir():
                if dest_path.exists():
                    shutil.rmtree(dest_path)
                shutil.copytree(source_path, dest_path)
                print(f"  [OK] {item}/ (폴더)")
            else:
                shutil.copy2(source_path, dest_path)
                print(f"  [OK] {item}")

            copied_count += 1

    print(f"\n[OK] {copied_count}개 항목 복사 완료")
    print()

    # 설치 및 실행 스크립트 생성
    print("[+] 실행 스크립트 생성 중...")

    create_install_script(release_dir)
    create_run_script(release_dir)
    create_readme(release_dir, package_name)
    create_requirements_check(release_dir)

    print("[OK] 스크립트 생성 완료")
    print()

    # 패키지 정보 저장
    package_info = {
        "name": "DoctorVoice Pro",
        "version": "1.0.0",
        "created_at": datetime.now().isoformat(),
        "backend_port": 8000,
        "frontend_port": 3000,
    }

    with open(release_dir / "package_info.json", "w", encoding="utf-8") as f:
        json.dump(package_info, f, indent=2, ensure_ascii=False)

    print("=" * 70)
    print("  [SUCCESS] Portable 패키지 생성 완료!")
    print("=" * 70)
    print()
    print(f"[*] 위치: {release_dir}")
    print()
    print("[*] 배포 방법:")
    print(f"  1. '{package_name}' 폴더를 USB나 다른 컴퓨터로 복사")
    print(f"  2. '실행하기.bat' 더블클릭")
    print(f"  3. 첫 실행 시 자동으로 필요한 프로그램 설치")
    print()

    return release_dir

def create_install_script(release_dir):
    """설치 스크립트 생성"""
    script = """@echo off
chcp 65001 > nul
cls
echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║                                                            ║
echo ║          닥터보이스 프로 - 자동 설치                        ║
echo ║                                                            ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
echo.

cd /d "%~dp0"

REM Python 확인
echo [1/4] Python 확인 중...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ❌ Python이 설치되어 있지 않습니다!
    echo.
    echo Python 3.9 이상이 필요합니다.
    echo https://www.python.org/downloads/ 에서 다운로드하세요.
    echo.
    echo 설치 시 "Add Python to PATH" 옵션을 체크하세요!
    echo.
    pause
    exit /b 1
)
echo ✓ Python 설치됨

REM Node.js 확인
echo [2/4] Node.js 확인 중...
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ❌ Node.js가 설치되어 있지 않습니다!
    echo.
    echo Node.js 18 이상이 필요합니다.
    echo https://nodejs.org/ 에서 다운로드하세요.
    echo.
    pause
    exit /b 1
)
echo ✓ Node.js 설치됨

REM Backend 설치
echo [3/4] Backend 의존성 설치 중...
cd backend
if not exist "venv" (
    echo   가상환경 생성 중...
    python -m venv venv
)
call venv\\Scripts\\activate.bat
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo ❌ Backend 설치 실패
    pause
    exit /b 1
)
cd ..
echo ✓ Backend 설치 완료

REM Frontend 설치
echo [4/4] Frontend 의존성 설치 중...
cd frontend
call npm install --loglevel=error
if %errorlevel% neq 0 (
    echo ❌ Frontend 설치 실패
    pause
    exit /b 1
)
cd ..
echo ✓ Frontend 설치 완료

REM 설치 완료 표시 파일 생성
echo installed > .installed

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║                  설치 완료!                                 ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
echo 이제 '🚀 실행하기.bat'을 실행하세요.
echo.
pause
"""

    with open(release_dir / "설치하기.bat", "w", encoding="utf-8") as f:
        f.write(script)

def create_run_script(release_dir):
    """실행 스크립트 생성"""
    script = """@echo off
chcp 65001 > nul
cls

cd /d "%~dp0"

REM 설치 확인
if not exist ".installed" (
    echo.
    echo ╔════════════════════════════════════════════════════════════╗
    echo ║                                                            ║
    echo ║          첫 실행입니다!                                     ║
    echo ║                                                            ║
    echo ╚════════════════════════════════════════════════════════════╝
    echo.
    echo 먼저 설치가 필요합니다.
    echo.
    echo 자동으로 설치를 시작합니다...
    timeout /t 3 /nobreak > nul
    call "설치하기.bat"
    exit /b 0
)

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║                                                            ║
echo ║          닥터보이스 프로 시작                               ║
echo ║                                                            ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

echo [1/3] Backend 서버 시작 중... (Port: 8000)
start "DoctorVoice - Backend" cmd /k "cd /d %~dp0\\backend && call venv\\Scripts\\activate.bat && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo [2/3] 대기 중... (5초)
timeout /t 5 /nobreak > nul

echo [3/3] Frontend 서버 시작 중... (Port: 3000)
start "DoctorVoice - Frontend" cmd /k "cd /d %~dp0\\frontend && npm run dev"

timeout /t 8 /nobreak > nul

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║              서버가 시작되었습니다!                          ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
echo   ✓ Frontend:  http://localhost:3000
echo   ✓ Backend:   http://localhost:8000
echo   ✓ API Docs:  http://localhost:8000/docs
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

    with open(release_dir / "실행하기.bat", "w", encoding="utf-8") as f:
        f.write(script)

def create_readme(release_dir, package_name):
    """README 파일 생성"""
    readme = f"""# 닥터보이스 프로 - Portable Edition

## 패키지 정보

- **버전**: 1.0.0
- **생성일**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **패키지명**: {package_name}

---

## 빠른 시작

### 1. 필수 프로그램 설치

이 프로그램을 실행하려면 다음 프로그램이 필요합니다:

#### Python 3.9 이상
- 다운로드: https://www.python.org/downloads/
- **중요**: 설치 시 "Add Python to PATH" 체크!

#### Node.js 18 이상
- 다운로드: https://nodejs.org/
- LTS 버전 권장

### 2. 실행 방법

```
실행하기.bat
```
위 파일을 더블클릭하세요!

- 첫 실행 시 자동으로 설치가 진행됩니다 (5-10분 소요)
- 두 번째 실행부터는 바로 시작됩니다

### 3. 접속

브라우저에서 자동으로 열립니다:
- **메인 앱**: http://localhost:3000
- **API 문서**: http://localhost:8000/docs

---

## 폴더 구조

```
{package_name}/
├── 실행하기.bat              # 실행 파일 (원클릭)
├── 설치하기.bat              # 수동 설치 (필요시)
├── README.txt               # 이 파일
├── backend/                 # 백엔드 서버
│   ├── app/                # 애플리케이션 코드
│   ├── requirements.txt    # Python 의존성
│   └── .env               # 환경 설정
└── frontend/               # 프론트엔드 앱
    ├── src/               # 소스 코드
    ├── package.json       # Node.js 의존성
    └── .env.local        # 환경 설정
```

---

## 문제 해결

### "Python이 설치되어 있지 않습니다"
- Python을 설치하고 PATH에 추가하세요

### "Node.js가 설치되어 있지 않습니다"
- Node.js를 설치하세요

### "포트가 이미 사용 중입니다"
- 작업 관리자에서 python.exe, node.exe 프로세스 종료

### 설치가 실패합니다
- 인터넷 연결을 확인하세요 (의존성 다운로드 필요)

---

## 사용 팁

- **서버 종료**: 서버 창(검은 창)을 닫으면 됩니다
- **재시작**: `실행하기.bat`을 다시 실행
- **설정 변경**: backend/.env 또는 frontend/.env.local 수정

---

## 지원

문제가 발생하면:
1. 서버 창의 에러 메시지 확인
2. README.txt의 문제 해결 섹션 참고
3. 모든 프로그램을 종료하고 재시작

---

© 2025 닥터보이스 프로. All rights reserved.
"""

    with open(release_dir / "README.txt", "w", encoding="utf-8") as f:
        f.write(readme)

def create_requirements_check(release_dir):
    """시스템 요구사항 체크 스크립트"""
    script = """@echo off
chcp 65001 > nul
cls
echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║                                                            ║
echo ║          시스템 요구사항 확인                               ║
echo ║                                                            ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
echo.

echo 현재 시스템을 확인하는 중...
echo.

REM Python 확인
echo [1/3] Python 확인
python --version 2>nul
if %errorlevel% equ 0 (
    echo ✓ Python 설치됨
) else (
    echo ❌ Python 없음 - https://www.python.org/downloads/
)
echo.

REM Node.js 확인
echo [2/3] Node.js 확인
node --version 2>nul
if %errorlevel% equ 0 (
    echo ✓ Node.js 설치됨
) else (
    echo ❌ Node.js 없음 - https://nodejs.org/
)
echo.

REM npm 확인
echo [3/3] npm 확인
npm --version 2>nul
if %errorlevel% equ 0 (
    echo ✓ npm 설치됨
) else (
    echo ❌ npm 없음 - Node.js와 함께 설치됨
)
echo.

echo.
echo ════════════════════════════════════════════════════════════
echo.
pause
"""

    with open(release_dir / "시스템_확인.bat", "w", encoding="utf-8") as f:
        f.write(script)

if __name__ == "__main__":
    try:
        release_dir = create_portable_package()
        print(f"[OK] 완료! 폴더를 확인하세요: {release_dir.name}")
    except Exception as e:
        print(f"[ERROR] 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        input("\nEnter를 눌러 종료...")
