"""Generate a private firmware header from this checkout's own tracker keys."""
import argparse
import hashlib
import os
from datetime import datetime, timezone
from common import ROOT, tracker
from findmy.util.crypto import x963_kdf

def make_header(accessory, now=None):
    now = now or datetime.now(timezone.utc)
    index = max(0, int((now - accessory.paired_at).total_seconds() // 900))
    seed = accessory.skn
    for _ in range(index):
        seed = x963_kdf(seed, b'update', 32)
    identity = int.from_bytes(hashlib.sha256(accessory.master_key + accessory.skn).digest()[:4], 'big')
    def array(value): return ','.join(str(byte) for byte in value)
    return ('#pragma once\n#include <stdint.h>\n'
        f'static const uint8_t MASTER_KEY[28]={{{array(accessory.master_key)}}};\n'
        f'static const uint8_t INITIAL_SEED[32]={{{array(seed)}}};\n'
        f'static const uint32_t INITIAL_INDEX={index};\n'
        f'static const uint32_t IDENTITY_ID={identity}U;\n'), index

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', action='store_true', help='Build test only: generate fresh, unregistered disposable keys.')
    args = parser.parse_args()
    os.umask(0o077)
    if args.demo:
        from records import make_identity, check_candidate, build_record, UnwrappedProtection
        import secrets
        identity = make_identity()
        p = UnwrappedProtection(secrets.token_bytes(16), False, False, True, True)
        m = build_record(identity['id'], 'MasterBeaconRecord', identity['master'], p)
        n = build_record(identity['naming_id'], 'BeaconNamingRecord', identity['naming'], p)
        accessory, _ = check_candidate(identity, m, n, p, p)
        print('DEMO: unregistered disposable keys; native location tracking is unavailable with these keys.')
    else:
        accessory = tracker()
    value, index = make_header(accessory)
    path = ROOT / 'firmware/include/device_secrets.h'
    path.parent.mkdir(exist_ok=True)
    path.write_text(value)
    path.chmod(0o600)
    print('Private header generated; starting index:', index)
    print('Never publish this header or firmware built from it.')
