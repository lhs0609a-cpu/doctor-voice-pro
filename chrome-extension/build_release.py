"""Build a reproducible unpacked-extension ZIP. Does not sign CRX or deploy."""
import hashlib
import json
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parent
manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
version = manifest['version']
destination = root.parent / 'frontend' / 'public' / 'extension'
destination.mkdir(parents=True, exist_ok=True)
artifact = destination / f'doctorvoice-extension-v{version}.zip'
files = sorted(p for p in root.rglob('*') if p.is_file() and
               (p.parent == root and p.suffix in ('.js', '.json', '.html', '.css') or p.parent == root / 'icons' and p.suffix in ('.png', '.svg')))
with zipfile.ZipFile(artifact, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    for file in files:
        info = zipfile.ZipInfo(file.relative_to(root).as_posix(), date_time=(2026, 9, 8, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, file.read_bytes())
checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()
(destination / f'{artifact.name}.sha256').write_text(f'{checksum}  {artifact.name}\n', encoding='utf-8')
(destination / 'version.json').write_text(json.dumps({
    'version': version,
    'downloadUrl': f'https://doctor-voice-pro-ghwi.vercel.app/extension/{artifact.name}',
    'notes': 'v17.1 — 랜딩 링크 검증, URL 입력 보존, 서버 예약 동작 연결 수정, 결과 보고 복구.',
    'minVersion': version, 'releasedAt': '2026-09-09', 'sha256': checksum,
}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'{artifact.name}: {len(files)} files, sha256={checksum}')
