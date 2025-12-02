"""
Doctor Voice Pro - 포터블 패키지 생성
다른 폴더에 실행 가능한 버전 생성
"""

import os
import sys
import shutil
import zipfile
from pathlib import Path
from datetime import datetime

# UTF-8 인코딩 설정
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

PROJECT_ROOT = Path(__file__).parent

# 제외할 파일/폴더
EXCLUDE_PATTERNS = [
    '__pycache__',
    '*.pyc',
    '*.pyo',
    '.pytest_cache',
    '.git',
    '.gitignore',
    'node_modules',
    '.next',
    'venv',
    '*.log',
    '.env.local.backup',
    'doctorvoice.db',
    'doctorvoice.db-journal',
    '*.backup',
    '.DS_Store',
    'Thumbs.db',
]

# 포함할 파일/폴더
INCLUDE_PATTERNS = [
    'backend/**/*.py',
    'backend/requirements.txt',
    'backend/.env',
    'frontend/src/**/*',
    'frontend/public/**/*',
    'frontend/package.json',
    'frontend/package-lock.json',
    'frontend/tsconfig.json',
    'frontend/tailwind.config.ts',
    'frontend/postcss.config.js',
    'frontend/next.config.js',
    'frontend/.env.local',
    '*.bat',
    '*.py',
    '*.txt',
]


def print_header(title: str):
    """헤더 출력"""
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)
    print()


def should_exclude(path: Path) -> bool:
    """제외할 파일/폴더인지 확인"""
    path_str = str(path)

    for pattern in EXCLUDE_PATTERNS:
        if pattern.startswith('*'):
            # 확장자 체크
            if path_str.endswith(pattern[1:]):
                return True
        else:
            # 폴더명 또는 파일명 체크
            if pattern in path_str:
                return True

    return False


def copy_directory(src: Path, dst: Path):
    """디렉토리 복사 (제외 패턴 적용)"""
    if not src.exists():
        return

    for item in src.rglob('*'):
        if should_exclude(item):
            continue

        # 상대 경로 계산
        rel_path = item.relative_to(src)
        dst_path = dst / rel_path

        if item.is_dir():
            dst_path.mkdir(parents=True, exist_ok=True)
        else:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(item, dst_path)
                print(f"  복사: {rel_path}")
            except Exception as e:
                print(f"  오류: {rel_path} - {e}")


