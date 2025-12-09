"""
릴리스 폴더 복사 스크립트
"""
import shutil
import os
from pathlib import Path

# 현재 스크립트가 있는 디렉토리를 소스로 사용
source_dir = Path(__file__).parent
target_dir = source_dir.parent / "DoctorVoicePro-v1.1.2-20251030"

# 제외할 파일 및 폴더
exclude_dirs = {
    '__pycache__', '.pytest_cache', 'node_modules', '.git',
    'venv', '.next', '.venv', 'dist', 'build'
}
exclude_files = {
    '*.pyc', '*.log', 'doctorvoice.db', '*.db-journal'
}

def should_exclude(path: Path) -> bool:
    """제외할 경로인지 확인"""
    # 폴더 이름 체크
    for part in path.parts:
        if part in exclude_dirs:
            return True

    # 파일 확장자 체크
    if path.is_file():
        if path.suffix == '.pyc' or path.suffix == '.log':
            return True
        if 'doctorvoice.db' in path.name:
            return True

    return False

def copy_directory(src: Path, dst: Path):
    """디렉토리 복사 (제외 규칙 적용)"""
    print(f"복사 중: {src} -> {dst}")

    if not dst.exists():
        dst.mkdir(parents=True)

    for item in src.iterdir():
        src_path = src / item.name
        dst_path = dst / item.name

        # 제외 규칙 확인
        if should_exclude(src_path):
            print(f"  [제외] {src_path.name}")
            continue

        if src_path.is_dir():
            copy_directory(src_path, dst_path)
        else:
            print(f"  [복사] {src_path.name}")
            shutil.copy2(src_path, dst_path)

# 백엔드 복사
print("\n" + "="*70)
print("백엔드 파일 복사 시작")
print("="*70)
backend_src = source_dir / "backend"
backend_dst = target_dir / "backend"
if backend_src.exists():
    copy_directory(backend_src, backend_dst)
    print("\n백엔드 복사 완료!")
else:
    print("백엔드 폴더를 찾을 수 없습니다.")

# 프론트엔드 복사
print("\n" + "="*70)
print("프론트엔드 파일 복사 시작")
print("="*70)
frontend_src = source_dir / "frontend"
frontend_dst = target_dir / "frontend"
if frontend_src.exists():
    copy_directory(frontend_src, frontend_dst)
    print("\n프론트엔드 복사 완료!")
else:
    print("프론트엔드 폴더를 찾을 수 없습니다.")

print("\n" + "="*70)
print("모든 파일 복사 완료!")
print("="*70)
print(f"\n릴리스 폴더: {target_dir}")
