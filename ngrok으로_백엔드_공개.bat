@echo off
chcp 65001 > nul
echo ================================================================
echo   ngrok으로 로컬 백엔드 공개
echo ================================================================
echo.
echo 이 방법은 Render보다 훨씬 빠릅니다!
echo.
echo 1. 먼저 백엔드 서버를 시작하세요:
echo    최종실행파일5.bat 실행
echo.
echo 2. 그 다음 ngrok을 실행하세요:
echo    ngrok http 8010
echo.
echo 3. ngrok이 생성한 URL을 복사하세요
echo    예: https://abc123.ngrok.io
echo.
echo 4. 프론트엔드 환경 변수에 설정:
echo    frontend/.env.production:
echo    NEXT_PUBLIC_API_URL=https://abc123.ngrok.io
echo.
echo 5. 프론트엔드 재배포:
echo    cd frontend
echo    vercel --prod --yes
echo.
pause

echo.
echo ngrok 실행 중...
echo.
ngrok http 8010
