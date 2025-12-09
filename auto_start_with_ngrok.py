"""
Doctor Voice Pro - ngrok 자동 연결 및 실행
하나의 명령으로 백엔드(ngrok으로 공개) + 프론트엔드 실행 + 브라우저 열기
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

# 프로젝트 루트 디렉토리
PROJECT_ROOT = Path(__file__).parent
BACKEND_DIR = PROJECT_ROOT / 'backend'
FRONTEND_DIR = PROJECT_ROOT / 'frontend'

# 설정
BASE_BACKEND_PORT = 8010
BASE_FRONTEND_PORT = 3001
NGROK_CHECK_TIMEOUT = 30

# 전역 프로세스 변수
backend_process = None
frontend_process = None
ngrok_process = None


def print_header(title: str):
    """헤더 출력"""
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)
    print()


def get_local_ip() -> str:
    """로컬 네트워크 IP 주소 가져오기"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        try:
            s.connect(('8.8.8.8', 80))
            local_ip = s.getsockname()[0]
        except Exception:
            local_ip = '127.0.0.1'
        finally:
            s.close()
        return local_ip
    except Exception:
        return '127.0.0.1'


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


def setup_no_auth():
    """로그인 없이 사용 설정"""
    print("  로그인 없이 사용 설정 적용 중...")
    try:
        result = subprocess.run(
            ['python', 'setup_no_auth.py'],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print("  ✓ 로그인 없이 사용 설정 완료")
        else:
            print("  ⚠ 설정 적용 중 오류 발생 (무시하고 계속)")
    except Exception:
        print("  ⚠ 설정 파일 없음 (무시하고 계속)")


def update_backend_env(backend_port: int, local_ip: str):
    """백엔드 환경 변수 업데이트"""
    backend_env = BACKEND_DIR / '.env'
    backend_config = {
        'DATABASE_URL': f'sqlite+aiosqlite:///{BACKEND_DIR}/doctorvoice.db',
        'DATABASE_URL_SYNC': f'sqlite:///{BACKEND_DIR}/doctorvoice.db',
        'JWT_SECRET_KEY': 'change-this-jwt-secret-please-use-long-random-string',
        'ALLOWED_ORIGINS': '*'  # ngrok을 위해 모든 출처 허용
    }

    with open(backend_env, 'w', encoding='utf-8') as f:
        for key, value in backend_config.items():
            f.write(f'{key}={value}\n')


def update_frontend_env(ngrok_url: str, frontend_port: int):
    """프론트엔드 환경 변수 업데이트"""
    frontend_env = FRONTEND_DIR / '.env.local'
    with open(frontend_env, 'w', encoding='utf-8') as f:
        f.write(f'NEXT_PUBLIC_API_URL={ngrok_url}\n')
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


def check_server(port: int, max_time: int = 30) -> bool:
    """서버 연결 확인"""
    start_time = time.time()

    while time.time() - start_time < max_time:
        try:
            response = requests.get(f'http://localhost:{port}/health', timeout=1)
            if response.status_code == 200:
                return True
        except Exception:
            pass

        try:
            response = requests.get(f'http://localhost:{port}/', timeout=1)
            if response.status_code in [200, 304, 404, 307, 308]:
                return True
        except Exception:
            pass

        time.sleep(0.5)

    return False


def start_backend(port: int) -> subprocess.Popen:
    """백엔드 서버 시작"""
    os.chdir(BACKEND_DIR)

    # 가상환경 Python 사용
    venv_python = BACKEND_DIR / 'venv' / 'Scripts' / 'python.exe'
    if not venv_python.exists():
        venv_python = 'python'

    cmd = f'"{venv_python}" -m uvicorn app.main:app --host 0.0.0.0 --port {port} --reload'

    if sys.platform == 'win32':
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        process = subprocess.Popen(
            [str(venv_python), '-m', 'uvicorn', 'app.main:app',
             '--host', '0.0.0.0', '--port', str(port), '--reload'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

    os.chdir(PROJECT_ROOT)
    return process


def start_ngrok(port: int) -> subprocess.Popen:
    """ngrok 시작"""
    cmd = f'ngrok http {port} --log=stdout'

    if sys.platform == 'win32':
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        process = subprocess.Popen(
            ['ngrok', 'http', str(port), '--log=stdout'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

    return process


def get_ngrok_url(timeout: int = 30) -> str:
    """ngrok URL 가져오기"""
    start_time = time.time()

    print("  ngrok URL 확인 중...")

    while time.time() - start_time < timeout:
        try:
            # ngrok API를 통해 URL 가져오기
            response = requests.get('http://localhost:4040/api/tunnels', timeout=2)
            if response.status_code == 200:
                data = response.json()
                tunnels = data.get('tunnels', [])

                for tunnel in tunnels:
                    if tunnel.get('proto') == 'https':
                        url = tunnel.get('public_url')
                        if url:
                            return url

                # https가 없으면 http라도 사용
                for tunnel in tunnels:
                    url = tunnel.get('public_url')
                    if url:
                        return url
        except Exception:
            pass

        time.sleep(1)

    return None


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
    global backend_process, frontend_process, ngrok_process

    print("\n서버 종료 중...")

    processes = [
        ('Backend', backend_process),
        ('Frontend', frontend_process),
        ('ngrok', ngrok_process)
    ]

    for name, process in processes:
        if process:
            try:
                if sys.platform == 'win32':
                    subprocess.run(
                        ['taskkill', '/F', '/T', '/PID', str(process.pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                else:
                    process.terminate()
                    process.wait(timeout=5)
                print(f"  ✓ {name} 종료됨")
            except Exception:
                pass


def signal_handler(signum, frame):
    """시그널 핸들러"""
    print("\n\n프로그램을 종료합니다...")
    cleanup()
    sys.exit(0)


def main():
    """메인 함수"""
    global backend_process, frontend_process, ngrok_process

    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print_header("Doctor Voice Pro - ngrok 자동 연결 실행")
    print("  백엔드(ngrok) + 프론트엔드를 자동으로 실행합니다!")
    print_header("")

    try:
        # 로컬 IP 확인
        local_ip = get_local_ip()
        print(f"  🌐 로컬 IP: {local_ip}")
        print()

        # 포트 검색
        print("[1/8] 포트 검색...")
        backend_port = find_available_port(BASE_BACKEND_PORT)
        frontend_port = find_available_port(BASE_FRONTEND_PORT)
        print(f"  ✓ 백엔드: {backend_port}, 프론트엔드: {frontend_port}")

        # 포트 정리
        print("\n[2/8] 포트 정리...")
        kill_process_on_port(backend_port)
        kill_process_on_port(frontend_port)
        time.sleep(0.5)
        print("  ✓ 완료")

        # 로그인 없이 사용 설정
        print("\n[3/8] 로그인 없이 사용 설정...")
        setup_no_auth()

        # 백엔드 환경 변수 업데이트
        print("\n[4/8] 백엔드 환경 변수 업데이트...")
        update_backend_env(backend_port, local_ip)
        print("  ✓ 완료")

        # 백엔드 서버 시작
        print("\n[5/8] 백엔드 서버 시작...")
        backend_process = start_backend(backend_port)
        print(f"  ✓ 백엔드 시작 (0.0.0.0:{backend_port})")

        # 백엔드 연결 대기
        print("  백엔드 연결 확인 중...")
        if not check_server(backend_port, max_time=30):
            print("  ✗ 백엔드 연결 실패")
            cleanup()
            sys.exit(1)
        print("  ✓ 백엔드 연결됨")

        # ngrok 시작
        print("\n[6/8] ngrok 시작...")
        ngrok_process = start_ngrok(backend_port)
        print("  ✓ ngrok 프로세스 시작")

        # ngrok URL 가져오기
        time.sleep(3)  # ngrok이 시작될 시간을 줌
        ngrok_url = get_ngrok_url(timeout=NGROK_CHECK_TIMEOUT)

        if not ngrok_url:
            print("  ✗ ngrok URL을 가져올 수 없습니다")
            print("  ngrok이 설치되어 있고 인증되어 있는지 확인하세요")
            cleanup()
            sys.exit(1)

        print(f"  ✓ ngrok URL: {ngrok_url}")

        # 프론트엔드 환경 변수 업데이트
        print("\n[7/8] 프론트엔드 환경 변수 업데이트...")
        update_frontend_env(ngrok_url, frontend_port)
        print("  ✓ 완료")

        # 프론트엔드 서버 시작
        print("\n[8/8] 프론트엔드 서버 시작...")
        frontend_process = start_frontend(frontend_port)
        print(f"  ✓ 프론트엔드 시작 (포트 {frontend_port})")

        # 프론트엔드 연결 대기
        print("  프론트엔드 연결 확인 중...")
        if not check_server(frontend_port, max_time=60):
            print("  ✗ 프론트엔드 연결 실패")
            cleanup()
            sys.exit(1)
        print("  ✓ 프론트엔드 연결됨")

        # 성공!
        print_header("SUCCESS! 모든 서버 실행 완료!")
        print(f"  🌐 프론트엔드:  http://localhost:{frontend_port}")
        print(f"  🔗 백엔드(ngrok): {ngrok_url}")
        print(f"  📡 로컬 백엔드:  http://localhost:{backend_port}")
        print(f"  📚 API 문서:     http://localhost:{backend_port}/docs")

        if local_ip != '127.0.0.1':
            print(f"\n  🌐 네트워크 접근:")
            print(f"    프론트엔드:   http://{local_ip}:{frontend_port}")

        print_header("")

        # 브라우저 실행
        print("브라우저 여는 중...")
        time.sleep(2)

        webbrowser.open(f'http://localhost:{frontend_port}')

        print("\n✅ 서버 실행 중!")
        print(f"   프론트엔드는 ngrok URL({ngrok_url})로 백엔드에 연결됩니다")
        print("   Ctrl+C로 종료하세요.\n")

        # 서버 유지
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n서버를 종료합니다...")
            cleanup()

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
    main()
