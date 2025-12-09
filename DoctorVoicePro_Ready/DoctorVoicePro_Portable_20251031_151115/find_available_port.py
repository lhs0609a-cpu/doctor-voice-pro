"""
포트 자동 탐지 유틸리티
사용 가능한 포트를 자동으로 찾습니다
"""
import socket
import sys


def is_port_available(port: int) -> bool:
    """포트가 사용 가능한지 확인"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('0.0.0.0', port))
            return True
    except OSError:
        return False


def find_available_port(preferred_port: int, max_attempts: int = 100) -> int:
    """사용 가능한 포트 찾기"""
    # 먼저 선호 포트 확인
    if is_port_available(preferred_port):
        return preferred_port

    # 선호 포트가 사용 중이면 다른 포트 찾기
    for offset in range(1, max_attempts):
        port = preferred_port + offset
        if port > 65535:  # 최대 포트 번호
            port = preferred_port - offset

        if port < 1024:  # 시스템 예약 포트 건너뛰기
            continue

        if is_port_available(port):
            return port

    raise RuntimeError(f"사용 가능한 포트를 찾을 수 없습니다 (시도: {max_attempts})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python find_available_port.py <포트번호>")
        sys.exit(1)

    try:
        preferred_port = int(sys.argv[1])
        available_port = find_available_port(preferred_port)
        print(available_port)  # 포트 번호만 출력 (배치 파일에서 사용)
    except ValueError:
        print(f"오류: 잘못된 포트 번호", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"오류: {e}", file=sys.stderr)
        sys.exit(1)
