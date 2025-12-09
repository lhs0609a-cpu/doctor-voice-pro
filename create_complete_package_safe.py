import os
import shutil
from pathlib import Path

# Windows device names to exclude
WINDOWS_DEVICES = {
    'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4',
    'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2',
    'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
}

def is_windows_device(path):
    """Check if a path is a Windows device name"""
    name = os.path.basename(path).upper()
    # Remove extension if present
    name_without_ext = name.split('.')[0]
    return name_without_ext in WINDOWS_DEVICES

def safe_copytree(src, dst, ignore_patterns=None):
    """
    Safely copy directory tree, excluding Windows device files
    """
    if ignore_patterns is None:
        ignore_patterns = []

    # Add common patterns to ignore
    ignore_patterns.extend([
        'node_modules',
        '.next',
        '__pycache__',
        '*.pyc',
        '.git',
        'venv',
        '.env',
        'dist',
        'build',
        '.cache'
    ])

    def ignore_function(directory, contents):
        ignored = []
        for item in contents:
            item_path = os.path.join(directory, item)

            # Check if it's a Windows device
            if is_windows_device(item):
                print(f"  [!] Skipping Windows device: {item}")
                ignored.append(item)
                continue

            # Check against ignore patterns
            for pattern in ignore_patterns:
                if pattern.startswith('*'):
                    # Wildcard pattern
                    if item.endswith(pattern[1:]):
                        ignored.append(item)
                        break
                elif item == pattern:
                    ignored.append(item)
                    break

        return ignored

    print(f"Copying: {src} -> {dst}")
    try:
        shutil.copytree(src, dst, ignore=ignore_function, dirs_exist_ok=True)
        print(f"  [OK] Successfully copied")
        return True
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False

def main():
    print("=" * 60)
    print("  DoctorVoice Pro - Complete Package Creator (Safe Mode)")
    print("=" * 60)
    print()

    # Define source and destination
    source_dir = Path(r"C:\Users\u\doctor-voice-pro")
    dest_dir = Path(r"C:\Users\u\doctor-voice-pro\DoctorVoicePro_Complete_Package")

    # Create destination directory
    dest_dir.mkdir(parents=True, exist_ok=True)
    print(f"[OK] Created package directory: {dest_dir}")
    print()

    # Copy backend
    print("[*] Copying backend...")
    backend_src = source_dir / "backend"
    backend_dst = dest_dir / "backend"
    if backend_src.exists():
        safe_copytree(str(backend_src), str(backend_dst))
    else:
        print(f"  [!] Backend folder not found: {backend_src}")
    print()

    # Copy frontend
    print("[*] Copying frontend...")
    frontend_src = source_dir / "frontend"
    frontend_dst = dest_dir / "frontend"
    if frontend_src.exists():
        safe_copytree(str(frontend_src), str(frontend_dst))
    else:
        print(f"  [!] Frontend folder not found: {frontend_src}")
    print()

    # Copy Installer folder
    print("[*] Copying Installer...")
    installer_src = source_dir / "DoctorVoicePro_Installer"
    installer_dst = dest_dir / "Installer"
    if installer_src.exists():
        safe_copytree(str(installer_src), str(installer_dst))
    else:
        print(f"  [!] Installer folder not found: {installer_src}")
    print()

    # Create START_HERE.txt
    print("[*] Creating START_HERE guide...")
    start_here_content = """╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║       DoctorVoice Pro - 완전한 패키지                      ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

환영합니다! 이 폴더에는 DoctorVoice Pro의 모든 파일이 포함되어 있습니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 이 폴더에 포함된 내용
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ backend/          - 백엔드 소스 코드 (FastAPI)
✓ frontend/         - 프론트엔드 소스 코드 (Next.js)
✓ Installer/        - Windows 설치 파일 생성 도구

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 원하는 것을 선택하세요
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────────────────┐
│ 1️⃣  Windows 설치 파일(.exe) 만들기                       │
│                                                         │
│    다른 컴퓨터에 배포할 설치 파일을 만들고 싶다면:       │
│    ↓                                                    │
│    Installer 폴더로 이동                                │
│    ↓                                                    │
│    QUICK_START.txt 파일 읽기                            │
│    ↓                                                    │
│    BUILD_INSTALLER.bat 실행                             │
│                                                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ 2️⃣  개발 환경에서 직접 실행하기                          │
│                                                         │
│    개발하거나 수정하면서 바로 실행하고 싶다면:            │
│                                                         │
│    Backend 실행:                                        │
│    cd backend                                           │
│    python -m uvicorn app.main:app --host 0.0.0.0       │
│    --port 5000 --reload                                 │
│                                                         │
│    Frontend 실행:                                       │
│    cd frontend                                          │
│    npm run dev                                          │
│                                                         │
│    브라우저: http://localhost:5002                      │
│                                                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ 3️⃣  자동 실행 스크립트 사용                              │
│                                                         │
│    Installer\\scripts\\start_app.bat                      │
│    - 백엔드와 프론트엔드를 자동으로 시작                  │
│                                                         │
│    Installer\\scripts\\stop_app.bat                       │
│    - 실행 중인 서버 종료                                 │
│                                                         │
└─────────────────────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📁 폴더 구조
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DoctorVoicePro_Complete_Package/
│
├── 📂 backend/                    백엔드 애플리케이션
│   ├── app/                       주요 코드
│   ├── requirements.txt           Python 의존성
│   ├── recreate_db.py            DB 초기화
│   └── ...
│
├── 📂 frontend/                   프론트엔드 애플리케이션
│   ├── src/                       소스 코드
│   ├── public/                    정적 파일
│   ├── package.json               Node.js 의존성
│   └── ...
│
├── 📂 Installer/                  설치 파일 생성 도구
│   ├── BUILD_INSTALLER.bat        🎯 설치 파일 빌드
│   ├── DOWNLOAD_RUNTIMES.bat      런타임 다운로드
│   ├── QUICK_START.txt            빠른 시작
│   ├── README.md                  상세 설명
│   ├── installer_script.iss       Inno Setup 스크립트
│   │
│   └── 📂 scripts/
│       ├── start_app.bat          프로그램 시작
│       └── stop_app.bat           프로그램 종료
│
└── 📄 시작하세요_START_HERE.txt   이 파일

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔑 기본 관리자 계정
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

이메일: admin@doctorvoice.com
비밀번호: admin123!@#

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 필요한 프로그램
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

개발 환경에서 실행하려면:
✓ Node.js v20.18.0 이상
✓ Python 3.11.9 이상

설치 파일을 만들려면:
✓ Inno Setup 6.0 이상
  (https://jrsoftware.org/isdl.php)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📞 지원
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

문의: support@doctorvoice.com
웹사이트: https://doctorvoice.com

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎉 즐거운 개발 되세요!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    with open(dest_dir / "시작하세요_START_HERE.txt", "w", encoding="utf-8") as f:
        f.write(start_here_content)
    print("  [OK] Created START_HERE.txt")
    print()

    print("=" * 60)
    print("[SUCCESS] Package creation complete!")
    print("=" * 60)
    print()
    print(f"Package location: {dest_dir}")
    print()
    print("Next steps:")
    print("1. Open the folder: DoctorVoicePro_Complete_Package")
    print("2. Read START_HERE.txt")
    print("3. To create installer: Go to Installer folder and run BUILD_INSTALLER.bat")
    print()

if __name__ == "__main__":
    main()
