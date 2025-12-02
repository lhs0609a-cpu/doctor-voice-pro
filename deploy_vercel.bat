@echo off
cd /d E:\u\doctor-voice-pro\frontend
echo Deploying to Vercel...
call npx vercel --prod --yes
echo.
echo Deployment complete!
echo.
pause
