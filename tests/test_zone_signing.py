import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'host'))
from cryptography.hazmat.primitives.asymmetric import ec
from zone_signing import select_zone_identity
from fresh_protection import sequence, integer, octets
from common import WorkflowError


class ZoneSigningTests(unittest.TestCase):
    def test_published_identity_selected_even_when_not_first_private_key(self):
        unrelated=ec.generate_private_key(ec.SECP256R1())
        published=ec.generate_private_key(ec.SECP256R1())
        raw=sequence(sequence(integer(3),octets(published.public_key().public_numbers().x.to_bytes(32,'big'))))
        self.assertIs(select_zone_identity(raw,[unrelated,published]),published)
        self.assertIs(select_zone_identity(raw,[published,unrelated]),published)
        with self.assertRaises(WorkflowError):select_zone_identity(raw,[unrelated])

    def test_missing_or_ambiguous_reference_does_not_guess(self):
        one=ec.generate_private_key(ec.SECP256R1());two=ec.generate_private_key(ec.SECP256R1())
        with self.assertRaises(WorkflowError):select_zone_identity(b'',[one])
        raw=sequence(*[sequence(integer(3),octets(k.public_key().public_numbers().x.to_bytes(32,'big'))) for k in (one,two)])
        with self.assertRaises(WorkflowError):select_zone_identity(raw,[one,two])
