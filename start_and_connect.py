#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
통합 서버 시작 및 연결 확인 스크립트
서버를 시작하고, 연결이 완료될 때까지 자동으로 재시도합니다.
"""

import socket
import time
import subprocess
import sys
import os
import requests
import json
from pathlib import Path

# Windows 콘솔 인코딩 설정
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

PROJECT_ROOT = Path(__file__).parent

def find_free_port(start_port: int, max_attempts: int = 100) -> int:
    """사용 가능한 빈 포트를 찾습니다."""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                s.listen(1)
                return port
        except OSError:
            continue
    raise RuntimeError(f"포트 {start_port}부터 {start_port + max_attempts}까지 사용 가능한 포트를 찾을 수 없습니다.")

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
                        subprocess.run(f'taskkill /F /PID {pid}', shell=True, capture_output=True)
                        print(f"  포트 {port}의 기존 프로세스 (PID: {pid}) 종료")
                        time.sleep(2)
        except Exception as e:
            print(f"  프로세스 종료 중 오류: {e}")

def update_backend_env(backend_port: int, frontend_port: int):
    """백엔드 .env 파일 업데이트"""
    env_path = PROJECT_ROOT / 'backend' / '.env'

    if not env_path.exists():
        print(f"경고: {env_path} 파일을 찾을 수 없습니다.")
        return

    lines = env_path.read_text(encoding='utf-8').split('\n')
    updated_lines = []

    for line in lines:
        if line.startswith('ALLOWED_ORIGINS='):
            updated_lines.append(f'ALLOWED_ORIGINS=http://localhost:{frontend_port},http://127.0.0.1:{frontend_port}')
        else:
            updated_lines.append(line)

    env_path.write_text('\n'.join(updated_lines), encoding='utf-8')
    print(f"  백엔드 CORS 설정: http://localhost:{frontend_port}")

def update_frontend_env(backend_port: int, frontend_port: int):
    """프론트엔드 .env.local 파일 생성/업데이트"""
    env_path = PROJECT_ROOT / 'frontend' / '.env.local'

    content = f"""NEXT_PUBLIC_API_URL=http://localhost:{backend_port}
