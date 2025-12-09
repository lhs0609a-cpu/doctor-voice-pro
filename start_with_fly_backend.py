"""
Doctor Voice Pro - Fly.io 백엔드 사용 (프론트엔드만 로컬 실행)
"""

import os
import sys
import json
import time
import socket
import subprocess
import signal
import requests
import webbrowser
from pathlib import Path

# Windows 한글 출력 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 프로젝트 루트 디렉토리
PROJECT_ROOT = Path(__file__).parent
FRONTEND_DIR = PROJECT_ROOT / 'frontend'

# 설정
FLY_BACKEND_URL = "https://doctor-voice-pro-backend.fly.dev"
BASE_FRONTEND_PORT = 3001

# 전역 프로세스 변수
frontend_process = None


def print_header(title: str):
    """헤더 출력"""
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)
    print()


def is_port_available(port: int) -> bool:
    """포트 사용 가능 여부 확인"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(0.5)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result != 0
    except Exception:
        return True


def find_available_port(base_port: int) -> int:
    """사용 가능한 포트 찾기"""
    port = base_port
    while port < base_port + 100:
        if is_port_available(port):
            return port
        port += 1
    return base_port


def kill_process_on_port(port: int):
    """특정 포트를 사용하는 프로세스 종료"""
    try:
        if sys.platform == 'win32':
            result = subprocess.run(
                f'netstat -ano | findstr :{port}',
                shell=True, capture_output=True, text=True
            )
            lines = result.stdout.strip().split('\n')
            pids = set()
            for line in lines:
                if 'LISTENING' in line:
                    parts = line.split()
                    if parts:
                        pid = parts[-1]
                        if pid.isdigit():
                            pids.add(pid)

            for pid in pids:
                subprocess.run(f'taskkill /F /PID {pid}',
                             shell=True,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
    except Exception:
        pass


def check_backend() -> bool:
    """Fly.io 백엔드 확인"""
    try:
        response = requests.get(f'{FLY_BACKEND_URL}/health', timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"  백엔드 연결 오류: {e}")
        return False


def update_frontend_env(backend_url: str, frontend_port: int):
    """프론트엔드 환경 변수 업데이트"""
    frontend_env = FRONTEND_DIR / '.env.local'
    with open(frontend_env, 'w', encoding='utf-8') as f:
        f.write(f'NEXT_PUBLIC_API_URL={backend_url}\n')
        f.write(f'PORT={frontend_port}\n')

    # package.json 업데이트
    package_json_path = FRONTEND_DIR / 'package.json'
    try:
        with open(package_json_path, 'r', encoding='utf-8') as f:
            package_data = json.load(f)

        package_data['scripts']['dev'] = f'next dev -p {frontend_port}'
        package_data['scripts']['start'] = f'next start -p {frontend_port}'

        with open(package_json_path, 'w', encoding='utf-8') as f:
            json.dump(package_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"  ⚠ package.json 업데이트 오류: {e}")


def check_server(port: int, max_time: int = 60) -> bool:
    """서버 연결 확인"""
    start_time = time.time()

    while time.time() - start_time < max_time:
        try:
            response = requests.get(f'http://localhost:{port}/', timeout=1)
            if response.status_code in [200, 304, 404, 307, 308]:
                return True
        except Exception:
            pass

        time.sleep(0.5)

    return False


def start_frontend(port: int) -> subprocess.Popen:
    """프론트엔드 서버 시작"""
    os.chdir(FRONTEND_DIR)

    env = os.environ.copy()
    env['PORT'] = str(port)

    if sys.platform == 'win32':
        process = subprocess.Popen(
            'npm run dev',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            shell=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        process = subprocess.Popen(
            ['npm', 'run', 'dev'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )

    os.chdir(PROJECT_ROOT)
    return process


def cleanup():
    """프로세스 정리"""
    global frontend_process

    if frontend_process:
        try:
            if sys.platform == 'win32':
                subprocess.run(
                    ['taskkill', '/F', '/T', '/PID', str(frontend_process.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                frontend_process.terminate()
                frontend_process.wait(timeout=5)
        except Exception:
            pass


def signal_handler(signum, frame):
    """시그널 핸들러"""
    print("\n\n프로그램을 종료합니다...")
    cleanup()
    sys.exit(0)


def main():
    """메인 함수"""
    global frontend_process

    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print_header("Doctor Voice Pro - Fly.io 백엔드 사용")
    print("  Fly.io에 배포된 백엔드를 사용합니다")
    print_header("")

    try:
        # 백엔드 확인
        print("[1/4] Fly.io 백엔드 확인...")
        print(f"  URL: {FLY_BACKEND_URL}")

        if not check_backend():
            print("  ✗ 백엔드에 연결할 수 없습니다!")
            print()
            print("  확인 사항:")
            print("  1. Fly.io에 백엔드가 배포되어 있나요?")
            print("     → Fly_배포.bat 실행")
            print("  2. 인터넷 연결이 되어 있나요?")
            print(f"  3. 백엔드 URL이 올바른가요? {FLY_BACKEND_URL}")
            print()
            return False

        print("  ✓ 백엔드 연결됨")

        # 포트 검색
        print("\n[2/4] 포트 검색...")
        frontend_port = find_available_port(BASE_FRONTEND_PORT)
        print(f"  ✓ 프론트엔드 포트: {frontend_port}")

        # 포트 정리
        print("\n[3/4] 포트 정리...")
        kill_process_on_port(frontend_port)
        time.sleep(0.5)
        print("  ✓ 완료")

        # 환경 변수 업데이트
        print(f"\n  환경 변수 업데이트...")
        update_frontend_env(FLY_BACKEND_URL, frontend_port)
        print("  ✓ 완료")

        # 프론트엔드 시작
        print("\n[4/4] 프론트엔드 시작...")
        frontend_process = start_frontend(frontend_port)
        print(f"  ✓ 프론트엔드 시작 (포트 {frontend_port})")

        # 프론트엔드 연결 대기
        print("\n  프론트엔드 연결 확인 중...")
        if not check_server(frontend_port, max_time=60):
            print("  ✗ 프론트엔드 연결 실패")
            cleanup()
            return False
        print("  ✓ 프론트엔드 연결됨")

        # 성공!
        print_header("SUCCESS! 연결 완료!")
        print(f"  🌐 프론트엔드:  http://localhost:{frontend_port}")
        print(f"  🔗 백엔드:      {FLY_BACKEND_URL}")
        print(f"  📚 API 문서:    {FLY_BACKEND_URL}/docs")
        print_header("")

        # 브라우저 실행
        print("브라우저 여는 중...")
        time.sleep(2)

        webbrowser.open(f'http://localhost:{frontend_port}')

        print("\n✅ 서버 실행 중!")
        print(f"   프론트엔드는 Fly.io 백엔드({FLY_BACKEND_URL})를 사용합니다")
        print("   Ctrl+C로 종료하세요.\n")

        # 서버 유지
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n서버를 종료합니다...")
            cleanup()

        return True

    except KeyboardInterrupt:
        print("\n\n프로그램을 종료합니다...")
        cleanup()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        cleanup()
        sys.exit(1)


if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"오류: {e}")
        sys.exit(1)
