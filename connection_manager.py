#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
연결 관리 모듈
백엔드 연결 상태 관리 및 자동 재연결 기능을 제공합니다.
"""

import json
import time
import requests
import threading
from pathlib import Path
from typing import Optional, Dict, Callable


class ConnectionConfig:
    """연결 설정 관리 클래스"""

    def __init__(self, config_path: str = "connection_config.json"):
        """
        Args:
            config_path: 설정 파일 경로
        """
        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """설정 파일 로드"""
        if not self.config_path.exists():
            # 기본 설정 생성
            default_config = {
                "backend": {
                    "host": "localhost",
                    "port": 8010,
                    "protocol": "http"
                },
                "frontend": {
                    "host": "localhost",
                    "port": 3000,
                    "protocol": "http"
                },
                "connection": {
                    "health_check_interval": 5,  # 헬스체크 간격 (초)
                    "reconnect_interval": 3,      # 재연결 시도 간격 (초)
                    "max_reconnect_attempts": 100,  # 최대 재연결 시도 횟수 (0=무제한)
                    "timeout": 5                  # 연결 타임아웃 (초)
                }
            }
            self.config = default_config
            self.save_config()
            return default_config

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  설정 파일 로드 실패: {e}")
            return {}

    def save_config(self):
        """설정 파일 저장"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️  설정 파일 저장 실패: {e}")

    def get_backend_url(self) -> str:
        """백엔드 URL 반환"""
        backend = self.config['backend']
        return f"{backend['protocol']}://{backend['host']}:{backend['port']}"

    def get_frontend_url(self) -> str:
        """프론트엔드 URL 반환"""
        frontend = self.config['frontend']
        return f"{frontend['protocol']}://{frontend['host']}:{frontend['port']}"

    def update_backend_port(self, port: int):
        """백엔드 포트 업데이트"""
        self.config['backend']['port'] = port
        self.save_config()

    def update_frontend_port(self, port: int):
        """프론트엔드 포트 업데이트"""
        self.config['frontend']['port'] = port
        self.save_config()


