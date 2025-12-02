#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
터보 서버 시작 스크립트
최고 속도로 연결을 확인하고 서버를 시작합니다.
"""

import socket
import time
import subprocess
import sys
import os
import json
from pathlib import Path
from typing import Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# Windows 콘솔 인코딩 설정
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

PROJECT_ROOT = Path(__file__).parent

def print_progress_bar(iteration, total, prefix='', suffix='', length=40, fill='█'):
    """진행률 바 출력 - 고속 버전"""
    percent = int(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end='', flush=True)
    if iteration == total:
        print()

def quick_install_dependencies():
    """필요한 패키지 빠르게 설치"""
    try:
        import requests
        return True
    except ImportError:
        print("  requests 패키지 설치 중...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'requests'],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except:
            return False

def find_free_port(start_port: int, max_attempts: int = 100) -> Optional[int]:
    """사용 가능한 빈 포트를 빠르게 찾습니다."""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('', port))
                return port
        except OSError:
            continue
    return None

def check_port_in_use(port: int) -> bool:
    """포트 사용 여부 빠르게 확인"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex(('localhost', port)) == 0
    except:
        return False

def quick_kill_port(port: int):
    """포트를 사용하는 프로세스를 빠르게 종료"""
    if sys.platform == 'win32':
        try:
            subprocess.run(f'FOR /F "tokens=5" %P IN (\'netstat -ano ^| findstr :{port}\') DO taskkill /F /PID %P',
                          shell=True, capture_output=True, timeout=2)
        except:
            pass

def update_config_files(backend_port: int, frontend_port: int):
    """환경 설정 파일 빠르게 업데이트"""
    # Backend .env
    env_path = PROJECT_ROOT / 'backend' / '.env'
    if env_path.exists():
        content = env_path.read_text(encoding='utf-8')
        content = content.replace(
            content[content.find('ALLOWED_ORIGINS='):content.find('\n', content.find('ALLOWED_ORIGINS='))],
            f'ALLOWED_ORIGINS=http://localhost:{frontend_port},http://127.0.0.1:{frontend_port}'
        )
        env_path.write_text(content, encoding='utf-8')

    # Frontend .env.local
    (PROJECT_ROOT / 'frontend' / '.env.local').write_text(
        f'NEXT_PUBLIC_API_URL=http://localhost:{backend_port}\nPORT={frontend_port}\n',
        encoding='utf-8'
    )

    # Frontend package.json
    pkg_path = PROJECT_ROOT / 'frontend' / 'package.json'
    if pkg_path.exists():
        with open(pkg_path, 'r', encoding='utf-8') as f:
            pkg = json.load(f)
        pkg['scripts']['dev'] = f'next dev -p {frontend_port}'
        pkg['scripts']['start'] = f'next start -p {frontend_port}'
        with open(pkg_path, 'w', encoding='utf-8') as f:
            json.dump(pkg, f, indent=2, ensure_ascii=False)

def start_servers(backend_port: int, frontend_port: int):
    """서버를 빠르게 시작"""
    backend_dir = PROJECT_ROOT / 'backend'
    venv_python = backend_dir / 'venv' / 'Scripts' / 'python.exe'
    python_cmd = str(venv_python) if venv_python.exists() else 'python'

    # 백엔드 시작
    subprocess.Popen(
        f'start "Backend [{backend_port}]" cmd /k "cd /d {backend_dir} && {python_cmd} -m uvicorn app.main:app --host 0.0.0.0 --port {backend_port} --reload"',
        shell=True
    )

    # 프론트엔드 시작
    subprocess.Popen(
        f'start "Frontend [{frontend_port}]" cmd /k "cd /d {PROJECT_ROOT / "frontend"} && npm run dev"',
        shell=True
    )

def fast_check_server(port: int, endpoints: list, max_time: int = 30) -> bool:
    """서버 연결을 최고속으로 확인"""
    import requests

    start_time = time.time()
    checks = 0

    while time.time() - start_time < max_time:
        checks += 1
        progress = min(int((time.time() - start_time) / max_time * 100), 99)
        print_progress_bar(progress, 100, prefix=f'  포트 {port}', suffix=f'{int(time.time() - start_time)}초')

        for endpoint in endpoints:
            try:
                r = requests.get(f"http://localhost:{port}{endpoint}", timeout=1)
                if r.status_code in [200, 304, 404]:
                    print_progress_bar(100, 100, prefix=f'  포트 {port}', suffix='완료!')
                    return True
            except:
                pass

        time.sleep(0.5)  # 0.5초마다 체크 (고속)

    return False

