"""Own CloudKit candidate construction. No network or credentials in this module."""
import secrets, uuid
from datetime import datetime, timezone
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from findmy.cloudkit.proto import cloudkit_pb2 as ck
from findmy.cloudkit.constants import ValueType as V
from findmy.cloudkit.beacons import build_plaintext, interpret_plaintext, accessory_from_record, DecryptedRecord
from findmy.cloudkit.pcs import UnwrappedProtection, FieldContext, encrypt_field, decrypt_field, ShareProtection, unwrap_protection
from findmy.keys import KeyPairType

APPLE_EPOCH = datetime(2001,1,1,tzinfo=timezone.utc)

def plaintext(typ, value):
    if typ == V.DATE_TYPE:
        wrapper = ck.EncryptedValue()
        wrapper.date_value.time = (value-APPLE_EPOCH).total_seconds()
        return wrapper.SerializeToString()
    return build_plaintext(typ,value)

def make_identity(name='ESP32 Tracker', emoji='📍'):
    private = ec.generate_private_key(ec.SECP224R1())
    scalar = private.private_numbers().private_value.to_bytes(28,'big')
    public = private.public_key().public_bytes(Encoding.X962,PublicFormat.UncompressedPoint)
    identifier = str(uuid.uuid4()).upper()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return {
        'id':identifier, 'naming_id':str(uuid.uuid4()).upper(), 'name':name,
        'master':{
            'privateKey':(V.ENCRYPTED_BYTES_TYPE,public+scalar),
            'publicKey':(V.ENCRYPTED_BYTES_TYPE,public),
            'sharedSecret':(V.ENCRYPTED_BYTES_TYPE,secrets.token_bytes(32)),
            'sharedSecret2':(V.ENCRYPTED_BYTES_TYPE,secrets.token_bytes(32)),
            'pairingDate':(V.DATE_TYPE,now),
            'model':(V.STRING_TYPE,'ESP32'),
            'systemVersion':(V.STRING_TYPE,'1.0'),
            'vendorId':(V.INT64_TYPE,76),
            'productId':(V.INT64_TYPE,21760),
            'stableIdentifier':(V.STRING_TYPE,f'2001~#{uuid.UUID(identifier).hex[:16].upper()}~#{uuid.UUID(identifier).hex[-12:].upper()}'),
            'isZeus':(V.INT64_TYPE,0),
            'batteryLevel':(V.INT64_TYPE,100),
        },
        'naming':{
            'name':(V.STRING_TYPE,name),
            'emoji':(V.STRING_TYPE,emoji),
            'associatedBeacon':(V.STRING_TYPE,identifier),
            'roleId':(V.INT64_TYPE,999),
        },
    }

def build_record(identifier, kind, values, protection, template=None, *, protection_info=None, zone_identifier=None):
    if template is not None and (protection_info is not None or zone_identifier is not None):
        raise ValueError('Cannot combine a template and a fresh envelope')
    record = ck.Record()
    if template is not None:
        # Preserve the zone addressing and recipient wrapping, never old fields/IDs.
        record.record_identifier.zone_identifier.CopyFrom(template.record_identifier.zone_identifier)
        record.protection_info.protection_info = template.protection_info.protection_info
    else:
        record.record_identifier.zone_identifier.value.name = 'BeaconStore'
        if zone_identifier is not None:
            record.record_identifier.zone_identifier.CopyFrom(zone_identifier)
        if protection_info is not None:
            record.protection_info.protection_info = protection_info
    record.record_identifier.value.name = identifier
    record.type.name = kind
    for name,(typ,value) in values.items():
        f = record.record_field.add()
        f.identifier.name = name
        f.value.type = typ
        f.value.is_encrypted = True
        f.value.bytes_value = encrypt_field(plaintext(typ,value),protection,FieldContext('BeaconStore',identifier,name))
    return record

def decode_local(record, protection):
    values={}
    for f in record.record_field:
        context=FieldContext('BeaconStore',record.record_identifier.value.name,f.identifier.name)
        values[f.identifier.name]=interpret_plaintext(f.value.type,decrypt_field(f.value.bytes_value,protection,context))
    return values

def check_candidate(identity, master, naming, p_master, p_naming):
    mv=decode_local(master,p_master);nv=decode_local(naming,p_naming)
    acc=accessory_from_record(DecryptedRecord(name=identity['id'],record_type='MasterBeaconRecord',values=mv),
        naming=DecryptedRecord(name=identity['naming_id'],record_type='BeaconNamingRecord',values=nv))
    assert acc.name==identity['name']
    assert acc.identifier==nv['associatedBeacon']
    assert len(acc.master_key)==28 and len(acc.skn)==32 and len(acc.sks)==32
    schedule=[]
    for index in range(48):
        key=next(k for k in acc.keys_at(index) if k.key_type==KeyPairType.PRIMARY)
        # Public broadcast material only; no derived private keys are exported here.
        schedule.append({'index':index,'offset_seconds':index*900,'mac':key.mac_address,
                         'advertisement':key.adv_data().hex()})
    assert len({x['advertisement'] for x in schedule})==48
    return acc,schedule
