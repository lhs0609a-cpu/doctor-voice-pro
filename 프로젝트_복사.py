"""
Doctor Voice Pro - 프로젝트 전체 복사
다른 폴더에 현재 버전 전체를 복사
"""

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime

# UTF-8 인코딩 설정
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

PROJECT_ROOT = Path(__file__).parent

# 제외할 폴더 (복사하지 않음)
EXCLUDE_FOLDERS = [
    '.git',
    '__pycache__',
    '.pytest_cache',
    '.next',  # Next.js 빌드 캐시
]

# 제외할 파일 패턴
EXCLUDE_FILES = [
    '.DS_Store',
    'Thumbs.db',
    '*.log',
    'doctorvoice.db',
    'doctorvoice.db-journal',
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

    # 폴더 체크
    for folder in EXCLUDE_FOLDERS:
        if folder in path.parts:
            return True

    # 파일 패턴 체크
    for pattern in EXCLUDE_FILES:
        if pattern.startswith('*'):
            if path_str.endswith(pattern[1:]):
                return True
        else:
            if path.name == pattern:
                return True

    return False


def copy_project(src_dir: Path, dst_dir: Path):
    """프로젝트 전체 복사"""
    print_header("프로젝트 전체 복사 시작")

    print(f"원본: {src_dir}")
    print(f"대상: {dst_dir}")
    print()

    # 대상 디렉토리 생성
    if dst_dir.exists():
        print("기존 폴더가 존재합니다. 삭제하시겠습니까? (Y/N)")
        choice = input("선택: ").strip().upper()
        if choice == 'Y':
            print("기존 폴더 삭제 중...")
            shutil.rmtree(dst_dir)
            print("✓ 삭제 완료")
        else:
            print("취소되었습니다.")
            return

    dst_dir.mkdir(parents=True, exist_ok=True)

    # 복사할 항목 카운트
    total_items = sum(1 for _ in src_dir.rglob('*') if not should_exclude(_))
    copied_items = 0

    print(f"\n복사할 파일/폴더: 약 {total_items}개")
    print("\n복사 중...\n")

    # 모든 파일/폴더 복사
    for item in src_dir.rglob('*'):
        # 제외 대상 확인
        if should_exclude(item):
            continue

        # 상대 경로
        rel_path = item.relative_to(src_dir)
        dst_path = dst_dir / rel_path

        try:
            if item.is_dir():
                dst_path.mkdir(parents=True, exist_ok=True)
            else:
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dst_path)

                copied_items += 1

                # 진행률 표시
                if copied_items % 50 == 0:
                    progress = int(copied_items / total_items * 100)
                    print(f"  진행률: {progress}% ({copied_items}/{total_items})")

        except Exception as e:
            print(f"  오류: {rel_path} - {e}")

    print(f"\n✓ 복사 완료: {copied_items}개 파일")
    print()


def main():
    """메인 함수"""
    print_header("Doctor Voice Pro - 프로젝트 복사")
    print("현재 프로젝트 전체를 다른 폴더에 복사합니다.")
    print()

    # 대상 위치 선택
    print("복사할 위치를 선택하세요:")
    print()
    print("1. 바탕화면")
    print("2. 다운로드 폴더")
    print("3. C 드라이브")
    print("4. D 드라이브")
    print("5. 직접 입력")
    print()

    choice = input("선택 (1-5): ").strip()

    # 기본 경로 설정
    if choice == '1':
        base_dir = Path.home() / 'Desktop'
    elif choice == '2':
        base_dir = Path.home() / 'Downloads'
    elif choice == '3':
        base_dir = Path('C:/')
    elif choice == '4':
        base_dir = Path('D:/')
    elif choice == '5':
        custom_path = input("경로 입력: ").strip()
        base_dir = Path(custom_path)
    else:
        print("잘못된 선택입니다. 바탕화면을 사용합니다.")
        base_dir = Path.home() / 'Desktop'

    if not base_dir.exists():
        print(f"\n오류: 경로가 존재하지 않습니다: {base_dir}")
        print()
        input("종료하려면 Enter를 누르세요...")
        return

    # 폴더 이름 입력
    print()
    print("새 폴더 이름을 입력하세요:")
    print("(예: doctor-voice-pro-new)")
    print("(Enter만 누르면 자동으로 'doctor-voice-pro-복사본' 생성)")
    print()

    folder_name = input("폴더 이름: ").strip()

    if not folder_name:
        folder_name = "doctor-voice-pro-복사본"

    # 최종 경로
    dst_dir = base_dir / folder_name

    print()
    print(f"최종 경로: {dst_dir}")
    print()
    print("이 위치에 복사하시겠습니까? (Y/N)")

    confirm = input("선택: ").strip().upper()

    if confirm != 'Y':
        print("취소되었습니다.")
        print()
        input("종료하려면 Enter를 누르세요...")
        return

    # 복사 시작
    copy_project(PROJECT_ROOT, dst_dir)

    # 완료
    print_header("복사 완료!")
    print(f"위치: {dst_dir}")
    print()
    print("다음 단계:")
    print(f"  1. {dst_dir} 폴더로 이동")
    print(f"  2. 자동설치2.bat 실행 (필요시)")
    print(f"  3. 최종실행파일5.bat 실행")
    print()
    print("제외된 항목:")
    print("  - .git (버전 관리)")
    print("  - __pycache__ (Python 캐시)")
    print("  - .next (빌드 캐시)")
    print("  - 데이터베이스 파일")
    print()
    print("node_modules와 venv는 포함되어 있습니다.")
    print("(복사 시간이 오래 걸릴 수 있지만, 재설치 불필요)")
    print()

    input("완료! Enter를 눌러 종료하세요...")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n오류 발생: {e}")
        input("\nEnter를 눌러 종료하세요...")
