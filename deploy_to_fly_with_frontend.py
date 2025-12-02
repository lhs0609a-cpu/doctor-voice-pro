"""
Doctor Voice Pro - Fly.io 백엔드 배포 및 프론트엔드 자동 연결
"""

import os
import sys
import json
import subprocess
from pathlib import Path

# Windows 한글 출력 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

PROJECT_ROOT = Path(__file__).parent
BACKEND_DIR = PROJECT_ROOT / 'backend'
FRONTEND_DIR = PROJECT_ROOT / 'frontend'

FLY_APP_NAME = "doctor-voice-pro-backend"
FLY_REGION = "nrt"  # Tokyo


def print_header(title: str):
    """헤더 출력"""
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)
    print()


def run_command(cmd: str, cwd: Path = None, shell: bool = True) -> bool:
    """명령어 실행"""
    try:
        result = subprocess.run(
            cmd,
            shell=shell,
            cwd=cwd or os.getcwd(),
            capture_output=False,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"  ✗ 오류: {e}")
        return False


def get_flyctl_path() -> str:
    """flyctl 경로 찾기"""
    # Windows 기본 설치 경로
    default_path = Path.home() / '.fly' / 'bin' / 'flyctl.exe'
    if default_path.exists():
        return str(default_path)

    # PATH에서 찾기
    try:
        result = subprocess.run(
            'where flyctl',
            shell=True,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip().split('\n')[0]
    except Exception:
        pass

    return 'flyctl'

def check_flyctl() -> bool:
    """flyctl 설치 확인"""
    flyctl = get_flyctl_path()
    try:
        result = subprocess.run(
            f'"{flyctl}" version',
            shell=True,
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def check_fly_auth() -> bool:
    """Fly.io 로그인 확인"""
    flyctl = get_flyctl_path()
    try:
        result = subprocess.run(
            f'"{flyctl}" auth whoami',
            shell=True,
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def get_fly_url() -> str:
    """Fly.io 앱 URL 가져오기"""
    return f"https://{FLY_APP_NAME}.fly.dev"


def update_frontend_env(backend_url: str):
    """프론트엔드 환경 변수 업데이트"""
    print("  프론트엔드 환경 변수 업데이트 중...")

    # .env.local 업데이트
    env_local = FRONTEND_DIR / '.env.local'
    with open(env_local, 'w', encoding='utf-8') as f:
        f.write(f'NEXT_PUBLIC_API_URL={backend_url}\n')

    print(f"  ✓ .env.local 업데이트: {backend_url}")

    # .env.production 업데이트
    env_production = FRONTEND_DIR / '.env.production'
    with open(env_production, 'w', encoding='utf-8') as f:
        f.write(f'NEXT_PUBLIC_API_URL={backend_url}\n')

    print(f"  ✓ .env.production 업데이트: {backend_url}")


def main():
    """메인 함수"""
    print_header("Doctor Voice Pro - Fly.io 배포")

    # flyctl 경로 가져오기
    flyctl = get_flyctl_path()
    print(f"flyctl 경로: {flyctl}")
    print()

    # 1. flyctl 확인
    print("[1/6] flyctl 설치 확인...")
    if not check_flyctl():
        print("  ✗ flyctl이 설치되어 있지 않습니다!")
        print()
        print("  설치 방법:")
        print("  1. PowerShell을 관리자 권한으로 실행")
        print("  2. 다음 명령어 실행:")
        print("     iwr https://fly.io/install.ps1 -useb | iex")
        print()
        print("  또는 공식 가이드: https://fly.io/docs/hands-on/install-flyctl/")
        print()
        return False
    print("  ✓ flyctl 설치됨")

    # 2. Fly.io 로그인 확인
    print("\n[2/6] Fly.io 로그인 확인...")
    if not check_fly_auth():
        print("  로그인이 필요합니다...")
        if not run_command(f'"{flyctl}" auth login'):
            print("  ✗ 로그인 실패")
            return False
    print("  ✓ Fly.io 로그인됨")

    # 3. 백엔드 디렉토리로 이동
    print("\n[3/6] 백엔드 배포 준비...")
    os.chdir(BACKEND_DIR)

    # 4. 앱 존재 여부 확인 및 생성
    print("\n[4/6] Fly.io 앱 확인...")
    result = subprocess.run(
        f'"{flyctl}" status -a {FLY_APP_NAME}',
        shell=True,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print("  새로운 앱 생성 중...")

        # 앱 생성
        if not run_command(
            f'"{flyctl}" launch --name {FLY_APP_NAME} --region {FLY_REGION} --copy-config --yes --no-deploy',
            cwd=BACKEND_DIR
        ):
            print("  ✗ 앱 생성 실패")
            return False

        print("  ✓ 앱 생성됨")

        # 볼륨 생성
        print("  데이터베이스 볼륨 생성 중...")
        run_command(
            f'"{flyctl}" volumes create doctorvoice_data --region {FLY_REGION} --size 1 -a {FLY_APP_NAME}',
            cwd=BACKEND_DIR
        )
        print("  ✓ 볼륨 생성됨")
    else:
        print("  ✓ 앱이 이미 존재함")

    # 5. 환경 변수 설정
    print("\n[5/6] 환경 변수 설정...")

    # JWT 시크릿 키 설정
    run_command(
        f'"{flyctl}" secrets set JWT_SECRET_KEY="your-secret-key-here-change-me-please-use-long-random-string" -a {FLY_APP_NAME}',
        cwd=BACKEND_DIR
    )

    # ANTHROPIC_API_KEY 설정
    api_key_file = BACKEND_DIR / 'api_key.txt'
    if api_key_file.exists():
        api_key = api_key_file.read_text().strip()
        print("  ANTHROPIC_API_KEY 설정 중...")
        run_command(
            f'"{flyctl}" secrets set ANTHROPIC_API_KEY="{api_key}" -a {FLY_APP_NAME}',
            cwd=BACKEND_DIR
        )
    else:
        print("  ⚠ api_key.txt 파일이 없습니다")
        print("    나중에 수동으로 설정하세요:")
        print(f"    {flyctl} secrets set ANTHROPIC_API_KEY=your-key -a {FLY_APP_NAME}")

    print("  ✓ 환경 변수 설정 완료")

    # 6. 배포
    print("\n[6/6] 배포 시작...")
    if not run_command(f'"{flyctl}" deploy -a {FLY_APP_NAME}', cwd=BACKEND_DIR):
        print("  ✗ 배포 실패")
        return False

    print("  ✓ 배포 완료!")

    # 백엔드 URL
    backend_url = get_fly_url()

    # 프론트엔드 환경 변수 업데이트
    print("\n프론트엔드 연결 설정...")
    os.chdir(PROJECT_ROOT)
    update_frontend_env(backend_url)

    # 완료
    print_header("배포 완료!")
    print(f"  백엔드 URL:  {backend_url}")
    print(f"  API 문서:    {backend_url}/docs")
    print(f"  헬스 체크:   {backend_url}/health")
    print()
    print("  ✓ 프론트엔드가 자동으로 백엔드에 연결되었습니다!")
    print()
    print("  다음 단계:")
    print("  1. 프론트엔드를 실행하세요: 최종실행파일5.bat")
    print("  2. 또는 프론트엔드도 배포하세요 (Vercel 등)")
    print_header("")

    return True


if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n배포가 취소되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