PORT={frontend_port}
"""
    env_path.write_text(content, encoding='utf-8')
    print(f"  프론트엔드 API URL: http://localhost:{backend_port}")

def update_frontend_package_json(frontend_port: int):
    """프론트엔드 package.json의 dev 스크립트 업데이트"""
    package_json_path = PROJECT_ROOT / 'frontend' / 'package.json'

    if not package_json_path.exists():
        print(f"경고: {package_json_path} 파일을 찾을 수 없습니다.")
        return

    with open(package_json_path, 'r', encoding='utf-8') as f:
        package_data = json.load(f)

    package_data['scripts']['dev'] = f'next dev -p {frontend_port}'
    package_data['scripts']['start'] = f'next start -p {frontend_port}'

    with open(package_json_path, 'w', encoding='utf-8') as f:
        json.dump(package_data, f, indent=2, ensure_ascii=False)

    print(f"  프론트엔드 포트: {frontend_port}")

def start_backend(backend_port: int):
    """백엔드 서버 시작"""
    backend_dir = PROJECT_ROOT / 'backend'
    venv_python = backend_dir / 'venv' / 'Scripts' / 'python.exe'

    if venv_python.exists():
        python_cmd = str(venv_python)
    else:
        python_cmd = 'python'

    cmd = f'start "Doctor Voice Pro - Backend" cmd /k "cd /d {backend_dir} && {python_cmd} -m uvicorn app.main:app --host 0.0.0.0 --port {backend_port} --reload"'

    subprocess.Popen(cmd, shell=True)
    print(f"  백엔드 서버 시작: http://localhost:{backend_port}")

def start_frontend(frontend_port: int):
    """프론트엔드 서버 시작"""
    frontend_dir = PROJECT_ROOT / 'frontend'

    cmd = f'start "Doctor Voice Pro - Frontend" cmd /k "cd /d {frontend_dir} && npm run dev"'

    subprocess.Popen(cmd, shell=True)
    print(f"  프론트엔드 서버 시작: http://localhost:{frontend_port}")

def check_backend_health(port: int, max_retries: int = 60, retry_interval: int = 2) -> bool:
    """백엔드 헬스 체크"""
    print(f"\n백엔드 서버 연결 대기 중... (포트: {port})")

    for i in range(max_retries):
        try:
            response = requests.get(f"http://localhost:{port}/health", timeout=2)
            if response.status_code == 200:
                print(f"✓ 백엔드 서버 연결 성공! ({i+1}초 소요)")
                return True
        except requests.exceptions.RequestException:
            pass

        try:
            response = requests.get(f"http://localhost:{port}/docs", timeout=2)
            if response.status_code == 200:
                print(f"✓ 백엔드 서버 연결 성공! ({i+1}초 소요)")
                return True
        except requests.exceptions.RequestException:
            pass

        if (i + 1) % 5 == 0:
            print(f"  대기 중... ({i+1}/{max_retries}초)")

        time.sleep(retry_interval)

    return False

def check_frontend_health(port: int, max_retries: int = 60, retry_interval: int = 2) -> bool:
    """프론트엔드 헬스 체크"""
    print(f"\n프론트엔드 서버 연결 대기 중... (포트: {port})")

    for i in range(max_retries):
        try:
            response = requests.get(f"http://localhost:{port}", timeout=2)
            if response.status_code in [200, 304, 404]:
                print(f"✓ 프론트엔드 서버 연결 성공! ({i+1}초 소요)")
                return True
        except requests.exceptions.RequestException:
            pass

        if (i + 1) % 5 == 0:
            print(f"  대기 중... ({i+1}/{max_retries}초)")

        time.sleep(retry_interval)

    return False

def check_connection(backend_port: int, frontend_port: int, max_attempts: int = 20) -> bool:
    """프론트엔드와 백엔드 연결 확인"""
    print("\n프론트엔드 <-> 백엔드 연결 확인 중...")

    for attempt in range(1, max_attempts + 1):
        try:
            # 백엔드 API 확인
            response = requests.get(f"http://localhost:{backend_port}/health", timeout=5)
            if response.status_code == 200:
                print(f"✓ 연결 성공! (시도 {attempt}/{max_attempts})")
                return True
        except Exception as e:
            if attempt % 5 == 0:
                print(f"  재시도 중... ({attempt}/{max_attempts})")

        time.sleep(2)

    return False

def open_browser(frontend_port: int):
    """브라우저 열기"""
    print(f"\n브라우저를 여는 중... http://localhost:{frontend_port}")
    time.sleep(3)

    if sys.platform == 'win32':
        subprocess.run(f'start http://localhost:{frontend_port}', shell=True)
    elif sys.platform == 'darwin':
        subprocess.run(['open', f'http://localhost:{frontend_port}'])
    else:
        subprocess.run(['xdg-open', f'http://localhost:{frontend_port}'])

def main():
    print("=" * 70)
    print("  Doctor Voice Pro - 자동 서버 시작 및 연결")
    print("=" * 70)
    print()

    # 1. 포트 찾기
    print("1단계: 사용 가능한 포트 찾기")
    print("-" * 70)

    backend_port = find_free_port(8010)
    frontend_port = find_free_port(3001)

    print(f"  백엔드 포트: {backend_port}")
    print(f"  프론트엔드 포트: {frontend_port}")
    print()

    # 2. 환경 설정 업데이트
    print("2단계: 환경 설정 업데이트")
    print("-" * 70)
    update_backend_env(backend_port, frontend_port)
    update_frontend_env(backend_port, frontend_port)
    update_frontend_package_json(frontend_port)
    print()

    # 3. 기존 서버 확인 및 종료
    print("3단계: 기존 서버 확인")
    print("-" * 70)

    backend_running = check_port_in_use(backend_port)
    frontend_running = check_port_in_use(frontend_port)

    if backend_running:
        print(f"  백엔드 포트 {backend_port}가 사용 중입니다. 기존 서버 종료 중...")
        kill_process_on_port(backend_port)
        time.sleep(2)

    if frontend_running:
        print(f"  프론트엔드 포트 {frontend_port}가 사용 중입니다. 기존 서버 종료 중...")
        kill_process_on_port(frontend_port)
        time.sleep(2)

    print()

    # 4. 서버 시작
    print("4단계: 서버 시작")
    print("-" * 70)
    start_backend(backend_port)
    time.sleep(3)
    start_frontend(frontend_port)
    print()

    # 5. 백엔드 연결 대기
    print("5단계: 백엔드 연결 대기")
    print("-" * 70)
    if not check_backend_health(backend_port):
        print("✗ 백엔드 서버 연결 실패")
        return False
    print()

    # 6. 프론트엔드 연결 대기
    print("6단계: 프론트엔드 연결 대기")
    print("-" * 70)
    if not check_frontend_health(frontend_port):
        print("✗ 프론트엔드 서버 연결 실패")
        return False
    print()

    # 7. 연결 확인
    print("7단계: 프론트엔드 <-> 백엔드 연결 확인")
    print("-" * 70)
    if not check_connection(backend_port, frontend_port):
        print("✗ 서버 간 연결 실패")
        return False
    print()

    # 8. 완료
    print("=" * 70)
    print("  ✓✓✓ 모든 서버가 성공적으로 시작되었습니다! ✓✓✓")
    print("=" * 70)
    print()
    print(f"  백엔드:      http://localhost:{backend_port}")
    print(f"  프론트엔드:  http://localhost:{frontend_port}")
    print(f"  API 문서:    http://localhost:{backend_port}/docs")
    print()
    print("  서버를 중지하려면 각 서버 창에서 Ctrl+C를 누르세요.")
    print("=" * 70)
    print()

    # 9. 브라우저 열기
    open_browser(frontend_port)

    return True

if __name__ == "__main__":
    try:
        success = main()
        if success:
            print("\n서버가 실행 중입니다. 이 창을 닫아도 서버는 계속 실행됩니다.")
            input("\n아무 키나 눌러 종료하세요...")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n작업이 사용자에 의해 취소되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()
        input("\n아무 키나 눌러 종료하세요...")
        sys.exit(1)
