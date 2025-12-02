"""
서버 자동 관리 유틸리티 (강화 버전)
- 포트 자동 탐지 및 할당
- 서버 헬스 체크
- 자동 재시작
- 백엔드-프론트엔드 연결 확인
- 연결될 때까지 계속 시도
"""
import socket
import subprocess
import time
import requests
import json
import os
import sys
from pathlib import Path
from typing import Optional, Tuple

class ServerManager:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.backend_port = None
        self.frontend_port = None
        self.backend_process = None
        self.frontend_process = None

    def is_port_available(self, port: int) -> bool:
        """포트 사용 가능 여부 확인"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', port))
                return True
        except OSError:
            return False

    def find_available_port(self, preferred_port: int, max_attempts: int = 100) -> int:
        """사용 가능한 포트 찾기"""
        if self.is_port_available(preferred_port):
            return preferred_port

        for offset in range(1, max_attempts):
            port = preferred_port + offset
            if port > 65535:
                port = preferred_port - offset
            if port < 1024:
                continue
            if self.is_port_available(port):
                return port

        raise RuntimeError(f"사용 가능한 포트를 찾을 수 없습니다 (시도: {max_attempts})")

    def check_backend_health(self, port: int, max_retries: int = 5) -> bool:
        """백엔드 서버 헬스 체크"""
        for i in range(max_retries):
            try:
                response = requests.get(f"http://localhost:{port}/health", timeout=2)
                if response.status_code == 200:
                    return True
            except requests.exceptions.RequestException:
                if i < max_retries - 1:
                    time.sleep(2)
        return False

    def check_frontend_health(self, port: int, max_retries: int = 5) -> bool:
        """프론트엔드 서버 헬스 체크"""
        for i in range(max_retries):
            try:
                response = requests.get(f"http://localhost:{port}", timeout=2)
                if response.status_code in [200, 304]:
                    return True
            except requests.exceptions.RequestException:
                if i < max_retries - 1:
                    time.sleep(2)
        return False

    def update_backend_config(self, backend_port: int, frontend_port: int):
        """백엔드 설정 파일 업데이트"""
        env_file = self.project_root / "backend" / ".env"

        if not env_file.exists():
            # .env.example에서 복사
            example_file = self.project_root / "backend" / ".env.example"
            if example_file.exists():
                import shutil
                shutil.copy(example_file, env_file)

        # ALLOWED_ORIGINS 업데이트
        if env_file.exists():
            content = env_file.read_text(encoding='utf-8')
            # ALLOWED_ORIGINS 라인 찾기 및 업데이트
            lines = content.split('\n')
            updated = False
            for i, line in enumerate(lines):
                if line.startswith('ALLOWED_ORIGINS='):
                    lines[i] = f'ALLOWED_ORIGINS=http://localhost:{frontend_port},http://127.0.0.1:{frontend_port}'
                    updated = True
                    break

            if not updated:
                lines.append(f'ALLOWED_ORIGINS=http://localhost:{frontend_port},http://127.0.0.1:{frontend_port}')

            env_file.write_text('\n'.join(lines), encoding='utf-8')

    def update_frontend_config(self, backend_port: int, frontend_port: int):
        """프론트엔드 설정 파일 업데이트"""
        env_local = self.project_root / "frontend" / ".env.local"
        content = f"NEXT_PUBLIC_API_URL=http://localhost:{backend_port}\nPORT={frontend_port}\n"
        env_local.write_text(content, encoding='utf-8')

    def start_backend(self, port: int) -> subprocess.Popen:
        """백엔드 서버 시작"""
        backend_dir = self.project_root / "backend"

        # Python 실행 파일 찾기
        venv_python = backend_dir / "venv" / "Scripts" / "python.exe"
        if not venv_python.exists():
            python_cmd = "python"
        else:
            python_cmd = str(venv_python)

        cmd = [
            python_cmd, "-m", "uvicorn",
            "app.main:app",
            "--host", "0.0.0.0",
            "--port", str(port),
            "--reload"
        ]

        process = subprocess.Popen(
            cmd,
            cwd=str(backend_dir),
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
        )

        return process

    def start_frontend(self, port: int) -> subprocess.Popen:
        """프론트엔드 서버 시작"""
        frontend_dir = self.project_root / "frontend"

        cmd = ["npm", "run", "dev", "--", "-p", str(port)]

        env = os.environ.copy()
        env['PORT'] = str(port)

        process = subprocess.Popen(
            cmd,
            cwd=str(frontend_dir),
            env=env,
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
        )

        return process

    def verify_connection(self, backend_port: int, frontend_port: int, max_attempts: int = 30) -> bool:
        """백엔드-프론트엔드 연결 확인"""
        print(f"\n연결 확인 중 (최대 {max_attempts}회 시도)...")

        for attempt in range(1, max_attempts + 1):
            print(f"  시도 {attempt}/{max_attempts}...", end='')

            # 백엔드 확인
            backend_ok = self.check_backend_health(backend_port, max_retries=1)

            # 프론트엔드 확인
            frontend_ok = self.check_frontend_health(frontend_port, max_retries=1)

            if backend_ok and frontend_ok:
                print(" ✓ 성공!")
                return True

            status = []
            if not backend_ok:
                status.append("Backend X")
            if not frontend_ok:
                status.append("Frontend X")

            print(f" {', '.join(status)}")

            if attempt < max_attempts:
                time.sleep(2)

        return False

    def auto_sync_servers(self, max_retries: int = 5) -> Tuple[Optional[int], Optional[int]]:
        """서버 자동 동기화 - 연결될 때까지 계속 시도"""
        print("=" * 60)
        print("  서버 자동 동기화 시작")
        print("=" * 60)

        for retry in range(max_retries):
            print(f"\n[ 시도 {retry + 1}/{max_retries} ]")

            # 1. 사용 가능한 포트 찾기
            print("\n1. 사용 가능한 포트 탐색 중...")
            try:
                backend_port = self.find_available_port(8010)
                frontend_port = self.find_available_port(3000)

                if backend_port == 8010:
                    print(f"   Backend: {backend_port} (기본 포트)")
                else:
                    print(f"   Backend: {backend_port} (대체 포트)")

                if frontend_port == 3000:
                    print(f"   Frontend: {frontend_port} (기본 포트)")
                else:
                    print(f"   Frontend: {frontend_port} (대체 포트)")

                self.backend_port = backend_port
                self.frontend_port = frontend_port

            except RuntimeError as e:
                print(f"   오류: {e}")
                continue

            # 2. 설정 파일 업데이트
            print("\n2. 설정 파일 업데이트 중...")
            self.update_backend_config(backend_port, frontend_port)
            self.update_frontend_config(backend_port, frontend_port)
            print("   완료!")

            # 3. 서버 시작
            print("\n3. 서버 시작 중...")
            try:
                print("   Backend 시작...")
                self.backend_process = self.start_backend(backend_port)
                time.sleep(5)  # 백엔드 시작 대기

                print("   Frontend 시작...")
                self.frontend_process = self.start_frontend(frontend_port)
                time.sleep(5)  # 프론트엔드 시작 대기

            except Exception as e:
                print(f"   오류: {e}")
                continue

            # 4. 연결 확인
            print("\n4. 서버 연결 확인 중...")
            if self.verify_connection(backend_port, frontend_port):
                print("\n" + "=" * 60)
                print("  ✓ 서버 동기화 성공!")
                print("=" * 60)
                print(f"\n  Backend:  http://localhost:{backend_port}")
                print(f"  Frontend: http://localhost:{frontend_port}")
                print(f"\n  로그인: admin@doctorvoice.com / admin123!@#")
                print("\n" + "=" * 60)
                return backend_port, frontend_port
            else:
                print("\n  X 연결 실패 - 재시도 중...")
                # 프로세스 종료 후 재시도
                if self.backend_process:
                    self.backend_process.terminate()
                if self.frontend_process:
                    self.frontend_process.terminate()
                time.sleep(3)

        print("\n" + "=" * 60)
        print("  X 서버 동기화 실패")
        print("=" * 60)
        return None, None

    def save_server_info(self, backend_port: int, frontend_port: int):
        """서버 정보 저장"""
        info_file = self.project_root / "server_info.json"
        info = {
            "backend_port": backend_port,
            "frontend_port": frontend_port,
            "timestamp": time.time()
        }
        info_file.write_text(json.dumps(info, indent=2), encoding='utf-8')

    def load_server_info(self) -> Optional[dict]:
        """저장된 서버 정보 로드"""
        info_file = self.project_root / "server_info.json"
        if info_file.exists():
            try:
                return json.loads(info_file.read_text(encoding='utf-8'))
            except:
                return None
        return None


def main():
    project_root = Path(__file__).parent
    manager = ServerManager(str(project_root))

    # 서버 자동 동기화 실행
    backend_port, frontend_port = manager.auto_sync_servers(max_retries=5)

    if backend_port and frontend_port:
        # 서버 정보 저장
        manager.save_server_info(backend_port, frontend_port)

        # 브라우저 자동 열기
        import webbrowser
        time.sleep(3)
        webbrowser.open(f"http://localhost:{frontend_port}")

        print("\n이 창을 닫으면 서버가 종료됩니다.")
        input("\nPress Enter to stop servers...")

        # 서버 종료
        if manager.backend_process:
            manager.backend_process.terminate()
        if manager.frontend_process:
            manager.frontend_process.terminate()
    else:
        print("\n서버 시작 실패!")
        input("\nPress Enter to exit...")
        sys.exit(1)


if __name__ == "__main__":
    main()