class ConnectionManager:
    """연결 관리 클래스"""

    def __init__(self, config: ConnectionConfig):
        """
        Args:
            config: 연결 설정 객체
        """
        self.config = config
        self.is_connected = False
        self.last_check_time = None
        self.reconnect_attempts = 0
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None

    def check_backend_health(self) -> bool:
        """
        백엔드 헬스체크

        Returns:
            True: 연결됨, False: 연결 안됨
        """
        try:
            url = f"{self.config.get_backend_url()}/health"
            timeout = self.config.config['connection']['timeout']

            response = requests.get(url, timeout=timeout)
            self.last_check_time = time.time()

            if response.status_code == 200:
                self.is_connected = True
                return True
            else:
                self.is_connected = False
                return False

        except Exception:
            self.is_connected = False
            self.last_check_time = time.time()
            return False

    def wait_for_backend(self, verbose: bool = True) -> bool:
        """
        백엔드 연결 대기 (재연결 시도)

        Args:
            verbose: 진행 상황 출력 여부

        Returns:
            True: 연결 성공, False: 최대 시도 횟수 초과
        """
        max_attempts = self.config.config['connection']['max_reconnect_attempts']
        interval = self.config.config['connection']['reconnect_interval']

        start_time = time.time()
        self.reconnect_attempts = 0

        while True:
            self.reconnect_attempts += 1
            elapsed_time = int(time.time() - start_time)

            if verbose:
                if max_attempts > 0:
                    print(f"\r[CONNECTING] 재연결 시도 중... ({self.reconnect_attempts}/{max_attempts}) "
                          f"| 경과 시간: {elapsed_time}초", end='', flush=True)
                else:
                    print(f"\r[CONNECTING] 재연결 시도 중... ({self.reconnect_attempts}회) "
                          f"| 경과 시간: {elapsed_time}초", end='', flush=True)

            # 헬스체크 시도
            if self.check_backend_health():
                if verbose:
                    print(f"\n[OK] 백엔드 연결 성공! (시도: {self.reconnect_attempts}회)")
                self.reconnect_attempts = 0
                return True

            # 최대 시도 횟수 확인 (0이면 무제한)
            if max_attempts > 0 and self.reconnect_attempts >= max_attempts:
                if verbose:
                    print(f"\n[ERROR] 최대 재연결 시도 횟수({max_attempts})를 초과했습니다.")
                return False

            # 대기
            time.sleep(interval)

    def start_monitoring(self, callback: Optional[Callable[[bool], None]] = None):
        """
        백그라운드 연결 모니터링 시작

        Args:
            callback: 연결 상태 변경 시 호출할 콜백 함수
        """
        if self.monitoring:
            return

        self.monitoring = True

        def monitor():
            interval = self.config.config['connection']['health_check_interval']
            previous_status = self.is_connected

            while self.monitoring:
                current_status = self.check_backend_health()

                # 상태가 변경되었을 때 콜백 호출
                if callback and current_status != previous_status:
                    callback(current_status)

                previous_status = current_status
                time.sleep(interval)

        self.monitor_thread = threading.Thread(target=monitor, daemon=True)
        self.monitor_thread.start()

    def stop_monitoring(self):
        """백그라운드 모니터링 중지"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)

    def get_status(self) -> Dict:
        """
        현재 연결 상태 반환

        Returns:
            상태 정보 딕셔너리
        """
        return {
            'connected': self.is_connected,
            'backend_url': self.config.get_backend_url(),
            'reconnect_attempts': self.reconnect_attempts,
            'last_check_time': self.last_check_time,
            'monitoring': self.monitoring
        }

    def print_status(self):
        """현재 상태 출력"""
        status = self.get_status()
        print("\n" + "=" * 60)
        print("  연결 상태")
        print("=" * 60)
        print(f"백엔드 URL: {status['backend_url']}")
        print(f"연결 상태: {'[CONNECTED]' if status['connected'] else '[DISCONNECTED]'}")
        if status['reconnect_attempts'] > 0:
            print(f"재연결 시도: {status['reconnect_attempts']}회")
        print(f"모니터링: {'실행 중' if status['monitoring'] else '중지됨'}")
        print("=" * 60)


# CLI 도구
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='연결 관리 도구')
    parser.add_argument('--check', action='store_true', help='백엔드 헬스체크')
    parser.add_argument('--wait', action='store_true', help='백엔드 연결 대기')
    parser.add_argument('--status', action='store_true', help='현재 상태 출력')
    parser.add_argument('--monitor', action='store_true', help='모니터링 시작')
    parser.add_argument('--config', default='connection_config.json', help='설정 파일 경로')

    args = parser.parse_args()

    # 설정 로드
    config = ConnectionConfig(args.config)
    manager = ConnectionManager(config)

    if args.check:
        print(f"백엔드 헬스체크: {config.get_backend_url()}/health")
        if manager.check_backend_health():
            print("[OK] 백엔드 정상")
        else:
            print("[ERROR] 백엔드 연결 실패")

    elif args.wait:
        print(f"백엔드 연결 대기: {config.get_backend_url()}")
        manager.wait_for_backend()

    elif args.status:
        manager.print_status()

    elif args.monitor:
        print(f"백엔드 모니터링 시작: {config.get_backend_url()}")
        print("종료하려면 Ctrl+C를 누르세요.")

        def on_status_change(connected: bool):
            if connected:
                print("\n[CONNECTED] 백엔드 연결됨")
            else:
                print("\n[DISCONNECTED] 백엔드 연결 끊김")

        manager.start_monitoring(callback=on_status_change)

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n모니터링 중지 중...")
            manager.stop_monitoring()
            print("종료되었습니다.")

    else:
        parser.print_help()
