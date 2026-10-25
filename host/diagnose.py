"""Compare only this installation's encrypted records; never export keys or coordinates."""
import asyncio
import json

from common import account, cloud_account, tracker, WorkflowError
from cloud import load, allowed_removal
from snapshot import complete_records
from service_limits import request, error_info
from findmy.cloudkit import AsyncBeaconStore


def compare_record(expected, actual):
    if actual is None:
        return {'present': False}
    before = {f.identifier.name: f.value.SerializeToString() for f in expected.record_field}
    after = {f.identifier.name: f.value.SerializeToString() for f in actual.record_field}
    changed = {name for name in before.keys() | after.keys() if before.get(name) != after.get(name)}
    # Output only field names from our own schema, never untrusted cloud values.
    known = set(before)
    key_fields = {'privateKey', 'publicKey', 'sharedSecret', 'sharedSecret2', 'pairingDate'}
    return {
        'present': True,
        'record_type_matches': expected.type == actual.type,
        'record_address_matches': expected.record_identifier == actual.record_identifier,
        'envelope_matches_local': expected.protection_info.protection_info == actual.protection_info.protection_info,
        'encrypted_fields_match_local': not changed,
        'changed_known_fields': sorted(changed & known),
        'additional_field_count': len(set(after) - known),
        'tracking_fields_match_local': all(before.get(name) == after.get(name) for name in key_fields if name in before),
        'association_matches_local': before.get('associatedBeacon') == after.get('associatedBeacon'),
        'matches_current_removal_guard': allowed_removal(expected, actual),
    }


async def diagnose():
    manifest, expected = load()
    accessory = tracker()
    value = account()
    store = None
    result = {'cloud_records_modified': False, 'coordinates_exported': False,
              'local_registration_verified': True, 'records': {}}
    try:
        store = AsyncBeaconStore(cloud_account(value))
        current = {record.name: record for record in await complete_records(store)}
        for label, record in zip(('master', 'naming'), expected):
            remote = current.get(record.record_identifier.value.name)
            result['records'][label] = compare_record(record, remote.source if remote else None)
        reports = await request('reports', lambda: value.fetch_location_history(accessory))
        result['decrypted_reports'] = len(reports)
        if reports:
            result['newest_report_time'] = max(report.timestamp for report in reports).isoformat()
        print(json.dumps(result, indent=2))
        print('Read-only comparison complete. No record IDs, keys, names or coordinates printed.')
        print('Ciphertext equality checks stored bytes; it does not prove Find My can use them for location.')
    finally:
        if store is not None:
            await store.close()
        await value.close()


if __name__ == '__main__':
    try:
        asyncio.run(diagnose())
    except WorkflowError as error:
        raise SystemExit(str(error)) from None
    except Exception as error:
        raise SystemExit('Diagnosis stopped: ' + json.dumps(error_info(error)) + '. No automatic retry.') from None
