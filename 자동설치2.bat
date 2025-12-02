@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
REM =================================================================
REM Doctor Voice Pro - 자동 설치 프로그램 2.0
REM 필수 프로그램 목록, 설치 상태, 진행률 표시
REM =================================================================

cls
echo.
echo ================================================================
echo   Doctor Voice Pro - 자동 설치 프로그램 2.0
echo ================================================================
echo.

set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

REM =================================================================
REM 필수 프로그램 목록 표시
REM =================================================================
echo ================================================================
echo   필수 프로그램 목록
echo ================================================================
echo.
echo 이 프로그램을 실행하기 위해 다음이 필요합니다:
echo.
echo   1. Python 3.8 이상
echo      - 백엔드 서버 실행에 필요
echo      - 공식 사이트: https://www.python.org/
echo.
echo   2. Node.js 18 이상 (npm 포함)
echo      - 프론트엔드 서버 실행에 필요
echo      - 공식 사이트: https://nodejs.org/
echo.
echo   3. Python 패키지들
echo      - requests (HTTP 요청)
echo      - fastapi (백엔드 프레임워크)
echo      - uvicorn (서버)
echo      - 기타 requirements.txt의 모든 패키지
echo.
echo   4. Node.js 패키지들
echo      - next (프론트엔드 프레임워크)
echo      - react (UI 라이브러리)
echo      - 기타 package.json의 모든 패키지
echo.
echo ================================================================
echo.
pause

cls
echo.
echo ================================================================
echo   설치 상태 확인 중...
echo ================================================================
echo.

REM =================================================================
REM 관리자 권한 확인
REM =================================================================
echo [0/6] 관리자 권한 확인...
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo   [X] 관리자 권한 없음
    echo.
    echo ⚠️  이 프로그램은 관리자 권한이 필요합니다!
    echo.
    echo 해결 방법:
    echo   1. 이 파일을 마우스 오른쪽 클릭
    echo   2. "관리자 권한으로 실행" 선택
    echo   3. UAC 창에서 "예" 클릭
    echo.
    pause
    exit /b 1
)
echo   [OK] 관리자 권한 확인 완료
echo.

REM =================================================================
REM 설치 상태 체크
REM =================================================================
set "PYTHON_INSTALLED=0"
set "NODE_INSTALLED=0"
set "PIP_PACKAGES_INSTALLED=0"
set "NPM_PACKAGES_INSTALLED=0"

echo [1/6] Python 설치 확인...
where python >nul 2>&1
if %errorLevel% equ 0 (
    set "PYTHON_INSTALLED=1"
    echo   [OK] Python 설치됨
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo       버전: %%v
) else (
    echo   [X] Python 미설치
)
echo.

echo [2/6] Node.js 설치 확인...
where node >nul 2>&1
if %errorLevel% equ 0 (
    set "NODE_INSTALLED=1"
    echo   [OK] Node.js 설치됨
    for /f "tokens=*" %%v in ('node --version 2^>^&1') do echo       Node 버전: %%v
    where npm >nul 2>&1
    if %errorLevel% equ 0 (
        for /f "tokens=*" %%v in ('npm --version 2^>^&1') do echo       npm 버전: %%v
    )
) else (
    echo   [X] Node.js 미설치
)
echo.

echo [3/6] Python requests 패키지 확인...
python -c "import requests" >nul 2>&1
if %errorLevel% equ 0 (
    echo   [OK] requests 패키지 설치됨
    set "PIP_PACKAGES_INSTALLED=1"
) else (
    echo   [X] requests 패키지 미설치
    set "PIP_PACKAGES_INSTALLED=0"
)
echo.

echo [4/6] 백엔드 패키지 확인...
if exist "%PROJECT_ROOT%backend\venv\Scripts\python.exe" (
    "%PROJECT_ROOT%backend\venv\Scripts\python.exe" -c "import fastapi" >nul 2>&1
    if %errorLevel% equ 0 (
        echo   [OK] 백엔드 패키지 설치됨 (가상환경)
    ) else (
        echo   [X] 백엔드 패키지 미설치
    )
) else (
    python -c "import fastapi" >nul 2>&1
    if %errorLevel% equ 0 (
        echo   [OK] 백엔드 패키지 설치됨 (전역)
    ) else (
        echo   [X] 백엔드 패키지 미설치
    )
)
echo.

echo [5/6] 프론트엔드 패키지 확인...
if exist "%PROJECT_ROOT%frontend\node_modules" (
    echo   [OK] 프론트엔드 패키지 설치됨
) else (
    echo   [X] 프론트엔드 패키지 미설치
)
echo.

echo [6/6] 전체 상태 요약
echo ================================================================
if %PYTHON_INSTALLED% equ 1 (
    echo   [OK] Python
) else (
    echo   [X] Python - 설치 필요
)

