import shutil
import os
from pathlib import Path

src = Path(r'C:\Users\u\doctor-voice-pro')
dst = Path(r'C:\Users\u\doctor-voice-pro-new')

print(f"복사 시작...")
print(f"원본: {src}")
print(f"대상: {dst}")

# 대상 폴더가 이미 있으면 삭제
if dst.exists():
    print("기존 폴더 삭제 중...")
    shutil.rmtree(dst)

# 제외할 파일/폴더
def ignore_patterns(dir, files):
    ignore_list = []
    for name in files:
        # nul 파일과 임시 파일 제외
        if name in ['nul', 'temp_copy.py']:
            ignore_list.append(name)
    return ignore_list

print("프로젝트 복사 중... (시간이 걸릴 수 있습니다)")
shutil.copytree(src, dst, ignore=ignore_patterns)

print(f"\n✓ 복사 완료!")
print(f"위치: {dst}")
