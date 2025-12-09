import shutil
import os
from pathlib import Path

source = r"C:\Users\u\doctor-voice-pro"
destination = r"C:\Users\u\DoctorVoicePro-v2.0.0-20251030"

# 제외할 디렉토리 및 파일
exclude_dirs = {
    '__pycache__',
    '.pytest_cache',
    'node_modules',
    '.next',
    'venv',
    'env',
    '.git',
    '.vscode',
    'dist',
    'build'
}

exclude_files = {
    '.pyc',
    '.pyo',
    '.pyd',
    'copy_project.py'
}

print(f"복사 시작: {source} -> {destination}")

# 대상 디렉토리 생성
os.makedirs(destination, exist_ok=True)

copied_count = 0
skipped_count = 0

# 파일 복사
for root, dirs, files in os.walk(source):
    # 제외할 디렉토리 필터링
    dirs[:] = [d for d in dirs if d not in exclude_dirs]

    # 상대 경로 계산
    rel_path = os.path.relpath(root, source)
    dest_dir = os.path.join(destination, rel_path)

    # 대상 디렉토리 생성
    os.makedirs(dest_dir, exist_ok=True)

    # 파일 복사
    for file in files:
        # 제외할 파일 확장자 체크
        if any(file.endswith(ext) for ext in exclude_files):
            skipped_count += 1
            continue

        if file in exclude_files:
            skipped_count += 1
            continue

        src_file = os.path.join(root, file)
        dest_file = os.path.join(dest_dir, file)

        try:
            shutil.copy2(src_file, dest_file)
            copied_count += 1
            if copied_count % 100 == 0:
                print(f"복사 중... {copied_count}개 파일 완료")
        except Exception as e:
            print(f"오류 발생 ({file}): {e}")
            skipped_count += 1

print(f"\n복사 완료!")
print(f"- 복사된 파일: {copied_count}개")
print(f"- 건너뛴 파일: {skipped_count}개")
print(f"- 대상 폴더: {destination}")
