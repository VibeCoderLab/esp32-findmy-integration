"""Fetch the pinned Apple archive atomically before running upstream extraction."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import sys

from common import UPSTREAM, WorkflowError


def verified_download(url, destination, expected, runner=None):
    runner = runner or subprocess.run
    destination = Path(destination)
    def valid(path):
        if not path.is_file():
            return False
        with path.open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest() == expected
    if valid(destination):
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    pending = destination.with_suffix(destination.suffix + '.pending')
    pending.unlink(missing_ok=True)
    try:
        runner(['curl', '-L', '--fail', '--retry', '3', '--retry-all-errors',
                '--retry-delay', '2', '--connect-timeout', '15', '--max-time', '600',
                '-o', str(pending), url], check=True)
        if not valid(pending):
            raise WorkflowError('Apple download checksum mismatch; file not accepted. Run setup again.')
        pending.replace(destination)
    except subprocess.CalledProcessError:
        raise WorkflowError('Apple download failed after retries. Check your internet connection/DNS and rerun the same installation command.') from None
    finally:
        pending.unlink(missing_ok=True)


def main():
    helper = UPSTREAM / 'tools/fetch_mac_coreadi.py'
    spec = importlib.util.spec_from_file_location('upstream_coreadi_fetch', helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    verified_download(module.DMG_URL, UPSTREAM / 'ext/itunes/mac/iTunes12.8.3.dmg', module.DMG_SHA256)
    try:
        subprocess.run([sys.executable, str(helper)], cwd=UPSTREAM, check=True)
    except subprocess.CalledProcessError:
        raise WorkflowError('Failed to extract/verify the Apple file. Check the output above; setup can be run again.') from None


if __name__ == '__main__':
    try:
        main()
    except WorkflowError as error:
        raise SystemExit(str(error)) from None