def open_browser(frontend_port: int):
    """브라우저 빠르게 열기"""
    if sys.platform == 'win32':
        subprocess.Popen(f'start http://localhost:{frontend_port}', shell=True)

def main():
    print("=" * 70)
    print("  Doctor Voice Pro - TURBO 서버 시작")
    print("  최고 속도로 연결합니다!")
    print("=" * 70)
    print()

    # 의존성 빠르게 확인
    print("의존성 확인 중...")
    if not quick_install_dependencies():
        print("  ERROR requests 설치 실패")
        return False

    import requests
    print("  OK 준비 완료")
    print()

    attempt = 0
    max_attempts = 50

    while attempt < max_attempts:
        attempt += 1
        print(f"\n{'='*70}")
        print(f"  시도 #{attempt}/{max_attempts}")
        print(f"{'='*70}\n")

        # 1. 포트 빠르게 찾기
        backend_start = 8010 + ((attempt - 1) * 10)
        frontend_start = 3001 + ((attempt - 1) * 10)

        print(f"[1/5] 포트 검색... ", end='', flush=True)
        backend_port = find_free_port(backend_start)
        frontend_port = find_free_port(frontend_start)

        if not backend_port or not frontend_port:
            print("SKIP")
            continue

        print(f"OK (B:{backend_port}, F:{frontend_port})")

        # 2. 포트 정리
        print(f"[2/5] 포트 정리... ", end='', flush=True)
        if check_port_in_use(backend_port):
            quick_kill_port(backend_port)
        if check_port_in_use(frontend_port):
            quick_kill_port(frontend_port)
        time.sleep(0.5)
        print("OK")

        # 3. 설정 업데이트
        print(f"[3/5] 설정 업데이트... ", end='', flush=True)
        update_config_files(backend_port, frontend_port)
        print("OK")

        # 4. 서버 시작
        print(f"[4/5] 서버 시작... ", end='', flush=True)
        start_servers(backend_port, frontend_port)
        time.sleep(2)  # 최소 대기
        print("OK")

        # 5. 연결 확인 (병렬)
        print(f"[5/5] 연결 확인 중...\n")

        # 백엔드 확인
        print("  백엔드 확인 중...")
        if not fast_check_server(backend_port, ['/health', '/docs'], max_time=30):
            print("\n  FAILED 백엔드 연결 실패 - 재시도")
            quick_kill_port(backend_port)
            quick_kill_port(frontend_port)
            continue

        print("\n  프론트엔드 확인 중...")
        if not fast_check_server(frontend_port, ['/', '/_next'], max_time=30):
            print("\n  FAILED 프론트엔드 연결 실패 - 재시도")
            quick_kill_port(backend_port)
            quick_kill_port(frontend_port)
            continue

        # 최종 연결 확인
        print("\n  최종 연결 확인... ", end='', flush=True)
        try:
            r = requests.get(f"http://localhost:{backend_port}/health", timeout=2)
            if r.status_code == 200:
                print("OK")
            else:
                print("FAILED - 재시도")
                continue
        except:
            print("FAILED - 재시도")
            continue

        # 성공!
        print(f"\n{'='*70}")
        print(f"  SUCCESS! 연결 완료!")
        print(f"{'='*70}")
        print(f"\n  백엔드:      http://localhost:{backend_port}")
        print(f"  프론트엔드:  http://localhost:{frontend_port}")
        print(f"  API 문서:    http://localhost:{backend_port}/docs")
        print(f"\n{'='*70}\n")

        print("브라우저 여는 중...")
        time.sleep(1)
        open_browser(frontend_port)

        print("\n서버 실행 중. 서버 창을 닫으면 종료됩니다.")
        input("아무 키나 눌러 종료...")
        return True

    print(f"\n최대 시도 횟수 도달")
    return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n취소됨")
        sys.exit(1)
    except Exception as e:
        print(f"\n오류: {e}")
        input("아무 키나 눌러 종료...")
        sys.exit(1)
