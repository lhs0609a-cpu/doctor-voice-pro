"""
v1.3.0 Final Working 릴리스 폴더 복사 스크립트
"""
import shutil
from pathlib import Path

# 현재 스크립트가 있는 디렉토리를 소스로 사용
source_dir = Path(__file__).parent
target_dir = source_dir.parent / "DoctorVoicePro-v1.3.0-20251030-Final"

exclude_dirs = {'__pycache__', '.pytest_cache', 'node_modules', '.git', 'venv', '.next', '.venv', 'dist', 'build'}

def should_exclude(path: Path) -> bool:
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
            shutil.copy2(src_path, dst_path)

print("\n" + "="*70)
print("DoctorVoicePro v1.3.0 Final Working - 릴리스 폴더 생성")
print("="*70)

print("\n백엔드 파일 복사 중...")
copy_directory(source_dir / "backend", target_dir / "backend")

print("\n프론트엔드 파일 복사 중...")
copy_directory(source_dir / "frontend", target_dir / "frontend")

print("\n실행 파일 복사 중...")
shutil.copy2(source_dir / "실행.bat", target_dir / "실행.bat")
shutil.copy2(source_dir / "종료.bat", target_dir / "종료.bat")

print("\n완료!")
print(f"릴리스 폴더: {target_dir}")
