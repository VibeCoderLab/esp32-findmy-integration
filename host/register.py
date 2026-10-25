"""Prepare locally, apply one own pair, inspect it, or remove that same pair."""
import argparse
import asyncio
import getpass
import json
from datetime import datetime, timezone

from common import STATE, account, cloud_account, private_directory, write_json, durable_unlink, WorkflowError
from cloud import apply, digest, load, remove
from snapshot import complete_records
from service_limits import guard, request
from recovery_status import safe_details, summary, release_retry
from records import make_identity, build_record, check_candidate
from findmy.cloudkit import AsyncBeaconStore
from findmy.cloudkit.pcs import ShareProtection, unwrap_protection
from findmy.cloudkit.proto import cloudkit_pb2 as ck
from findmy.keychain.session import AsyncKeychainSession
from findmy.cloudkit.pcs import ObjectSignature
from zone_signing import select_zone_identity

async def prepare(name, emoji, fresh_protection=True):
    private_directory()
    if (STATE / 'registration.json').exists():
        raise SystemExit('A preparation already exists. No new keys generated.')
    if (STATE / 'recovery-blocked.json').exists():
        raise SystemExit('Recovery is blocked. Check the cause; no automatic retries.')
    value = account()
    session = store = None
    try:
        guard('keychain')
        value._password = getpass.getpass('Apple password (not saved): ')
        wrapped = cloud_account(value)
        session = await request('keychain', lambda: AsyncKeychainSession.open(wrapped))
        options = list((await request('keychain', lambda: session.recovery_options())).recoverable)
        if not options:
            raise WorkflowError('No recoverable device identity available.')
        for index, record in enumerate(options):
            print(f'[{index}] {record.describe()}')
        choice = input('Device number: ').strip()
        if not choice.isdigit() or int(choice) >= len(options):
            raise WorkflowError('Invalid selection; no passcode attempt made.')
        code = getpass.getpass('Device screen unlock passcode (one attempt): ')
        try:
            # Checkpoint BEFORE sending: crashes/cancellation leave an unknown-outcome block.
            write_json(STATE / 'recovery-blocked.json', {
                'reason': 'recovery attempt pending; outcome unknown', 'automatic_retries': False,
                'started_at': datetime.now(timezone.utc).isoformat()})
            try:
                peer = await request('keychain', lambda: session.recover(options[int(choice)], code))
            except BaseException as error:
                failure = {'reason': 'recovery failed' if isinstance(error, Exception) else 'recovery interrupted; outcome unknown',
                           'automatic_retries': False, 'details': safe_details(error)}
                write_json(STATE / 'recovery-blocked.json', failure)
                if not isinstance(error, Exception):
                    raise
                raise WorkflowError('Recovery failed. ' + summary(failure) +
                    '\nNo automatic retry. Use recovery-status before explicitly releasing one manual retry.') from None
            else:
                durable_unlink(STATE / 'recovery-blocked.json')
        finally:
            del code
        service_keys = await request('keychain', lambda: session.pcs_keys(peer))
        store = AsyncBeaconStore(wrapped)
        existing = await complete_records(store)
        identity = make_identity(name, emoji)
        if fresh_protection:
            from fresh_protection import build_fresh_records
            zones = await request('cloudkit', lambda: store.client.zone_retrieve())
            zone = next((z.target_zone for z in zones
                if z.target_zone.zone_identifier.value.name == 'BeaconStore'), None)
            if zone is None:
                raise WorkflowError('BeaconStore zone is missing. It will not be created automatically.')
            zone_protection = ShareProtection.from_der(zone.protection_info.protection_info)
            parent = unwrap_protection(zone_protection, service_keys, require_hmac=True, require_signature=True)
            zone_object = ObjectSignature.from_der(zone_protection.signature_data.data)
            signing_key = select_zone_identity(zone_object.ec_key_list_der, parent.private_keys)
            records, (pm, pn) = build_fresh_records(identity, [signing_key], zone.zone_identifier,
                                                   signing_key=signing_key)
            print('Experimental: fresh PCS envelopes generated; no accessory encryption templates used.')
            print('Zone identity, HMAC, inner/outer signatures and decryption verified; check visibility in Find My.')
        else:
            zone_keys = await request('cloudkit', lambda: store.zone_keys(service_keys))
            templates = {}
            for kind in ('MasterBeaconRecord', 'BeaconNamingRecord'):
                for record in existing:
                    if record.record_type != kind or not record.protection_info or record.source is None:
                        continue
                    try:
                        protection = unwrap_protection(ShareProtection.from_der(record.protection_info), zone_keys)
                    except Exception:
                        continue
                    if not protection.read_only:
                        templates[kind] = record, protection
                        break
                if kind not in templates:
                    raise WorkflowError(f'No decryptable template for {kind}. Experimental alternative: prepare --fresh-protection; an existing BeaconStore zone is still required.')
            tm, pm = templates['MasterBeaconRecord']
            tn, pn = templates['BeaconNamingRecord']
            records = [build_record(identity['id'], 'MasterBeaconRecord', identity['master'], pm, tm.source),
                       build_record(identity['naming_id'], 'BeaconNamingRecord', identity['naming'], pn, tn.source)]
        for record in records:
            record.record_identifier.value.type = ck.Identifier.RECORD
        accessory, _ = check_candidate(identity, *records, pm, pn)
        ids = [identity['id'], identity['naming_id']]
        if set(ids) & {r.name for r in existing}:
            raise WorkflowError('ID collision; no changes made.')
        for filename, record in zip(('master.pb', 'naming.pb'), records):
            (STATE / filename).write_bytes(record.SerializeToString())
        write_json(STATE / 'tracker.private.json', accessory.to_json())
        write_json(STATE / 'registration.json', {'ids': ids, 'digests': [digest(r) for r in records],
            'baseline_ids': [r.name for r in existing], 'creation_attempted': [], 'status': 'prepared',
            'protection_mode': 'fresh-experimental' if fresh_protection else 'template',
            **({'fresh_protection_version': 2} if fresh_protection else {})})
        print('Prepared locally and cryptographically verified. No cloud records created.')
        print('To create the records: scripts/register.sh apply')
    finally:
        value._password = None
        if store: await store.close()
        if session: await session.close()
        await value.close()

