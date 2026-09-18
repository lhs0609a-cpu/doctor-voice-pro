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


# ── 코드 서명 ────────────────────────────────────────────────────
# 서명이 없으면 Windows Smart App Control 이 '처음 보는 파일'이라며 실행 자체를 막는다
# (WinError 4551). 인증서가 준비되면 아래 환경변수 중 하나만 채우면 그때부터 서명된다.
#   SIGN_PFX (+ SIGN_PFX_PASSWORD)  파일로 받은 인증서
#   SIGN_SHA1                       인증서 저장소에 설치한 인증서의 지문
#   SIGN_AZURE_METADATA             Azure Trusted Signing 설정 json 경로 (+ SIGN_AZURE_DLIB)
TIMESTAMP_URL = 'http://timestamp.digicert.com'
SIGNTOOL_CANDIDATES = (
    Path(os.environ.get('SIGNTOOL', '')),
    *sorted(Path(r'C:\Program Files (x86)\Windows Kits\10\bin').glob('*/x64/signtool.exe'), reverse=True),
)


def find_signtool():
    for candidate in SIGNTOOL_CANDIDATES:
        if candidate.name and candidate.is_file():
            return candidate
    found = shutil.which('signtool')
    return Path(found) if found else None


def signing_args():
    """환경변수에서 서명 방법을 고른다. 아무것도 없으면 None(서명하지 않는다)."""
    if os.environ.get('SIGN_PFX'):
        args = ['/f', os.environ['SIGN_PFX']]
        if os.environ.get('SIGN_PFX_PASSWORD'):
            args += ['/p', os.environ['SIGN_PFX_PASSWORD']]
        return args
    if os.environ.get('SIGN_SHA1'):
        return ['/sha1', os.environ['SIGN_SHA1']]
    if os.environ.get('SIGN_AZURE_METADATA'):
        dlib = os.environ.get('SIGN_AZURE_DLIB') or 'Azure.CodeSigning.Dlib.dll'
        return ['/dlib', dlib, '/dmdf', os.environ['SIGN_AZURE_METADATA']]
    return None


def sign(*targets: Path) -> bool:
    """서명 설정이 있으면 서명하고 True. 설정이 없으면 건너뛰고 False(빌드는 계속한다)."""
    args = signing_args()
    if not args:
        return False
    tool = find_signtool()
    if not tool:
        raise SystemExit('서명 설정은 있는데 signtool.exe 를 찾지 못했습니다. '
                         'Windows SDK 를 설치하거나 SIGNTOOL 환경변수에 경로를 넣으세요')
    for target in targets:
        subprocess.run([str(tool), 'sign', *args, '/fd', 'SHA256',
                        '/tr', TIMESTAMP_URL, '/td', 'SHA256', str(target)], check=True)
        print(f'서명함: {target.name}')
    return True


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
    try:
        subprocess.run([str(app / 'DoctorVoiceAutopilot.exe'), '--self-check', str(report)], check=True, timeout=60)
    except OSError as error:
        if getattr(error, 'winerror', None) != 4551:
            raise
        # Smart App Control 은 서명 없는 '처음 보는 파일'을 평판이 없다는 이유로 실행 자체를 막는다.
        # 이 PC에서 막힌다면 같은 정책이 켜진 고객 PC에서도 설치가 막힌다 — 서명 없이는 내보낼 수 없다.
        raise SystemExit(
            '이 PC의 Windows 앱 제어 정책(Smart App Control)이 갓 만든 실행 파일을 막았습니다.\n'
            '  · 확인: reg query "HKLM\\SYSTEM\\CurrentControlSet\\Control\\CI\\Policy" '
            '/v VerifiedAndReputablePolicyState  (1이면 적용 중)\n'
            '  · 해결: 코드 서명 인증서를 준비한 뒤 SIGN_PFX / SIGN_SHA1 / SIGN_AZURE_METADATA 중 하나를 채우세요.\n'
            '  · 검증하지 못한 빌드는 내보내지 않습니다(배포본은 그대로 둡니다).') from error
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
    # 서명은 자체 점검보다 먼저 한다 — 서명해야 앱 제어 정책이 실행을 허용한다.
    if not sign(app_dir / 'DoctorVoiceAutopilot.exe'):
        print('서명 설정이 없어 서명하지 않습니다(SIGN_PFX / SIGN_SHA1 / SIGN_AZURE_METADATA)')
    self_check(app_dir)
    installer = build_installer(app_dir, dist)
    sign(installer)
    publish(installer)
    print(installer)
