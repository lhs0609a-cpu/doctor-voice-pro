#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
연결 관리 자동 실행 스크립트
포트 자동 탐색, 설정 파일 업데이트, 서버 시작을 통합 관리합니다.
"""

import os
import sys
import json
import subprocess
import time
import signal
from pathlib import Path
from typing import Optional, Tuple

# 모듈 임포트
try:
    from port_finder import find_backend_port, find_frontend_port
    from connection_manager import ConnectionConfig, ConnectionManager
except ImportError:
    print("[ERROR] 필수 모듈을 찾을 수 없습니다.")
    print("현재 디렉토리:", os.getcwd())
    sys.exit(1)


class ServerManager:
    """서버 시작 및 관리 클래스"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.backend_process: Optional[subprocess.Popen] = None
        self.frontend_process: Optional[subprocess.Popen] = None
        self.config = ConnectionConfig(str(project_root / "connection_config.json"))

    def find_and_update_ports(self) -> Tuple[int, int]:
        """
        사용 가능한 포트를 찾아서 설정 파일 업데이트

        Returns:
            (backend_port, frontend_port)
        """
        print("\n" + "=" * 60)
        print("  [1] 포트 탐색 및 설정")
        print("=" * 60)

        # 백엔드 포트 탐색
        try:
            backend_port = find_backend_port()
            print(f"[OK] 백엔드 포트: {backend_port}")
        except RuntimeError as e:
            print(f"[ERROR] 백엔드 포트 탐색 실패: {e}")
            sys.exit(1)

        # 프론트엔드 포트 탐색
        try:
            frontend_port = find_frontend_port()
            print(f"[OK] 프론트엔드 포트: {frontend_port}")
        except RuntimeError as e:
            print(f"[ERROR] 프론트엔드 포트 탐색 실패: {e}")
            sys.exit(1)

        # 설정 파일 업데이트
        self.config.update_backend_port(backend_port)
        self.config.update_frontend_port(frontend_port)

        # 프론트엔드 public 폴더에도 복사
        frontend_config = self.project_root / "frontend" / "public" / "connection_config.json"
        try:
            frontend_config.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config.config_path, 'r', encoding='utf-8') as src:
                with open(frontend_config, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
            print(f"[OK] 프론트엔드 설정 복사: {frontend_config}")
        except Exception as e:
            print(f"[WARN] 프론트엔드 설정 복사 실패: {e}")

        print("=" * 60)

        return backend_port, frontend_port

    def start_backend(self, port: int) -> bool:
        """
        백엔드 서버 시작

        Args:
            port: 백엔드 포트

        Returns:
            True: 성공, False: 실패
        """
        print("\n" + "=" * 60)
        print("  [2] 백엔드 서버 시작")
        print("=" * 60)

        backend_dir = self.project_root / "backend"

        if not backend_dir.exists():
            print(f"[ERROR] 백엔드 폴더를 찾을 수 없습니다: {backend_dir}")
            return False

        # 환경 변수 설정
        env = os.environ.copy()
        env['PORT'] = str(port)

        # uvicorn 실행 명령
        cmd = [
            sys.executable,
            '-m',
            'uvicorn',
            'app.main:app',
            '--host', '0.0.0.0',
            '--port', str(port),
            '--reload'
        ]

        try:
            print(f"[BACKEND] 백엔드 시작 중... (포트: {port})")
            print(f"   명령: {' '.join(cmd)}")

            self.backend_process = subprocess.Popen(
                cmd,
                cwd=str(backend_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )

            # 백엔드 시작 대기 (최대 30초)
            print("   백엔드 시작 대기 중...")

            manager = ConnectionManager(self.config)
            max_wait_time = 30
            start_time = time.time()

            while time.time() - start_time < max_wait_time:
                # 프로세스 종료 확인
                if self.backend_process.poll() is not None:
                    print("\n[ERROR] 백엔드 프로세스가 종료되었습니다.")
                    print("\n[ERROR OUTPUT]")
                    print("=" * 60)
                    # 에러 출력 읽기
                    if self.backend_process.stdout:
                        output = self.backend_process.stdout.read()
                        if output:
                            # 마지막 50줄만 출력
                            lines = output.strip().split('\n')
                            for line in lines[-50:]:
                                print(line)
                    print("=" * 60)
                    print("\n[TROUBLESHOOTING]")
                    print("1. Python 패키지 설치:")
                    print("   cd backend")
                    print("   pip install -r requirements.txt")
                    print("\n2. Python 3.14 호환성 문제:")
                    print("   pip install --upgrade sqlalchemy anthropic")
                    print("\n3. 데이터베이스 초기화:")
                    print("   cd backend")
                    print("   python -m alembic upgrade head")
                    return False

                # 헬스체크 성공
                if manager.check_backend_health():
                    print(f"[OK] 백엔드 서버 실행 중 (PID: {self.backend_process.pid})")
                    print(f"   URL: http://localhost:{port}")
                    print(f"   API Docs: http://localhost:{port}/docs")
                    print("=" * 60)
                    return True

                time.sleep(1)

            # 타임아웃
            print(f"\n[WARN] 백엔드 서버가 {max_wait_time}초 내에 응답하지 않습니다.")
            print("\n[PROCESS OUTPUT]")
            print("=" * 60)
            if self.backend_process.stdout:
                output = self.backend_process.stdout.read()
                if output:
                    lines = output.strip().split('\n')
                    for line in lines[-50:]:
                        print(line)
            print("=" * 60)
            return False

        except Exception as e:
            print(f"[ERROR] 백엔드 시작 실패: {e}")
            return False

    def start_frontend(self, port: int) -> bool:
        """
        프론트엔드 서버 시작

        Args:
            port: 프론트엔드 포트

        Returns:
            True: 성공, False: 실패
        """
        print("\n" + "=" * 60)
        print("  [3] 프론트엔드 서버 시작")
        print("=" * 60)

        frontend_dir = self.project_root / "frontend"

        if not frontend_dir.exists():
            print(f"[ERROR] 프론트엔드 폴더를 찾을 수 없습니다: {frontend_dir}")
            return False

        # 환경 변수 설정
        env = os.environ.copy()
        env['PORT'] = str(port)

        # npm run dev 실행
        cmd = ['npm', 'run', 'dev']

        try:
            print(f"[FRONTEND] 프론트엔드 시작 중... (포트: {port})")
            print(f"   명령: {' '.join(cmd)}")

            self.frontend_process = subprocess.Popen(
                cmd,
                cwd=str(frontend_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )

            # 프론트엔드 시작 대기
            print("   프론트엔드 시작 대기 중...")
            time.sleep(5)

            if self.frontend_process.poll() is not None:
                print("[ERROR] 프론트엔드 프로세스가 종료되었습니다.")
                return False

            print(f"[OK] 프론트엔드 서버 실행 중 (PID: {self.frontend_process.pid})")
            print(f"   URL: http://localhost:{port}")
            print("=" * 60)
            return True

        except Exception as e:
            print(f"[ERROR] 프론트엔드 시작 실패: {e}")
            return False

    def stop_servers(self):
        """서버 중지"""
        print("\n서버 종료 중...")

        if self.backend_process:
            print("[BACKEND] 백엔드 서버 종료 중...")
            self.backend_process.terminate()
            try:
                self.backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.backend_process.kill()
            print("[OK] 백엔드 서버 종료 완료")

        if self.frontend_process:
            print("[FRONTEND] 프론트엔드 서버 종료 중...")
            self.frontend_process.terminate()
            try:
                self.frontend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.frontend_process.kill()
            print("[OK] 프론트엔드 서버 종료 완료")

    def run(self):
        """전체 실행 프로세스"""
        print("\n" + "=" * 60)
        print("  Doctor Voice Pro 서버 시작")
        print("=" * 60)

        # 시그널 핸들러 등록
        def signal_handler(sig, frame):
            print("\n\n종료 시그널 수신...")
            self.stop_servers()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)

        try:
            # 1. 포트 탐색 및 설정
            backend_port, frontend_port = self.find_and_update_ports()

            # 2. 백엔드 시작
            if not self.start_backend(backend_port):
                print("[ERROR] 백엔드 시작 실패")
                return False

            # 3. 프론트엔드 시작
            if not self.start_frontend(frontend_port):
                print("[ERROR] 프론트엔드 시작 실패")
                self.stop_servers()
                return False

            # 4. 완료 메시지
            print("\n" + "=" * 60)
            print("  [SUCCESS] 모든 서버가 실행 중입니다!")
            print("=" * 60)
            print(f"\n[FRONTEND] 프론트엔드: http://localhost:{frontend_port}")
            print(f"[BACKEND] 백엔드: http://localhost:{backend_port}")
            print(f"[DOCS] API 문서: http://localhost:{backend_port}/docs")
            print("\n종료하려면 Ctrl+C를 누르세요.")
            print("=" * 60)

            # 대기
            while True:
                time.sleep(1)

                # 프로세스 상태 확인
                if self.backend_process and self.backend_process.poll() is not None:
                    print("\n[ERROR] 백엔드 프로세스가 예기치 않게 종료되었습니다.")
                    self.stop_servers()
                    return False

                if self.frontend_process and self.frontend_process.poll() is not None:
                    print("\n[ERROR] 프론트엔드 프로세스가 예기치 않게 종료되었습니다.")
                    self.stop_servers()
                    return False

        except KeyboardInterrupt:
            self.stop_servers()
        except Exception as e:
            print(f"\n[ERROR] 오류 발생: {e}")
            self.stop_servers()
            return False

        return True


def main():
    """메인 함수"""
    # 프로젝트 루트 디렉토리
    project_root = Path(__file__).parent.absolute()

    # 서버 관리자 생성 및 실행
    manager = ServerManager(project_root)
    success = manager.run()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
