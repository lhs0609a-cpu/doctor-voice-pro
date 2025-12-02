@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ================================================================
echo   Node.js 자동 설치
echo ================================================================
echo.

REM 관리자 권한 확인
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ❌ 관리자 권한이 필요합니다!
    echo.
    echo 이 파일을 마우스 우클릭 후 "관리자 권한으로 실행"을 선택하세요.
    echo.
    pause
    exit /b 1
)

echo ✅ 관리자 권한 확인 완료
echo.

REM 임시 다운로드 폴더 생성
set DOWNLOAD_DIR=%TEMP%\DoctorVoicePro_NodeJS
if not exist "%DOWNLOAD_DIR%" mkdir "%DOWNLOAD_DIR%"

echo 📥 Node.js 다운로드 중...
set NODE_URL=https://nodejs.org/dist/v20.11.1/node-v20.11.1-x64.msi
set NODE_INSTALLER=%DOWNLOAD_DIR%\nodejs-installer.msi

REM PowerShell로 다운로드
powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%NODE_URL%' -OutFile '%NODE_INSTALLER%'}"

if exist "%NODE_INSTALLER%" (
    echo ✅ Node.js 다운로드 완료
    echo.
    echo 📦 Node.js 설치 중... (잠시만 기다려주세요)
    echo.

    REM 자동 설치
    msiexec /i "%NODE_INSTALLER%" /quiet /norestart

    REM 설치 완료 대기
    timeout /t 30 /nobreak >nul

    echo ✅ Node.js 설치 완료
    echo.
) else (
    echo ❌ Node.js 다운로드 실패
    echo.
    echo 수동으로 설치하세요: https://nodejs.org/
    pause
    exit /b 1
)

REM 임시 파일 삭제
if exist "%DOWNLOAD_DIR%" (
    echo 🧹 임시 파일 정리 중...
    rmdir /s /q "%DOWNLOAD_DIR%"
)

echo.
echo ================================================================
echo   ✅ 설치 완료!
echo ================================================================
echo.
echo Node.js가 설치되었습니다.
echo 이제 run.bat을 실행하세요.
echo.
pause
