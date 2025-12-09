@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo.
echo ================================================================
echo   Doctor Voice Pro - 스마트 자동 시작
echo ================================================================
echo.

set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

REM 1. 기존 포트 정리
echo [1/4] 기존 서버 프로세스 정리 중...
call cleanup_all_ports.bat
echo.

REM 2. Python 확인
echo [2/4] Python 확인 중...
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo    X Python이 설치되지 않았습니다.
    echo    수동 설치: https://python.org
    pause
    exit /b 1
)
echo    OK Python 설치 확인
echo.

REM 3. Node.js 확인 및 자동 설치
echo [3/4] Node.js 확인 중...
where node >nul 2>&1
if %errorLevel% neq 0 (
    echo    X Node.js가 설치되지 않았습니다.
    echo.
    echo    자동으로 Node.js를 설치하시겠습니까?
    echo      - 예(Y): 자동 설치 시작 (관리자 권한 필요)
    echo      - 아니오(N): 수동 설치 안내
    choice /C YN /M "선택"
    if not errorlevel 2 (
        echo.
        echo    Node.js 자동 설치를 시작합니다...
        powershell -Command "Start-Process 'auto_install_nodejs.bat' -Verb RunAs -Wait"
        echo.
        echo    설치가 완료되었습니다. START.bat을 다시 실행하세요.
        pause
        exit /b 0
    ) else (
        echo.
        echo    X Node.js가 필요합니다.
        echo    수동 설치: https://nodejs.org/
        pause
        exit /b 1
    )
) else (
    echo    OK Node.js 설치 확인
)
echo.

REM 4. 서버 자동 동기화 시작
echo [4/4] 서버 자동 동기화 시작...
echo.
python server_manager.py

pause