async def run(args):
    if args.mode in ('recovery-status', 'allow-recovery-retry'):
        private_directory()
        marker = STATE / 'recovery-blocked.json'
        if args.mode == 'allow-recovery-retry':
            if not args.confirm_one_recovery_retry:
                raise WorkflowError('Explicit --confirm-one-recovery-retry is required. No Apple request sent.')
            release_retry(STATE)
            print('One manual retry released locally; prior failure archived. No Apple request sent.')
        elif marker.is_file():
            print(summary(json.loads(marker.read_text())))
            print('Recovery remains blocked. Verify the selected device and its unlock passcode before authorizing one manual retry.')
        else:
            print('No blocked recovery attempt recorded.')
        return
    if args.mode == 'prepare':
        return await prepare(args.name, args.emoji, args.fresh_protection)
    private_directory()
    value = account()
    store = AsyncBeaconStore(cloud_account(value))
    try:
        if args.mode == 'apply': await apply(store)
        elif args.mode == 'remove': await remove(store)
        else:
            manifest, _ = load()
            current = {r.name for r in await complete_records(store)}
            print('Journal:', manifest['status'])
            for field in ('primary_error', 'cleanup_error'):
                if field in manifest:
                    print(field + ':', json.dumps(manifest[field], sort_keys=True))
            print('Records belonging to this installation present:', len(current & set(manifest['ids'])), '/ 2')
    finally:
        await store.close()
        await value.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'apply', 'status', 'remove', 'recovery-status', 'allow-recovery-retry'))
    parser.add_argument('--confirm-one-recovery-retry', action='store_true', help='Release one local recovery block after reviewing it; sends no request.')
    parser.add_argument('--name', default='ESP32 Tracker')
    parser.add_argument('--emoji', default='📍')
    protection = parser.add_mutually_exclusive_group()
    protection.add_argument('--fresh-protection', dest='fresh_protection', action='store_true',
        default=True, help='Generate fresh PCS envelopes without accessory templates (default; experimental).')
    protection.add_argument('--template-protection', dest='fresh_protection', action='store_false',
        help='Legacy mode: reuse encryption templates from existing decryptable accessory records.')
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except WorkflowError as error:
        raise SystemExit(str(error)) from None
    except Exception as error:
        # No response bodies or credentials in the normal error output.
        raise SystemExit(f'{type(error).__name__}: Operation stopped. No automatic retry. Keep local data and check the error.') from None
