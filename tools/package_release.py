"""Deterministic source archive, excluding local binaries and machine paths."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = [p for p in ROOT.rglob('*') if p.is_file() and not any(part in {
        '.git', '.pytest_cache', '__pycache__', 'build', 'dist'} for part in p.relative_to(ROOT).parts)]
    target = ROOT / 'dist/fir-parity-v0.1.0.zip'
    target.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            info = zipfile.ZipInfo(path.relative_to(ROOT).as_posix(), date_time=(2026, 10, 19, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        for path in files:
            assert archive.read(path.relative_to(ROOT).as_posix()) == path.read_bytes()
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (target.parent / 'SHA256SUMS-v0.1.0.txt').write_text(f'{digest}  {target.name}\n', encoding='ascii')
    print(json.dumps({'sha256': digest, 'files': len(files), 'verified': True}))


if __name__ == '__main__':
    main()
