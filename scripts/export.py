#!/usr/bin/env python3
"""Export source by allowlist. Never package a whole working installation."""
import argparse
import hashlib
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = ('VERSION', 'CHANGELOG.md', 'README.md', 'README.de.md', 'LICENSE', 'SECURITY.md', 'THIRD_PARTY.md', 'requirements.txt', 'requirements.lock', 'requirements-build.txt', 'requirements-build.lock', 'sources.lock.json',
    '.gitignore', '.gitattributes', 'host/*.py', 'scripts/*.py', 'scripts/*.sh',
    'tests/*.py', 'docs/*.md', 'patches/*.patch', 'patches/LICENSE.*',
    'firmware/platformio.ini', 'firmware/src/*.cpp', 'firmware/include/.gitkeep')

def files(root=ROOT):
    result = sorted({path for pattern in PATTERNS for path in root.glob(pattern) if path.is_file()})
    if not result: raise RuntimeError('No source files found.')
    for path in result:
        current = root
        for part in path.relative_to(root).parts:
            current = current / part
            if current.is_symlink(): raise RuntimeError('Export refused a symbolic link: ' + str(path.relative_to(root)))
    return result

def audit(paths, root=ROOT):
    checks = {
        'personal home path': rb'/' + rb'(?:home|Users)/[A-Za-z0-9_.-]+/',
        'email address': rb'[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
        'literal service token': rb'''(?:searchPartyToken|cloudKitToken|mmeAuthToken)["']?\s*[:=]\s*["'][A-Za-z0-9+/~_-]{20,}''',
        'literal tracker key': rb'''(?:master_key|skn|sks|privateKey|private_key)["']?\s*[:=]\s*["'][A-Za-z0-9+/=_-]{32,}''',
        'literal firmware key': rb'MASTER_KEY\s*\[\s*28\s*\]\s*=\s*\{(?:\s*\d+\s*,){5}',
        'private key PEM': rb'-----BEGIN ' + rb'(?:EC |RSA |OPENSSH )?PRIVATE KEY-----',
    }
    failures = []
    for path in paths:
        raw = path.read_bytes()
        for reason, pattern in checks.items():
            if re.search(pattern, raw): failures.append(str(path.relative_to(root)) + ': ' + reason)
    if failures: raise RuntimeError('Export audit failed:\n' + '\n'.join(failures))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Audit only; do not create a ZIP archive.')
    args = parser.parse_args()
    paths = files()
    audit(paths)
    if args.check:
        print(f'PASS: {len(paths)} public source files checked; private/build/dependency directories excluded.')
        return
    destination = ROOT / 'dist'
    destination.mkdir(exist_ok=True)
    archive = destination / 'esp32-findmy-public.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as target:
        for path in paths:
            target.write(path, 'esp32-findmy-public/' + str(path.relative_to(ROOT)))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (destination / (archive.name + '.sha256')).write_text(checksum + '  ' + archive.name + '\n')
    print(f'Exported: {archive.name} ({len(paths)} source files), SHA-256: {checksum}')

if __name__ == '__main__': main()
