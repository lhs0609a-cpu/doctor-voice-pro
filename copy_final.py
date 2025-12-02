"""
v1.3.0 Final 복사 스크립트
"""
import shutil
import os
from pathlib import Path

source_dir = Path(r"C:\Users\u\doctor-voice-pro")
target_dir = Path(r"C:\Users\u\DoctorVoicePro-v1.3.0-20251030-Final")

exclude_dirs = {'__pycache__', '.pytest_cache', 'node_modules', '.git', 'venv', '.next', '.venv', 'dist', 'build'}

def should_exclude(path: Path) -> bool:
    # 폴더 이름 체크
    for part in path.parts:
        if part in exclude_dirs:
            return True

    # 파일 체크
    if path.is_file():
        if path.suffix in ['.pyc', '.log']:
            return True
        if 'doctorvoice.db' in path.name:
            return True
        if path.name.startswith('copy_'):
            return True

    return False

def copy_directory(src: Path, dst: Path):
    print(f"복사 중: {src.name}")

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
            try:
                shutil.copy2(src_path, dst_path)
            except Exception as e:
                print(f"  오류: {src_path.name} - {e}")

print("\n" + "="*70)
print("DoctorVoicePro v1.3.0 Final - 릴리스 폴더 생성")
print("="*70)

# 백엔드 복사
backend_src = source_dir / "backend"
backend_dst = target_dir / "backend"
print(f"\n백엔드 폴더 복사: {backend_src} -> {backend_dst}")
if backend_src.exists():
    copy_directory(backend_src, backend_dst)
    print(f"백엔드 복사 완료! 파일 수: {len(list(backend_dst.rglob('*')))}")
else:
    print("오류: 백엔드 폴더를 찾을 수 없습니다!")

# 프론트엔드 복사
frontend_src = source_dir / "frontend"
frontend_dst = target_dir / "frontend"
print(f"\n프론트엔드 폴더 복사: {frontend_src} -> {frontend_dst}")
if frontend_src.exists():
    copy_directory(frontend_src, frontend_dst)
    print(f"프론트엔드 복사 완료! 파일 수: {len(list(frontend_dst.rglob('*')))}")
else:
    print("오류: 프론트엔드 폴더를 찾을 수 없습니다!")

print("\n" + "="*70)
print("완료!")
print("="*70)
print(f"\n릴리스 폴더: {target_dir}")

# 폴더 구조 확인
print("\n생성된 폴더 구조:")
for item in target_dir.iterdir():
    if item.is_dir():
        file_count = len(list(item.rglob('*')))
        print(f"  [폴더] {item.name} ({file_count} 파일)")
    else:
        print(f"  [파일] {item.name}")
