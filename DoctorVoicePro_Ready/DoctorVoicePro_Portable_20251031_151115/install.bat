@echo off
chcp 65001 > nul
REM =================================================================
REM Doctor Voice Pro - 원클릭 설치 스크립트 (Windows)
REM =================================================================
REM 이 스크립트는 프로그램에 필요한 모든 것을 자동으로 설치합니다.
REM =================================================================

echo.
echo ================================================================
echo   🚀 Doctor Voice Pro 자동 설치
echo ================================================================
echo.

REM 관리자 권한 확인
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ⚠️  경고: 관리자 권한이 없습니다.
    echo    일부 기능이 제한될 수 있습니다.
    echo.
    timeout /t 3 > nul
)

REM 현재 디렉토리 저장
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

echo 📁 프로젝트 경로: %PROJECT_ROOT%
echo.

REM =================================================================
REM STEP 1: 시스템 자가 진단
REM =================================================================
echo ================================================================
echo   STEP 1/6: 시스템 자가 진단
echo ================================================================
echo.

python --version > nul 2>&1
if %errorLevel% neq 0 (
    echo ❌ Python이 설치되어 있지 않습니다!
    echo.
    echo Python 3.8 이상을 설치해주세요:
    echo https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo ✅ Python 확인 완료
python --version

REM 자가 진단 실행
echo.
echo 🛡️  자가 진단 시스템 실행 중...
python health_check.py
if %errorLevel% neq 0 (
    echo.
    echo ⚠️  자가 진단에서 일부 문제가 발견되었습니다.
    echo    계속 진행하시겠습니까?
    choice /C YN /M "계속 (Y/N)"
    if errorlevel 2 exit /b 1
)

echo.
pause

REM =================================================================
REM STEP 2: 필수 디렉토리 생성
REM =================================================================
echo.
echo ================================================================
echo   STEP 2/6: 필수 디렉토리 생성
echo ================================================================
echo.

if not exist "logs" mkdir logs
if not exist "data" mkdir data
if not exist "error_reports" mkdir error_reports
if not exist "backups" mkdir backups

echo ✅ logs/ - 로그 파일 저장
echo ✅ data/ - 데이터베이스 저장
echo ✅ error_reports/ - 에러 리포트 저장
echo ✅ backups/ - 백업 파일 저장

REM =================================================================
REM STEP 3: Python 패키지 설치 (Backend)
REM =================================================================
echo.
echo ================================================================
echo   STEP 3/6: Backend 패키지 설치
echo ================================================================
echo.

cd /d "%PROJECT_ROOT%\backend"

REM pip 업그레이드
echo 📦 pip 업그레이드 중...
python -m pip install --upgrade pip
if %errorLevel% neq 0 (
    echo ⚠️  pip 업그레이드 실패 (계속 진행)
)

REM requirements.txt 설치
echo.
echo 📦 Python 패키지 설치 중... (시간이 걸릴 수 있습니다)
python -m pip install -r requirements.txt
if %errorLevel% neq 0 (
    echo ❌ 패키지 설치 실패!
    echo.
    echo 다음을 시도해보세요:
    echo 1. 인터넷 연결 확인
    echo 2. Python 재설치
    echo 3. 수동 설치: python -m pip install -r backend\requirements.txt
    echo.
    pause
    exit /b 1
)

echo ✅ Backend 패키지 설치 완료

REM =================================================================
REM STEP 4: Node.js 패키지 설치 (Frontend)
REM =================================================================
echo.
echo ================================================================
echo   STEP 4/6: Frontend 패키지 설치
echo ================================================================
echo.

cd /d "%PROJECT_ROOT%\frontend"

REM Node.js 확인
node --version > nul 2>&1
if %errorLevel% neq 0 (
    echo ⚠️  Node.js가 설치되어 있지 않습니다.
    echo    Frontend는 수동으로 설치해야 합니다.
    echo.
    echo Node.js 설치: https://nodejs.org/
    echo 설치 후 실행: cd frontend ^&^& npm install
    echo.
) else (
    echo ✅ Node.js 확인 완료
    node --version

    echo.
    echo 📦 npm 패키지 설치 중... (시간이 걸릴 수 있습니다)
    call npm install
    if %errorLevel% neq 0 (
        echo ⚠️  npm 설치 중 일부 오류 발생 (계속 진행)
    ) else (
        echo ✅ Frontend 패키지 설치 완료
    )
)

REM =================================================================
REM STEP 5: 환경 설정 파일 생성
REM =================================================================
echo.
echo ================================================================
echo   STEP 5/6: 환경 설정
echo ================================================================
echo.

cd /d "%PROJECT_ROOT%\backend"

if not exist ".env" (
    if exist ".env.example" (
        echo 📝 .env 파일 생성 중... (.env.example에서 복사)
        copy ".env.example" ".env" > nul
        echo ✅ .env 파일 생성 완료
    ) else (
        echo 📝 기본 .env 파일 생성 중...
        (
            echo # Database
            echo DATABASE_URL=sqlite:///./app.db
            echo.
            echo # Security
            echo SECRET_KEY=change-this-in-production-please-use-long-random-string
            echo ALGORITHM=HS256
            echo ACCESS_TOKEN_EXPIRE_MINUTES=30
            echo.
            echo # API Keys ^(optional^)
            echo ANTHROPIC_API_KEY=
            echo OPENAI_API_KEY=
            echo.
            echo # CORS
            echo CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
            echo.
            echo # Environment
            echo ENVIRONMENT=development
        ) > ".env"
        echo ✅ 기본 .env 파일 생성 완료
    )

    echo.
    echo ⚠️  중요: .env 파일을 열어서 다음을 설정하세요:
    echo    - SECRET_KEY: 보안을 위해 변경하세요
    echo    - ANTHROPIC_API_KEY: Claude AI 사용 시 필요
    echo    - OPENAI_API_KEY: OpenAI API 사용 시 필요
    echo.
) else (
    echo ✅ .env 파일이 이미 존재합니다.
)

REM =================================================================
REM STEP 6: 데이터베이스 초기화
REM =================================================================
echo.
echo ================================================================
echo   STEP 6/6: 데이터베이스 초기화
echo ================================================================
echo.

cd /d "%PROJECT_ROOT%\backend"

REM 데이터베이스가 없으면 생성
if not exist "app.db" (
    echo 🗄️  데이터베이스 초기화 중...

    REM init_db.py 스크립트가 있으면 실행
    if exist "init_db.py" (
        python init_db.py
        if %errorLevel% equ 0 (
            echo ✅ 데이터베이스 초기화 완료
        ) else (
            echo ⚠️  초기화 스크립트 실행 실패
            echo    서버 시작 시 자동으로 생성됩니다.
        )
    ) else (
        echo ℹ️  init_db.py가 없습니다.
        echo    서버 시작 시 자동으로 생성됩니다.
    )
) else (
    echo ✅ 데이터베이스가 이미 존재합니다.
)

REM =================================================================
REM 설치 완료
REM =================================================================
echo.
echo ================================================================
echo   🎉 설치 완료!
echo ================================================================
echo.
echo 다음 단계:
echo.
echo 1. .env 파일 확인 및 API 키 설정 (선택사항)
echo    위치: backend\.env
echo.
echo 2. 서버 실행:
echo    방법 1: run.bat 더블클릭
echo    방법 2: 명령줄에서 "run.bat" 실행
echo.
echo 3. 브라우저에서 확인:
echo    Backend:  http://localhost:8010
echo    Frontend: http://localhost:3000
echo.
echo ================================================================
echo.

cd /d "%PROJECT_ROOT%"

echo 지금 서버를 시작하시겠습니까?
choice /C YN /M "서버 시작 (Y/N)"
if errorlevel 2 (
    echo.
    echo 나중에 run.bat을 실행하여 서버를 시작할 수 있습니다.
    pause
    exit /b 0
)

echo.
echo 서버를 시작합니다...
timeout /t 2 > nul
call run.bat
