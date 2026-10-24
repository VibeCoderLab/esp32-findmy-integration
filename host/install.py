"""One-command setup, resumable within one private state directory."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from common import ROOT, STATE, private_directory, write_json, WorkflowError
from logout import logout


def run(command, **kwargs):
    subprocess.run([str(part) for part in command], cwd=ROOT, check=True, **kwargs)


def parse_chip(output):
    chip = re.search(r'Chip type:\s*(ESP32[^\r\n]+)', output)
    size = re.search(r'Detected flash size:\s*(\d+)MB', output)
    mac = re.search(r'MAC:\s*([0-9a-fA-F:]{17})', output)
    if not chip or not size or not mac:
        raise WorkflowError('Could not unambiguously identify the ESP32 type, flash size or hardware identifier.')
    if not re.match(r'ESP32-(?:D0WD|PICO|U4WDH|S0WD)', chip.group(1)):
        raise WorkflowError('This installer supports only the tested classic ESP32, not S2/S3/C3 variants.')
    if int(size.group(1)) != 4:
        raise WorkflowError('This installer is configured for 4 MB boards only. Nothing has been flashed.')
    return {'chip': chip.group(1), 'flash_bytes': 4 * 1024 * 1024, 'mac': mac.group(1).lower()}


def inspect_board(port):
    result = subprocess.run(['uvx', '--from', 'esptool==5.6.0', 'esptool', '--port', port, 'flash-id'],
        cwd=ROOT, check=True, capture_output=True, text=True)
    (STATE / 'installer-chip.log').write_text(result.stdout + result.stderr)
    return parse_chip(result.stdout + result.stderr)


def check_same_board(expected, actual):
    if expected['mac'] != actual['mac'] or expected['flash_bytes'] != actual['flash_bytes']:
        raise WorkflowError('USB device changed or does not match the backup. No upload performed.')


def ensure_backup(board, port):
    backup = STATE / 'installer-flash-before.bin'
    journal = STATE / 'installer-board.json'
    if journal.exists():
        saved = json.loads(journal.read_text())
        check_same_board(saved, board)
        if not backup.is_file() or backup.stat().st_size != board['flash_bytes']:
            raise WorkflowError('The recorded flash backup is missing or incomplete.')
        if hashlib.sha256(backup.read_bytes()).hexdigest() != saved['sha256']:
            raise WorkflowError('The existing flash backup has been modified.')
        print('Keeping the existing verified backup for this board.', flush=True)
        return
    if backup.exists():
        raise WorkflowError('A backup exists without its journal; it was not overwritten. Check the local state.')
    pending = STATE / 'installer-flash-before.pending.bin'
    # Let the board settle after flash-id's automatic reset. Read retries never
    # write to the board, and only a successful complete read becomes a backup.
    for attempt, baud in enumerate((1500000, 115200)):
        time.sleep(2)
        pending.unlink(missing_ok=True)
        try:
            print(f'Reading flash backup at {baud} baud.', flush=True)
            run(['uvx', '--from', 'esptool==5.6.0', 'esptool', '--port', port, '--baud', str(baud),
                 'read-flash', '0', hex(board['flash_bytes']), pending])
            break
        except subprocess.CalledProcessError:
            pending.unlink(missing_ok=True)
            if attempt == 1:
                raise
            print('USB read interrupted; retrying once at 115200 baud.', flush=True)
    if pending.stat().st_size != board['flash_bytes']:
        raise WorkflowError('Flash backup has an unexpected size. No upload performed.')
    pending.replace(backup)
    backup.chmod(0o600)
    write_json(journal, {**board, 'sha256': hashlib.sha256(backup.read_bytes()).hexdigest()})


def registration_action(manifest, fresh_protection=True):
    if manifest is None:
        return 'prepare'
    if fresh_protection and manifest.get('protection_mode') != 'fresh-experimental':
        raise WorkflowError('Existing preparation uses accessory templates. The default mode requires a fresh private state directory; use --template-protection only to resume a legacy template installation. No records were automatically replaced.')
    if manifest.get('protection_mode') == 'fresh-experimental' and manifest.get('fresh_protection_version') != 2:
        raise WorkflowError('Older experimental PCS preparation lacks a verified zone identity. It will not be reused automatically; use a fresh isolated state directory.')
    if manifest['status'] == 'prepared' and not manifest['creation_attempted']:
        return 'apply'
    if manifest['status'] == 'created_verified':
        return 'reuse'
    raise WorkflowError('Registration partially failed or was removed. Check the existing journal; no new IDs generated.')


async def validate_existing_registration():
    from common import account, cloud_account
    from cloud import load, allowed_removal
    from findmy.cloudkit import AsyncBeaconStore
    _, expected = load()
    value = account()
    store = AsyncBeaconStore(cloud_account(value))
    try:
        current = {record.name: record for record in await store.fetch_records()}
        for record in expected:
            ident = record.record_identifier.value.name
            if ident not in current or not allowed_removal(record, current[ident].source):
                raise WorkflowError('Registered record is missing or changed unexpectedly. No duplicate will be created.')
    finally:
        await store.close()
        await value.close()


def install(args):
    private_directory()
    journal = STATE / 'installer-progress.json'
    def stage(name):
        write_json(journal, {'stage': name, 'port': args.port})
        print('\n>>> ' + name, flush=True)
    stage('Inspect USB board and back up the original flash')
    board = inspect_board(args.port)
    print('Detected:', board['chip'], 'with 4 MB flash.', flush=True)
    ensure_backup(board, args.port)
    stage('Apple login')
    if not (STATE / 'login.json').exists():
        run([ROOT / 'scripts/login.sh'])
    else:
        print('Using the saved login from this installation directory.', flush=True)
    manifest_path = STATE / 'registration.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    action = registration_action(manifest, args.fresh_protection)
    if action == 'prepare':
        stage('Prepare new keys and cloud records locally')
        command = [ROOT / 'scripts/register.sh', 'prepare', '--name', args.name, '--emoji', args.emoji]
        command.append('--fresh-protection' if args.fresh_protection else '--template-protection')
        run(command)
        manifest = json.loads(manifest_path.read_text())
        action = registration_action(manifest, args.fresh_protection)
    if action == 'apply':
        stage('Create the two records for this installation in iCloud')
        run([ROOT / 'scripts/register.sh', 'apply'])
    stage('Verify existing registration')
    asyncio.run(validate_existing_registration())
    stage('Build firmware with the tracker keys')
    run([ROOT / 'scripts/build.sh'])
    stage('Recheck USB device identity and upload firmware')
    check_same_board(board, inspect_board(args.port))
    time.sleep(2)
    run(['uvx', '--from', 'platformio==6.2.0', 'pio', 'run', '-d', ROOT / 'firmware',
         '--target', 'upload', '--upload-port', args.port])
    stage('Verify firmware keys on the board')
    command = [sys.executable, ROOT / 'host/verify.py', '--port', args.port]
    if not args.verify_ble:
        command.append('--serial-only')
    run(command)
    stage('Fetch location reports')
    run([ROOT / 'scripts/fetch.sh'])
    stage('completed')
    print('Setup complete. Check the new item in Find My.', flush=True)
    print('Zero reports immediately after startup is possible; an Apple device must first report the beacon. The first report may take around 30 minutes or longer.', flush=True)


def run_install(args):
    try:
        install(args)
    finally:
        logout(quiet=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True, help='USB port of the board to flash, e.g. /dev/ttyUSB0')
    parser.add_argument('--name', default='ESP32 Tracker')
    parser.add_argument('--emoji', default='📍')
    protection = parser.add_mutually_exclusive_group()
    protection.add_argument('--fresh-protection', dest='fresh_protection', action='store_true',
        default=True, help='Generate fresh PCS envelopes without accessory templates (default; experimental).')
    protection.add_argument('--template-protection', dest='fresh_protection', action='store_false',
        help='Legacy mode: reuse encryption templates from existing decryptable accessory records.')
    parser.add_argument('--verify-ble', action='store_true', help='Also require a local Linux BLE reception test.')
    args = parser.parse_args()
    try:
        run_install(args)
    except WorkflowError as error:
        raise SystemExit(str(error)) from None
    except subprocess.CalledProcessError as error:
        raise SystemExit(f'Setup stopped in a subprocess (exit {error.returncode}). Keep the private state and check the output of the failed step.') from None
