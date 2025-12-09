#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
자동 배포 스크립트
프로젝트를 새 버전으로 복사하고 버전 번호를 자동으로 증가시킵니다.
"""

import os
import sys
import shutil
import argparse
from datetime import datetime
from pathlib import Path


class AutoDeploy:
    """자동 배포 관리 클래스"""

    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.version_file = self.project_root / "version.txt"
        self.changelog_file = self.project_root / "CHANGELOG.md"

    def read_version(self):
        """현재 버전 읽기"""
        if not self.version_file.exists():
            return "1.0.0"

        with open(self.version_file, 'r', encoding='utf-8') as f:
            return f.read().strip()

    def write_version(self, version):
        """버전 파일 쓰기"""
        with open(self.version_file, 'w', encoding='utf-8') as f:
            f.write(version)

    def parse_version(self, version_str):
        """버전 문자열을 숫자 튜플로 변환"""
        try:
            parts = version_str.split('.')
            return tuple(map(int, parts))
        except:
            return (1, 0, 0)

    def increment_version(self, current_version, bump_type='patch'):
        """
        버전 증가
        bump_type: 'major' (1.0.0 -> 2.0.0)
                  'minor' (1.0.0 -> 1.1.0)
                  'patch' (1.0.0 -> 1.0.1)
        """
        major, minor, patch = self.parse_version(current_version)

        if bump_type == 'major':
            return f"{major + 1}.0.0"
        elif bump_type == 'minor':
            return f"{major}.{minor + 1}.0"
        else:  # patch
            return f"{major}.{minor}.{patch + 1}"

    def update_changelog(self, new_version, changes):
        """CHANGELOG.md 업데이트"""
        today = datetime.now().strftime("%Y-%m-%d")

        # 새 변경사항 엔트리
        new_entry = f"\n## [{new_version}] - {today}\n\n"

        if changes:
            new_entry += "### 변경사항\n"
            for change in changes:
                new_entry += f"- {change}\n"
        else:
            new_entry += "### 변경사항\n- 버그 수정 및 성능 개선\n"

        new_entry += "\n---\n"

        # CHANGELOG 읽기
        if self.changelog_file.exists():
            with open(self.changelog_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 첫 번째 ## 이후에 삽입
            parts = content.split('\n## [', 1)
            if len(parts) == 2:
                updated_content = parts[0] + new_entry + "\n## [" + parts[1]
            else:
                updated_content = content + new_entry
        else:
            updated_content = "# 변경 이력 (Changelog)\n" + new_entry

        # CHANGELOG 쓰기
        with open(self.changelog_file, 'w', encoding='utf-8') as f:
            f.write(updated_content)

    def get_deploy_path(self, version):
        """배포 폴더 경로 생성"""
        project_name = self.project_root.name
        parent_dir = self.project_root.parent
        return parent_dir / f"{project_name}_v{version}"

    def copy_project(self, dest_path):
        """
        프로젝트를 새 폴더에 복사
        제외 항목: node_modules, __pycache__, .env, *.pyc, logs, data
        """
        print(f"📦 프로젝트 복사 중: {dest_path}")

        # 제외할 항목들
        exclude_patterns = {
            'node_modules',
            '__pycache__',
            '.next',
            '.git',
            '*.pyc',
            '*.pyo',
            '*.log',
            '.env',
            'venv',
            'env',
            '.venv',
            'logs',
            'data',
            'error_reports',
            'backups',
            '*.db',
            '*.sqlite',
            '*.sqlite3',
        }

        def should_ignore(directory, files):
            """무시할 파일/폴더 결정"""
            ignored = []
            for f in files:
                # 패턴 매칭
                for pattern in exclude_patterns:
                    if pattern.startswith('*'):
                        if f.endswith(pattern[1:]):
                            ignored.append(f)
                            break
                    elif f == pattern or f.startswith(pattern):
                        ignored.append(f)
                        break
            return ignored

        try:
            if dest_path.exists():
                print(f"⚠️  경고: {dest_path} 폴더가 이미 존재합니다.")
                response = input("덮어쓰시겠습니까? (y/N): ").strip().lower()
                if response != 'y':
                    print("❌ 배포 취소")
                    return False
                shutil.rmtree(dest_path)

            shutil.copytree(
                self.project_root,
                dest_path,
                ignore=should_ignore,
                dirs_exist_ok=False
            )

            print(f"✅ 복사 완료: {dest_path}")
            return True

        except Exception as e:
            print(f"❌ 복사 실패: {e}")
            return False

    def create_directories(self, dest_path):
        """필요한 빈 디렉토리 생성"""
        dirs_to_create = [
            'logs',
            'data',
            'error_reports',
            'backups',
        ]

        for dir_name in dirs_to_create:
            dir_path = dest_path / dir_name
            dir_path.mkdir(exist_ok=True)

            # .gitkeep 파일 생성 (폴더 유지용)
            gitkeep = dir_path / '.gitkeep'
            gitkeep.touch()

    def deploy(self, bump_type='patch', changes=None):
        """전체 배포 프로세스"""
        print("=" * 60)
        print("🚀 자동 배포 시스템")
        print("=" * 60)

        # 1. 현재 버전 읽기
        current_version = self.read_version()
        print(f"📌 현재 버전: {current_version}")

        # 2. 새 버전 계산
        new_version = self.increment_version(current_version, bump_type)
        print(f"📌 새 버전: {new_version}")

        # 3. 배포 경로 결정
        deploy_path = self.get_deploy_path(new_version)
        print(f"📌 배포 경로: {deploy_path}")

        # 4. 사용자 확인
        print("\n계속하시겠습니까?")
        response = input("Enter를 누르면 계속, 'n'을 입력하면 취소: ").strip().lower()
        if response == 'n':
            print("❌ 배포 취소")
            return False

        # 5. 프로젝트 복사
        if not self.copy_project(deploy_path):
            return False

        # 6. 필요한 디렉토리 생성
        self.create_directories(deploy_path)

        # 7. 버전 파일 업데이트
        version_file_dest = deploy_path / "version.txt"
        with open(version_file_dest, 'w', encoding='utf-8') as f:
            f.write(new_version)
        print(f"✅ 버전 파일 업데이트: {new_version}")

        # 8. CHANGELOG 업데이트
        changelog_dest = deploy_path / "CHANGELOG.md"
        self.changelog_file = changelog_dest
        self.update_changelog(new_version, changes)
        print(f"✅ CHANGELOG 업데이트")

        # 9. 원본 프로젝트 버전도 업데이트
        self.write_version(new_version)

        # 10. 완료 메시지
        print("\n" + "=" * 60)
        print("🎉 배포 완료!")
        print("=" * 60)
        print(f"📁 배포 위치: {deploy_path}")
        print(f"📌 버전: {new_version}")
        print("\n다음 단계:")
        print(f"1. cd {deploy_path}")
        print("2. install.bat (Windows) 또는 ./install.sh (Linux/Mac) 실행")
        print("=" * 60)

        return True


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description='프로젝트 자동 배포 스크립트',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python auto_deploy.py                    # 패치 버전 증가 (1.0.0 -> 1.0.1)
  python auto_deploy.py --minor            # 마이너 버전 증가 (1.0.0 -> 1.1.0)
  python auto_deploy.py --major            # 메이저 버전 증가 (1.0.0 -> 2.0.0)
  python auto_deploy.py -m "버그 수정"     # 변경사항과 함께 배포
        """
    )

    parser.add_argument(
        '--major',
        action='store_true',
        help='메이저 버전 증가 (1.0.0 -> 2.0.0)'
    )

    parser.add_argument(
        '--minor',
        action='store_true',
        help='마이너 버전 증가 (1.0.0 -> 1.1.0)'
    )

    parser.add_argument(
        '-m', '--message',
        action='append',
        help='변경사항 메시지 (여러 개 가능)'
    )

    args = parser.parse_args()

    # 버전 타입 결정
    if args.major:
        bump_type = 'major'
    elif args.minor:
        bump_type = 'minor'
    else:
        bump_type = 'patch'

    # 현재 스크립트 위치에서 프로젝트 루트 찾기
    script_dir = Path(__file__).parent.absolute()

    # 배포 실행
    deployer = AutoDeploy(script_dir)
    success = deployer.deploy(bump_type, args.message)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
