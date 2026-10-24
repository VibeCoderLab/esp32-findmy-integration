"""Simulate CloudKit, including a save whose successful reply was lost."""
import json
import secrets
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
import cloud
from common import write_json
from records import make_identity, build_record, UnwrappedProtection
from findmy.cloudkit.proto import cloudkit_pb2 as ck
from findmy.cloudkit.records import iter_wire_fields

class FakeStore:
    def __init__(self, baseline, fail_after_second_save=False):
        self.records = {baseline.record_identifier.value.name: baseline}
        self.client = self
        self.saved_ids = []
        self.fail_after_second_save = fail_after_second_save

    async def fetch_records(self):
        return [SimpleNamespace(name=name, source=record) for name, record in self.records.items()]

    async def _zone_protection_tag(self): return 'test-zone-tag'

    async def record_save(self, record, **kwargs):
        ident = record.record_identifier.value.name
        if ident in self.records: raise AssertionError('Must never overwrite any existing ID')
        self.saved_ids.append(ident)
        copy = ck.Record(); copy.CopyFrom(record); self.records[ident] = copy
        if self.fail_after_second_save and len(self.saved_ids) == 2:
            raise RuntimeError('Simulated lost response after successful save')

    def _build_request(self, operation):
        return ck.RequestOperation(request=ck.Operation(type=int(operation)))

    async def _post_operation(self, endpoint, request):
        if endpoint != '/api/client/record/delete': raise AssertionError(endpoint)
        outer = next(value for number, _, value in iter_wire_fields(request.SerializeToString()) if number == 214)
        raw_id = next(value for number, _, value in iter_wire_fields(outer) if number == 1)
        ident = ck.RecordIdentifier.FromString(raw_id).value.name
        if ident not in self.saved_ids: raise AssertionError('Must never delete a baseline ID')
        self.records.pop(ident, None)

class TransactionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.old_state = cloud.STATE; cloud.STATE = Path(self.directory.name)
        p = UnwrappedProtection(secrets.token_bytes(16), False, False, True, True)
        identity = make_identity()
        self.records = [build_record(identity['id'], 'MasterBeaconRecord', identity['master'], p),
                        build_record(identity['naming_id'], 'BeaconNamingRecord', identity['naming'], p)]
        baseline_identity = make_identity()
        self.baseline = build_record(baseline_identity['id'], 'MasterBeaconRecord', baseline_identity['master'], p)
        for name, record in zip(('master.pb', 'naming.pb'), self.records):
            (cloud.STATE / name).write_bytes(record.SerializeToString())
        self.ids = [r.record_identifier.value.name for r in self.records]
        write_json(cloud.STATE / 'registration.json', {'ids': self.ids,
            'digests': [cloud.digest(r) for r in self.records],
            'baseline_ids': [self.baseline.record_identifier.value.name],
            'creation_attempted': [], 'status': 'prepared'})

    def tearDown(self):
        cloud.STATE = self.old_state
        self.directory.cleanup()

    async def test_create_then_remove_only_owned_pair_after_ui_rename(self):
        store = FakeStore(self.baseline)
        await cloud.apply(store)
        self.assertEqual(store.saved_ids, self.ids)
        naming = store.records[self.ids[1]]
        next(f for f in naming.record_field if f.identifier.name == 'name').value.bytes_value = b'UI edit'
        await cloud.remove(store)
        self.assertEqual(list(store.records), [self.baseline.record_identifier.value.name])

    async def test_lost_reply_rolls_back_both_new_records(self):
        store = FakeStore(self.baseline, fail_after_second_save=True)
        with self.assertRaisesRegex(RuntimeError, 'lost response'):
            await cloud.apply(store)
        self.assertEqual(list(store.records), [self.baseline.record_identifier.value.name])
        self.assertEqual(json.loads((cloud.STATE / 'registration.json').read_text())['status'], 'removed')

    async def test_existing_target_refused_before_any_write(self):
        store = FakeStore(self.baseline)
        store.records[self.ids[0]] = self.records[0]
        with self.assertRaises(RuntimeError): await cloud.apply(store)
        self.assertEqual(store.saved_ids, [])
