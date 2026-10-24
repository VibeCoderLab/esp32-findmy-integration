"""Experimental new PCS record envelopes, addressed to the current account's zone.

No accessory record, recipient ciphertext or record master key is reused.
The zone-signed update was displayed with a location in one live account.
A fresh-ZIP installation passed on that account; other accounts remain untested. This does not
create a missing BeaconStore zone.
"""
from dataclasses import replace
import hashlib
import hmac
import secrets
import struct

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.keywrap import aes_key_wrap
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from findmy.cloudkit import der, pcs

from common import WorkflowError


def tlv(tag, body):
    return bytes([tag]) + der.encode_length(len(body)) + body


def sequence(*parts):
    return tlv(0x30, b''.join(parts))


def integer(value):
    if value < 0:
        raise ValueError('Only nonnegative protocol integers are supported')
    return tlv(2, value.to_bytes(max(1, (value.bit_length() + 8) // 8), 'big'))


def octets(value):
    return tlv(4, value)


def wrap_key(recipient, master):
    if not isinstance(recipient.curve, ec.SECP256R1) or len(master) != 16:
        raise WorkflowError('A fresh PCS envelope requires P-256 zone recipients and a 16-byte key.')
    ephemeral = ec.generate_private_key(ec.SECP256R1())
    shared = ephemeral.exchange(ec.ECDH(), recipient)
    # PCS's RFC 6637 parameter block is defined by the pinned dependency.
    kek = hashlib.sha256(struct.pack('>I', 1) + shared + pcs._RFC6637_PARAM).digest()[:16]
    framed = b'\x01' + master + (sum(master) % 65536).to_bytes(2, 'big')
    # Match the observed RFC6637 length-hiding frame: at least 40 octets
    # before AES wrapping, not merely the next 8-octet boundary.
    padded_length = max(40, ((len(framed) // 8) + 1) * 8)
    pad = padded_length - len(framed)
    wrapped = aes_key_wrap(kek, framed + bytes([pad]) * pad)
    point = ephemeral.public_key().public_numbers().x.to_bytes(32, 'big')
    return b'\x01\x00' + point + bytes([len(wrapped)]) + wrapped


def signature_der(value):
    return sequence(octets(value.key_id), integer(value.digest), octets(value.signature))


def object_der(value):
    return sequence(integer(value.roll_count), integer(value.outer_sign_key_type),
                    sequence(integer(value.public.key_type), octets(value.public.public_key)),
                    signature_der(value.signature))


def create_protection(zone_keys, *, signing_key=None):
    """Return fresh DER and a strictly verified, locally usable field key."""
    if not zone_keys:
        raise WorkflowError('No existing BeaconStore zone keys; a new zone will not be created.')
    recipients = {}
    private_recipients = []
    for key in zone_keys:
        if not isinstance(key.curve, ec.SECP256R1):
            raise WorkflowError('Unknown curve in BeaconStore zone keys.')
        # PCS key type 3 uses the compact P-256 x coordinate; both y roots
        # produce the same ECDH shared x coordinate.
        public_key = key.public_key() if isinstance(key, ec.EllipticCurvePrivateKey) else key
        if isinstance(key, ec.EllipticCurvePrivateKey):
            private_recipients.append(key)
        recipients[public_key.public_numbers().x.to_bytes(32, 'big')] = public_key
    if signing_key is not None:
        if not isinstance(signing_key, ec.EllipticCurvePrivateKey) or not isinstance(signing_key.curve, ec.SECP256R1):
            raise WorkflowError('The outer PCS signature requires a private P-256 zone key.')
        if signing_key.public_key().public_numbers().x.to_bytes(32, 'big') not in recipients:
            raise WorkflowError('The PCS signer is not a recipient of this zone.')
    master = secrets.token_bytes(16)
    entries = [sequence(sequence(integer(3), octets(public)), octets(wrap_key(key, master)), integer(0))
               for public, key in recipients.items()]
    keyset = sequence(integer(0), tlv(0x31, b''.join(sorted(entries))))
    field_key = pcs.UnwrappedProtection(master, False, False, True, True)
    # Observed empty metadata structure, containing no device/account data:
    # SEQUENCE { [1] SEQUENCE { INTEGER 0, OCTET STRING empty } }.
    empty_meta = sequence(tlv(0xa1, sequence(integer(0), octets(b''))))
    meta = pcs.encrypt_field(empty_meta, field_key, pcs.FieldContext.none())
    signer = ec.derive_private_key(pcs.derive_master_ec_private_key(master), ec.SECP256R1())
    # The object-signature public KeyRef uses type 1 / uncompressed X9.62.
    public = signer.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    obj = pcs.ObjectSignature(roll_count=0, outer_sign_key_type=3 if signing_key is not None else 0,
        public=pcs.KeyRef(1, public), signature=pcs.Signature(b'', 1, b''))
    draft = pcs.ShareProtection([], meta, pcs.SignatureData(5, b''), b'',
        pcs.compute_key_id(master)[:4], keyset_der=keyset)
    signed = signer.sign(pcs.build_signed_data(draft, obj), ec.ECDSA(hashes.SHA256()))
    obj = replace(obj, signature=pcs.Signature(b'', 1, signed))
    object_bytes = object_der(obj)
    signature_data = sequence(integer(5), octets(object_bytes))
    mac = hmac.new(pcs.derive_hmac_key(master), keyset + meta + object_bytes, hashlib.sha256).digest()
    outer = b''
    if signing_key is not None:
        message = pcs.build_signed_data(draft, obj)
        signed_outer = signing_key.sign(message, ec.ECDSA(hashes.SHA256()))
        outer = tlv(0xa3, signature_der(pcs.Signature(
            signing_key.public_key().public_numbers().x.to_bytes(32, 'big'), 1, signed_outer)))
    encoded = tlv(0x61, sequence(keyset, tlv(0xa0, octets(meta)), tlv(0xa1, signature_data),
        octets(mac), tlv(0xa2, octets(pcs.compute_key_id(master)[:4])), outer))
    parsed = pcs.ShareProtection.from_der(encoded)
    if not pcs.verify_protection_hmac(parsed, master) or not pcs.verify_protection_signature(parsed, master):
        raise WorkflowError('Local HMAC/signature verification failed.')
    if signing_key is not None:
        signing_key.public_key().verify(parsed.signature.signature,
            pcs.build_signed_data(parsed, pcs.ObjectSignature.from_der(parsed.signature_data.data)),
            ec.ECDSA(hashes.SHA256()))
    for key in private_recipients:
        unwrapped = pcs.unwrap_protection(parsed, [key], require_hmac=True, require_signature=True)
        if (unwrapped.master_key != master or unwrapped.read_only
                or not unwrapped.hmac_verified or not unwrapped.signature_verified):
            raise WorkflowError('Fresh PCS envelope self-test failed.')
        if pcs.decrypt_field(meta, unwrapped, pcs.FieldContext.none()) != empty_meta:
            raise WorkflowError('Fresh PCS envelope metadata self-test failed.')
    return encoded, field_key


def build_fresh_records(identity, zone_keys, zone_identifier, *, signing_key):
    from records import build_record
    records, protections = [], []
    for ident, kind, values in (
        (identity['id'], 'MasterBeaconRecord', identity['master']),
        (identity['naming_id'], 'BeaconNamingRecord', identity['naming']),
    ):
        if signing_key is None:
            raise WorkflowError('The published zone identity key required for fresh PCS envelopes is missing.')
        encoded, protection = create_protection(zone_keys, signing_key=signing_key)
        record = build_record(ident, kind, values, protection,
            protection_info=encoded, zone_identifier=zone_identifier)
        records.append(record)
        protections.append(protection)
    return records, protections
