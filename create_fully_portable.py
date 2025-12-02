"""
완전 포터블 패키지 생성
Python과 Node.js를 포함하여 다른 설치 없이 실행 가능
"""
import os
import shutil
import zipfile
import urllib.request
from pathlib import Path
from datetime import datetime
import subprocess


class FullyPortablePackageBuilder:
    def __init__(self):
        self.package_name = f"DoctorVoicePro_FullyPortable_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.package_dir = Path(self.package_name)

        # 다운로드 URL
        self.python_url = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
        self.node_url = "https://nodejs.org/dist/v20.11.1/node-v20.11.1-win-x64.zip"
        self.get_pip_url = "https://bootstrap.pypa.io/get-pip.py"

    def print_section(self, title):
        print("\n" + "=" * 70)
        print(f"  {title}")
        print("=" * 70)

    def download_file(self, url, dest_path, desc):
        """파일 다운로드"""
        print(f"[DOWNLOAD] {desc} downloading...")
        print(f"   URL: {url}")

        try:
            urllib.request.urlretrieve(url, dest_path)
            size_mb = os.path.getsize(dest_path) / (1024 * 1024)
            print(f"[OK] Download complete ({size_mb:.1f} MB)")
            return True
        except Exception as e:
            print(f"[ERROR] Download failed: {e}")
            return False

    def create_package_structure(self):
        """패키지 디렉토리 구조 생성"""
        self.print_section("패키지 디렉토리 생성")

        if self.package_dir.exists():
            print("기존 디렉토리 삭제 중...")
            shutil.rmtree(self.package_dir)

        self.package_dir.mkdir()
        (self.package_dir / "runtime").mkdir()
        (self.package_dir / "app").mkdir()

        print("[OK] Directory structure created")

    def setup_python(self):
        """Python Embedded 설정"""
        self.print_section("Python Embedded 설정")

        python_zip = self.package_dir / "python.zip"
        python_dir = self.package_dir / "runtime" / "python"

        # Python 다운로드
        if not self.download_file(self.python_url, python_zip, "Python 3.12 Embedded"):
            return False

        # 압축 해제
        print(" Python 압축 해제 중...")
        with zipfile.ZipFile(python_zip, 'r') as zip_ref:
            zip_ref.extractall(python_dir)
        python_zip.unlink()
        print(" Python 압축 해제 완료")

        # python312._pth 파일 수정 (pip 사용 가능하게)
        pth_file = python_dir / "python312._pth"
        if pth_file.exists():
            content = pth_file.read_text()
            content = content.replace("#import site", "import site")
            content += "\n..\\..\\app\\backend\n"
            pth_file.write_text(content)
            print(" Python 경로 설정 완료")

        # get-pip.py 다운로드 및 실행
        get_pip = python_dir / "get-pip.py"
        if self.download_file(self.get_pip_url, get_pip, "pip installer"):
            print("[INSTALL] Installing pip...")
            subprocess.run([
                str(python_dir / "python.exe"),
                "get-pip.py",
                "--no-warn-script-location"
            ], check=True, cwd=str(python_dir))
            print("[OK] pip installed")

        return True

    def setup_nodejs(self):
        """Node.js Portable 설정"""
        self.print_section("Node.js Portable 설정")

        node_zip = self.package_dir / "nodejs.zip"
        node_dir = self.package_dir / "runtime" / "nodejs"

        # Node.js 다운로드
        if not self.download_file(self.node_url, node_zip, "Node.js v20.11.1"):
            return False

        # 압축 해제
        print(" Node.js 압축 해제 중...")
        with zipfile.ZipFile(node_zip, 'r') as zip_ref:
            zip_ref.extractall(self.package_dir / "runtime")
        node_zip.unlink()

        # 디렉토리 이름 변경
        extracted_dir = list((self.package_dir / "runtime").glob("node-v*"))[0]
        extracted_dir.rename(node_dir)
        print(" Node.js 압축 해제 완료")

        return True

    def copy_application(self):
        """애플리케이션 파일 복사"""
        self.print_section("애플리케이션 파일 복사")

        app_dir = self.package_dir / "app"

        # Backend 복사
        print(" Backend 복사 중...")
        if Path("backend").exists():
            shutil.copytree(
                "backend",
                app_dir / "backend",
                ignore=shutil.ignore_patterns(
                    '__pycache__', '*.pyc', '*.pyo', 'venv',
                    '*.db', '*.db.backup', 'logs', 'error_reports'
                )
            )
            print(" Backend 복사 완료")

        # Frontend 복사
        print(" Frontend 복사 중...")
        if Path("frontend").exists():
            shutil.copytree(
                "frontend",
                app_dir / "frontend",
                ignore=shutil.ignore_patterns(
                    'node_modules', '.next', '*.log'
                )
            )
            print(" Frontend 복사 완료")

        # 유틸리티 파일 복사
        print(" 유틸리티 파일 복사 중...")
        utility_files = [
            'find_available_port.py',
            'health_check.py',
        ]
        for file in utility_files:
            if Path(file).exists():
                shutil.copy2(file, self.package_dir)

        print(" 애플리케이션 파일 복사 완료")

    def install_dependencies(self):
        """의존성 설치"""
        self.print_section("의존성 설치")

        python_exe = self.package_dir / "runtime" / "python" / "python.exe"
        node_dir = self.package_dir / "runtime" / "nodejs"
        npm_cmd = node_dir / "npm.cmd"

        # Backend 의존성 설치
        print(" Backend 의존성 설치 중...")
        requirements = self.package_dir / "app" / "backend" / "requirements.txt"
        if requirements.exists():
            subprocess.run([
                str(python_exe),
                "-m", "pip", "install",
                "-r", str(requirements),
                "--no-warn-script-location"
            ], check=True)
            print(" Backend 의존성 설치 완료")

        # Frontend 의존성 설치
        print(" Frontend 의존성 설치 중...")
        frontend_dir = self.package_dir / "app" / "frontend"
        if (frontend_dir / "package.json").exists():
            env = os.environ.copy()
            env["PATH"] = f"{node_dir};{env['PATH']}"

            subprocess.run([
                str(npm_cmd),
                "install",
                "--legacy-peer-deps"
            ], cwd=frontend_dir, env=env, check=True)
            print(" Frontend 의존성 설치 완료")

    def create_launcher(self):
        """실행 스크립트 생성"""
        self.print_section("실행 스크립트 생성")

        # 메인 실행 파일
        launcher = self.package_dir / "START.bat"
        launcher.write_text('''@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║          Doctor Voice Pro - Portable Edition               ║
echo ║          별도 설치 없이 바로 실행!                         ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

set "ROOT=%~dp0"
set "PYTHON=%ROOT%runtime\\python\\python.exe"
set "NODE=%ROOT%runtime\\nodejs\\node.exe"
set "NPM=%ROOT%runtime\\nodejs\\npm.cmd"

REM PATH 설정
set "PATH=%ROOT%runtime\\python;%ROOT%runtime\\nodejs;%PATH%"

REM 포트 자동 탐지
echo  사용 가능한 포트 확인 중...
for /f %%i in ('"%PYTHON%" "%ROOT%find_available_port.py" 8010') do set BACKEND_PORT=%%i
for /f %%i in ('"%PYTHON%" "%ROOT%find_available_port.py" 3000') do set FRONTEND_PORT=%%i

if "%BACKEND_PORT%"=="8010" (
    echo  Backend 포트: %BACKEND_PORT% ^(기본 포트^)
) else (
    echo   포트 8010 사용 중. 대체 포트: %BACKEND_PORT%
)

if "%FRONTEND_PORT%"=="3000" (
    echo  Frontend 포트: %FRONTEND_PORT% ^(기본 포트^)
) else (
    echo   포트 3000 사용 중. 대체 포트: %FRONTEND_PORT%
)

echo.
echo ================================================================
echo   서버 시작 중...
echo ================================================================
echo.
echo Backend:  http://localhost:%BACKEND_PORT%
echo Frontend: http://localhost:%FRONTEND_PORT%
echo.
echo 종료하려면 Ctrl+C를 누르세요.
echo ================================================================
echo.

REM Backend .env 업데이트
cd /d "%ROOT%app\\backend"
if not exist .env copy .env.example .env
powershell -Command "(Get-Content .env -Raw) -replace 'ALLOWED_ORIGINS=.*', 'ALLOWED_ORIGINS=http://localhost:%FRONTEND_PORT%,http://127.0.0.1:%FRONTEND_PORT%' | Set-Content .env" 2>nul

REM Frontend .env.local 생성
cd /d "%ROOT%app\\frontend"
echo NEXT_PUBLIC_API_URL=http://localhost:%BACKEND_PORT% > .env.local
echo PORT=%FRONTEND_PORT% >> .env.local

REM Backend 시작
echo  Backend 서버 시작 중 ^(포트: %BACKEND_PORT%^)...
start "DoctorVoicePro - Backend" cmd /k "cd /d %ROOT%app\\backend && %PYTHON% -m uvicorn app.main:app --host 0.0.0.0 --port %BACKEND_PORT% --reload"

REM 대기
timeout /t 5 > nul

REM Frontend 시작
echo  Frontend 서버 시작 중 ^(포트: %FRONTEND_PORT%^)...
cd /d "%ROOT%app\\frontend"
start "DoctorVoicePro - Frontend" cmd /k "set PATH=%ROOT%runtime\\nodejs;%%PATH%% && %NPM% run dev -- -p %FRONTEND_PORT%"

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║   서버가 시작되었습니다!                                 ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
echo  브라우저에서 접속: http://localhost:%FRONTEND_PORT%
echo  API 문서: http://localhost:%BACKEND_PORT%/docs
echo.
echo  기본 계정:
echo    이메일: admin@doctorvoice.com
echo    비밀번호: admin123!@#
echo.

REM 브라우저 자동 열기
timeout /t 5 > nul
start http://localhost:%FRONTEND_PORT%

echo 이 창을 닫아도 서버는 계속 실행됩니다.
echo.
pause
''', encoding='utf-8')

        print(" START.bat 생성 완료")

        # README 생성
        readme = self.package_dir / "README_포터블.txt"
        readme.write_text('''
╔════════════════════════════════════════════════════════════════╗
║     Doctor Voice Pro - 완전 포터블 에디션                      ║
║     Python과 Node.js 포함 - 설치 불필요!                      ║
╚════════════════════════════════════════════════════════════════╝

【 사용 방법 】

  1. 이 폴더를 원하는 위치에 복사/이동
  2. START.bat 더블클릭
  3. 끝! (자동으로 브라우저가 열립니다)

【 포함 내용 】

   Python 3.12 (Embedded)
   Node.js v20.11.1 (Portable)
   모든 필요한 라이브러리
   포트 자동 탐지
   자동 설정 업데이트

【 접속 주소 】

  프론트엔드: http://localhost:3000
  백엔드 API: http://localhost:8010/docs

【 기본 계정 】

  이메일: admin@doctorvoice.com
  비밀번호: admin123!@#

【 특징 】

   별도 설치 필요 없음
   USB에서도 바로 실행
   포트 자동 변경
   데이터는 같은 폴더에 저장

【 폴더 구조 】

  START.bat          ← 이것만 클릭!
  runtime/           ← Python + Node.js
  app/               ← 프로그램 파일
  doctorvoice.db     ← 데이터베이스 (자동 생성)

【 문제 해결 】

   포트가 사용 중이라고 나오면?
  → 자동으로 다른 포트를 사용합니다. 메시지를 확인하세요.

   로그인이 안 되면?
  → 기본 계정으로 로그인하세요.

   데이터베이스 초기화가 필요하면?
  → app/backend 폴더의 doctorvoice.db 파일을 삭제하고 재시작

【 시스템 요구사항 】

  - Windows 10/11 (64-bit)
  - 디스크 공간: 약 500MB
  - 메모리: 최소 2GB

【 주의사항 】

  - 백신 프로그램이 차단할 수 있습니다 (예외 처리 필요)
  - 폴더 경로에 한글이 있어도 작동합니다
  - USB나 외장 하드에서도 실행 가능합니다

''', encoding='utf-8')

        print(" README 생성 완료")

    def create_archive(self):
        """ZIP 파일 생성"""
        self.print_section("ZIP 압축 파일 생성")

        zip_filename = f"{self.package_name}.zip"

        print(f" 압축 중... (시간이 걸릴 수 있습니다)")

        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(self.package_dir):
                # node_modules는 이미 포함되어 있어야 함
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(self.package_dir.parent)
                    zipf.write(file_path, arcname)

        zip_size = os.path.getsize(zip_filename) / (1024 * 1024)
        print(f" 압축 완료: {zip_filename} ({zip_size:.1f} MB)")

        return zip_filename, zip_size

    def cleanup(self):
        """임시 폴더 삭제"""
        print("\n 임시 폴더 정리 중...")
        if self.package_dir.exists():
            shutil.rmtree(self.package_dir)
        print(" 정리 완료")

    def build(self):
        """전체 빌드 프로세스"""
        try:
            print("\n" + "=" * 70)
            print("  Doctor Voice Pro - 완전 포터블 패키지 빌더")
            print("  Python + Node.js 포함 버전")
            print("=" * 70)

            self.create_package_structure()

            if not self.setup_python():
                return False

            if not self.setup_nodejs():
                return False

            self.copy_application()
            self.install_dependencies()
            self.create_launcher()

            zip_file, zip_size = self.create_archive()

            # 임시 폴더 유지 (사용자가 확인할 수 있도록)
            # self.cleanup()

            print("\n" + "=" * 70)
            print("   완전 포터블 패키지 생성 완료!")
            print("=" * 70)
            print(f"\n 파일: {zip_file}")
            print(f" 크기: {zip_size:.1f} MB")
            print(f"\n 압축 해제 폴더도 생성됨: {self.package_name}/")
            print("\n사용 방법:")
            print("  1. ZIP 파일을 다른 컴퓨터로 복사")
            print("  2. 압축 해제")
            print("  3. START.bat 더블클릭")
            print("  4. 끝!")
            print("\n" + "=" * 70)

            return True

        except Exception as e:
            print(f"\n 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    builder = FullyPortablePackageBuilder()
    builder.build()
    input("\nPress Enter to exit...")
