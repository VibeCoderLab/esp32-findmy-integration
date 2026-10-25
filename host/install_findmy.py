"""Build the hash-verified pinned FindMy source with two reviewed local patches."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
import zipfile

from common import ROOT, WorkflowError
from fetch_coreadi import verified_download


def unpack(source, destination, commit):
    prefix = 'FindMy.py-' + commit
    with zipfile.ZipFile(source) as archive:
        entries = archive.infolist()
        if len(entries) > 10000 or sum(info.file_size for info in entries) > 32 * 1024 * 1024:
            raise WorkflowError('FindMy source archive exceeds the expected size.')
        for info in entries:
            path = PurePosixPath(info.filename)
            if (not path.parts or path.parts[0] != prefix or '..' in path.parts or path.is_absolute()
                    or stat.S_ISLNK(info.external_attr >> 16)):
                raise WorkflowError('Unsafe FindMy source archive entry.')
        archive.extractall(destination)
    return destination / prefix


def apply_reviewed_patch(source, patch, expected_paths):
    paths = [line[4:] for line in patch.read_text().splitlines() if line.startswith(('--- ', '+++ '))]
    if paths != expected_paths:
        raise WorkflowError('Unexpected dependency patch paths; refusing to apply.')
    subprocess.run(['git', 'apply', '--check', str(patch)], cwd=source, check=True)
    subprocess.run(['git', 'apply', str(patch)], cwd=source, check=True)


def main():
    locked = json.loads((ROOT / 'sources.lock.json').read_text())['findmy']
    if (not re.fullmatch(r'[0-9a-f]{40}', locked['commit'])
            or not re.fullmatch(r'[0-9a-f]{64}', locked['sha256'])
            or locked['url'] != 'https://github.com/parawanderer/FindMy.py/archive/' + locked['commit'] + '.zip'):
        raise WorkflowError('Invalid pinned FindMy source manifest.')
    cache = ROOT / '.deps/findmy-source.zip'
    verified_download(locked['url'], cache, locked['sha256'], label='FindMy source')
    with tempfile.TemporaryDirectory(prefix='findmy-build-', dir=ROOT / '.deps') as directory:
        destination = Path(directory)
        source = unpack(cache, destination, locked['commit'])
        apply_reviewed_patch(source, ROOT / 'patches/findmy-packaging.patch', ['a/pyproject.toml','b/pyproject.toml'])
        apply_reviewed_patch(source, ROOT / 'patches/cloudkit-status.patch', ['a/findmy/cloudkit/client.py','b/findmy/cloudkit/client.py'])
        wheels = destination / 'wheels'
        subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-index', '--no-deps', '--no-build-isolation',
                        '--wheel-dir', str(wheels), str(source)], check=True)
        found = list(wheels.glob('findmy-*.whl'))
        if len(found) != 1:
            raise WorkflowError('Expected one FindMy wheel from the reviewed source.')
        wheel = found[0]
        with zipfile.ZipFile(wheel) as archive:
            for required in ['findmy/cloudkit/client.py','findmy/keychain/session.py','findmy/util/crypto.py']:
                if required not in archive.namelist():
                    raise WorkflowError('FindMy wheel is missing required subpackages.')
        digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
        requirements = destination / 'wheel.lock'
        requirements.write_text(f'FindMy @ {wheel.as_uri()} --hash=sha256:{digest}\n')
        subprocess.run(['uv','pip','install','--python',sys.executable,'--no-deps','--require-hashes',
                        '--reinstall-package','FindMy','-r',str(requirements)],check=True)
    print('Pinned FindMy source checksum, packaging fix and HTTP status patch installed.')


if __name__ == '__main__':
    try:
        main()
    except WorkflowError as error:
        raise SystemExit(str(error)) from None
