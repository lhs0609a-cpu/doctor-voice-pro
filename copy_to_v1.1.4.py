"""
v1.1.4 Final 릴리스 폴더 복사 스크립트
"""
import shutil
import os
from pathlib import Path

# 현재 스크립트가 있는 디렉토리를 소스로 사용
source_dir = Path(__file__).parent
target_dir = source_dir.parent / "DoctorVoicePro-v1.1.4-20251030-Final"

# 제외할 파일 및 폴더
exclude_dirs = {
    '__pycache__', '.pytest_cache', 'node_modules', '.git',
    'venv', '.next', '.venv', 'dist', 'build'
}

def should_exclude(path: Path) -> bool:
    """제외할 경로인지 확인"""
    for part in path.parts:
        if part in exclude_dirs:
            return True

    if path.is_file():
        if path.suffix in ['.pyc', '.log']:
            return True
        if 'doctorvoice.db' in path.name:
            return True
        if path.name.startswith('copy_to_'):
            return True

    return False

def copy_directory(src: Path, dst: Path):
    """디렉토리 복사"""
    if not dst.exists():
        dst.mkdir(parents=True)

    for item in src.iterdir():
        src_path = src / item.name
        dst_path = dst / item.name

        if should_exclude(src_path):
            continue

        if src_path.is_dir():
            copy_directory(src_path, dst_path)
        else:
            print(f"  [복사] {src_path.name}")
            shutil.copy2(src_path, dst_path)

print("\n" + "="*70)
print("DoctorVoicePro v1.1.4 Final - 릴리스 폴더 생성")
print("="*70)

# 백엔드 복사
print("\n백엔드 파일 복사 중...")
backend_src = source_dir / "backend"
backend_dst = target_dir / "backend"
if backend_src.exists():
    copy_directory(backend_src, backend_dst)
    print("백엔드 복사 완료!")

# 프론트엔드 복사
print("\n프론트엔드 파일 복사 중...")
frontend_src = source_dir / "frontend"
frontend_dst = target_dir / "frontend"
if frontend_src.exists():
    copy_directory(frontend_src, frontend_dst)
    print("프론트엔드 복사 완료!")

# 배치 파일 복사
print("\n실행 파일 복사 중...")
shutil.copy2(source_dir / "improved_start_backend.bat", target_dir / "start_backend.bat")
shutil.copy2(source_dir / "improved_start_frontend.bat", target_dir / "start_frontend.bat")
shutil.copy2(source_dir / "install_and_start.bat", target_dir / "install_and_start.bat")
print("실행 파일 복사 완료!")

print("\n" + "="*70)
print("완료!")
print("="*70)
print(f"\n릴리스 폴더: {target_dir}")