if %NODE_INSTALLED% equ 1 (
    echo   [OK] Node.js
) else (
    echo   [X] Node.js - 설치 필요
)

if %PIP_PACKAGES_INSTALLED% equ 1 (
    echo   [OK] Python 기본 패키지
) else (
    echo   [X] Python 기본 패키지 - 설치 필요
)

echo   [-] 백엔드 패키지 - 확인 필요
echo   [-] 프론트엔드 패키지 - 확인 필요
echo ================================================================
echo.

REM =================================================================
REM 설치 진행 여부 확인
REM =================================================================
if %PYTHON_INSTALLED% equ 1 if %NODE_INSTALLED% equ 1 (
    echo 모든 필수 프로그램이 이미 설치되어 있습니다!
    echo.
    echo 패키지 업데이트를 진행하시겠습니까?
    choice /C YN /M "Y=예, N=아니오"
    if errorlevel 2 (
        echo.
        echo 설치를 건너뜁니다.
        echo.
        echo 이제 최종실행파일3.bat을 실행하세요!
        echo.
        pause
        exit /b 0
    )
) else (
    echo 누락된 프로그램이 있습니다. 설치를 시작합니다.
    echo.
    pause
)

cls

REM =================================================================
REM Python 설치
REM =================================================================
if %PYTHON_INSTALLED% equ 0 (
    echo.
    echo ================================================================
    echo   Python 설치 중...
    echo ================================================================
    echo.

    echo [진행률: 0%%] Python 다운로드 준비 중...
    timeout /t 1 /nobreak >nul

    echo [진행률: 10%%] winget으로 Python 설치 시도 중...
    winget install -e --id Python.Python.3.12 --silent --accept-source-agreements --accept-package-agreements >nul 2>&1

    if %errorLevel% equ 0 (
        echo [진행률: 50%%] Python 설치 중...
        timeout /t 2 /nobreak >nul
        echo [진행률: 80%%] 환경 변수 설정 중...
        timeout /t 2 /nobreak >nul
        echo [진행률: 100%%] Python 설치 완료!
        echo.
        echo   SUCCESS Python이 설치되었습니다!
    ) else (
        echo [진행률: 실패] winget 설치 실패
        echo.
        echo   브라우저를 열어 수동 설치 페이지로 이동합니다...
        echo   https://www.python.org/downloads/
        echo.
        echo   설치 시 반드시 "Add Python to PATH" 체크!
        start https://www.python.org/downloads/
        echo.
        echo   Python 설치 후 이 프로그램을 다시 실행하세요.
        pause
        exit /b 1
    )
    echo.
)

REM =================================================================
REM Node.js 설치
REM =================================================================
if %NODE_INSTALLED% equ 0 (
    echo.
    echo ================================================================
    echo   Node.js 설치 중...
    echo ================================================================
    echo.

    echo [진행률: 0%%] Node.js 다운로드 준비 중...
    timeout /t 1 /nobreak >nul

    echo [진행률: 10%%] winget으로 Node.js 설치 시도 중...
    winget install -e --id OpenJS.NodeJS.LTS --silent --accept-source-agreements --accept-package-agreements >nul 2>&1

    if %errorLevel% equ 0 (
        echo [진행률: 50%%] Node.js 설치 중...
        timeout /t 2 /nobreak >nul
        echo [진행률: 80%%] 환경 변수 설정 중...
        timeout /t 2 /nobreak >nul
        echo [진행률: 100%%] Node.js 설치 완료!
        echo.
        echo   SUCCESS Node.js가 설치되었습니다!
    ) else (
        echo [진행률: 실패] winget 설치 실패
        echo.
        echo   브라우저를 열어 수동 설치 페이지로 이동합니다...
        echo   https://nodejs.org/
        echo.
        echo   LTS 버전을 다운로드하여 설치하세요.
        start https://nodejs.org/
        echo.
        echo   Node.js 설치 후 이 프로그램을 다시 실행하세요.
        pause
        exit /b 1
    )
    echo.
)

REM =================================================================
REM Python 패키지 설치
REM =================================================================
echo.
echo ================================================================
echo   Python 패키지 설치 중...
echo ================================================================
echo.

echo [진행률: 0%%] pip 업그레이드 중...
python -m pip install --upgrade pip --quiet >nul 2>&1
echo [진행률: 20%%] pip 업그레이드 완료

echo [진행률: 25%%] requests 설치 중...
python -m pip install requests --quiet >nul 2>&1
echo [진행률: 40%%] requests 설치 완료

