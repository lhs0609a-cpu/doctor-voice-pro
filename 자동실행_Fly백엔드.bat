@echo off
chcp 65001 > nul
REM =====================================================================
REM Doctor Voice Pro - Fly.io 백엔드 + 로컬 프론트엔드 실행
REM =====================================================================

echo.
echo ================================================================
echo   Doctor Voice Pro - Fly.io 백엔드 사용
echo ================================================================
echo.
echo   Fly.io에 배포된 백엔드를 사용하여 프론트엔드만 실행합니다
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

echo.
echo [시작] 프론트엔드 시작 중...
echo.

REM Python 스크립트 실행
python start_with_fly_backend.py

if %errorLevel% neq 0 (
    echo.
    echo [오류] 프로그램 실행 중 오류가 발생했습니다.
    echo.
    pause
    exit /b 1
)

pause
