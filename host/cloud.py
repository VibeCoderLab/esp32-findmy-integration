"""Bounded writes to one pair of newly generated CloudKit record IDs."""
import hashlib
import json

from common import STATE, write_json, WorkflowError
from findmy.cloudkit.constants import OperationType, SaveSemantics
from findmy.cloudkit.proto import cloudkit_pb2 as ck
from findmy.cloudkit.client import _encode_varint
from snapshot import complete_records
from service_limits import request, error_info, ServicePaused, SessionExpired

def signature(record):
    return (record.record_identifier.value.name, record.type.name,
            sorted((field.identifier.name, field.value.SerializeToString()) for field in record.record_field),
            record.protection_info.protection_info)

def digest(record):
    return hashlib.sha256(repr(signature(record)).encode()).hexdigest()

def load():
    manifest = json.loads((STATE / 'registration.json').read_text())
    records = [ck.Record.FromString((STATE / name).read_bytes()) for name in ('master.pb', 'naming.pb')]
    ids = manifest['ids']
    if len(ids) != 2 or len(set(ids)) != 2 or len(manifest['digests']) != 2:
        raise WorkflowError('Invalid registration journal.')
    if set(ids) & set(manifest['baseline_ids']):
        raise WorkflowError('A new test ID belongs to a previous record.')
    for record, ident, expected, kind in zip(records, ids, manifest['digests'], ('MasterBeaconRecord', 'BeaconNamingRecord')):
        if record.record_identifier.value.name != ident or record.type.name != kind or digest(record) != expected:
            raise WorkflowError('Local records do not match the journal.')
    return manifest, records

def delete_request(client, record):
    def framed(number, payload):
        return _encode_varint((number << 3) | 2) + _encode_varint(len(payload)) + payload
    request = client._build_request(OperationType.RECORD_DELETE_TYPE)
    request.MergeFromString(framed(214, framed(1, record.record_identifier.SerializeToString())))
    return request

def allowed_removal(expected, actual):
    if signature(expected) == signature(actual):
        return True
    # Permit a name/emoji edited in Find My, but never changed keys or association.
    if (expected.record_identifier != actual.record_identifier or expected.type != actual.type
            or expected.protection_info.protection_info != actual.protection_info.protection_info):
        return False
    old = {f.identifier.name: f.value.SerializeToString() for f in expected.record_field}
    new = {f.identifier.name: f.value.SerializeToString() for f in actual.record_field}
    changed = {name for name in old.keys() | new.keys() if old.get(name) != new.get(name)}
    return expected.type.name == 'BeaconNamingRecord' and changed <= {'name', 'emoji'}

class TransactionFailure(WorkflowError):
    """Retain both causes in memory; show only credential-free classifications."""
    def __init__(self, original, cleanup):
        self.original_error = original
        self.cleanup_error = cleanup
        super().__init__('Registration failed (' + error_info(original)['type'] +
            '); cleanup is incomplete (' + error_info(cleanup)['type'] +
            '). Keep the journal. Review service pauses, sign in manually if needed, then run register.sh remove.')


def checkpoint_failure(manifest, primary=None, cleanup=None):
    manifest['status'] = 'cleanup_pending'
    if primary is not None:
        manifest['primary_error'] = error_info(primary)
    if cleanup is not None:
        manifest['cleanup_error'] = error_info(cleanup)
    write_json(STATE / 'registration.json', manifest)


async def remove(store):
    manifest, records = load()
    manifest['status'] = 'cleanup_in_progress'
    write_json(STATE / 'registration.json', manifest)
    try:
        current = {r.name: r for r in await complete_records(store)}
        # Check the entire owned pair before deleting either half.
        for expected in records:
            ident = expected.record_identifier.value.name
            if ident in manifest['creation_attempted'] and ident in current:
                if not allowed_removal(expected, current[ident].source):
                    raise WorkflowError('Test record changed unexpectedly; removal refused.')
        for expected in reversed(records):
            ident = expected.record_identifier.value.name
            if ident not in manifest['creation_attempted']:
                continue
            current = {r.name: r for r in await complete_records(store)}
            if ident in current:
                record = current[ident].source
                if not allowed_removal(expected, record):
                    raise WorkflowError('Test record changed unexpectedly; removal refused.')
                await request('cloudkit', lambda: store.client._post_operation(
                    '/api/client/record/delete', delete_request(store.client, record)))
                if ident in {r.name for r in await complete_records(store)}:
                    raise WorkflowError('Removal not confirmed.')
            verified = manifest.setdefault('removal_verified', [])
            if ident not in verified:
                verified.append(ident)
            write_json(STATE / 'registration.json', manifest)
        final = {r.name for r in await complete_records(store)}
        if set(manifest['creation_attempted']) & final:
            raise WorkflowError('Removal not confirmed by a complete final snapshot.')
        manifest['status'] = 'removed'
        manifest.pop('cleanup_error', None)
        manifest.pop('cleanup_deferred', None)
        write_json(STATE / 'registration.json', manifest)
        print('Registered test records removed or confirmed absent in a complete snapshot.')
    except BaseException as error:
        try:
            checkpoint_failure(manifest, cleanup=error)
        except OSError as journal_error:
            raise TransactionFailure(error, journal_error) from None
        raise


async def apply(store):
    manifest, records = load()
    before = {r.name: r for r in await complete_records(store)}
    if manifest['creation_attempted'] or any(ident in before for ident in manifest['ids']):
        raise WorkflowError('Registration already attempted. No duplicate records created; use status/remove.')
    zone_tag = await request('cloudkit', lambda: store._zone_protection_tag())
    try:
        for record, ident in zip(records, manifest['ids']):
            manifest['creation_attempted'].append(ident)
            manifest['status'] = 'creation_in_progress'
            write_json(STATE / 'registration.json', manifest)
            await request('cloudkit', lambda: store.client.record_save(record, record_protection_info_tag='',
                zone_protection_info_tag=zone_tag, semantics=SaveSemantics.CREATE))
            after = {r.name: r for r in await complete_records(store)}
            if ident not in after or signature(after[ident].source) != signature(record):
                raise WorkflowError('New record did not match when read back.')
        if any(ident not in after or signature(record.source) != signature(after[ident].source)
               for ident, record in before.items()):
            raise WorkflowError('Existing records changed during the test.')
        manifest['status'] = 'created_verified'
        write_json(STATE / 'registration.json', manifest)
        print('Created and read back two new records. Complete snapshots verified the existing baseline.')
    except BaseException as original:
        try:
            checkpoint_failure(manifest, primary=original)
        except OSError as journal_error:
            raise TransactionFailure(original, journal_error) from None
        # Authentication failures and throttling cannot be repaired by another request.
        if isinstance(original, (ServicePaused, SessionExpired)):
            manifest['cleanup_deferred'] = error_info(original)['type']
            try:
                write_json(STATE / 'registration.json', manifest)
            except OSError as journal_error:
                raise TransactionFailure(original, journal_error) from None
            raise TransactionFailure(original, original) from None
        try:
            await remove(store)
        except BaseException as cleanup:
            raise TransactionFailure(original, cleanup) from None
        raise
