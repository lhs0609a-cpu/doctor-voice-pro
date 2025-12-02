#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
스마트 서버 시작 스크립트
- 의존성 자동 설치
- 포트 진행률 표시
- 다른 컴퓨터에서도 작동
"""

import socket
import time
import subprocess
import sys
import os
import json
from pathlib import Path
from typing import Optional, Tuple

# Windows 콘솔 인코딩 설정
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

PROJECT_ROOT = Path(__file__).parent

def print_progress_bar(iteration, total, prefix='', suffix='', length=40, fill='█'):
    """진행률 바 출력"""
    percent = ("{0:.1f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end='', flush=True)
    if iteration == total:
        print()

def check_and_install_dependencies():
    """필요한 Python 패키지 확인 및 설치"""
    print("\n" + "=" * 70)
    print("  의존성 확인 중...")
    print("=" * 70)

    required_packages = ['requests']
    missing_packages = []

    for package in required_packages:
        try:
            __import__(package)
            print(f"  OK {package}")
        except ImportError:
            print(f"  MISSING {package}")
            missing_packages.append(package)

    if missing_packages:
        print(f"\n필요한 패키지를 설치합니다: {', '.join(missing_packages)}")
        for i, package in enumerate(missing_packages, 1):
            print(f"\n[{i}/{len(missing_packages)}] {package} 설치 중...")
            try:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', package],
                                     stdout=subprocess.DEVNULL)
                print(f"  OK {package} 설치 완료")
            except:
                print(f"  ERROR {package} 설치 실패")
                return False

    print("\n모든 의존성 확인 완료!")
    return True

def find_free_port(start_port: int, max_attempts: int = 100) -> Optional[int]:
    """사용 가능한 빈 포트를 찾습니다."""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                s.listen(1)
                return port
        except OSError:
            continue
    return None

def check_port_in_use(port: int) -> bool:
    """포트가 사용 중인지 확인합니다."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def kill_process_on_port(port: int):
    """특정 포트를 사용하는 프로세스를 종료합니다."""
    if sys.platform == 'win32':
        try:
            result = subprocess.run(
                f'netstat -ano | findstr ":{port}"',
                shell=True,
                capture_output=True,
                text=True
            )
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        subprocess.run(f'taskkill /F /PID {pid}', shell=True,
                                     capture_output=True, stderr=subprocess.DEVNULL)
                        time.sleep(1)
        except Exception:
            pass

def update_backend_env(backend_port: int, frontend_port: int):
    """백엔드 .env 파일 업데이트"""
    env_path = PROJECT_ROOT / 'backend' / '.env'
    if not env_path.exists():
        return

    lines = env_path.read_text(encoding='utf-8').split('\n')
    updated_lines = []

    for line in lines:
        if line.startswith('ALLOWED_ORIGINS='):
            updated_lines.append(f'ALLOWED_ORIGINS=http://localhost:{frontend_port},http://127.0.0.1:{frontend_port}')
        else:
            updated_lines.append(line)

    env_path.write_text('\n'.join(updated_lines), encoding='utf-8')

def update_frontend_env(backend_port: int, frontend_port: int):
    """프론트엔드 .env.local 파일 생성/업데이트"""
    env_path = PROJECT_ROOT / 'frontend' / '.env.local'
    content = f"""NEXT_PUBLIC_API_URL=http://localhost:{backend_port}
PORT={frontend_port}
"""
    env_path.write_text(content, encoding='utf-8')

def update_frontend_package_json(frontend_port: int):
    """프론트엔드 package.json의 dev 스크립트 업데이트"""
    package_json_path = PROJECT_ROOT / 'frontend' / 'package.json'
    if not package_json_path.exists():
        return

    with open(package_json_path, 'r', encoding='utf-8') as f:
        package_data = json.load(f)

    package_data['scripts']['dev'] = f'next dev -p {frontend_port}'
    package_data['scripts']['start'] = f'next start -p {frontend_port}'

    with open(package_json_path, 'w', encoding='utf-8') as f:
        json.dump(package_data, f, indent=2, ensure_ascii=False)