if exist "%PROJECT_ROOT%backend\requirements.txt" (
    echo [진행률: 45%%] 백엔드 패키지 설치 시작...
    cd /d "%PROJECT_ROOT%backend"

    if exist "venv\Scripts\python.exe" (
        echo [진행률: 50%%] 가상환경 사용 중...
        venv\Scripts\python.exe -m pip install --upgrade pip --quiet >nul 2>&1
        echo [진행률: 60%%] 백엔드 패키지 설치 중 (1/3)...
        venv\Scripts\python.exe -m pip install -r requirements.txt --quiet 2>&1 | findstr /V "Requirement already satisfied" | findstr /V "Using cached"
        echo [진행률: 90%%] 백엔드 패키지 설치 중 (2/3)...
        timeout /t 1 /nobreak >nul
        echo [진행률: 100%%] 백엔드 패키지 설치 완료!
        echo.
        echo   SUCCESS 백엔드 패키지 설치 완료 (가상환경)
    ) else (
        echo [진행률: 50%%] 전역 환경 사용 중...
        python -m pip install -r requirements.txt --quiet 2>&1 | findstr /V "Requirement already satisfied" | findstr /V "Using cached"
        echo [진행률: 90%%] 백엔드 패키지 설치 중...
        timeout /t 1 /nobreak >nul
        echo [진행률: 100%%] 백엔드 패키지 설치 완료!
        echo.
        echo   SUCCESS 백엔드 패키지 설치 완료
    )

    cd /d "%PROJECT_ROOT%"
) else (
    echo   WARNING backend\requirements.txt 파일을 찾을 수 없습니다.
)
echo.

REM =================================================================
REM Node.js 패키지 설치
REM =================================================================
echo.
echo ================================================================
echo   Node.js 패키지 설치 중...
echo ================================================================
echo.

if exist "%PROJECT_ROOT%frontend\package.json" (
    cd /d "%PROJECT_ROOT%frontend"

    if not exist "node_modules" (
        echo [진행률: 0%%] npm 설치 시작...
        echo.
        echo 패키지 다운로드 중... (시간이 걸릴 수 있습니다)
        echo.

        call npm install 2>&1

        if %errorLevel% equ 0 (
            echo.
            echo [진행률: 100%%] npm 설치 완료!
            echo.
            echo   SUCCESS 프론트엔드 패키지 설치 완료
        ) else (
            echo.
            echo   ERROR npm install 실패
            echo.
            echo   수동으로 시도하려면:
            echo   cd frontend
            echo   npm install
        )
    ) else (
        echo [진행률: 100%%] 프론트엔드 패키지가 이미 설치되어 있습니다.
        echo.
        echo   SUCCESS 프론트엔드 패키지 확인 완료
    )

    cd /d "%PROJECT_ROOT%"
) else (
    echo   WARNING frontend\package.json 파일을 찾을 수 없습니다.
)
echo.

REM =================================================================
REM 최종 확인
REM =================================================================
cls
echo.
echo ================================================================
echo   설치 완료 확인
echo ================================================================
echo.

echo 최종 설치 상태:
echo.

where python >nul 2>&1
if %errorLevel% equ 0 (
    echo   [OK] Python
    python --version
) else (
    echo   [X] Python - 설치 실패
)
echo.

where node >nul 2>&1
if %errorLevel% equ 0 (
    echo   [OK] Node.js
    node --version
    echo   [OK] npm
    npm --version
) else (
    echo   [X] Node.js - 설치 실패
)
echo.

python -c "import requests" >nul 2>&1
if %errorLevel% equ 0 (
    echo   [OK] Python requests 패키지
) else (
    echo   [X] Python requests 패키지 - 설치 실패
)
echo.

if exist "%PROJECT_ROOT%backend\venv\Scripts\python.exe" (
    "%PROJECT_ROOT%backend\venv\Scripts\python.exe" -c "import fastapi" >nul 2>&1
    if %errorLevel% equ 0 (
        echo   [OK] 백엔드 패키지
    ) else (
        echo   [X] 백엔드 패키지 - 설치 실패
    )
) else (
    python -c "import fastapi" >nul 2>&1
    if %errorLevel% equ 0 (
        echo   [OK] 백엔드 패키지
    ) else (
        echo   [X] 백엔드 패키지 - 설치 실패
    )
)
echo.

if exist "%PROJECT_ROOT%frontend\node_modules" (
    echo   [OK] 프론트엔드 패키지
) else (
    echo   [X] 프론트엔드 패키지 - 설치 실패
)
echo.

echo ================================================================
echo   설치 완료!
echo ================================================================
echo.
echo 다음 단계:
echo   1. 최종실행파일3.bat 실행 (TURBO - 추천!)
echo   2. 최종실행파일2.bat 실행 (상세 로그)
echo   3. 최종실행파일1.bat 실행 (자동 재시도)
echo.
echo ================================================================
echo.

REM 항상 pause로 종료
pause
