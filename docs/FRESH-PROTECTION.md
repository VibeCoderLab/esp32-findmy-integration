# Experimental record envelopes without accessory templates

The default installation constructs new PCS protection structures from the
current account's BeaconStore zone, without accessory-record encryption templates.
The method remains experimental. `--fresh-protection` is still accepted but is
no longer required. `--template-protection` explicitly selects the legacy
accessory-template mode; existing template registrations are never silently
converted to the new default.

## Live result and its limits

On 24 October 2026, the owner confirmed that a test item using corrected,
independently generated zone-signed envelopes appeared in Find My **with a
location**. The final change updated the envelopes of an already created test
pair, preserving its tracker keys and record IDs. Existing accessory envelopes
were not used to construct the replacement envelopes.

Earlier unsigned envelopes, and envelopes signed with an unadvertised recovered
key, passed local checks but did not produce a visible item. Mathematical
signature validity alone did not establish that the selected signer was the
zone's published identity. Device-template comparisons also did not establish a
working alternative.

A subsequent full run from a fresh ZIP extraction on the same account completed
initial record creation, flashing and BLE verification. The owner confirmed the
new item, name/emoji editing and finally a location in Find My. The first location
took roughly half an hour to appear. This is an observed allowance, not a
guaranteed maximum; longer delays are possible, including after reports become
available to the fetch tool.

An account without accessories or without a BeaconStore zone has not been
tested. These results do not establish universal compatibility or certification.

## General format, account-specific recipients

The format and algorithms are general protocol logic. No account keys,
recipient identities, protection structures or tracker keys are distributed.
After login and one device-passcode recovery, the program:

1. Unwraps the current account's existing BeaconStore zone and verifies its
   HMAC and object signature.
2. Reads the zone object's public EC identity references. It requires exactly
   one matching recovered private identity key; it never chooses the first
   arbitrary recovered key or falls back to an accessory.
3. Generates an independent random 16-byte PCS master key for each new record,
   wrapping it to that zone identity using fresh ephemeral P-256 ECDH and AES
   key wrap, including the observed length-hiding padding.
4. Builds the observed empty metadata structure, inner master-key signature,
   **outer zone-identity signature**, HMAC and truncated key identifier.
5. Verifies both signatures and the HMAC, unwraps and decrypts locally, and
   encrypts the new tracker's independently generated keys and metadata.

The zone address is preserved. Existing records are fetched only for the
unchanged-record baseline; no accessory protection template is consumed. Master
and naming records receive independent PCS master keys.

## Remaining requirements

Authentication, a recoverable iCloud Keychain identity, the selected device's
unlock code, an existing BeaconStore zone and usable published zone identity are
still required. This does not create a missing zone or enroll a new trust peer.
Missing or ambiguous zone identities stop preparation without guessing.

Local tests use the pinned FindMy.py reader. These checks supplement the live
result; they cannot establish how every Apple client or account will behave.

## Fresh installation test

Use a new extraction/state so an earlier preparation is not reused:

```bash
unset ESP32_FINDMY_STATE
scripts/install.sh --port /dev/ttyUSB0 --name 'ESP32 PCS Test' --emoji '🧪' --fresh-protection --verify-ble
```

`scripts/register.sh prepare --fresh-protection` prepares locally without cloud
writes. The installer subsequently applies the pair and flashes the board.
The installer refuses older experimental preparations without the corrected
format-version marker. Preserve their journals for targeted cleanup; do not
silently convert them by changing the flag or deleting private state.

Flashing new tracker keys stops the board from reporting under its previous
item's keys. Existing cloud items are not automatically removed. The public
installer logs out locally at completion or failure.

Confirm the new item, name/emoji editing and location in Find My. Cloud save and
readback or BLE reception alone are insufficient. To remove only this test pair,
log in and run `scripts/register.sh remove`, then `scripts/logout.sh`.