def create_package(output_dir: Path):
    """포터블 패키지 생성"""
    print_header("Doctor Voice Pro - 포터블 패키지 생성")

    # 출력 디렉토리 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    package_name = f"DoctorVoicePro_{timestamp}"
    package_dir = output_dir / package_name

    print(f"패키지 디렉토리: {package_dir}")
    print()

    if package_dir.exists():
        print("기존 디렉토리 삭제 중...")
        shutil.rmtree(package_dir)

    package_dir.mkdir(parents=True, exist_ok=True)

    # 1. 백엔드 복사
    print("\n[1/4] 백엔드 복사 중...")
    backend_src = PROJECT_ROOT / 'backend'
    backend_dst = package_dir / 'backend'

    if backend_src.exists():
        backend_dst.mkdir(parents=True, exist_ok=True)

        # 백엔드 파일들 복사
        for item in backend_src.rglob('*'):
            if should_exclude(item):
                continue

            # .py, .txt, .env 파일만 복사
            if item.is_file() and (
                item.suffix in ['.py', '.txt', '.env', '.md'] or
                item.name in ['requirements.txt', '.env']
            ):
                rel_path = item.relative_to(backend_src)
                dst_path = backend_dst / rel_path
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dst_path)
                print(f"  ✓ {rel_path}")

    # 2. 프론트엔드 복사
    print("\n[2/4] 프론트엔드 복사 중...")
    frontend_src = PROJECT_ROOT / 'frontend'
    frontend_dst = package_dir / 'frontend'

    if frontend_src.exists():
        frontend_dst.mkdir(parents=True, exist_ok=True)

        # src 폴더
        src_dir = frontend_src / 'src'
        if src_dir.exists():
            dst_src = frontend_dst / 'src'
            dst_src.mkdir(parents=True, exist_ok=True)
            for item in src_dir.rglob('*'):
                if should_exclude(item) or item.is_dir():
                    continue
                rel_path = item.relative_to(src_dir)
                dst_path = dst_src / rel_path
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dst_path)
                print(f"  ✓ src/{rel_path}")

        # public 폴더
        public_dir = frontend_src / 'public'
        if public_dir.exists():
            dst_public = frontend_dst / 'public'
            dst_public.mkdir(parents=True, exist_ok=True)
            for item in public_dir.rglob('*'):
                if should_exclude(item) or item.is_dir():
                    continue
                rel_path = item.relative_to(public_dir)
                dst_path = dst_public / rel_path
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dst_path)
                print(f"  ✓ public/{rel_path}")

        # 설정 파일들
        config_files = [
            'package.json',
            'package-lock.json',
            'tsconfig.json',
            'tailwind.config.ts',
            'postcss.config.js',
            'next.config.js',
            '.env.local',
        ]

        for filename in config_files:
            src_file = frontend_src / filename
            if src_file.exists():
                shutil.copy2(src_file, frontend_dst / filename)
                print(f"  ✓ {filename}")

    # 3. 실행 파일 및 스크립트 복사
    print("\n[3/4] 실행 파일 복사 중...")
    script_files = [
        '최종실행파일.bat',
        '최종실행파일1.bat',
        '최종실행파일2.bat',
        '최종실행파일3.bat',
        '최종실행파일4.bat',
        '최종실행파일5.bat',
        '자동설치.bat',
        '자동설치2.bat',
        '포트정리.bat',
        '인증복원.bat',
        'auto_connect_and_start.py',
        'auto_retry_start.py',
        'smart_start.py',
        'turbo_start.py',
        'universal_start.py',
        'universal_start_no_auth.py',
        'setup_no_auth.py',
    ]

    for filename in script_files:
        src_file = PROJECT_ROOT / filename
        if src_file.exists():
            shutil.copy2(src_file, package_dir / filename)
            print(f"  ✓ {filename}")

    # 4. 문서 파일 복사
    print("\n[4/4] 문서 파일 복사 중...")
    doc_files = [
        '사용방법.txt',
        '최종실행파일1_사용법.txt',
        '최종실행파일2_사용법.txt',
        '최종실행파일3_사용법.txt',
        '최종실행파일4_사용법.txt',
        '최종실행파일5_사용법.txt',
        '자동설치2_사용법.txt',
        '새컴퓨터_설치가이드.txt',
    ]

    for filename in doc_files:
        src_file = PROJECT_ROOT / filename
        if src_file.exists():
            shutil.copy2(src_file, package_dir / filename)
            print(f"  ✓ {filename}")

    # README 생성
    readme_content = f"""
======================================================================
  Doctor Voice Pro - 포터블 패키지
  생성일시: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
======================================================================

## 빠른 시작

1. 자동설치2.bat 실행 (관리자 권한)
   - Python, Node.js, 패키지 자동 설치

2. 최종실행파일5.bat 실행 (로그인 없이 사용)
   또는
   최종실행파일4.bat 실행 (로그인 기능 포함)

3. 브라우저가 자동으로 열립니다!

======================================================================

## 실행 파일 설명

로그인 없이 사용:
  최종실행파일5.bat - 바로 글작성 페이지로 이동 (추천!)

로그인 기능 포함:
  최종실행파일4.bat - Universal (다른 컴퓨터 지원)
  최종실행파일3.bat - TURBO (가장 빠름)
  최종실행파일2.bat - 상세 로그
  최종실행파일1.bat - 자동 재시도

설치:
  자동설치2.bat - 필수 프로그램 자동 설치 (관리자 권한)

유틸리티:
  포트정리.bat - 실행 중인 서버 종료
  인증복원.bat - 로그인 기능 다시 활성화

======================================================================

## 시스템 요구사항

- Windows 10 이상
- Python 3.8+ (자동 설치됨)
- Node.js 18+ (자동 설치됨)
- 4GB RAM
- 5GB 여유 공간

======================================================================

## 문제 해결

포트 충돌:
  포트정리.bat 실행

설치 오류:
  자동설치2.bat을 관리자 권한으로 실행

실행 안됨:
  1. 포트정리.bat
  2. 최종실행파일5.bat 다시 실행

로그인 문제:
  인증복원.bat 실행

======================================================================

## 상세 가이드

각 실행 파일의 상세 사용법:
  - 최종실행파일5_사용법.txt (로그인 없이)
  - 최종실행파일4_사용법.txt (Universal)
  - 최종실행파일3_사용법.txt (TURBO)
  - 최종실행파일2_사용법.txt (상세 로그)
  - 최종실행파일1_사용법.txt (자동 재시도)
  - 자동설치2_사용법.txt (설치 가이드)
  - 새컴퓨터_설치가이드.txt (새 컴퓨터 설치)

======================================================================

## 지원

문제가 있으면 사용법.txt 파일들을 참고하세요.

======================================================================
"""

    readme_file = package_dir / 'README.txt'
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print("  ✓ README.txt")

    # 완료
    print_header("패키지 생성 완료!")
    print(f"  위치: {package_dir}")
    print(f"\n  다음 단계:")
    print(f"  1. {package_dir} 폴더를 원하는 위치로 복사")
    print(f"  2. 자동설치2.bat 실행 (관리자 권한)")
    print(f"  3. 최종실행파일5.bat 실행 (로그인 없이)")
    print()

    # ZIP 파일 생성 옵션
    print("ZIP 파일로 압축하시겠습니까? (Y/N)")
    choice = input("선택: ").strip().upper()

    if choice == 'Y':
        print("\nZIP 파일 생성 중...")
        zip_file = output_dir / f"{package_name}.zip"

        with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in package_dir.rglob('*'):
                if file.is_file():
                    arcname = file.relative_to(output_dir)
                    zipf.write(file, arcname)
                    print(f"  압축: {arcname}")

        print(f"\n✓ ZIP 파일 생성 완료: {zip_file}")
        print(f"  크기: {zip_file.stat().st_size / 1024 / 1024:.2f} MB")


def main():
    """메인 함수"""
    print_header("Doctor Voice Pro - 포터블 패키지 생성")
    print("다른 컴퓨터에서 사용할 수 있는 패키지를 생성합니다.")
    print()

    # 출력 디렉토리 선택
    print("패키지를 생성할 위치를 선택하세요:")
    print()
    print("1. 바탕화면 (추천)")
    print("2. 다운로드 폴더")
    print("3. 직접 입력")
    print()

    choice = input("선택 (1-3): ").strip()

    if choice == '1':
        output_dir = Path.home() / 'Desktop'
    elif choice == '2':
        output_dir = Path.home() / 'Downloads'
    elif choice == '3':
        custom_path = input("경로 입력: ").strip()
        output_dir = Path(custom_path)
    else:
        print("잘못된 선택입니다. 바탕화면을 사용합니다.")
        output_dir = Path.home() / 'Desktop'

    if not output_dir.exists():
        print(f"\n오류: 경로가 존재하지 않습니다: {output_dir}")
        return

    print(f"\n출력 위치: {output_dir}")
    print()
    input("계속하려면 Enter를 누르세요...")

    # 패키지 생성
    create_package(output_dir)


if __name__ == '__main__':
    main()
