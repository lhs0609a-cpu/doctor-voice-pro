"""
포트 사용 여부 확인 및 사용 가능한 포트 찾기
"""
import socket
import json
import sys

def is_port_available(port, host='127.0.0.1'):
    """포트가 사용 가능한지 확인"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex((host, port))
            return result != 0  # 0이 아니면 사용 가능
    except Exception:
        return False

def find_available_port(start_port, max_attempts=50):
    """사용 가능한 포트 찾기"""
    for port in range(start_port, start_port + max_attempts):
        if is_port_available(port):
            return port
    return None

def check_and_find_ports():
    """백엔드와 프론트엔드용 포트 확인 및 찾기"""

    # 기본 포트
    default_backend_port = 8000
    default_frontend_port = 3000

    # 백엔드 포트 확인
    backend_port = default_backend_port
    if not is_port_available(backend_port):
        print(f"[!] 포트 {backend_port}가 사용 중입니다.")
        backend_port = find_available_port(8000)
        if backend_port:
            print(f"[OK] 대체 포트를 찾았습니다: {backend_port}")
        else:
            print(f"[ERROR] 사용 가능한 포트를 찾을 수 없습니다.")
            sys.exit(1)
    else:
        print(f"[OK] 백엔드 포트 {backend_port} 사용 가능")

    # 프론트엔드 포트 확인
    frontend_port = default_frontend_port
    if not is_port_available(frontend_port):
        print(f"[!] 포트 {frontend_port}가 사용 중입니다.")
        frontend_port = find_available_port(3000)
        if frontend_port:
            print(f"[OK] 대체 포트를 찾았습니다: {frontend_port}")
        else:
            print(f"[ERROR] 사용 가능한 포트를 찾을 수 없습니다.")
            sys.exit(1)
    else:
        print(f"[OK] 프론트엔드 포트 {frontend_port} 사용 가능")

    # 결과 저장
    result = {
        "backend_port": backend_port,
        "frontend_port": frontend_port,
        "backend_url": f"http://localhost:{backend_port}",
        "frontend_url": f"http://localhost:{frontend_port}"
    }

    with open('port_config.json', 'w') as f:
        json.dump(result, f, indent=2)

    print(f"\n[*] 포트 설정 완료:")
    print(f"    Backend:  {backend_port}")
    print(f"    Frontend: {frontend_port}")

    return result

if __name__ == "__main__":
    try:
        config = check_and_find_ports()
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
