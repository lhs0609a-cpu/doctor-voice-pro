@echo off
chcp 65001 > nul
REM =====================================================================
REM Doctor Voice Pro - ngrok 자동 연결 실행
REM 하나의 명령으로 백엔드(ngrok) + 프론트엔드 자동 실행
REM =====================================================================

echo.
echo ================================================================
echo   Doctor Voice Pro - ngrok 자동 연결 실행
echo ================================================================
echo.
echo   이 스크립트는 다음을 자동으로 실행합니다:
echo   1. 백엔드 서버 시작
echo   2. ngrok으로 백엔드 공개
echo   3. 프론트엔드 서버 시작 (ngrok URL 연결)
echo   4. 브라우저 자동 열기
echo.
echo ================================================================
echo.

REM 프로젝트 디렉토리로 이동
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

REM Python 확인
python --version > nul 2>&1
if %errorLevel% neq 0 (
    echo [오류] Python을 찾을 수 없습니다!
    echo Python 3.8 이상을 설치해주세요.
    echo.
    pause
    exit /b 1
)

REM ngrok 확인
where ngrok > nul 2>&1
if %errorLevel% neq 0 (
    echo [오류] ngrok을 찾을 수 없습니다!
    echo.
    echo ngrok 설치 방법:
    echo 1. https://ngrok.com 에서 가입
    echo 2. ngrok 다운로드 및 설치
    echo 3. ngrok authtoken YOUR_TOKEN 으로 인증
    echo.
    pause
    exit /b 1
)

REM requests 패키지 확인
python -c "import requests" 2>nul
if %errorLevel% neq 0 (
    echo.
    echo [정보] requests 패키지 설치 중...
    python -m pip install requests --quiet
    if %errorLevel% neq 0 (
        echo [오류] requests 패키지 설치 실패
        pause
        exit /b 1
    )
)

echo.
echo [시작] 서버 시작 중...
echo.

REM Python 스크립트 실행
python auto_start_with_ngrok.py

if %errorLevel% neq 0 (
    echo.
    echo [오류] 프로그램 실행 중 오류가 발생했습니다.
    echo.
    pause
    exit /b 1
)

pause
