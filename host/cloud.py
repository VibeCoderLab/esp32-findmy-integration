"""Bounded writes to one pair of newly generated CloudKit record IDs."""
import hashlib
import json

from common import STATE, write_json, WorkflowError
from findmy.cloudkit.constants import OperationType, SaveSemantics
from findmy.cloudkit.proto import cloudkit_pb2 as ck
from findmy.cloudkit.client import _encode_varint

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

async def remove(store):
    manifest, records = load()
    for expected in reversed(records):
        ident = expected.record_identifier.value.name
        if ident not in manifest['creation_attempted']:
            continue
        current = {r.name: r for r in await store.fetch_records()}
        if ident not in current:
            continue
        record = current[ident].source
        if not allowed_removal(expected, record):
            raise WorkflowError('Test record changed unexpectedly; removal refused.')
        await store.client._post_operation('/api/client/record/delete', delete_request(store.client, record))
        if ident in {r.name for r in await store.fetch_records()}:
            raise WorkflowError('Removal not confirmed.')
    manifest['status'] = 'removed'
    write_json(STATE / 'registration.json', manifest)
    print('Registered test records for this installation were removed or are already absent.')

async def apply(store):
    manifest, records = load()
    before = {r.name: r for r in await store.fetch_records()}
    if manifest['creation_attempted'] or any(ident in before for ident in manifest['ids']):
        raise WorkflowError('Registration already attempted. No duplicate records created; use status/remove.')
    zone_tag = await store._zone_protection_tag()
    try:
        for record, ident in zip(records, manifest['ids']):
            manifest['creation_attempted'].append(ident)
            write_json(STATE / 'registration.json', manifest)
            await store.client.record_save(record, record_protection_info_tag='',
                zone_protection_info_tag=zone_tag, semantics=SaveSemantics.CREATE)
            after = {r.name: r for r in await store.fetch_records()}
            if ident not in after or signature(after[ident].source) != signature(record):
                raise WorkflowError('New record did not match when read back.')
        if any(ident not in after or signature(record.source) != signature(after[ident].source)
               for ident, record in before.items()):
            raise WorkflowError('Existing records changed during the test.')
        manifest['status'] = 'created_verified'
        write_json(STATE / 'registration.json', manifest)
        print('Created and read back two new records for this installation. Previous records unchanged.')
    except BaseException:
        await remove(store)
        raise
