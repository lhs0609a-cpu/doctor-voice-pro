import shutil
from pathlib import Path

source = Path(r"C:\Users\u\doctor-voice-pro")
target = Path(r"C:\Users\u\DoctorVoicePro-v2.0-Final")

exclude = {'__pycache__', '.pytest_cache', 'node_modules', '.git', 'venv', '.next', '.venv', 'dist', 'build'}

def should_exclude(p):
    for part in p.parts:
        if part in exclude:
            return True
    if p.is_file():
        if p.suffix in ['.pyc', '.log'] or 'doctorvoice.db' in p.name or p.name.startswith('copy_'):
            return True
    return False

def copy_dir(src, dst):
    if not dst.exists():
        dst.mkdir(parents=True)
    for item in src.iterdir():
        s, d = src / item.name, dst / item.name
        if should_exclude(s):
            continue
        copy_dir(s, d) if s.is_dir() else shutil.copy2(s, d)

print("복사 중...")
copy_dir(source / "backend", target / "backend")
copy_dir(source / "frontend", target / "frontend")
shutil.copy2(source / "최종실행.bat", target / "실행.bat")
print("완료!")
