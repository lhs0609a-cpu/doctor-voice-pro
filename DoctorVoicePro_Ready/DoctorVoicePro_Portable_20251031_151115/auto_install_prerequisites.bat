@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ================================================================
echo      Doctor Voice Pro - 필수 프로그램 자동 설치
echo ================================================================
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

echo [OK] 관리자 권한 확인 완료
echo.

REM 임시 다운로드 폴더 생성
set DOWNLOAD_DIR=%TEMP%\DoctorVoicePro_Install
if not exist "%DOWNLOAD_DIR%" mkdir "%DOWNLOAD_DIR%"

REM ============================================================
REM Python 확인 및 설치
REM ============================================================
echo [1/2] Python 확인 중...
python --version >nul 2>&1
if %errorLevel% equ 0 (
    for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VER=%%i
    echo [OK] Python !PYTHON_VER! 이미 설치됨
) else (
    echo [INFO] Python이 설치되지 않았습니다.
    echo [DOWNLOAD] Python 3.11.9 다운로드 중...

    set PYTHON_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
    set PYTHON_INSTALLER=%DOWNLOAD_DIR%\python-installer.exe

    REM PowerShell로 다운로드
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '!PYTHON_URL!' -OutFile '!PYTHON_INSTALLER!'}"

    if exist "!PYTHON_INSTALLER!" (
        echo [OK] Python 다운로드 완료
        echo [INSTALL] Python 설치 중... (잠시만 기다려주세요)

        REM 자동 설치 (PATH에 추가, 모든 사용자용)
        "!PYTHON_INSTALLER!" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0

        REM 설치 완료 대기
        timeout /t 30 /nobreak >nul

        REM PATH 새로고침
        set PATH=%PATH%;C:\Program Files\Python311;C:\Program Files\Python311\Scripts

        echo [OK] Python 설치 완료
    ) else (
        echo [ERROR] Python 다운로드 실패
        echo.
        echo 수동으로 설치하세요: https://www.python.org/downloads/
        pause
        exit /b 1
    )
)
echo.

REM ============================================================
REM Node.js 확인 및 설치
REM ============================================================
echo [2/2] Node.js 확인 중...
node --version >nul 2>&1
if %errorLevel% equ 0 (
    for /f "tokens=*" %%i in ('node --version 2^>^&1') do set NODE_VER=%%i
    echo [OK] Node.js !NODE_VER! 이미 설치됨
) else (
    echo [INFO] Node.js가 설치되지 않았습니다.
    echo [DOWNLOAD] Node.js 20.11.1 LTS 다운로드 중...

    set NODE_URL=https://nodejs.org/dist/v20.11.1/node-v20.11.1-x64.msi
    set NODE_INSTALLER=%DOWNLOAD_DIR%\nodejs-installer.msi

    REM PowerShell로 다운로드
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '!NODE_URL!' -OutFile '!NODE_INSTALLER!'}"

    if exist "!NODE_INSTALLER!" (
        echo [OK] Node.js 다운로드 완료
        echo [INSTALL] Node.js 설치 중... (잠시만 기다려주세요)

        REM 자동 설치
        msiexec /i "!NODE_INSTALLER!" /quiet /norestart

        REM 설치 완료 대기
        timeout /t 30 /nobreak >nul

        REM PATH 새로고침
        set PATH=%PATH%;C:\Program Files\nodejs

        echo [OK] Node.js 설치 완료
    ) else (
        echo [ERROR] Node.js 다운로드 실패
        echo.
        echo 수동으로 설치하세요: https://nodejs.org/
        pause
        exit /b 1
    )
)
echo.

REM ============================================================
REM 설치 확인
REM ============================================================
echo ================================================================
echo      설치 확인
echo ================================================================
echo.

echo Python 버전:
python --version 2>&1
echo.

echo Node.js 버전:
node --version 2>&1
echo.

echo npm 버전:
call npm --version 2>&1
echo.

REM 임시 파일 삭제
if exist "%DOWNLOAD_DIR%" (
    echo [CLEANUP] 임시 파일 정리 중...
    rmdir /s /q "%DOWNLOAD_DIR%"
)

echo.
echo ================================================================
echo      설치 완료!
echo ================================================================
echo.
echo [중요] 컴퓨터를 재시작해야 PATH가 제대로 적용됩니다.
echo.
echo 다음 단계:
echo   1. 컴퓨터 재시작 (권장)
echo   2. install.bat 실행
echo   3. run.bat 실행
echo.
pause
