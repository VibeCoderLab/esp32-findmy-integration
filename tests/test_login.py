"""First-run provisioning and identity reuse, with no real Apple requests."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
from login import ensure_machine
from common import WorkflowError


class ProvisioningTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.state = self.root / 'private'; self.state.mkdir()
        self.upstream = self.root / 'upstream'
        helper = self.upstream / 'tools/machoadi/mac_anisette.py'
        helper.parent.mkdir(parents=True); helper.touch()
        self.calls = []

    def tearDown(self):
        self.directory.cleanup()

    def provision(self, command, **kwargs):
        self.calls.append(command)
        self.assertEqual(command[2], 'provision')
        self.assertTrue(kwargs['check'])
        self.assertTrue(kwargs['capture_output'])
        machine = self.state / 'machine'
        (machine / 'store').mkdir(parents=True)
        (machine / 'identity.json').write_text(json.dumps({
            'device_id': str(uuid.uuid4()), 'host_uuid': uuid.uuid4().hex,
            'local_user_uuid': str(uuid.uuid4()), 'provisioned_at': 1}))
        (machine / 'store/adi-00000000.pb').write_bytes(b'test-only')

    def test_first_run_provisions_once_and_second_run_reuses_identity(self):
        self.assertTrue(ensure_machine(self.state, self.upstream, self.provision))
        before = (self.state / 'machine/identity.json').read_bytes()
        self.assertFalse(ensure_machine(self.state, self.upstream, self.provision))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual((self.state / 'machine/identity.json').read_bytes(), before)

    def test_saved_session_without_machine_never_generates_a_replacement(self):
        (self.state / 'login.json').write_text('{}')
        with self.assertRaises(WorkflowError): ensure_machine(self.state, self.upstream, self.provision)
        self.assertEqual(self.calls, [])

    def test_partial_machine_is_not_overwritten(self):
        machine = self.state / 'machine'; machine.mkdir()
        (machine / 'partial-state').write_bytes(b'preserve')
        with self.assertRaises(WorkflowError): ensure_machine(self.state, self.upstream, self.provision)
        self.assertEqual(self.calls, [])
        self.assertEqual((machine / 'partial-state').read_bytes(), b'preserve')

    def test_provision_failure_never_retries(self):
        def fail(command, **kwargs):
            self.calls.append(command)
            raise subprocess.CalledProcessError(1, command)
        with self.assertRaises(WorkflowError): ensure_machine(self.state, self.upstream, fail)
        self.assertEqual(len(self.calls), 1)

    def test_identity_without_store_is_refused(self):
        self.provision(['python', 'helper', 'provision'], check=True, capture_output=True)
        (self.state / 'machine/store/adi-00000000.pb').unlink()
        with self.assertRaises(WorkflowError): ensure_machine(self.state, self.upstream, self.provision)
        self.assertEqual(len(self.calls), 1)
