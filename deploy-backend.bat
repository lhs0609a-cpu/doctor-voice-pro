@echo off
echo ================================================================
echo   Deploying Backend to Fly.io
echo ================================================================
echo.
cd /d D:\u\doctor-voice-pro\backend
fly deploy
echo.
echo Deployment complete!
pause