def start_backend_window(backend_port: int):
    """백엔드 서버를 새 창에서 시작"""
    backend_dir = PROJECT_ROOT / 'backend'
    venv_python = backend_dir / 'venv' / 'Scripts' / 'python.exe'

    if venv_python.exists():
        python_cmd = str(venv_python)
    else:
        python_cmd = 'python'

    cmd = f'start "Doctor Voice Pro - Backend [{backend_port}]" cmd /k "cd /d {backend_dir} && {python_cmd} -m uvicorn app.main:app --host 0.0.0.0 --port {backend_port} --reload"'
    subprocess.Popen(cmd, shell=True)

def start_frontend_window(frontend_port: int):
    """프론트엔드 서버를 새 창에서 시작"""
    frontend_dir = PROJECT_ROOT / 'frontend'
    cmd = f'start "Doctor Voice Pro - Frontend [{frontend_port}]" cmd /k "cd /d {frontend_dir} && npm run dev"'
    subprocess.Popen(cmd, shell=True)

def check_server_with_progress(port: int, server_name: str, max_retries: int = 30) -> bool:
    """서버 연결을 진행률과 함께 확인"""
    import requests

    print(f"\n{server_name} 연결 확인 중...")

    for i in range(max_retries):
        print_progress_bar(i + 1, max_retries,
                         prefix=f'  포트 {port}',
                         suffix=f'({i+1}/{max_retries}초)')

        try:
            if 'Backend' in server_name:
                response = requests.get(f"http://localhost:{port}/health", timeout=2)
                if response.status_code == 200:
                    print(f"\n  SUCCESS {server_name} 연결 성공!")
                    return True
            else:
                response = requests.get(f"http://localhost:{port}", timeout=2)
                if response.status_code in [200, 304, 404]:
                    print(f"\n  SUCCESS {server_name} 연결 성공!")
                    return True
        except:
            pass

        time.sleep(2)

    print(f"\n  FAILED {server_name} 연결 실패")
    return False

def check_connection_with_progress(backend_port: int) -> bool:
    """백엔드-프론트엔드 연결을 진행률과 함께 확인"""
    import requests

    print("\n서버 간 연결 확인 중...")
    max_attempts = 10

    for i in range(max_attempts):
        print_progress_bar(i + 1, max_attempts,
                         prefix='  연결 테스트',
                         suffix=f'({i+1}/{max_attempts})')

        try:
            response = requests.get(f"http://localhost:{backend_port}/health", timeout=3)
            if response.status_code == 200:
                print(f"\n  SUCCESS 서버 간 연결 성공!")
                return True
        except:
            pass

        time.sleep(2)

    print(f"\n  FAILED 서버 간 연결 실패")
    return False

def open_browser(frontend_port: int):
    """브라우저 열기"""
    time.sleep(2)
    if sys.platform == 'win32':
        subprocess.run(f'start http://localhost:{frontend_port}', shell=True)
    elif sys.platform == 'darwin':
        subprocess.run(['open', f'http://localhost:{frontend_port}'])
    else:
        subprocess.run(['xdg-open', f'http://localhost:{frontend_port}'])

