@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

REM 현재 배치 파일이 있는 디렉토리로 이동
cd /d "%~dp0"

echo ================================================================
echo      Doctor Voice Pro - 완전 자동 설치 및 실행
echo ================================================================
echo.
echo 이 스크립트는 다음을 자동으로 수행합니다:
echo   - Python 설치 확인 및 자동 설치
echo   - Node.js 설치 확인 및 자동 설치
echo   - 필요한 패키지 설치
echo   - 데이터베이스 초기화
echo   - 서버 실행
echo.

REM 관리자 권한 확인
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [WARNING] 관리자 권한이 필요합니다!
    echo.
    echo 이 파일을 마우스 우클릭 후 "관리자 권한으로 실행"을 선택하세요.
    echo.
    pause
    exit /b 1
)

echo.
echo ================================================================
echo  1단계: 필수 프로그램 확인 및 설치
echo ================================================================
echo.

REM Python 확인
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo Python이 없습니다. 자동 설치를 시작합니다...
    call "%~dp0auto_install_prerequisites.bat"
    if %errorLevel% neq 0 (
        echo.
        echo [ERROR] 필수 프로그램 설치 실패
        pause
        exit /b 1
    )
) else (
    echo [OK] Python 설치 확인 완료
)

REM Node.js 확인
node --version >nul 2>&1
if %errorLevel% neq 0 (
    echo Node.js가 없습니다. 자동 설치를 시작합니다...
    call "%~dp0auto_install_prerequisites.bat"
    if %errorLevel% neq 0 (
        echo.
        echo [ERROR] 필수 프로그램 설치 실패
        pause
        exit /b 1
    )
) else (
    echo [OK] Node.js 설치 확인 완료
)

echo.
echo ================================================================
echo  2단계: 애플리케이션 설치
echo ================================================================
echo.

REM install.bat 실행
if exist "%~dp0install.bat" (
    echo install.bat 실행 중...
    call "%~dp0install.bat"
) else (
    echo [ERROR] install.bat 파일을 찾을 수 없습니다.
    echo 현재 위치: %~dp0
    pause
    exit /b 1
)

echo.
echo ================================================================
echo  3단계: 서버 실행
echo ================================================================
echo.

REM run.bat 실행
if exist "%~dp0run.bat" (
    echo run.bat 실행 중...
    call "%~dp0run.bat"
) else (
    echo [ERROR] run.bat 파일을 찾을 수 없습니다.
    echo 현재 위치: %~dp0
    pause
    exit /b 1
)
