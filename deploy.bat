@echo off
chcp 65001 > nul
echo.
echo ================================================================
echo   Doctor Voice Pro - Deployment Script
echo ================================================================
echo.

echo [1/2] Deploying Backend to Fly.io...
echo ----------------------------------------------------------------
cd /d "%~dp0backend"
C:\Users\u\.fly\bin\flyctl.exe deploy -a doctor-voice-pro-backend
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ Backend deployment failed!
    pause
    exit /b 1
)

echo.
echo ✅ Backend deployed successfully!
echo Backend URL: https://doctor-voice-pro-backend.fly.dev
echo.

echo [2/2] Deploying Frontend to Vercel...
echo ----------------------------------------------------------------
cd /d "%~dp0frontend"
C:\Users\u\AppData\Roaming\npm\vercel.cmd --prod --yes
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ Frontend deployment failed!
    pause
    exit /b 1
)

echo.
echo ================================================================
echo   ✅ Deployment Complete!
echo ================================================================
echo.
echo Backend:  https://doctor-voice-pro-backend.fly.dev
echo Frontend: Check the Vercel output above for the URL
echo.
pause
