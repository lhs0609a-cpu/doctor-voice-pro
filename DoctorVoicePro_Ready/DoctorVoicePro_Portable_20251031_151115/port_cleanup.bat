@echo off
chcp 65001 > nul
echo ================================================================
echo   포트 8010 및 3000 프로세스 종료
echo ================================================================
echo.

echo 포트 8010 사용 프로세스 확인 중...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8010.*LISTENING"') do (
    echo 포트 8010 프로세스 종료: %%a
    taskkill /F /PID %%a 2>nul
)

echo.
echo 포트 3000 사용 프로세스 확인 중...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000.*LISTENING"') do (
    echo 포트 3000 프로세스 종료: %%a
    taskkill /F /PID %%a 2>nul
)

echo.
echo ================================================================
echo   완료!
echo ================================================================
pause
