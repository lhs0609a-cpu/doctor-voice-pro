@echo off
chcp 65001 > nul
REM =================================================================
REM Doctor Voice Pro - 연결 관리 서버 실행 스크립트 (Windows)
REM 포트 자동 탐색 및 연결 관리 기능 포함
REM =================================================================

echo.
echo ================================================================
echo   Doctor Voice Pro 서버 시작 (연결 관리)
echo ================================================================
echo.

set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

REM Python 실행 확인
python --version > nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Python을 찾을 수 없습니다!
    echo Python 3.8 이상을 설치해주세요.
    pause
    exit /b 1
)

REM 통합 실행 스크립트 실행
echo [INFO] 포트 자동 탐색 및 서버 시작...
echo.

python start_with_connection.py

REM 종료 코드 확인
if %errorLevel% neq 0 (
    echo.
    echo [ERROR] 서버 시작 실패
    pause
    exit /b 1
)

pause
