@echo off
echo ================================================================
echo   Deploying Frontend to Vercel
echo ================================================================
echo.
cd /d D:\u\doctor-voice-pro\frontend
vercel --prod --yes
echo.
echo Deployment complete!
pause
