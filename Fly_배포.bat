@echo off
chcp 65001 > nul
REM =====================================================================
REM Doctor Voice Pro - Fly.io 백엔드 배포 (프론트엔드 자동 연결)
REM =====================================================================

echo.
echo ================================================================
echo   Doctor Voice Pro - Fly.io 배포
echo ================================================================
echo.
echo   이 스크립트는 다음을 자동으로 실행합니다:
echo   1. Fly.io에 백엔드 배포
echo   2. 프론트엔드를 Fly.io URL로 자동 연결
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

REM flyctl 확인
where flyctl > nul 2>&1
if %errorLevel% neq 0 (
    echo [오류] flyctl이 설치되어 있지 않습니다!
    echo.
    echo 설치 방법:
    echo 1. PowerShell을 관리자 권한으로 실행
    echo 2. 다음 명령어 실행:
    echo    iwr https://fly.io/install.ps1 -useb ^| iex
    echo.
    echo 또는 공식 가이드: https://fly.io/docs/hands-on/install-flyctl/
    echo.
    pause
    exit /b 1
)

echo.
echo [시작] 배포 시작...
echo.

REM Python 스크립트 실행
python deploy_to_fly_with_frontend.py

if %errorLevel% neq 0 (
    echo.
    echo [오류] 배포 중 오류가 발생했습니다.
    echo.
    pause
    exit /b 1
)

echo.
echo ================================================================
echo   배포 완료!
echo ================================================================
echo.
echo 백엔드 URL: https://doctor-voice-pro-backend.fly.dev
echo API 문서:   https://doctor-voice-pro-backend.fly.dev/docs
echo.
echo 프론트엔드가 자동으로 백엔드에 연결되었습니다!
echo.
echo 다음 단계:
echo 1. 로컬에서 프론트엔드 실행: 최종실행파일5.bat
echo 2. 또는 프론트엔드도 배포 (Vercel 등)
echo.

pause
