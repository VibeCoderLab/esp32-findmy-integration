"""Provision one persistent machine, then authenticate without saving a password."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from common import STATE, UPSTREAM, private_directory, WorkflowError


def validate_machine(machine):
    try:
        identity = json.loads((machine / 'identity.json').read_text())
        if not isinstance(identity, dict) or not {'device_id', 'host_uuid', 'local_user_uuid', 'provisioned_at'} <= identity.keys():
            raise ValueError('Incomplete identity')
        if (machine / '.store-update.pending').exists():
            raise ValueError('Interrupted machine-state update')
        if not any((machine / 'store').glob('adi-*.pb')):
            raise ValueError('Missing provisioned store')
    except (OSError, ValueError, TypeError):
        raise WorkflowError('The saved machine identity is incomplete. Restore the entire machine directory; do not create a new identity over it.') from None


def ensure_machine(state=None, upstream=None, runner=None):
    state = Path(state) if state is not None else STATE
    upstream = Path(upstream) if upstream is not None else UPSTREAM
    runner = runner or subprocess.run
    machine = state / 'machine'
    if (machine / 'identity.json').exists():
        validate_machine(machine)
        return False
    if (state / 'login.json').exists() or (state / 'session.json').exists():
        raise WorkflowError('Saved session has no matching machine identity. Restore the original machine directory.')
    if machine.exists() and any(machine.iterdir()):
        raise WorkflowError('The machine directory is incomplete and not empty. Check the cause; it will not be regenerated automatically.')
    helper = upstream / 'tools/machoadi/mac_anisette.py'
    if not helper.is_file():
        raise WorkflowError('Run scripts/setup.sh first.')
    print('First run: provisioning a machine identity once; no Apple password is needed yet.', flush=True)
    try:
        runner([sys.executable, str(helper), 'provision', '--state', str(machine)],
               cwd=upstream, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError:
        raise WorkflowError('Machine provisioning failed. No login attempted; check the connection and local machine state.') from None
    validate_machine(machine)
    print('Machine identity created; it will be reused for subsequent logins.', flush=True)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provision-only', action='store_true', help='Only provision the machine identity; do not sign in to Apple.')
    args = parser.parse_args()
    private_directory()
    if not (UPSTREAM / 'auth_probe.py').exists():
        raise WorkflowError('Run scripts/setup.sh first.')
    sys.path.insert(0, str(UPSTREAM / 'tools/machoadi'))
    from cooldown import guard as login_guard
    login_guard()
    ensure_machine()
    if args.provision_only:
        return 0
    env = os.environ.copy()
    # The project path is interactive; do not inherit stale account/password overrides.
    env.pop('APPLE_ID', None)
    env.pop('APPLE_PASSWORD', None)
    env['FINDMY_DIAGNOSTICS'] = '0'
    command = [sys.executable, str(Path(__file__).with_name('auth_entry.py')),
        str(UPSTREAM / 'auth_probe.py'), '--macadi', str(STATE / 'machine'),
        '--state-dir', str(STATE / 'auth'), '--auto-resync', '--sms',
        '--save-session', str(STATE / 'session.json'), '--save-login', str(STATE / 'login.json'),
        '--no-save-password']
    return subprocess.call(command, cwd=UPSTREAM, env=env)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except WorkflowError as error:
        raise SystemExit(str(error)) from None
