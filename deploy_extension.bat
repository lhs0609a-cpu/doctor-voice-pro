@echo off
chcp 65001 >nul
echo [1/2] 크롬 확장 프로그램 ZIP 생성 중...
powershell -Command "Remove-Item 'E:\u\doctor-voice-pro\frontend\public\doctorvoice-chrome-extension.zip' -Force -ErrorAction SilentlyContinue; Compress-Archive -Path 'E:\u\doctor-voice-pro\chrome-extension\*' -DestinationPath 'E:\u\doctor-voice-pro\frontend\public\doctorvoice-chrome-extension.zip' -Force"

echo [2/2] Vercel 배포 중...
cd /d E:\u\doctor-voice-pro\frontend
C:\Users\u\AppData\Roaming\npm\vercel.cmd --prod --yes

echo.
echo 배포 완료!
echo 다운로드: https://frontend-fewfs-projects-83cc0821.vercel.app/doctorvoice-chrome-extension.zip
pause
