"""
백엔드-프론트엔드 연결 헬스체크 시스템
서버 연결 상태를 지속적으로 모니터링하고 자동 복구 시도
"""
import requests
import time
import json
import os
from typing import Optional, Dict
from datetime import datetime


class HealthChecker:
    """서버 헬스체크 및 자동 재연결 클래스"""

    def __init__(self, backend_url: str = None, max_retries: int = 100, retry_interval: int = 3):
        self.backend_url = backend_url or self.load_backend_url()
        self.max_retries = max_retries
        self.retry_interval = retry_interval
        self.is_connected = False

    def load_backend_url(self) -> str:
        """설정 파일에서 백엔드 URL 로드"""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            config_file = os.path.join(project_root, 'connection_config.json')

            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    backend = config.get('backend', {})
                    protocol = backend.get('protocol', 'http')
                    host = backend.get('host', 'localhost')
                    port = backend.get('port', 8010)
                    return f"{protocol}://{host}:{port}"
        except Exception as e:
            print(f"설정 파일 로드 실패: {e}")

        return "http://localhost:8010"

    def check_health(self, url: str = None, timeout: int = 5) -> bool:
        """단일 헬스체크 수행"""
        test_url = url or self.backend_url
        try:
            response = requests.get(
                f"{test_url}/health",
                timeout=timeout,
                headers={'Content-Type': 'application/json'}
            )
            return response.status_code == 200
        except Exception:
            return False

    def wait_for_connection(self, show_progress: bool = True) -> bool:
        """
        연결될 때까지 대기 및 재시도
        Returns: True if connected, False if max retries exceeded
        """
        print("=" * 60)
        print("백엔드 서버 연결 대기 중...")
        print(f"URL: {self.backend_url}")
        print("=" * 60)

        for attempt in range(1, self.max_retries + 1):
            if show_progress:
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] 시도 {attempt}/{self.max_retries}...", end=" ")

            if self.check_health():
                if show_progress:
                    print("✓ 연결 성공!")
                self.is_connected = True
                print("\n" + "=" * 60)
                print("백엔드 서버 연결 완료!")
                print("=" * 60)
                return True
            else:
                if show_progress:
                    print("✗ 연결 실패")

                if attempt < self.max_retries:
                    time.sleep(self.retry_interval)

        print("\n" + "=" * 60)
        print("⚠️  백엔드 서버 연결 실패")
        print(f"최대 재시도 횟수({self.max_retries})를 초과했습니다.")
        print("=" * 60)
        self.is_connected = False
        return False

    def monitor_connection(self, check_interval: int = 5, auto_reconnect: bool = True):
        """
        연결 상태를 지속적으로 모니터링
        연결이 끊어지면 자동으로 재연결 시도
        """
        print("\n백엔드 연결 모니터링 시작...")
        print(f"체크 간격: {check_interval}초")
        print("Ctrl+C를 눌러 중단하세요.\n")

        try:
            while True:
                if self.check_health():
                    if not self.is_connected:
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        print(f"[{timestamp}] ✓ 백엔드 서버 연결됨")
                        self.is_connected = True
                else:
                    if self.is_connected or self.is_connected is None:
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        print(f"[{timestamp}] ✗ 백엔드 서버 연결 끊김")
                        self.is_connected = False

                        if auto_reconnect:
                            print("자동 재연결 시도 중...")
                            self.wait_for_connection(show_progress=True)

                time.sleep(check_interval)

        except KeyboardInterrupt:
            print("\n\n모니터링을 중단합니다.")

    def get_server_info(self) -> Optional[Dict]:
        """백엔드 서버 정보 가져오기"""
        try:
            response = requests.get(
                f"{self.backend_url}/",
                timeout=5,
                headers={'Content-Type': 'application/json'}
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"서버 정보 조회 실패: {e}")
        return None


def scan_for_backend(ports: list = None, timeout: int = 1) -> Optional[str]:
    """
    일반적인 포트에서 백엔드 서버 자동 검색
    Returns: 찾은 백엔드 URL 또는 None
    """
    if ports is None:
        ports = [8010, 8000, 8001, 8002, 8003, 8011, 8012, 8020, 9000, 9001]

    print("백엔드 서버 자동 검색 중...")
    for port in ports:
        url = f"http://localhost:{port}"
        print(f"  포트 {port} 확인...", end=" ")

        try:
            response = requests.get(f"{url}/health", timeout=timeout)
            if response.status_code == 200:
                print("✓ 발견!")
                return url
        except:
            pass

        print("✗")

    print("백엔드 서버를 찾을 수 없습니다.")
    return None


if __name__ == "__main__":
    import sys

    # 명령행 옵션 처리
    if len(sys.argv) > 1:
        if sys.argv[1] == "--scan":
            # 자동 스캔
            backend_url = scan_for_backend()
            if backend_url:
                print(f"\n백엔드 URL: {backend_url}")
                checker = HealthChecker(backend_url)
                if checker.check_health():
                    info = checker.get_server_info()
                    if info:
                        print(f"\n서버 정보:")
                        print(json.dumps(info, indent=2, ensure_ascii=False))
        elif sys.argv[1] == "--monitor":
            # 연결 모니터링
            checker = HealthChecker()
            checker.monitor_connection()
        else:
            # 특정 URL 테스트
            backend_url = sys.argv[1]
            checker = HealthChecker(backend_url)
            if checker.check_health():
                print(f"✓ 연결 성공: {backend_url}")
                info = checker.get_server_info()
                if info:
                    print(json.dumps(info, indent=2, ensure_ascii=False))
            else:
                print(f"✗ 연결 실패: {backend_url}")
    else:
        # 기본: 연결 대기
        checker = HealthChecker()
        checker.wait_for_connection()
