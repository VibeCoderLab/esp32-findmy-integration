# Design and validation

1. `os-findmy-e` produces Anisette headers by running Apple's CoreADI under local
   emulation. The login session is held in a private directory during setup and
   deleted when the installer exits. Machine provisioning and tracker keys remain.
2. Keychain recovery reads available PCS zone keys without adding a new member
   to the keychain trust circle.
3. By default, new CloudKit records use fresh PCS envelopes signed with the
   published zone identity and wrapped for the recovered zone key. No accessory
   encryption template is needed. Their encrypted fields are bound to the new
   record ID and field name. The explicit legacy `--template-protection` mode
   reuses recipient wrapping from decryptable records. Existing accessory keys
   are not copied or overwritten. See
   [validation status and limitations](FRESH-PROTECTION.md).
4. A new `MasterBeaconRecord` holds the tracker's own P-224 keys and two rolling
   secrets. A `BeaconNamingRecord` references its new UUID and carries the name
   and emoji.
5. The firmware derives primary keys using X9.63 KDF/SHA-256 and P-224, then
   broadcasts Apple Offline Finding advertisements. Nearby reporting devices
   encrypt their location; the owner can decrypt matching reports.

## Product profile

The descriptive Apple/AirTag values come from public
[OpenTagViewer test exports](https://github.com/parawanderer/OpenTagViewer/tree/main/app/src/test/resources/19032025):
vendor 76, product 21760, role 999, and the identifier format
`2001~#<16 hex characters>~#<12-character serial>`. The hardware and serial
identifiers are generated independently. No keys or serial identifiers from
those exports are copied.

In the original experiment, an item with unknown product identifiers could be
located but could not be renamed in Apple's app. The known AirTag class allowed
name/emoji editing and location display without a third-party manufacturer's
app link. Changing product metadata under an existing record ID sometimes left
the old classification visible; a fresh record picked up the new class. The
app's exact internal classification and caching behavior has not been established.

This is not MFi certification or an implementation of official accessory
pairing. UWB Precision Finding and a speaker are not implemented. A product label
in Find My does not add that hardware. The model text stored in CloudKit may not
override the name displayed from Apple's product catalog.

## Validation status

- Original hardware: a classic ESP32 board with 4 MB flash. BLE reception and
  key derivation were checked; the user confirmed native location display and
  name/emoji editing.
- Public source version: offline encryption round trips, reference key rotation,
  bounded creation/removal, export exclusions, and a firmware build were tested
  without a live Apple account.
- A complete fresh setup with a second real account has not been performed.
  Empty accounts without an existing BeaconStore zone, other ESP32 chip families,
  and future Apple interface changes are not validated.

Protocol reference:
[OpenTagViewer findmy-export](https://github.com/parawanderer/OpenTagViewer/tree/main/docs/findmy-export).
