#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
원클릭 실행 가능한 배포 패키지 생성
"""

import os
import shutil
from pathlib import Path
from datetime import datetime

# 제외할 패턴
EXCLUDE_PATTERNS = {
    'node_modules',
    '__pycache__',
    '.next',
    '.git',
    '.env',
    '.env.local',
    '.venv',
    'venv',
    '.pytest_cache',
    'dist',
    'build',
    '.DS_Store',
    'Thumbs.db',
    '*.pyc',
    '*.pyo',
    '*.pyd',
    '.Python',
    '*.so',
    '*.egg',
    '*.egg-info',
    '.idea',
    '.vscode',
    '*.log',
    'logs',
    'error_reports',
    'backups',
    'data/*.db',
    '*.db',
    'deploy_with_connection.py',
    'quick_copy.py',
    'auto_deploy.py',
    'create_one_click_release.py',  # 이 스크립트 자체 제외
    'DoctorVoicePro-*'  # 이전 배포 폴더들 제외
}

def should_exclude(path: Path, base_path: Path) -> bool:
    """파일/폴더를 제외할지 판단"""
    rel_path = path.relative_to(base_path)
    path_str = str(rel_path)
    name = path.name

    for pattern in EXCLUDE_PATTERNS:
        if pattern in path_str or name == pattern:
            return True
        if pattern.startswith('*.') and name.endswith(pattern[1:]):
            return True
        if '/' in pattern and path_str.startswith(pattern.split('/')[0]):
            return True

    return False

def copy_project(source: Path, dest: Path):
    """프로젝트 파일 복사"""
    print(f"[INFO] 소스: {source}")
    print(f"[INFO] 대상: {dest}")
    print()

    dest.mkdir(parents=True, exist_ok=True)

    copied_files = 0
    skipped_files = 0

    for item in source.rglob('*'):
        if item == dest or dest in item.parents:
            continue

        if should_exclude(item, source):
            skipped_files += 1
            continue

        rel_path = item.relative_to(source)
        dest_path = dest / rel_path

        try:
            if item.is_dir():
                dest_path.mkdir(parents=True, exist_ok=True)
            else:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest_path)
                copied_files += 1

                if copied_files % 100 == 0:
                    print(f"[INFO] 복사 중... {copied_files}개 파일", end='\r')
        except Exception as e:
            print(f"\n[WARN] 복사 실패: {rel_path} - {e}")

    print(f"\n[OK] 총 {copied_files}개 파일 복사 완료")
    print(f"[INFO] {skipped_files}개 항목 제외")

    # 빈 폴더 생성
    empty_dirs = ['logs', 'data', 'error_reports', 'backups']
    for dir_name in empty_dirs:
        (dest / dir_name).mkdir(exist_ok=True)
    print(f"[OK] 빈 폴더 생성: {', '.join(empty_dirs)}")

def main():
    source_dir = Path(__file__).parent.absolute()
    dest_name = f"DoctorVoicePro-OneClick-v2.2.0-{datetime.now().strftime('%Y%m%d')}"
    dest_dir = source_dir.parent / dest_name

    print("=" * 60)
    print("  Doctor Voice Pro 원클릭 배포 패키지 생성")
    print("=" * 60)
    print()

    if dest_dir.exists():
        print(f"[WARN] 대상 폴더가 이미 존재합니다: {dest_dir}")
        print("[INFO] 기존 폴더를 삭제하고 새로 생성합니다...")
        shutil.rmtree(dest_dir)

    # 프로젝트 복사
    copy_project(source_dir, dest_dir)

    # README 파일 이름 변경
    readme_simple = dest_dir / "README_SIMPLE.md"
    if readme_simple.exists():
        shutil.move(str(readme_simple), str(dest_dir / "README.md"))
        print("[OK] README.md 생성")

    print()
    print("=" * 60)
    print("  [SUCCESS] 원클릭 배포 패키지 생성 완료!")
    print("=" * 60)
    print(f"\n폴더 위치: {dest_dir}")
    print()
    print("포함된 내용:")
    print("  - 원클릭 설치 및 실행 스크립트")
    print("  - 연결 관리 시스템")
    print("  - 포트 자동 탐색")
    print("  - 상세한 문제 해결 가이드")
    print()
    print("사용 방법:")
    print(f"  1. {dest_dir} 폴더를 원하는 위치로 복사")
    print("  2. ONE_CLICK_INSTALL_AND_RUN.bat 더블클릭")
    print("  3. 완료!")
    print()

if __name__ == '__main__':
    main()
