"""
포트 자동 감지 및 관리 유틸리티
사용 가능한 포트를 자동으로 찾고 할당합니다.
"""
import socket
import json
import os
from typing import List, Optional, Tuple


def is_port_available(port: int, host: str = '127.0.0.1') -> bool:
    """
    지정된 포트가 사용 가능한지 확인
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            return result != 0  # 0이 아니면 사용 가능
    except Exception:
        return False


def kill_port(port: int) -> bool:
    """
    지정된 포트를 사용하는 프로세스 종료 (Windows)
    """
    try:
        import subprocess
        # netstat으로 포트를 사용하는 PID 찾기
        result = subprocess.run(
            f'netstat -ano | findstr :{port}',
            shell=True,
            capture_output=True,
            text=True
        )

        if result.stdout:
            lines = result.stdout.strip().split('\n')
            pids = set()
            for line in lines:
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    if pid.isdigit():
                        pids.add(pid)

            # PID로 프로세스 종료
            for pid in pids:
                subprocess.run(f'taskkill /F /PID {pid}', shell=True, capture_output=True)
                print(f"포트 {port}를 사용하던 프로세스 (PID: {pid}) 종료")

            return True
        return False
    except Exception as e:
        print(f"포트 {port} 종료 실패: {e}")
        return False


def find_available_port(preferred_port: int, port_range: List[int] = None) -> int:
    """
    사용 가능한 포트 찾기
    preferred_port가 사용 가능하면 그것을 반환,
    아니면 port_range에서 사용 가능한 포트를 찾음
    """
    if is_port_available(preferred_port):
        return preferred_port

    if port_range is None:
        # 기본 포트 범위
        if preferred_port == 3000:
            port_range = [3001, 3002, 3003, 3004, 3005, 3010, 3020]
        elif preferred_port == 8010:
            port_range = [8000, 8001, 8002, 8003, 8011, 8012, 8020, 9000, 9001]
        else:
            port_range = list(range(preferred_port + 1, preferred_port + 100))

    for port in port_range:
        if is_port_available(port):
            return port

    # 모든 포트가 사용 중이면 랜덤 포트
    import random
    for _ in range(100):
        random_port = random.randint(10000, 65535)
        if is_port_available(random_port):
            return random_port

    raise Exception("사용 가능한 포트를 찾을 수 없습니다")


def cleanup_all_ports(backend_ports: List[int] = None, frontend_ports: List[int] = None):
    """
    모든 관련 포트 정리
    """
    if backend_ports is None:
        backend_ports = [8000, 8001, 8002, 8003, 8010, 8011, 8012, 8020, 9000, 9001]
    if frontend_ports is None:
        frontend_ports = [3000, 3001, 3002, 3003, 3004, 3005, 3010, 3020]

    print("=" * 60)
    print("포트 정리 시작...")
    print("=" * 60)

    cleaned = 0
    for port in backend_ports + frontend_ports:
        if not is_port_available(port):
            print(f"\n포트 {port} 사용 중 감지...")
            if kill_port(port):
                cleaned += 1

    print("\n" + "=" * 60)
    print(f"포트 정리 완료: {cleaned}개 포트 정리됨")
    print("=" * 60)


def allocate_ports() -> Tuple[int, int]:
    """
    백엔드와 프론트엔드 포트를 자동으로 할당
    Returns: (backend_port, frontend_port)
    """
    backend_port = find_available_port(8010)
    frontend_port = find_available_port(3000)

    return backend_port, frontend_port


def save_port_config(backend_port: int, frontend_port: int, config_file: str = None):
    """
    포트 설정을 JSON 파일로 저장
    """
    if config_file is None:
        # 프로젝트 루트 찾기
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        config_file = os.path.join(project_root, 'connection_config.json')

    config = {
        "backend": {
            "host": "localhost",
            "port": backend_port,
            "protocol": "http"
        },
        "frontend": {
            "host": "localhost",
            "port": frontend_port,
            "protocol": "http"
        },
        "connection": {
            "health_check_interval": 5,
            "reconnect_interval": 3,
            "max_reconnect_attempts": 100,
            "timeout": 5
        }
    }

    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"\n포트 설정 저장: {config_file}")
    print(f"  - Backend:  http://localhost:{backend_port}")
    print(f"  - Frontend: http://localhost:{frontend_port}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # 명령행 인자로 포트 지정
        preferred_port = int(sys.argv[1])
        available_port = find_available_port(preferred_port)
        print(available_port)
    else:
        # 전체 포트 할당
        backend_port, frontend_port = allocate_ports()
        save_port_config(backend_port, frontend_port)
