@echo off
cd /d E:\u\doctor-voice-pro\frontend
echo === Vercel Project Info ===
npx vercel project ls
echo.
echo === Recent Deployments ===
npx vercel ls
echo.
echo === Setting alias ===
npx vercel alias set frontend-1o95b2yvk-fewfs-projects-83cc0821.vercel.app doctor-voice-pro.vercel.app
pause
