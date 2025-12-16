@echo off
chcp 65001 > nul
REM =====================================================================
REM Doctor Voice Pro - Fly.io 백엔드 배포 스크립트
REM =====================================================================

echo.
echo ================================================================
echo   Doctor Voice Pro - Fly.io 백엔드 배포
echo ================================================================
echo.

REM 백엔드 디렉토리로 이동
cd /d "%~dp0"

REM flyctl 설치 확인
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

echo ✓ flyctl 설치됨
echo.

REM Fly.io 로그인 확인
flyctl auth whoami > nul 2>&1
if %errorLevel% neq 0 (
    echo [정보] Fly.io에 로그인이 필요합니다.
    echo.
    flyctl auth login
    if %errorLevel% neq 0 (
        echo [오류] 로그인 실패
        pause
        exit /b 1
    )
)

echo ✓ Fly.io 로그인됨
echo.

REM 앱 존재 여부 확인
flyctl status -a doctor-voice-pro-backend > nul 2>&1
if %errorLevel% neq 0 (
    echo [정보] 새로운 앱을 생성합니다...
    echo.

    REM 앱 생성
    flyctl launch --name doctor-voice-pro-backend --region nrt --copy-config --yes --no-deploy

    if %errorLevel% neq 0 (
        echo [오류] 앱 생성 실패
        pause
        exit /b 1
    )

    echo ✓ 앱 생성됨
    echo.

    REM 볼륨 생성
    echo [정보] 데이터베이스 볼륨 생성...
    flyctl volumes create doctorvoice_data --region nrt --size 1 -a doctor-voice-pro-backend

    if %errorLevel% neq 0 (
        echo [경고] 볼륨 생성 실패 (이미 존재할 수 있음)
    else
        echo ✓ 볼륨 생성됨
    )
    echo.
)

echo [정보] 환경 변수 설정...
echo.

REM 환경 변수 설정
flyctl secrets set JWT_SECRET_KEY="your-secret-key-here-change-me-please-use-long-random-string" -a doctor-voice-pro-backend 2>nul

REM ANTHROPIC_API_KEY가 있으면 설정
if exist "api_key.txt" (
    set /p API_KEY=<api_key.txt
    echo ANTHROPIC_API_KEY 설정 중...
    flyctl secrets set ANTHROPIC_API_KEY="%API_KEY%" -a doctor-voice-pro-backend
) else if not "%ANTHROPIC_API_KEY%"=="" (
    echo ANTHROPIC_API_KEY 설정 중...
    flyctl secrets set ANTHROPIC_API_KEY="%ANTHROPIC_API_KEY%" -a doctor-voice-pro-backend
) else (
    echo.
    echo [경고] ANTHROPIC_API_KEY가 설정되지 않았습니다!
    echo        나중에 수동으로 설정해주세요:
    echo        flyctl secrets set ANTHROPIC_API_KEY=your-key -a doctor-voice-pro-backend
    echo.
)

echo ✓ 환경 변수 설정 완료
echo.

echo [정보] 배포 시작...
echo.

REM 배포
flyctl deploy -a doctor-voice-pro-backend

if %errorLevel% neq 0 (
    echo.
    echo [오류] 배포 실패
    pause
    exit /b 1
)

echo.
echo ================================================================
echo   배포 완료!
echo ================================================================
echo.

REM 앱 URL 가져오기
for /f "tokens=*" %%a in ('flyctl info -a doctor-voice-pro-backend ^| findstr "Hostname"') do (
    echo %%a
)

echo.
echo 백엔드 URL: https://doctor-voice-pro-backend.fly.dev
echo API 문서:   https://doctor-voice-pro-backend.fly.dev/docs
echo.
echo ================================================================
echo.

echo 다음 단계:
echo 1. 백엔드 URL을 복사하세요
echo 2. 프론트엔드 환경 변수에 설정:
echo    NEXT_PUBLIC_API_URL=https://doctor-voice-pro-backend.fly.dev
echo.

pause
