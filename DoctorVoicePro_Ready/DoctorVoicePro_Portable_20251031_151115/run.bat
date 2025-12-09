@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
REM =================================================================
REM Doctor Voice Pro - 서버 실행 스크립트 (Windows)
REM =================================================================

echo.
echo ================================================================
echo   🚀 Doctor Voice Pro 서버 시작
echo ================================================================
echo.

set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

REM Node.js 자동 설치 확인
echo 🔍 Node.js 확인 중...
where node >nul 2>&1
if %errorLevel% neq 0 (
    echo ⚠️  Node.js가 설치되지 않았습니다.
    echo.
    echo 🤖 자동으로 Node.js를 설치하시겠습니까?
    echo    - 예(Y): 자동 설치 시작 (관리자 권한 필요)
    echo    - 아니오(N): 수동 설치 안내
    choice /C YN /M "선택"
    if not errorlevel 2 (
        echo.
        echo 📥 Node.js 자동 설치를 시작합니다...
        echo 관리자 권한이 필요합니다. UAC 창이 나타나면 "예"를 클릭하세요.
        echo.

        REM 관리자 권한으로 설치 스크립트 실행
        powershell -Command "Start-Process 'auto_install_nodejs.bat' -Verb RunAs -Wait"

        echo.
        echo 설치가 완료되었습니다. run.bat을 다시 실행하세요.
        pause
        exit /b 0
    ) else (
        echo.
        echo ❌ Node.js가 필요합니다.
        echo 수동 설치: https://nodejs.org/
        echo 설치 후 run.bat을 다시 실행하세요.
        echo.
        pause
        exit /b 1
    )
) else (
    echo ✅ Node.js 설치 확인 완료
)
echo.

REM 포트 자동 탐지
echo 🔍 사용 가능한 포트 확인 중...
for /f %%i in ('python find_available_port.py 8010') do set BACKEND_PORT=%%i
for /f %%i in ('python find_available_port.py 3001') do set FRONTEND_PORT=%%i

if "%BACKEND_PORT%"=="8010" (
    echo ✅ Backend 포트: %BACKEND_PORT% ^(기본 포트^)
) else (
    echo ⚠️  포트 8010이 사용 중입니다. 대체 포트: %BACKEND_PORT%
)

if "%FRONTEND_PORT%"=="3001" (
    echo ✅ Frontend 포트: %FRONTEND_PORT% ^(기본 포트^)
) else (
    echo ⚠️  포트 3001이 사용 중입니다. 대체 포트: %FRONTEND_PORT%
)
echo.

echo.
echo ================================================================
echo   서버 시작 중...
echo ================================================================
echo.
echo Backend:  http://localhost:%BACKEND_PORT%
echo Frontend: http://localhost:%FRONTEND_PORT%
echo.
echo 종료하려면 Ctrl+C를 누르세요.
echo ================================================================
echo.

REM Backend .env 파일 업데이트
echo 📝 Backend 설정 업데이트 중...
if not "%FRONTEND_PORT%"=="3000" (
    REM .env 파일의 ALLOWED_ORIGINS 업데이트
    powershell -Command "(Get-Content '%PROJECT_ROOT%\backend\.env' -Raw) -replace 'ALLOWED_ORIGINS=.*', 'ALLOWED_ORIGINS=http://localhost:%FRONTEND_PORT%,http://127.0.0.1:%FRONTEND_PORT%' | Set-Content '%PROJECT_ROOT%\backend\.env'" 2>nul
)

REM Frontend 환경변수 파일 생성
echo 📝 Frontend 설정 업데이트 중...
echo NEXT_PUBLIC_API_URL=http://localhost:%BACKEND_PORT% > "%PROJECT_ROOT%\frontend\.env.local"
echo PORT=%FRONTEND_PORT% >> "%PROJECT_ROOT%\frontend\.env.local"

REM Backend 시작 (새 창에서)
echo 🔵 Backend 서버 시작 중 ^(포트: %BACKEND_PORT%^)...
start "Doctor Voice Pro - Backend" cmd /k "cd /d %PROJECT_ROOT%\backend && python -m uvicorn app.main:app --host 0.0.0.0 --port %BACKEND_PORT% --reload"

REM 잠시 대기 (Backend가 시작될 때까지)
timeout /t 5 > nul

REM Frontend 시작 (새 창에서)
echo 🟢 Frontend 서버 시작 중 ^(포트: %FRONTEND_PORT%^)...
start "Doctor Voice Pro - Frontend" cmd /k "cd /d %PROJECT_ROOT%\frontend && set PORT=%FRONTEND_PORT% && npm run dev -- -p %FRONTEND_PORT%"

echo.
echo ================================================================
echo   ✅ 서버가 시작되었습니다!
echo ================================================================
echo.
echo 브라우저에서 다음 주소로 접속하세요:
echo   http://localhost:%FRONTEND_PORT%
echo.
echo Backend API 문서:
echo   http://localhost:%BACKEND_PORT%/docs
echo.
echo 서버를 중지하려면 각 창에서 Ctrl+C를 누르세요.
echo ================================================================
echo.

REM 브라우저 자동 열기 (5초 후)
timeout /t 5 > nul
start http://localhost:%FRONTEND_PORT%

echo 이 창을 닫아도 서버는 계속 실행됩니다.
echo.
pause
