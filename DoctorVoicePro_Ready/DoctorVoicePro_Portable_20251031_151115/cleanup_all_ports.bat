@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

echo ================================================================
echo   모든 Doctor Voice Pro 서버 종료
echo ================================================================
echo.

REM Python/Uvicorn 프로세스 종료
echo Python 서버 프로세스 종료 중...
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /NH 2^>nul') do (
    echo   종료: PID %%a
    taskkill /F /PID %%a 2>nul
)

REM Node.js 프로세스 종료
echo Node.js 서버 프로세스 종료 중...
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq node.exe" /NH 2^>nul') do (
    echo   종료: PID %%a
    taskkill /F /PID %%a 2>nul
)

REM 포트 8010-8020 범위 정리
echo.
echo 포트 8010-8020 정리 중...
for /L %%p in (8010,1,8020) do (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%%p.*LISTENING" 2^>nul') do (
        echo   포트 %%p 프로세스 종료: PID %%a
        taskkill /F /PID %%a 2>nul
    )
)

REM 포트 3000-3010 범위 정리
echo 포트 3000-3010 정리 중...
for /L %%p in (3000,1,3010) do (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%%p.*LISTENING" 2^>nul') do (
        echo   포트 %%p 프로세스 종료: PID %%a
        taskkill /F /PID %%a 2>nul
    )
)

echo.
echo ================================================================
echo   정리 완료!
echo ================================================================
timeout /t 2 > nul
