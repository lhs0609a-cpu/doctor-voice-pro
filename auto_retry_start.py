#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
자동 재시도 서버 시작 스크립트
연결이 성공할 때까지 계속 다른 포트를 찾아서 시도합니다.
"""

import socket
import time
import subprocess
import sys
import os
import requests
import json
from pathlib import Path
from typing import Optional, Tuple

# Windows 콘솔 인코딩 설정
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

PROJECT_ROOT = Path(__file__).parent

class ServerProcess:
    """서버 프로세스 관리"""
    def __init__(self):
        self.backend_process = None
        self.frontend_process = None

    def kill_all(self):
        """모든 프로세스 종료"""
        if self.backend_process:
            try:
                self.backend_process.terminate()
                self.backend_process.wait(timeout=5)
            except:
                pass
            self.backend_process = None

        if self.frontend_process:
            try:
                self.frontend_process.terminate()
                self.frontend_process.wait(timeout=5)
            except:
                pass
            self.frontend_process = None

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
                        subprocess.run(f'taskkill /F /PID {pid}', shell=True, capture_output=True)
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

def start_backend(backend_port: int) -> subprocess.Popen:
    """백엔드 서버 시작"""
    backend_dir = PROJECT_ROOT / 'backend'
    venv_python = backend_dir / 'venv' / 'Scripts' / 'python.exe'

    if venv_python.exists():
        python_cmd = str(venv_python)
    else:
        python_cmd = 'python'

    cmd = f'{python_cmd} -m uvicorn app.main:app --host 0.0.0.0 --port {backend_port} --reload'

    process = subprocess.Popen(
        cmd,
        shell=True,
        cwd=str(backend_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
    )

    return process

def start_frontend(frontend_port: int) -> subprocess.Popen:
    """프론트엔드 서버 시작"""
    frontend_dir = PROJECT_ROOT / 'frontend'

    cmd = 'npm run dev'

    process = subprocess.Popen(
        cmd,
        shell=True,
        cwd=str(frontend_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
    )

    return process

def check_backend_health(port: int, max_retries: int = 30) -> bool:
    """백엔드 헬스 체크"""
    for i in range(max_retries):
        try:
            response = requests.get(f"http://localhost:{port}/health", timeout=2)
            if response.status_code == 200:
                return True
        except:
            pass

        try:
            response = requests.get(f"http://localhost:{port}/docs", timeout=2)
            if response.status_code == 200:
                return True
        except:
            pass

        time.sleep(2)

    return False

def check_frontend_health(port: int, max_retries: int = 30) -> bool:
    """프론트엔드 헬스 체크"""
    for i in range(max_retries):
        try:
            response = requests.get(f"http://localhost:{port}", timeout=2)
            if response.status_code in [200, 304, 404]:
                return True
        except:
            pass

        time.sleep(2)

    return False

def check_connection(backend_port: int) -> bool:
    """백엔드 연결 확인"""
    try:
        response = requests.get(f"http://localhost:{backend_port}/health", timeout=5)
        return response.status_code == 200
    except:
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

def try_ports(attempt: int) -> Tuple[Optional[int], Optional[int]]:
    """포트 조합 시도"""
    backend_start = 8010 + (attempt * 10)
    frontend_start = 3001 + (attempt * 10)

    backend_port = find_free_port(backend_start)
    if not backend_port:
        return None, None

    frontend_port = find_free_port(frontend_start)
    if not frontend_port:
        return None, None

    return backend_port, frontend_port

def main():
    print("=" * 70)
    print("  Doctor Voice Pro - 자동 재시도 서버 시작")
    print("=" * 70)
    print()
    print("연결이 성공할 때까지 자동으로 다른 포트를 시도합니다...")
    print()

    server_manager = ServerProcess()
    attempt = 0
    max_attempts = 50

    try:
        while attempt < max_attempts:
            attempt += 1
            print(f"\n{'=' * 70}")
            print(f"시도 #{attempt}")
            print(f"{'=' * 70}\n")

            # 1. 빈 포트 찾기
            print("1단계: 사용 가능한 포트 찾기...")
            backend_port, frontend_port = try_ports(attempt - 1)

            if not backend_port or not frontend_port:
                print(f"  사용 가능한 포트를 찾을 수 없습니다. 다음 시도...")
                time.sleep(2)
                continue

            print(f"  백엔드 포트: {backend_port}")
            print(f"  프론트엔드 포트: {frontend_port}")

            # 2. 기존 포트 정리
            print("\n2단계: 기존 프로세스 정리...")
            if check_port_in_use(backend_port):
                kill_process_on_port(backend_port)
            if check_port_in_use(frontend_port):
                kill_process_on_port(frontend_port)

            # 3. 환경 설정 업데이트
            print("\n3단계: 환경 설정 업데이트...")
            update_backend_env(backend_port, frontend_port)
            update_frontend_env(backend_port, frontend_port)
            update_frontend_package_json(frontend_port)
            print("  환경 설정 완료")

            # 4. 서버 시작
            print("\n4단계: 서버 시작...")
            server_manager.kill_all()

            print(f"  백엔드 시작 중... (포트: {backend_port})")
            backend_process = start_backend(backend_port)
            server_manager.backend_process = backend_process
            time.sleep(3)

            print(f"  프론트엔드 시작 중... (포트: {frontend_port})")
            frontend_process = start_frontend(frontend_port)
            server_manager.frontend_process = frontend_process

            # 5. 백엔드 연결 확인
            print("\n5단계: 백엔드 연결 확인...")
            if not check_backend_health(backend_port, max_retries=30):
                print("  백엔드 연결 실패. 다른 포트로 재시도...")
                server_manager.kill_all()
                time.sleep(2)
                continue

            print(f"  백엔드 연결 성공!")

            # 6. 프론트엔드 연결 확인
            print("\n6단계: 프론트엔드 연결 확인...")
            if not check_frontend_health(frontend_port, max_retries=30):
                print("  프론트엔드 연결 실패. 다른 포트로 재시도...")
                server_manager.kill_all()
                time.sleep(2)
                continue

            print(f"  프론트엔드 연결 성공!")

            # 7. 백엔드-프론트엔드 연결 확인
            print("\n7단계: 서버 간 연결 확인...")
            if not check_connection(backend_port):
                print("  서버 간 연결 실패. 다른 포트로 재시도...")
                server_manager.kill_all()
                time.sleep(2)
                continue

            print("  서버 간 연결 성공!")

            # 성공!
            print(f"\n{'=' * 70}")
            print("  SUCCESS! 모든 서버가 성공적으로 연결되었습니다!")
            print(f"{'=' * 70}\n")
            print(f"  백엔드:      http://localhost:{backend_port}")
            print(f"  프론트엔드:  http://localhost:{frontend_port}")
            print(f"  API 문서:    http://localhost:{backend_port}/docs")
            print(f"\n{'=' * 70}\n")

            # 브라우저 열기
            print("브라우저를 여는 중...")
            open_browser(frontend_port)

            print("\n서버가 실행 중입니다.")
            print("서버 창을 닫으면 서버가 종료됩니다.")
            print("\n이 창을 닫아도 서버는 계속 실행됩니다.")
            input("\n아무 키나 눌러 종료하세요...")

            return True

        print(f"\n최대 시도 횟수({max_attempts})에 도달했습니다.")
        return False

    except KeyboardInterrupt:
        print("\n\n사용자에 의해 취소되었습니다.")
        server_manager.kill_all()
        return False

    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()
        server_manager.kill_all()
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n치명적 오류: {e}")
        import traceback
        traceback.print_exc()
        input("\n아무 키나 눌러 종료하세요...")
        sys.exit(1)
