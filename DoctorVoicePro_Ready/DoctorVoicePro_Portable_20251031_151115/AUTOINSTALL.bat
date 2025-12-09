@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo.
echo ================================================================
echo   Doctor Voice Pro - 완전 자동 설치 및 실행
echo ================================================================
echo.
echo   이 스크립트는 다음을 자동으로 수행합니다:
echo   1. Python 3.12 확인 및 설치
echo   2. Node.js 확인 및 설치
echo   3. 버전 호환성 체크
echo   4. 의존성 자동 설치
echo   5. 서버 자동 시작
echo.
echo ================================================================
echo.

set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

REM ================================================================
REM Step 1: Python 확인 및 설치
REM ================================================================
echo [1/6] Python 확인 중...
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo    X Python이 설치되지 않았습니다.
    echo.
    echo    Python을 자동으로 설치하시겠습니까?
    echo      - 예(Y): 자동 설치 (권장)
    echo      - 아니오(N): 수동 설치 안내
    choice /C YN /M "선택"
    if not errorlevel 2 (
        echo.
        echo    Python 3.12 다운로드 중...

        set PYTHON_URL=https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe
        set PYTHON_INSTALLER=%TEMP%\python-installer.exe

        powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_INSTALLER%'}"

        if exist "%PYTHON_INSTALLER%" (
            echo    다운로드 완료. 설치 중...
            "%PYTHON_INSTALLER%" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
            timeout /t 30 /nobreak >nul

            REM 환경 변수 새로고침
            call refreshenv.cmd 2>nul

            echo    Python 설치 완료!
            del "%PYTHON_INSTALLER%"
        ) else (
            echo    X 다운로드 실패!
            echo    수동 설치: https://python.org
            pause
            exit /b 1
        )
    ) else (
        echo.
        echo    수동 설치: https://python.org (Python 3.12 권장)
        pause
        exit /b 1
    )
) else (
    for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
    echo    OK Python !PYTHON_VERSION! 설치 확인
)
echo.

REM ================================================================
REM Step 2: Python 버전 호환성 체크
REM ================================================================
echo [2/6] Python 버전 호환성 체크...
python -c "import sys; major, minor = sys.version_info[:2]; sys.exit(0 if (major == 3 and 10 <= minor <= 13) else 1)"
if %errorLevel% neq 0 (
    echo    ! Python 버전이 3.10-3.13 범위를 벗어났습니다.
    echo    Python 3.12 사용을 권장합니다.
    echo.
    echo    계속 진행하시겠습니까? (호환성 문제가 발생할 수 있습니다)
    choice /C YN /M "선택"
    if errorlevel 2 (
        echo    설치를 취소합니다.
        pause
        exit /b 1
    )
) else (
    echo    OK 호환 가능한 Python 버전입니다.
)
echo.

REM ================================================================
REM Step 3: Node.js 확인 및 설치
REM ================================================================
echo [3/6] Node.js 확인 중...
where node >nul 2>&1
if %errorLevel% neq 0 (
    echo    X Node.js가 설치되지 않았습니다.
    echo.
    echo    Node.js를 자동으로 설치하시겠습니까?
    choice /C YN /M "선택"
    if not errorlevel 2 (
        echo.
        echo    관리자 권한으로 auto_install_nodejs.bat 실행 중...
        powershell -Command "Start-Process 'auto_install_nodejs.bat' -Verb RunAs -Wait"

        REM 환경 변수 새로고침
        call refreshenv.cmd 2>nul

        echo    Node.js 설치 완료!
    ) else (
        echo.
        echo    수동 설치: https://nodejs.org/
        pause
        exit /b 1
    )
) else (
    for /f "tokens=*" %%i in ('node --version 2^>^&1') do set NODE_VERSION=%%i
    echo    OK Node.js !NODE_VERSION! 설치 확인
)
echo.

REM ================================================================
REM Step 4: 백엔드 의존성 설치
REM ================================================================
echo [4/6] 백엔드 의존성 설치 중...
cd /d "%PROJECT_ROOT%\backend"

REM Virtual Environment 확인 및 생성
if not exist "venv" (
    echo    가상 환경 생성 중...
    python -m venv venv
)

REM Virtual Environment 활성화 및 의존성 설치
echo    의존성 설치 중 (시간이 걸릴 수 있습니다)...
call venv\Scripts\activate.bat

REM pip 업그레이드
python -m pip install --upgrade pip --quiet

REM 호환 가능한 버전으로 설치
echo    FastAPI 및 Pydantic 설치 중...
pip install "fastapi>=0.68,<1.0" --quiet
pip install "pydantic>=1.10,<2.0" --quiet
pip install "uvicorn[standard]" --quiet

REM 나머지 의존성 설치
if exist "requirements.txt" (
    pip install -r requirements.txt --quiet
)

call deactivate
cd /d "%PROJECT_ROOT%"
echo    OK 백엔드 의존성 설치 완료!
echo.

REM ================================================================
REM Step 5: 프론트엔드 의존성 설치
REM ================================================================
echo [5/6] 프론트엔드 의존성 설치 중...
cd /d "%PROJECT_ROOT%\frontend"

if not exist "node_modules" (
    echo    패키지 설치 중 (시간이 걸릴 수 있습니다)...
    call npm install --loglevel=error
    echo    OK 프론트엔드 의존성 설치 완료!
) else (
    echo    OK 프론트엔드 의존성이 이미 설치되어 있습니다.
)

cd /d "%PROJECT_ROOT%"
echo.

REM ================================================================
REM Step 6: 서버 자동 시작
REM ================================================================
echo [6/6] 서버 시작 중...
echo.
echo ================================================================
echo   설치 완료!
echo ================================================================
echo.
echo   이제 서버를 시작합니다...
echo.
timeout /t 3 >nul

REM START.bat 실행
call START.bat
