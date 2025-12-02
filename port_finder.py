#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
포트 자동 탐색 유틸리티
사용 가능한 포트를 자동으로 찾아주는 도구입니다.
"""

import socket
from typing import Optional, List, Dict


class PortFinder:
    """포트 탐색 클래스"""

    def __init__(self, start_port: int, end_port: int):
        """
        Args:
            start_port: 탐색 시작 포트
            end_port: 탐색 종료 포트
        """
        self.start_port = start_port
        self.end_port = end_port

    def is_port_available(self, port: int) -> bool:
        """
        특정 포트가 사용 가능한지 확인

        Args:
            port: 확인할 포트 번호

        Returns:
            True: 사용 가능, False: 이미 사용 중
        """
        try:
            # TCP 소켓 생성
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                # SO_REUSEADDR 옵션 설정
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                # 포트 바인딩 시도
                s.bind(('127.0.0.1', port))
                return True
        except OSError:
            # 포트가 이미 사용 중
            return False

    def find_available_port(self, preferred_port: Optional[int] = None) -> Optional[int]:
        """
        사용 가능한 포트 찾기

        Args:
            preferred_port: 우선적으로 시도할 포트 (None이면 범위 처음부터 탐색)

        Returns:
            사용 가능한 포트 번호, 없으면 None
        """
        # 1. 우선 포트가 지정되어 있고 사용 가능하면 반환
        if preferred_port is not None:
            if self.start_port <= preferred_port <= self.end_port:
                if self.is_port_available(preferred_port):
                    return preferred_port

        # 2. 범위 내에서 사용 가능한 포트 탐색
        for port in range(self.start_port, self.end_port + 1):
            if self.is_port_available(port):
                return port

        # 3. 사용 가능한 포트를 찾지 못함
        return None

    def get_all_available_ports(self) -> List[int]:
        """
        범위 내 모든 사용 가능한 포트 목록 반환

        Returns:
            사용 가능한 포트 번호 리스트
        """
        available_ports = []
        for port in range(self.start_port, self.end_port + 1):
            if self.is_port_available(port):
                available_ports.append(port)
        return available_ports

    def check_port_status(self, port: int) -> Dict[str, any]:
        """
        포트 상태 상세 정보 반환

        Args:
            port: 확인할 포트 번호

        Returns:
            포트 상태 정보 딕셔너리
        """
        is_available = self.is_port_available(port)
        return {
            'port': port,
            'available': is_available,
            'status': '사용 가능' if is_available else '사용 중',
            'in_range': self.start_port <= port <= self.end_port
        }


# 백엔드용 포트 탐색 함수
def find_backend_port(preferred_port: int = 8010) -> int:
    """
    백엔드용 포트 찾기 (8010-8110 범위)

    Args:
        preferred_port: 우선적으로 시도할 포트 (기본: 8010)

    Returns:
        사용 가능한 포트 번호

    Raises:
        RuntimeError: 사용 가능한 포트를 찾지 못한 경우
    """
    finder = PortFinder(8010, 8110)
    port = finder.find_available_port(preferred_port)

    if port is None:
        raise RuntimeError(
            f"포트 범위 8010-8110 내에서 사용 가능한 포트를 찾지 못했습니다."
        )

    return port


# 프론트엔드용 포트 탐색 함수
def find_frontend_port(preferred_port: int = 3000) -> int:
    """
    프론트엔드용 포트 찾기 (3000-3100 범위)

    Args:
        preferred_port: 우선적으로 시도할 포트 (기본: 3000)

    Returns:
        사용 가능한 포트 번호

    Raises:
        RuntimeError: 사용 가능한 포트를 찾지 못한 경우
    """
    finder = PortFinder(3000, 3100)
    port = finder.find_available_port(preferred_port)

    if port is None:
        raise RuntimeError(
            f"포트 범위 3000-3100 내에서 사용 가능한 포트를 찾지 못했습니다."
        )

    return port


# CLI 도구
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='포트 탐색 유틸리티')
    parser.add_argument('--backend', action='store_true', help='백엔드 포트 찾기')
    parser.add_argument('--frontend', action='store_true', help='프론트엔드 포트 찾기')
    parser.add_argument('--port', type=int, help='확인할 포트')
    parser.add_argument('--range', nargs=2, type=int, metavar=('START', 'END'),
                        help='탐색 범위 (예: --range 5000 5100)')
    parser.add_argument('--list', action='store_true', help='사용 가능한 모든 포트 나열')

    args = parser.parse_args()

    if args.backend:
        try:
            port = find_backend_port()
            print(f"[OK] 백엔드 포트: {port}")
        except RuntimeError as e:
            print(f"[ERROR] 오류: {e}")

    elif args.frontend:
        try:
            port = find_frontend_port()
            print(f"[OK] 프론트엔드 포트: {port}")
        except RuntimeError as e:
            print(f"[ERROR] 오류: {e}")

    elif args.port:
        finder = PortFinder(1, 65535)
        status = finder.check_port_status(args.port)
        print(f"포트 {args.port}: {status['status']}")

    elif args.range:
        start, end = args.range
        finder = PortFinder(start, end)

        if args.list:
            ports = finder.get_all_available_ports()
            print(f"범위 {start}-{end}에서 사용 가능한 포트 ({len(ports)}개):")
            for port in ports[:10]:  # 최대 10개만 표시
                print(f"  - {port}")
            if len(ports) > 10:
                print(f"  ... 외 {len(ports) - 10}개")
        else:
            port = finder.find_available_port()
            if port:
                print(f"[OK] 사용 가능한 포트: {port}")
            else:
                print(f"[ERROR] 범위 {start}-{end}에서 사용 가능한 포트 없음")

    else:
        parser.print_help()
