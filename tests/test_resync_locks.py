"""Offline integration of patched classes; never load CoreADI or contact Apple."""
import __future__
import ast
import asyncio
import base64
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_machine_state import helper_source

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / '.deps/os-findmy-e/tools/machoadi'


def load_class(path, name, namespace):
    tree = ast.parse(path.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec', flags=__future__.annotations.compiler_flag), namespace)
    return namespace[name]


@unittest.skipUnless((UPSTREAM / 'resync.py').exists(), 'Run scripts/setup.sh to test patched upstream integration')
class ResyncLockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name)
        (self.state / 'identity.json').write_text(json.dumps({'host_uuid': '00' * 16, 'client_info': 'synthetic',
            'device_id': 'synthetic', 'local_user_uuid': 'synthetic'}))
        (self.state / 'store').mkdir()
        (self.state / 'store/adi-test.pb').write_bytes(b'original')
        atomic = {}; exec(helper_source(), atomic)
        self.lock_state = atomic['lock_state']
        def fake_core(**kwargs):
            return SimpleNamespace(stubs=SimpleNamespace(files={}), initialize=lambda: None,
                synchronize=lambda *args: SimpleNamespace(ret=0, outputs={'mid': b'synthetic', 'srm': b'synthetic'}))
        namespace = dict(Path=Path, json=json, lock_state=self.lock_state, CoreADI=fake_core, STORE_DIR='/adi')
        self.Machine = load_class(UPSTREAM / 'mac_anisette.py', 'MacAnisette', namespace)
        namespace = dict(Path=Path, json=json, MacAnisette=self.Machine, provisioned_at=lambda state: 0,
            CONTEXT={}, GSA=lambda device: object(), Device=lambda *args: None,
            base64=base64, DS_ID=1, time=SimpleNamespace(time=lambda: 0, strftime=lambda format: 'synthetic'))
        self.Resyncer = load_class(UPSTREAM / 'resync.py', 'Resyncer', namespace)

    def assert_provider_process_can_lock(self):
        code = 'import fcntl,sys; f=open(sys.argv[1],"r+"); fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)'
        subprocess.run([sys.executable, '-c', code, str(self.state / '.machine.lock')], check=True, capture_output=True)

    def test_idle_resyncer_does_not_block_header_subprocess(self):
        resyncer = self.Resyncer(self.state, log=lambda row: None)
        self.assertIsNone(resyncer.machine)
        self.assert_provider_process_can_lock()

    def test_sync_reloads_latest_store_and_releases_lock_even_on_failure(self):
        resyncer = self.Resyncer(self.state, log=lambda row: None)
        (self.state / 'store/adi-test.pb').write_bytes(b'advanced-by-provider')
        def fail_sync(*args):
            self.assertEqual(bytes(resyncer.machine.adi.stubs.files['/adi/adi-test.pb']), b'advanced-by-provider')
            with self.assertRaises(BlockingIOError): self.lock_state(self.state)
            raise RuntimeError('synthetic sync failure')
        with patch.object(resyncer, 'sync_machine', side_effect=fail_sync):
            with self.assertRaisesRegex(RuntimeError, 'synthetic sync failure'):
                asyncio.run(resyncer.answer_sim(base64.b64encode(b'synthetic').decode()))
        self.assertIsNone(resyncer.machine)
        self.assert_provider_process_can_lock()
