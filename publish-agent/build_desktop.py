"""Windows 설치 파일(Inno Setup)을 만듭니다. 자체 점검을 통과해야만 패키지를 내놓습니다."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys

from version import VERSION

HERE = Path(__file__).resolve().parent
PUBLIC = HERE.parent / 'frontend' / 'public' / 'downloads'
DOWNLOAD_BASE = 'https://doctor-voice-pro-ghwi.vercel.app/downloads'
ISCC_CANDIDATES = (
    Path(os.environ.get('ISCC', '')),
    Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Inno Setup 6' / 'ISCC.exe',
    Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Inno Setup 6' / 'ISCC.exe',
    Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Inno Setup 6' / 'ISCC.exe',
)


def find_iscc() -> Path:
    for candidate in ISCC_CANDIDATES:
        if candidate.name and candidate.is_file():
            return candidate
    found = shutil.which('iscc')
    if found:
        return Path(found)
    raise SystemExit('Inno Setup 6 이 필요합니다: winget install JRSoftware.InnoSetup '
                     '(다른 위치에 설치했다면 ISCC 환경변수에 ISCC.exe 경로를 넣으세요)')


def build_app(output: Path) -> Path:
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm', '--windowed', '--onedir',
        '--name', 'DoctorVoiceAutopilot', '--contents-directory', 'app', '--distpath', str(output),
        '--workpath', str(HERE / 'build'), '--specpath', str(HERE / 'build'), '--collect-all', 'playwright',
        '--hidden-import', 'naver_editor', '--hidden-import', 'journal', str(HERE / 'desktop.py')], check=True)
    return output / 'DoctorVoiceAutopilot'


def self_check(app: Path) -> None:
    """실행 파일이 실제로 뜨는지 확인합니다. 깨진 빌드를 설치 파일로 감싸 배포하면 되돌리기 어렵습니다."""
    report = HERE / 'build' / 'desktop-self-check.json'
    report.unlink(missing_ok=True)
    subprocess.run([str(app / 'DoctorVoiceAutopilot.exe'), '--self-check', str(report)], check=True, timeout=60)
    if not report.exists() or json.loads(report.read_text(encoding='utf-8')).get('ok') is not True:
        raise RuntimeError('실행 파일 자체 점검 실패: 패키지를 배포하지 않습니다')


def build_installer(app: Path, output: Path) -> Path:
    subprocess.run([str(find_iscc()), f'/DAppVersion={VERSION}', f'/DSourceDir={app}', f'/DOutputDir={output}',
                    str(HERE / 'installer.iss')], check=True, cwd=HERE)
    setup = output / 'DoctorVoiceAutopilotSetup.exe'
    if not setup.is_file():
        raise RuntimeError('설치 파일이 만들어지지 않았습니다')
    return setup


def publish(setup: Path) -> None:
    """웹에서 내려받는 위치로 복사하고, 실행기가 확인할 버전 매니페스트를 씁니다."""
    digest = hashlib.sha256(setup.read_bytes()).hexdigest()
    setup.with_suffix('.exe.sha256').write_text(digest + '\n', encoding='utf-8')
    if not PUBLIC.is_dir():
        print(f'{PUBLIC} 이 없어 복사를 건너뜁니다')
        return
    shutil.copy2(setup, PUBLIC / setup.name)
    (PUBLIC / 'launcher-version.json').write_text(json.dumps(
        {'version': VERSION, 'url': f'{DOWNLOAD_BASE}/{setup.name}', 'sha256': digest},
        ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(PUBLIC / setup.name)


if __name__ == '__main__':
    if sys.platform != 'win32':
        raise SystemExit('Windows에서 빌드하세요')
    dist = HERE / 'dist'
    app_dir = build_app(dist)
    self_check(app_dir)
    installer = build_installer(app_dir, dist)
    publish(installer)
    print(installer)
