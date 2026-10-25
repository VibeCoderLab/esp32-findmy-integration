"""Paths are relative to this checkout. All account data lives in a private directory."""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = Path(os.environ.get('ESP32_FINDMY_STATE', ROOT / 'private')).expanduser().resolve()
UPSTREAM = ROOT / '.deps/os-findmy-e'

class WorkflowError(RuntimeError):
    """A project-owned, credential-free error that may be displayed to the user."""


def private_directory():
    os.umask(0o077)
    STATE.mkdir(parents=True, mode=0o700, exist_ok=True)
    STATE.chmod(0o700)
    return STATE

def fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def durable_unlink(path):
    path = Path(path)
    path.unlink()
    fsync_directory(path.parent)


def write_json(path, value):
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.tmp', dir=path.parent)
    pending = Path(name)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, path)
        fsync_directory(path.parent)
    finally:
        pending.unlink(missing_ok=True)

def account():
    if not (STATE / 'login.json').exists():
        raise SystemExit('Run scripts/login.sh first.')
    sys.path.insert(0, str(UPSTREAM / 'tools/machoadi'))
    from login_store import restore
    return restore(STATE / 'machine', STATE / 'login.json')

def cloud_account(value):
    sys.path.insert(0, str(UPSTREAM / 'tools/machoadi'))
    from tag_keys import for_cloudkit
    return for_cloudkit(value)

def tracker():
    from findmy import FindMyAccessory
    return FindMyAccessory.from_json(json.loads((STATE / 'tracker.private.json').read_text()))
