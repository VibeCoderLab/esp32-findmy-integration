"""Local PCS envelope checks, including account isolation and no accessory records.

These do not establish Apple's acceptance or the ability to create a missing zone.
"""
import asyncio
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from cryptography.hazmat.primitives.asymmetric import ec
from findmy.cloudkit import der, pcs
from findmy.cloudkit.proto import cloudkit_pb2 as ck

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
from common import WorkflowError
from fresh_protection import build_fresh_records, create_protection
from records import check_candidate, make_identity
import install
import register


class FreshProtectionTests(unittest.TestCase):
    def test_outer_signature_uses_zone_key_and_same_signed_data(self):
        from cryptography.hazmat.primitives import hashes
        from cryptography.exceptions import InvalidSignature
        key = ec.generate_private_key(ec.SECP256R1())
        encoded, _ = create_protection([key], signing_key=key)
        protection = pcs.ShareProtection.from_der(encoded)
        obj = pcs.ObjectSignature.from_der(protection.signature_data.data)
        self.assertEqual(obj.outer_sign_key_type, 3)
        self.assertEqual(protection.signature.key_id, key.public_key().public_numbers().x.to_bytes(32, 'big'))
        message = pcs.build_signed_data(protection, obj)
        key.public_key().verify(protection.signature.signature, message, ec.ECDSA(hashes.SHA256()))
        with self.assertRaises(InvalidSignature):
            key.public_key().verify(protection.signature.signature, message+b'changed', ec.ECDSA(hashes.SHA256()))
        wrong = ec.generate_private_key(ec.SECP256R1())
        with self.assertRaises(WorkflowError):
            create_protection([key], signing_key=wrong)

    def test_observed_empty_metadata_and_length_hiding_frame(self):
        key = ec.generate_private_key(ec.SECP256R1())
        encoded, local = create_protection([key.public_key()], signing_key=key)
        protection = pcs.ShareProtection.from_der(encoded)
        restored = pcs.unwrap_protection(protection, [key], require_hmac=True, require_signature=True)
        self.assertEqual(restored.master_key, local.master_key)
        self.assertEqual(len(restored.master_key), 16)
        point, wrapped = pcs._split_wrapped_key(protection.keys[0].ciphertext)
        self.assertEqual((len(point), len(wrapped)), (32, 48))
        self.assertEqual(pcs.decrypt_field(protection.meta, restored, pcs.FieldContext.none()),
                         bytes.fromhex('3009a10730050201000400'))

    def test_every_zone_recipient_can_decrypt_and_verify(self):
        keys = [ec.generate_private_key(ec.SECP256R1()) for _ in range(3)]
        encoded, local = create_protection(keys + keys[:1])
        protection = pcs.ShareProtection.from_der(encoded)
        self.assertEqual(len(protection.keys), 3)
        self.assertEqual({(entry.key_type, len(entry.public_key)) for entry in protection.keys}, {(3, 32)})
        obj = pcs.ObjectSignature.from_der(protection.signature_data.data)
        self.assertEqual((obj.public.key_type, len(obj.public.public_key)), (1, 65))
        for key in keys:
            restored = pcs.unwrap_protection(protection, [key], require_hmac=True, require_signature=True)
            self.assertEqual(restored.master_key, local.master_key)
            self.assertTrue(restored.hmac_verified)
            self.assertTrue(restored.signature_verified)
        keyset, _ = der.parse_one(protection.keyset_der)
        entries = [v.raw for v in keyset.children()[1].children()]
        self.assertEqual(entries, sorted(entries))

    def test_another_account_cannot_open_the_envelope(self):
        mine = ec.generate_private_key(ec.SECP256R1())
        theirs = ec.generate_private_key(ec.SECP256R1())
        encoded, _ = create_protection([mine])
        with self.assertRaises(pcs.PCSError):
            pcs.unwrap_protection(pcs.ShareProtection.from_der(encoded), [theirs], require_hmac=True, require_signature=True)

    def test_tampered_signature_and_hmac_are_rejected(self):
        from dataclasses import replace
        key = ec.generate_private_key(ec.SECP256R1())
        encoded, _ = create_protection([key])
        protection = pcs.ShareProtection.from_der(encoded)
        damaged = replace(protection, hmac=bytes(32))
        with self.assertRaises(pcs.PCSError):
            pcs.unwrap_protection(damaged, [key], require_hmac=True, require_signature=True)
        obj = pcs.ObjectSignature.from_der(protection.signature_data.data)
        from fresh_protection import object_der
        damaged = replace(protection, signature_data=pcs.SignatureData(5,
            object_der(replace(obj, signature=pcs.Signature(b'', 1, b'bad')))))
        with self.assertRaises(pcs.PCSError):
            pcs.unwrap_protection(damaged, [key], require_signature=True)

    def test_pair_uses_independent_new_field_keys_and_preserves_zone_address(self):
        zone = ck.Record().record_identifier.zone_identifier
        zone.value.name = 'BeaconStore'
        keys = [ec.generate_private_key(ec.SECP256R1())]
        identity = make_identity('Synthetic tracker', '🧪')
        records, protections = build_fresh_records(identity, keys, zone, signing_key=keys[0])
        self.assertNotEqual(protections[0].master_key, protections[1].master_key)
        another, _ = create_protection(keys)
        self.assertNotEqual(records[0].protection_info.protection_info, another)
        for record, local in zip(records, protections):
            self.assertEqual(record.record_identifier.zone_identifier, zone)
            restored = pcs.unwrap_protection(pcs.ShareProtection.from_der(record.protection_info.protection_info), keys,
                require_hmac=True, require_signature=True)
            self.assertEqual(restored.master_key, local.master_key)
            self.assertIsNotNone(pcs.ShareProtection.from_der(record.protection_info.protection_info).signature)
        accessory, schedule = check_candidate(identity, *records, *protections)
        self.assertEqual(accessory.name, 'Synthetic tracker')
        self.assertEqual(len(schedule), 48)

    def test_missing_zone_keys_and_unknown_curve_fail(self):
        for keys in ([], [ec.generate_private_key(ec.SECP384R1())]):
            with self.assertRaises(WorkflowError):
                create_protection(keys)
        with self.assertRaises(WorkflowError):
            build_fresh_records(make_identity(), [ec.generate_private_key(ec.SECP256R1())],
                                ck.Record().record_identifier.zone_identifier, signing_key=None)

    def test_default_cannot_reuse_old_template_preparation(self):
        old = {'status': 'prepared', 'creation_attempted': []}
        with self.assertRaises(WorkflowError):
            install.registration_action(old)
        self.assertEqual(install.registration_action(old, fresh_protection=False), 'apply')
        with self.assertRaises(WorkflowError):
            install.registration_action({**old, 'protection_mode': 'fresh-experimental'}, True)
        self.assertEqual(install.registration_action({**old, 'protection_mode': 'fresh-experimental',
            'fresh_protection_version': 2}, True), 'apply')

    def test_prepare_with_empty_accessory_zone_needs_no_template(self):
        keys = [ec.generate_private_key(ec.SECP256R1())]
        zone = ck.Record().record_identifier.zone_identifier
        zone.value.name = 'BeaconStore'
        value = SimpleNamespace(_password=None, close=AsyncMock())
        device = SimpleNamespace(describe=lambda: 'Synthetic device')
        session = SimpleNamespace(recovery_options=AsyncMock(return_value=SimpleNamespace(recoverable=[device])),
            recover=AsyncMock(return_value=object()), pcs_keys=AsyncMock(return_value=keys), close=AsyncMock())
        encoded, _ = create_protection(keys, signing_key=keys[0])
        client = SimpleNamespace(zone_retrieve=AsyncMock(return_value=[SimpleNamespace(target_zone=SimpleNamespace(
            zone_identifier=zone, protection_info=SimpleNamespace(protection_info=encoded)))]))
        store = SimpleNamespace(zone_keys=AsyncMock(return_value=keys), fetch_records=AsyncMock(return_value=[]),
            client=client, close=AsyncMock())
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            with patch.object(register, 'STATE', state), patch.object(register, 'private_directory'), \
                 patch.object(register, 'account', return_value=value), patch.object(register, 'cloud_account', return_value=object()), \
                 patch.object(register.AsyncKeychainSession, 'open', new=AsyncMock(return_value=session)), \
                 patch.object(register, 'AsyncBeaconStore', return_value=store), \
                 patch.object(register, 'unwrap_protection', return_value=SimpleNamespace(private_keys=keys)), \
                 patch.object(register, 'select_zone_identity', return_value=keys[0]) as select_identity, \
                 patch.object(register.getpass, 'getpass', return_value='synthetic'), patch('builtins.input', return_value='0'):
                asyncio.run(register.prepare('Synthetic tracker', '🧪'))
            import json
            manifest = json.loads((state / 'registration.json').read_text())
            self.assertEqual(manifest['protection_mode'], 'fresh-experimental')
            self.assertEqual(manifest['baseline_ids'], [])
            self.assertEqual(manifest['creation_attempted'], [])
            self.assertEqual(manifest['status'], 'prepared')
            self.assertEqual(manifest['fresh_protection_version'], 2)
            select_identity.assert_called_once()
