"""Simulate CloudKit, including a save whose successful reply was lost."""
import json
import secrets
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
import cloud
from common import write_json
from records import make_identity, build_record, UnwrappedProtection
from findmy.cloudkit.proto import cloudkit_pb2 as ck
from findmy.cloudkit.constants import PATH_RECORD_SYNC, SYNC_STATUS_COMPLETE, ResultCode
from findmy.cloudkit.client import CloudKitError
from findmy.cloudkit import beacons
from cryptography.hazmat.primitives.asymmetric import ec
from fresh_protection import build_fresh_records
import service_limits
from findmy.cloudkit.records import iter_wire_fields

class FakeStore:
    def __init__(self, baseline, fail_after_second_save=False):
        self.records = {baseline.record_identifier.value.name: baseline}
        self.client = self
        self.saved_ids = []
        self.fail_after_second_save = fail_after_second_save

    async def open_container(self): return SimpleNamespace(user_id='synthetic')

    def _zone_identifier(self, name):
        zone = ck.RecordZoneIdentifier(); zone.value.name = name
        return zone

    async def fetch_records(self):
        raise AssertionError('Strict snapshots must not use the permissive listing API')

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
        if endpoint == PATH_RECORD_SYNC:
            response = ck.ResponseOperation()
            response.result.code = ResultCode.SUCCESS
            response.retrieve_changes_response.status = SYNC_STATUS_COMPLETE
            for record in self.records.values():
                response.retrieve_changes_response.record_change.add().record.CopyFrom(record)
            return response
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
        self.old_limits = service_limits.LIMITS; service_limits.LIMITS = cloud.STATE / 'limits/service-limits.json'
        p = UnwrappedProtection(secrets.token_bytes(16), False, False, True, True)
        identity = make_identity()
        zone = ck.RecordZoneIdentifier(); zone.value.name = 'BeaconStore'
        signing_key = ec.generate_private_key(ec.SECP256R1())
        self.records, _ = build_fresh_records(identity, [signing_key], zone, signing_key=signing_key)
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
        service_limits.LIMITS = self.old_limits
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

    async def test_failed_rollback_preserves_both_causes_and_pending_status(self):
        class Store(FakeStore):
            async def _post_operation(inner, endpoint, request):
                if endpoint == '/api/client/record/delete':
                    raise OSError('synthetic-private-cleanup-detail')
                return await super(Store, inner)._post_operation(endpoint, request)
        store=Store(self.baseline,fail_after_second_save=True)
        with self.assertRaises(cloud.TransactionFailure) as raised:
            await cloud.apply(store)
        self.assertIsInstance(raised.exception.original_error,RuntimeError)
        self.assertIsInstance(raised.exception.cleanup_error,OSError)
        data=json.loads((cloud.STATE/'registration.json').read_text())
        self.assertEqual(data['status'],'cleanup_pending')
        self.assertEqual(data['primary_error']['type'],'RuntimeError')
        self.assertEqual(data['cleanup_error']['type'],'OSError')
        self.assertNotIn('synthetic-private',json.dumps(data)+str(raised.exception))
        self.assertEqual(set(store.records),{self.baseline.record_identifier.value.name,*self.ids})

    async def test_401_or_429_does_not_attempt_cleanup_requests(self):
        for status in [401,429]:
            with self.subTest(status=status):
                manifest=json.loads((cloud.STATE/'registration.json').read_text())
                manifest.update(creation_attempted=[],status='prepared')
                write_json(cloud.STATE/'registration.json',manifest)
                service_limits.LIMITS.unlink(missing_ok=True)
                class Failure(RuntimeError): pass
                error=Failure('synthetic-private-server-body');error.http_status=status;error.retry_after=90
                class Store(FakeStore):
                    async def record_save(inner,record,**kwargs): raise error
                    async def _post_operation(inner,endpoint,request):
                        self.assertNotEqual(endpoint,'/api/client/record/delete')
                        return await super(Store,inner)._post_operation(endpoint,request)
                store=Store(self.baseline)
                with self.assertRaises(cloud.TransactionFailure):await cloud.apply(store)
                data=json.loads((cloud.STATE/'registration.json').read_text())
                self.assertEqual(data['status'],'cleanup_pending')
                self.assertIn('cleanup_deferred',data)
                self.assertEqual(data['primary_error']['http_status'],status)
                self.assertNotIn('synthetic-private',json.dumps(data))

    async def test_changed_master_refuses_all_deletions_before_naming_is_removed(self):
        store=FakeStore(self.baseline);await cloud.apply(store)
        next(f for f in store.records[self.ids[0]].record_field if f.identifier.name=='publicKey').value.bytes_value=b'unexpected'
        with self.assertRaises(cloud.WorkflowError):await cloud.remove(store)
        self.assertTrue(all(ident in store.records for ident in self.ids))
        self.assertEqual(json.loads((cloud.STATE/'registration.json').read_text())['status'],'cleanup_pending')

    async def test_partial_snapshot_cannot_confirm_removal_or_absence(self):
        store=FakeStore(self.baseline);await cloud.apply(store)
        original=store._post_operation
        async def partial(endpoint,request):
            self.assertNotEqual(endpoint,'/api/client/record/delete')
            response=await original(endpoint,request)
            response.result.code=ResultCode.PARTIAL
            return response
        store._post_operation=partial
        with self.assertRaises(cloud.WorkflowError):await cloud.remove(store)
        self.assertTrue(all(ident in store.records for ident in self.ids))
        self.assertEqual(json.loads((cloud.STATE/'registration.json').read_text())['status'],'cleanup_pending')

    async def test_incomplete_snapshot_prevents_any_create(self):
        store=FakeStore(self.baseline);original=store._post_operation
        async def incomplete(endpoint,request):
            response=await original(endpoint,request)
            response.retrieve_changes_response.status=1
            response.retrieve_changes_response.ClearField('sync_continuation_token')
            return response
        store._post_operation=incomplete
        with self.assertRaises(cloud.WorkflowError):await cloud.apply(store)
        self.assertEqual(store.saved_ids,[])

    async def test_attempt_checkpoint_exists_before_save_is_sent(self):
        outer=self
        class Store(FakeStore):
            async def record_save(inner,record,**kwargs):
                journal=json.loads((cloud.STATE/'registration.json').read_text())
                outer.assertIn(record.record_identifier.value.name,journal['creation_attempted'])
                outer.assertEqual(journal['status'],'creation_in_progress')
                return await super(Store,inner).record_save(record,**kwargs)
        await cloud.apply(Store(self.baseline))
