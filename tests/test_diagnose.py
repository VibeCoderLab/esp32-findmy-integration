"""Read-only comparison must separate key changes from an editable label."""
from pathlib import Path
import secrets
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
from diagnose import compare_record
from records import make_identity, build_record, UnwrappedProtection
from findmy.cloudkit.proto import cloudkit_pb2 as ck


class DiagnosisTests(unittest.TestCase):
    def setUp(self):
        self.identity = make_identity()
        protection = UnwrappedProtection(secrets.token_bytes(16), False, False, True, True)
        self.master = build_record(self.identity['id'], 'MasterBeaconRecord', self.identity['master'], protection)
        self.naming = build_record(self.identity['naming_id'], 'BeaconNamingRecord', self.identity['naming'], protection)

    def test_matching_record_and_missing_record(self):
        self.assertTrue(compare_record(self.master, self.master)['tracking_fields_match_local'])
        self.assertEqual(compare_record(self.master, None), {'present': False})

    def test_key_change_is_detected_without_exporting_values(self):
        changed = ck.Record(); changed.CopyFrom(self.master)
        field = next(f for f in changed.record_field if f.identifier.name == 'privateKey')
        field.value.bytes_value = b'synthetic-sensitive-material'
        result = compare_record(self.master, changed)
        self.assertFalse(result['tracking_fields_match_local'])
        self.assertEqual(result['changed_known_fields'], ['privateKey'])
        self.assertNotIn('synthetic-sensitive-material', str(result))

    def test_name_edit_preserves_key_and_association_checks(self):
        changed = ck.Record(); changed.CopyFrom(self.naming)
        next(f for f in changed.record_field if f.identifier.name == 'name').value.bytes_value = b'synthetic-name'
        result = compare_record(self.naming, changed)
        self.assertFalse(result['encrypted_fields_match_local'])
        self.assertTrue(result['association_matches_local'])
        self.assertTrue(result['matches_current_removal_guard'])
        self.assertNotIn('synthetic-name', str(result))
