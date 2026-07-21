@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM ============================================================
REM  닥터보이스 프로 - 자동 업데이트 원클릭 설치
REM  더블클릭 -> "예"(관리자 승인) 한 번이면 끝.
REM  이후 새 버전은 크롬이 알아서 자동 업데이트합니다.
REM ============================================================

set "EXT_ID=cdmgfoemncdnoigiolpgaaompcmlfcpk"
set "UPDATE_URL=https://doctor-voice-pro-ghwi.vercel.app/extension/updates.xml"
set "KEY=HKLM\SOFTWARE\Policies\Google\Chrome\ExtensionInstallForcelist"

REM --- 관리자 권한이 아니면 스스로 승격해서 다시 실행 ---
net session >nul 2>&1
if %errorlevel% neq 0 (
  echo 관리자 권한이 필요합니다. 잠시 후 뜨는 창에서 "예"를 눌러주세요...
  powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs" >nul 2>&1
  exit /b
)

echo.
echo ============================================
echo   닥터보이스 프로 자동 업데이트 설정
echo ============================================
echo.

REM --- 정책 등록: 확장을 자동 설치 + 자동 업데이트 ---
reg add "%KEY%" /v 1 /t REG_SZ /d "%EXT_ID%;%UPDATE_URL%" /f >nul
if %errorlevel% neq 0 (
  echo [오류] 정책 등록에 실패했습니다. 관리자 권한으로 다시 실행해 주세요.
  echo.
  pause
  exit /b 1
)

echo [완료] 자동 업데이트가 설정되었습니다.
echo.
echo 다음 한 가지만 해주세요:
echo.
echo   1) 크롬을 "완전히" 종료했다가 다시 켜세요.
echo      (모든 크롬 창을 닫으면 됩니다)
echo   2) 다시 켜면 확장이 자동으로 설치되어 있습니다.
echo.
echo 이후로는 새 버전이 나와도 크롬이 조용히 자동 업데이트합니다.
echo 더 이상 다운로드/재설치가 필요 없습니다.
echo.
echo * 기존에 '개발자 모드'로 직접 불러온 닥터보이스 확장이 있다면
echo   chrome://extensions 에서 먼저 삭제하세요. (중복 방지)
echo.
echo ----------------------------------------------------------
echo 크롬을 지금 자동으로 재시작할까요?
echo   Y = 지금 재시작 (열린 탭이 닫힙니다)
echo   N = 나중에 직접 재시작
echo ----------------------------------------------------------
set /p RESTART="선택 (Y/N): "
if /i "!RESTART!"=="Y" (
  echo 크롬을 재시작합니다...
  taskkill /IM chrome.exe /F >nul 2>&1
  timeout /t 2 >nul
  start "" "chrome"
  echo 완료되었습니다. 이 창은 닫으셔도 됩니다.
  timeout /t 3 >nul
) else (
  echo 알겠습니다. 편하실 때 크롬을 완전히 종료 후 다시 켜주세요.
  echo.
  pause
)

endlocal
