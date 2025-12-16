@echo off
chcp 65001 > nul
echo ================================================================
echo   Railway로 백엔드 배포
echo ================================================================
echo.
echo 1. Railway 계정 필요 (https://railway.app)
echo 2. Railway CLI 설치 필요
echo.
echo Railway CLI 설치:
echo   npm i -g @railway/cli
echo.
echo 배포 명령어:
echo   railway login
echo   railway init
echo   railway up
echo.
pause
