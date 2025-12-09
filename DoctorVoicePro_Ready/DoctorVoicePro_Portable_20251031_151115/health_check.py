#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
시스템 자가 진단 모듈
프로그램 시작 전 모든 필수 요구사항을 체크하고 자동 수정을 시도합니다.
"""

import os
import sys
import platform
import subprocess
import socket
import shutil
import psutil
from pathlib import Path
from typing import List, Tuple, Dict
import importlib.util


class HealthCheck:
    """시스템 헬스 체크 클래스"""

    def __init__(self, project_root=None):
        self.project_root = Path(project_root or os.getcwd())
        self.backend_dir = self.project_root / "backend"
        self.frontend_dir = self.project_root / "frontend"
        self.issues = []
        self.fixes_applied = []
        self.warnings = []

    def print_header(self, text):
        """헤더 출력"""
        print(f"\n{'=' * 60}")
        print(f"  {text}")
        print(f"{'=' * 60}")

    def print_check(self, item, status, details=""):
        """체크 결과 출력"""
        symbols = {
            'ok': '✅',
            'fail': '❌',
            'warning': '⚠️ ',
            'info': 'ℹ️ '
        }
        symbol = symbols.get(status, '  ')
        print(f"{symbol} {item}")
        if details:
            print(f"   {details}")

    def check_python_version(self) -> bool:
        """Python 버전 확인 (3.8 이상 필요)"""
        version = sys.version_info
        version_str = f"{version.major}.{version.minor}.{version.micro}"

        if version.major == 3 and version.minor >= 8:
            self.print_check(
                f"Python 버전: {version_str}",
                'ok',
                "요구사항: Python 3.8 이상"
            )
            return True
        else:
            self.print_check(
                f"Python 버전: {version_str}",
                'fail',
                "Python 3.8 이상이 필요합니다."
            )
            self.issues.append({
                'type': 'python_version',
                'message': f'현재 버전: {version_str}, 필요 버전: 3.8+',
                'fix': '최신 Python을 https://www.python.org/downloads/ 에서 설치하세요.'
            })
            return False

    def check_pip(self) -> bool:
        """pip 설치 확인"""
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                self.print_check("pip 설치 확인", 'ok', result.stdout.strip())
                return True
            else:
                raise Exception("pip이 설치되어 있지 않습니다.")
        except Exception as e:
            self.print_check("pip 설치 확인", 'fail', str(e))
            self.issues.append({
                'type': 'pip_missing',
                'message': 'pip이 설치되어 있지 않습니다.',
                'fix': f'{sys.executable} -m ensurepip --upgrade 실행'
            })
            return False

    def check_packages(self) -> Tuple[bool, List[str]]:
        """필수 패키지 설치 확인"""
        requirements_file = self.backend_dir / "requirements.txt"

        if not requirements_file.exists():
            self.print_check("requirements.txt", 'warning', "파일을 찾을 수 없습니다.")
            return True, []

        # requirements.txt 읽기
        with open(requirements_file, 'r', encoding='utf-8') as f:
            requirements = [
                line.strip().split('==')[0].split('[')[0]
                for line in f
                if line.strip() and not line.startswith('#')
            ]

        missing_packages = []
        for package in requirements:
            if package and not self.is_package_installed(package):
                missing_packages.append(package)

        if missing_packages:
            self.print_check(
                f"패키지 설치 확인",
                'fail',
                f"{len(missing_packages)}개 패키지 누락: {', '.join(missing_packages[:5])}"
            )
            self.issues.append({
                'type': 'missing_packages',
                'message': f'누락된 패키지: {", ".join(missing_packages)}',
                'fix': 'auto',  # 자동 수정 가능
                'packages': missing_packages
            })
            return False, missing_packages
        else:
            self.print_check("패키지 설치 확인", 'ok', f"{len(requirements)}개 패키지 정상")
            return True, []

    def is_package_installed(self, package_name) -> bool:
        """패키지 설치 여부 확인"""
        try:
            # 특수 케이스 처리
            if package_name.lower() == 'pydantic':
                import pydantic
                return True
            elif package_name.lower() == 'fastapi':
                import fastapi
                return True
            elif package_name.lower() == 'uvicorn':
                import uvicorn
                return True

            # 일반 패키지 확인
            spec = importlib.util.find_spec(package_name.replace('-', '_'))
            return spec is not None
        except:
            return False

    def check_node_npm(self) -> bool:
        """Node.js 및 npm 설치 확인"""
        try:
            # Node.js 확인
            node_result = subprocess.run(
                ['node', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )

            # npm 확인
            npm_result = subprocess.run(
                ['npm', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if node_result.returncode == 0 and npm_result.returncode == 0:
                node_version = node_result.stdout.strip()
                npm_version = npm_result.stdout.strip()
                self.print_check(
                    "Node.js & npm",
                    'ok',
                    f"Node {node_version}, npm {npm_version}"
                )
                return True
            else:
                raise Exception("Node.js 또는 npm이 설치되어 있지 않습니다.")

        except Exception as e:
            self.print_check("Node.js & npm", 'fail', str(e))
            self.issues.append({
                'type': 'node_npm_missing',
                'message': 'Node.js와 npm이 필요합니다.',
                'fix': 'https://nodejs.org/ 에서 Node.js를 설치하세요.'
            })
            return False

    def check_database(self) -> bool:
        """데이터베이스 파일 확인"""
        db_paths = [
            self.backend_dir / "database.db",
            self.backend_dir / "app.db",
            self.backend_dir / "data" / "database.db",
        ]

        db_found = False
        for db_path in db_paths:
            if db_path.exists():
                size = db_path.stat().st_size
                self.print_check(
                    f"데이터베이스: {db_path.name}",
                    'ok',
                    f"크기: {size:,} bytes"
                )
                db_found = True
                break

        if not db_found:
            self.print_check(
                "데이터베이스",
                'warning',
                "데이터베이스 파일이 없습니다. 초기화가 필요합니다."
            )
            self.warnings.append({
                'type': 'db_missing',
                'message': '데이터베이스 파일이 없습니다.',
                'fix': 'auto'  # 자동 수정 가능
            })

        return True  # 데이터베이스는 나중에 생성 가능하므로 True 반환

    def check_env_file(self) -> bool:
        """환경 변수 파일 확인"""
        env_file = self.backend_dir / ".env"
        env_example = self.backend_dir / ".env.example"

        if env_file.exists():
            self.print_check(".env 파일", 'ok', "환경 설정 파일 존재")
            return True
        elif env_example.exists():
            self.print_check(".env 파일", 'warning', ".env.example에서 생성 필요")
            self.warnings.append({
                'type': 'env_missing',
                'message': '.env 파일이 없습니다.',
                'fix': 'auto'  # 자동 수정 가능
            })
            return True
        else:
            self.print_check(".env 파일", 'warning', "환경 설정 파일 없음")
            return True

    def check_ports(self) -> bool:
        """포트 사용 가능 여부 확인"""
        ports_to_check = {
            8010: 'Backend API',
            3000: 'Frontend'
        }

        all_available = True
        for port, service in ports_to_check.items():
            if self.is_port_in_use(port):
                self.print_check(
                    f"포트 {port} ({service})",
                    'warning',
                    "이미 사용 중입니다."
                )
                self.warnings.append({
                    'type': 'port_in_use',
                    'message': f'포트 {port}이(가) 사용 중입니다.',
                    'fix': f'다른 포트를 사용하거나 프로세스를 종료하세요.'
                })
                all_available = False
            else:
                self.print_check(f"포트 {port} ({service})", 'ok', "사용 가능")

        return all_available

    def is_port_in_use(self, port) -> bool:
        """특정 포트가 사용 중인지 확인"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0

    def check_disk_space(self) -> bool:
        """디스크 공간 확인 (최소 1GB 필요)"""
        try:
            usage = psutil.disk_usage(self.project_root)
            free_gb = usage.free / (1024 ** 3)

            if free_gb < 1:
                self.print_check(
                    "디스크 공간",
                    'fail',
                    f"여유 공간: {free_gb:.2f}GB (최소 1GB 필요)"
                )
                self.issues.append({
                    'type': 'disk_space',
                    'message': f'디스크 여유 공간 부족: {free_gb:.2f}GB',
                    'fix': '불필요한 파일을 삭제하여 공간을 확보하세요.'
                })
                return False
            else:
                self.print_check(
                    "디스크 공간",
                    'ok',
                    f"여유 공간: {free_gb:.2f}GB"
                )
                return True
        except:
            return True

    def check_memory(self) -> bool:
        """메모리 확인 (최소 2GB 권장)"""
        try:
            mem = psutil.virtual_memory()
            available_gb = mem.available / (1024 ** 3)

            if available_gb < 2:
                self.print_check(
                    "메모리",
                    'warning',
                    f"사용 가능: {available_gb:.2f}GB (2GB 이상 권장)"
                )
                self.warnings.append({
                    'type': 'low_memory',
                    'message': f'메모리 부족: {available_gb:.2f}GB',
                    'fix': '다른 프로그램을 종료하여 메모리를 확보하세요.'
                })
                return True  # 경고만 표시
            else:
                self.print_check(
                    "메모리",
                    'ok',
                    f"사용 가능: {available_gb:.2f}GB"
                )
                return True
        except:
            return True

    def check_file_structure(self) -> bool:
        """필수 파일/폴더 구조 확인"""
        required_items = [
            (self.backend_dir, "폴더", "backend"),
            (self.frontend_dir, "폴더", "frontend"),
            (self.backend_dir / "app", "폴더", "backend/app"),
            (self.backend_dir / "requirements.txt", "파일", "backend/requirements.txt"),
            (self.frontend_dir / "package.json", "파일", "frontend/package.json"),
        ]

        all_exists = True
        for item_path, item_type, item_name in required_items:
            if item_path.exists():
                self.print_check(f"{item_type}: {item_name}", 'ok')
            else:
                self.print_check(f"{item_type}: {item_name}", 'fail', "존재하지 않음")
                self.issues.append({
                    'type': 'missing_file',
                    'message': f'{item_name}이(가) 없습니다.',
                    'fix': '프로젝트 구조를 확인하세요.'
                })
                all_exists = False

        return all_exists

    def auto_fix_packages(self, packages: List[str]) -> bool:
        """누락된 패키지 자동 설치"""
        print(f"\n🔧 자동 수정: {len(packages)}개 패키지 설치 중...")

        requirements_file = self.backend_dir / "requirements.txt"
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '-r', str(requirements_file)],
                capture_output=True,
                text=True,
                timeout=300  # 5분 타임아웃
            )

            if result.returncode == 0:
                print(f"✅ 패키지 설치 완료")
                self.fixes_applied.append("패키지 자동 설치")
                return True
            else:
                print(f"❌ 패키지 설치 실패")
                print(result.stderr)
                return False
        except Exception as e:
            print(f"❌ 패키지 설치 중 오류: {e}")
            return False

    def auto_fix_env_file(self) -> bool:
        """".env 파일 자동 생성"""
        env_file = self.backend_dir / ".env"
        env_example = self.backend_dir / ".env.example"

        print(f"\n🔧 자동 수정: .env 파일 생성 중...")

        if env_example.exists():
            shutil.copy(env_example, env_file)
            print(f"✅ .env 파일 생성 완료 (.env.example에서 복사)")
            self.fixes_applied.append(".env 파일 생성")
            return True
        else:
            # 기본 .env 파일 생성
            default_env = """# Database
DATABASE_URL=sqlite:///./app.db

# Security
SECRET_KEY=your-secret-key-here-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# API Keys (optional)
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# CORS
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Environment
ENVIRONMENT=development
"""
            with open(env_file, 'w', encoding='utf-8') as f:
                f.write(default_env)
            print(f"✅ 기본 .env 파일 생성 완료")
            self.fixes_applied.append(".env 파일 생성 (기본값)")
            return True

    def auto_fix_database(self) -> bool:
        """데이터베이스 초기화"""
        print(f"\n🔧 자동 수정: 데이터베이스 초기화 중...")

        init_db_script = self.backend_dir / "init_db.py"

        if init_db_script.exists():
            try:
                result = subprocess.run(
                    [sys.executable, str(init_db_script)],
                    cwd=str(self.backend_dir),
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                if result.returncode == 0:
                    print(f"✅ 데이터베이스 초기화 완료")
                    self.fixes_applied.append("데이터베이스 초기화")
                    return True
                else:
                    print(f"⚠️  데이터베이스 초기화 스크립트 실행 실패")
                    return False
            except Exception as e:
                print(f"⚠️  데이터베이스 초기화 중 오류: {e}")
                return False
        else:
            print(f"ℹ️  초기화 스크립트가 없습니다. 서버 시작 시 자동 생성됩니다.")
            return True

    def apply_auto_fixes(self):
        """자동 수정 가능한 항목 처리"""
        self.print_header("🔧 자동 수정 시도")

        fixed_count = 0

        for issue in self.issues[:]:
            if issue.get('fix') == 'auto':
                if issue['type'] == 'missing_packages':
                    if self.auto_fix_packages(issue['packages']):
                        self.issues.remove(issue)
                        fixed_count += 1

        for warning in self.warnings[:]:
            if warning.get('fix') == 'auto':
                if warning['type'] == 'env_missing':
                    if self.auto_fix_env_file():
                        self.warnings.remove(warning)
                        fixed_count += 1
                elif warning['type'] == 'db_missing':
                    if self.auto_fix_database():
                        self.warnings.remove(warning)
                        fixed_count += 1

        if fixed_count > 0:
            print(f"\n✅ {fixed_count}개 항목 자동 수정 완료")
        else:
            print(f"\nℹ️  자동 수정 가능한 항목 없음")

    def generate_report(self) -> Dict:
        """진단 리포트 생성"""
        return {
            'issues': self.issues,
            'warnings': self.warnings,
            'fixes_applied': self.fixes_applied,
            'success': len(self.issues) == 0
        }

    def print_summary(self, report: Dict):
        """결과 요약 출력"""
        self.print_header("📊 진단 결과 요약")

        print(f"\n✅ 적용된 수정: {len(report['fixes_applied'])}개")
        for fix in report['fixes_applied']:
            print(f"   - {fix}")

        print(f"\n⚠️  경고: {len(report['warnings'])}개")
        for warning in report['warnings']:
            print(f"   - {warning['message']}")
            print(f"     해결: {warning['fix']}")

        print(f"\n❌ 오류: {len(report['issues'])}개")
        for issue in report['issues']:
            print(f"   - {issue['message']}")
            print(f"     해결: {issue['fix']}")

        print("\n" + "=" * 60)
        if report['success']:
            print("🎉 모든 체크 통과! 시스템이 정상입니다.")
        elif len(report['issues']) == 0 and len(report['warnings']) > 0:
            print("⚠️  경고가 있지만 시스템 실행 가능합니다.")
        else:
            print("❌ 오류를 수정한 후 다시 시도하세요.")
        print("=" * 60)

    def run_all_checks(self, auto_fix=True) -> Dict:
        """모든 체크 실행"""
        self.print_header("🛡️ 시스템 자가 진단")

        print(f"\n📁 프로젝트 경로: {self.project_root}")
        print(f"🖥️  운영 체제: {platform.system()} {platform.release()}")
        print(f"🐍 Python: {sys.version.split()[0]}")

        self.print_header("1️⃣  필수 요구사항 확인")
        self.check_python_version()
        self.check_pip()
        self.check_node_npm()
        self.check_file_structure()

        self.print_header("2️⃣  패키지 및 설정 확인")
        self.check_packages()
        self.check_env_file()
        self.check_database()

        self.print_header("3️⃣  시스템 리소스 확인")
        self.check_ports()
        self.check_disk_space()
        self.check_memory()

        # 자동 수정 시도
        if auto_fix:
            self.apply_auto_fixes()

        # 리포트 생성 및 출력
        report = self.generate_report()
        self.print_summary(report)

        return report


def main():
    """메인 함수"""
    import argparse

    parser = argparse.ArgumentParser(description='시스템 자가 진단 도구')
    parser.add_argument(
        '--no-auto-fix',
        action='store_true',
        help='자동 수정 비활성화'
    )
    parser.add_argument(
        '--project-root',
        type=str,
        help='프로젝트 루트 디렉토리 경로'
    )

    args = parser.parse_args()

    checker = HealthCheck(args.project_root)
    report = checker.run_all_checks(auto_fix=not args.no_auto_fix)

    # 종료 코드 설정
    sys.exit(0 if report['success'] or (not report['issues']) else 1)


if __name__ == '__main__':
    main()
