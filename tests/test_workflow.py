"""Offline checks only. All keys and identifiers are generated for each test run."""
import json
import os
import secrets
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
from records import make_identity, build_record, check_candidate, decode_local, UnwrappedProtection
from findmy.cloudkit.proto import cloudkit_pb2 as ck
from key_header import make_header
from cloud import allowed_removal, digest
from findmy.util.crypto import x963_kdf, derive_ps_key
from findmy import KeyPair

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.identity = make_identity('Test Tracker', '🔑')
        self.pm = UnwrappedProtection(secrets.token_bytes(16), False, False, True, True)
        self.pn = UnwrappedProtection(secrets.token_bytes(16), False, False, True, True)
        self.master = build_record(self.identity['id'], 'MasterBeaconRecord', self.identity['master'], self.pm)
        self.naming = build_record(self.identity['naming_id'], 'BeaconNamingRecord', self.identity['naming'], self.pn)
        self.accessory, self.schedule = check_candidate(self.identity, self.master, self.naming, self.pm, self.pn)

    def test_profile_and_encrypted_roundtrip(self):
        master = decode_local(self.master, self.pm)
        naming = decode_local(self.naming, self.pn)
        self.assertEqual((master['vendorId'], master['productId']), (76, 21760))
        self.assertEqual(master['stableIdentifier'].split('~#')[0], '2001')
        self.assertEqual(naming['associatedBeacon'], self.identity['id'])
        self.assertEqual(naming['name'], 'Test Tracker')
        self.assertEqual(naming['emoji'], '🔑')
        self.assertEqual(len(self.schedule), 48)

    def test_new_installation_has_different_keys(self):
        another = make_identity()
        for field in ('privateKey', 'sharedSecret', 'sharedSecret2'):
            self.assertNotEqual(self.identity['master'][field], another['master'][field])
        self.assertNotEqual(self.identity['id'], another['id'])

    def test_encryption_binds_record_and_field(self):
        changed = ck.Record(); changed.CopyFrom(self.master)
        changed.record_identifier.value.name = self.identity['naming_id']
        with self.assertRaises(Exception): decode_local(changed, self.pm)
        changed.CopyFrom(self.master)
        raw = bytearray(changed.record_field[0].value.bytes_value); raw[-1] ^= 1
        changed.record_field[0].value.bytes_value = bytes(raw)
        with self.assertRaises(Exception): decode_local(changed, self.pm)

    def test_header_alignment_matches_reference_key_generator(self):
        for index in (0, 1, 2, 95, 96):
            now = self.accessory.paired_at + timedelta(seconds=900 * index)
            header, actual_index = make_header(self.accessory, now)
            self.assertEqual(actual_index, index)
            seed = self.accessory.skn
            for _ in range(index): seed = x963_kdf(seed, b'update', 32)
            expected = KeyPair(derive_ps_key(self.accessory.master_key, seed))
            self.assertEqual(expected.adv_key_bytes, self.accessory._primary_key_at(index).adv_key_bytes)
            self.assertIn('INITIAL_INDEX=' + str(index) + ';', header)
            self.assertIn('{' + ','.join(str(v) for v in seed) + '}', header)

    def test_removal_permits_ui_rename_but_not_key_or_association_change(self):
        changed = ck.Record(); changed.CopyFrom(self.naming)
        next(f for f in changed.record_field if f.identifier.name == 'name').value.bytes_value = b'new encrypted value'
        self.assertTrue(allowed_removal(self.naming, changed))
        next(f for f in changed.record_field if f.identifier.name == 'associatedBeacon').value.bytes_value = b'wrong'
        self.assertFalse(allowed_removal(self.naming, changed))
        changed.CopyFrom(self.master)
        changed.record_field[0].value.bytes_value = b'wrong'
        self.assertFalse(allowed_removal(self.master, changed))

    def test_journal_refuses_existing_ids_and_tampered_candidates(self):
        import cloud
        from common import write_json
        with tempfile.TemporaryDirectory() as directory:
            old_state = cloud.STATE
            try:
                cloud.STATE = Path(directory)
                for name, record in [('master.pb', self.master), ('naming.pb', self.naming)]:
                    (cloud.STATE / name).write_bytes(record.SerializeToString())
                ids = [self.identity['id'], self.identity['naming_id']]
                manifest = {'ids': ids, 'digests': [digest(self.master), digest(self.naming)], 'baseline_ids': []}
                write_json(cloud.STATE / 'registration.json', manifest)
                cloud.load()
                manifest['baseline_ids'] = [ids[0]]
                write_json(cloud.STATE / 'registration.json', manifest)
                with self.assertRaises(RuntimeError): cloud.load()
                manifest['baseline_ids'] = []; manifest['digests'][0] = 'wrong'
                write_json(cloud.STATE / 'registration.json', manifest)
                with self.assertRaises(RuntimeError): cloud.load()
            finally:
                cloud.STATE = old_state

if __name__ == '__main__': unittest.main()
