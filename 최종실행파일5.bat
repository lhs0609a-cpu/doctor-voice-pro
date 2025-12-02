@echo off
chcp 65001 > nul
REM =====================================================================
REM Doctor Voice Pro - 로그인 없이 바로 사용 (최종실행파일5)
REM 바로 글작성 페이지로 접근
REM =====================================================================

REM 프로젝트 디렉토리로 이동
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

echo.
echo ================================================================
echo   Doctor Voice Pro - 로그인 없이 바로 사용
echo ================================================================
echo.

echo Python 확인 중...
python --version
if %errorLevel% neq 0 (
    echo.
    echo [오류] Python을 찾을 수 없습니다!
    echo 자동설치2.bat을 먼저 실행하여 Python을 설치하세요.
    echo.
    pause
    exit /b 1
)

echo.
echo requests 패키지 확인 중...
python -c "import requests" 2>nul
if %errorLevel% neq 0 (
    echo.
    echo [오류] requests 패키지가 설치되지 않았습니다!
    echo 설치 중...
    python -m pip install requests --quiet
    if %errorLevel% neq 0 (
        echo.
        echo [오류] requests 패키지 설치 실패
        echo 수동으로 설치하세요: pip install requests
        echo.
        pause
        exit /b 1
    )
    echo   OK requests 패키지 설치 완료
)

echo.
echo 서버 시작 중...
echo.

python universal_start_no_auth.py

if %errorLevel% neq 0 (
    echo.
    echo [오류] 프로그램 실행 중 오류가 발생했습니다.
    echo.
    pause
    exit /b 1
)

pause
