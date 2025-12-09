@echo off
chcp 65001 > nul
echo.
echo ================================================================
echo   Doctor Voice Pro - Starting Servers
echo ================================================================
echo.

echo Starting Backend Server (Port 8010)...
start "Backend Server" cmd /k "cd /d "%~dp0backend" && python -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload"

timeout /t 3 /nobreak > nul

echo Starting Frontend Server (Port 3001)...
start "Frontend Server" cmd /k "cd /d "%~dp0frontend" && set PORT=3001 && npm run dev"

echo.
echo Servers are starting...
echo Backend:  http://localhost:8010
echo Frontend: http://localhost:3001
echo.
echo Check the newly opened windows for server status.
echo.
pause