def main():
    print("=" * 70)
    print("  Doctor Voice Pro - 스마트 서버 시작")
    print("=" * 70)

    # 1. 의존성 확인 및 설치
    if not check_and_install_dependencies():
        print("\n의존성 설치 실패. 수동으로 설치해주세요:")
        print("  pip install requests")
        return False

    # requests를 이제 사용할 수 있음
    import requests

    attempt = 0
    max_attempts = 50

    print(f"\n연결될 때까지 최대 {max_attempts}번 시도합니다.")
    print("=" * 70)

    while attempt < max_attempts:
        attempt += 1

        print(f"\n\n{'=' * 70}")
        print(f"  시도 #{attempt}/{max_attempts}")
        print(f"{'=' * 70}\n")

        # 1. 포트 찾기
        backend_start = 8010 + ((attempt - 1) * 10)
        frontend_start = 3001 + ((attempt - 1) * 10)

        print(f"1단계: 포트 검색 중...")
        print(f"  검색 범위: 백엔드 {backend_start}~{backend_start+99}")
        print(f"  검색 범위: 프론트엔드 {frontend_start}~{frontend_start+99}")

        backend_port = find_free_port(backend_start)
        if not backend_port:
            print(f"  FAILED 사용 가능한 백엔드 포트 없음")
            continue

        frontend_port = find_free_port(frontend_start)
        if not frontend_port:
            print(f"  FAILED 사용 가능한 프론트엔드 포트 없음")
            continue

        print(f"  FOUND 백엔드 포트: {backend_port}")
        print(f"  FOUND 프론트엔드 포트: {frontend_port}")

        # 2. 기존 프로세스 정리
        print(f"\n2단계: 포트 정리 중...")
        if check_port_in_use(backend_port):
            print(f"  정리 중: 백엔드 포트 {backend_port}")
            kill_process_on_port(backend_port)
        if check_port_in_use(frontend_port):
            print(f"  정리 중: 프론트엔드 포트 {frontend_port}")
            kill_process_on_port(frontend_port)
        print(f"  OK 포트 정리 완료")

        # 3. 환경 설정
        print(f"\n3단계: 환경 설정 중...")
        update_backend_env(backend_port, frontend_port)
        update_frontend_env(backend_port, frontend_port)
        update_frontend_package_json(frontend_port)
        print(f"  OK 환경 설정 완료")

        # 4. 서버 시작
        print(f"\n4단계: 서버 시작 중...")
        print(f"  백엔드 서버 시작... (포트: {backend_port})")
        start_backend_window(backend_port)
        time.sleep(3)

        print(f"  프론트엔드 서버 시작... (포트: {frontend_port})")
        start_frontend_window(frontend_port)
        time.sleep(2)

        # 5. 백엔드 연결 확인
        print(f"\n5단계: 백엔드 연결 확인")
        if not check_server_with_progress(backend_port, 'Backend', max_retries=30):
            print(f"\n  다음 포트 조합으로 재시도...")
            kill_process_on_port(backend_port)
            kill_process_on_port(frontend_port)
            time.sleep(2)
            continue

        # 6. 프론트엔드 연결 확인
        print(f"\n6단계: 프론트엔드 연결 확인")
        if not check_server_with_progress(frontend_port, 'Frontend', max_retries=30):
            print(f"\n  다음 포트 조합으로 재시도...")
            kill_process_on_port(backend_port)
            kill_process_on_port(frontend_port)
            time.sleep(2)
            continue

        # 7. 연결 확인
        print(f"\n7단계: 서버 간 연결 확인")
        if not check_connection_with_progress(backend_port):
            print(f"\n  다음 포트 조합으로 재시도...")
            kill_process_on_port(backend_port)
            kill_process_on_port(frontend_port)
            time.sleep(2)
            continue

        # 성공!
        print(f"\n\n{'=' * 70}")
        print(f"  SUCCESS! 모든 서버가 성공적으로 연결되었습니다!")
        print(f"{'=' * 70}\n")
        print(f"  백엔드:      http://localhost:{backend_port}")
        print(f"  프론트엔드:  http://localhost:{frontend_port}")
        print(f"  API 문서:    http://localhost:{backend_port}/docs")
        print(f"\n{'=' * 70}\n")

        print("브라우저를 여는 중...")
        open_browser(frontend_port)

        print("\n서버가 실행 중입니다.")
        print("서버 창을 닫으면 서버가 종료됩니다.")
        input("\n아무 키나 눌러 종료하세요...")

        return True

    print(f"\n최대 시도 횟수({max_attempts})에 도달했습니다.")
    return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n사용자에 의해 취소되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n치명적 오류: {e}")
        import traceback
        traceback.print_exc()
        input("\n아무 키나 눌러 종료하세요...")
        sys.exit(1)
