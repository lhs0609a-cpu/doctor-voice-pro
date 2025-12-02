@echo off
chcp 65001 > nul
REM =====================================================================
REM Doctor Voice Pro - 인증 복원
REM 로그인 기능을 다시 활성화합니다
REM =====================================================================

set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

echo.
echo ================================================================
echo   Doctor Voice Pro - 인증 복원
echo ================================================================
echo.
echo 로그인 기능을 다시 활성화합니다...
echo.

python setup_no_auth.py --restore

if %errorLevel% equ 0 (
    echo.
    echo ================================================================
    echo   인증 복원 완료!
    echo ================================================================
    echo.
    echo 이제 다음 파일들을 사용하세요:
    echo   - 최종실행파일.bat
    echo   - 최종실행파일1.bat
    echo   - 최종실행파일2.bat
    echo   - 최종실행파일3.bat
    echo   - 최종실행파일4.bat
    echo.
    echo 로그인 없이 사용하려면:
    echo   - 최종실행파일5.bat
    echo.
) else (
    echo.
    echo [오류] 복원 중 오류가 발생했습니다.
    echo.
)

pause
