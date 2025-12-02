#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
연결 관리 시스템이 포함된 배포 폴더 생성 스크립트
"""

import os
import shutil
from pathlib import Path
from datetime import datetime

# 제외할 파일/폴더 패턴
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
    'deploy_with_connection.py',  # 이 스크립트 자체는 제외
    'quick_copy.py',
    'auto_deploy.py',
    'DoctorVoicePro-*'  # 이전 배포 폴더들 제외
}

def should_exclude(path: Path, base_path: Path) -> bool:
    """파일/폴더를 제외할지 판단"""
    rel_path = path.relative_to(base_path)
    path_str = str(rel_path)
    name = path.name

    # 패턴 매칭
    for pattern in EXCLUDE_PATTERNS:
        if pattern in path_str or name == pattern:
            return True
        if pattern.startswith('*.') and name.endswith(pattern[1:]):
            return True
        if '/' in pattern:
            if path_str.startswith(pattern.split('/')[0]):
                return True

    return False

def copy_project(source: Path, dest: Path):
    """프로젝트 파일 복사"""
    print(f"[INFO] 소스: {source}")
    print(f"[INFO] 대상: {dest}")
    print()

    # 대상 폴더 생성
    dest.mkdir(parents=True, exist_ok=True)

    copied_files = 0
    skipped_files = 0

    # 모든 파일/폴더 순회
    for item in source.rglob('*'):
        if item == dest or dest in item.parents:
            continue

        if should_exclude(item, source):
            skipped_files += 1
            continue

        # 상대 경로 계산
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
            print(f"[WARN] 복사 실패: {rel_path} - {e}")

    print(f"\n[OK] 총 {copied_files}개 파일 복사 완료")
    print(f"[INFO] {skipped_files}개 항목 제외")

    # 빈 폴더 생성
    empty_dirs = ['logs', 'data', 'error_reports', 'backups']
    for dir_name in empty_dirs:
        dir_path = dest / dir_name
        dir_path.mkdir(exist_ok=True)
    print(f"[OK] 빈 폴더 생성: {', '.join(empty_dirs)}")

def main():
    # 경로 설정
    source_dir = Path(__file__).parent.absolute()
    dest_name = f"DoctorVoicePro-v2.1.0-{datetime.now().strftime('%Y%m%d')}"
    dest_dir = source_dir.parent / dest_name

    print("=" * 60)
    print("  Doctor Voice Pro 배포 폴더 생성 (연결 관리 포함)")
    print("=" * 60)
    print()

    # 기존 폴더가 있으면 확인
    if dest_dir.exists():
        print(f"[WARN] 대상 폴더가 이미 존재합니다: {dest_dir}")
        print("[INFO] 기존 폴더를 삭제하고 새로 생성합니다...")
        shutil.rmtree(dest_dir)

    # 프로젝트 복사
    copy_project(source_dir, dest_dir)

    # 완료 메시지
    print()
    print("=" * 60)
    print("  [SUCCESS] 배포 폴더 생성 완료!")
    print("=" * 60)
    print(f"\n폴더 위치: {dest_dir}")
    print()
    print("포함된 기능:")
    print("  - 포트 자동 탐색 및 충돌 해결")
    print("  - 백엔드 연결 자동 모니터링")
    print("  - 재연결 시스템 (3초 간격, 최대 100회)")
    print("  - 실시간 연결 상태 표시")
    print()
    print("실행 방법:")
    print(f"  cd {dest_dir}")
    print("  run_connected.bat  (Windows)")
    print("  ./run_connected.sh (Linux/Mac)")
    print()

if __name__ == '__main__':
    main()
