@echo off
chcp 65001 > nul
REM =====================================================================
REM Doctor Voice Pro - 포트 정리
REM 백엔드/프론트엔드 포트를 사용하는 프로세스 종료
REM =====================================================================

echo.
echo ================================================================
echo   Doctor Voice Pro - 포트 정리
echo ================================================================
echo.
echo 실행 중인 서버를 모두 종료합니다...
echo.

REM 8010-8020 포트 정리 (백엔드)
for /L %%p in (8010,1,8020) do (
    echo [확인] 포트 %%p...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%%p ^| findstr LISTENING') do (
        echo   종료 중: PID %%a
        taskkill /F /PID %%a >nul 2>&1
    )
)

echo.

REM 3001-3010 포트 정리 (프론트엔드)
for /L %%p in (3001,1,3010) do (
    echo [확인] 포트 %%p...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%%p ^| findstr LISTENING') do (
        echo   종료 중: PID %%a
        taskkill /F /PID %%a >nul 2>&1
    )
)

echo.
echo ================================================================
echo   포트 정리 완료!
echo ================================================================
echo.
echo 이제 최종실행파일4.bat을 실행할 수 있습니다.
echo.

pause
