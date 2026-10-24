# ESP32 Find My — experimental tracker for Linux

Project prompts, progress messages and errors are in English, independent of the system language. External tools may use their own language settings.

[Deutsch](README.de.md)

ESP32 firmware and Linux tools for an experimental item in Apple's **Find My**
app. No Mac or physical AirTag is required. The ESP32 broadcasts Bluetooth Low
Energy (BLE) beacons; nearby Apple devices can upload encrypted location reports.
The ESP32 itself has no GPS.

**Feature limits:** Native nearby search, UWB Precision Finding and sound playback
are not supported.

The original hardware experiment successfully displayed a location in Find My
and allowed the item's name and emoji to be edited using an AirTag product
profile. This public version generates **new keys and identifiers for each
installation**. Its offline tests and firmware build can be checked without an
Apple account. A fresh-ZIP setup passed on the original account. Setup with a different
account still needs independent validation. Apple may change these private interfaces
at any time.

## Requirements

- Linux, Python 3.12, Git, `curl`, `7z`, and [uv](https://docs.astral.sh/uv/).
- A classic ESP32 with BLE, such as an ESP32-D0WD/ESP32-WROOM board.
  **ESP32-S2 does not support BLE.** Other ESP32 chip families have not been
  tested with this firmware configuration.
- A USB data cable and permission to access the board's serial port.
- A Linux Bluetooth adapter if you want to run the optional BLE verification.
- Your own Apple account with two-factor authentication and a recoverable
  iCloud Keychain device identity. You must know that device's screen-unlock
  passcode.
- An existing BeaconStore zone and recoverable zone keys in your Apple account.
  **An empty or newly created Apple account has not been demonstrated to work.**

The default installation generates fresh record encryption envelopes locally,
without copying encryption templates from accessories. No AirTag, AirPods or
other accessory is required as a template. This method remains experimental.
`--fresh-protection` is accepted for compatibility but is no longer necessary.
The legacy template mode is available only with `--template-protection`; it
requires existing, decryptable `MasterBeaconRecord` and `BeaconNamingRecord`
records. Existing template installations must explicitly select that legacy
mode to resume; the installer will not silently replace their registration.

A corrected, zone-signed envelope update was confirmed visible with a location on an Apple device in one
account. A subsequent fresh-ZIP installation also passed visibility, name/emoji
editing and location checks on that account. Empty-account setup remains unverified. See
[experimental setup and limitations](docs/FRESH-PROTECTION.md).

The tools create one new pair of records for your tracker. They do not rewrite
existing devices. Use this project only with accounts, devices, and belongings
that you own.

## Recommended: one-command installation

With the prerequisites above installed and only the intended 4 MB classic ESP32
connected, run this from the extracted project directory:

```bash
chmod +x scripts/*.sh
scripts/install.sh --port /dev/ttyUSB0 --name 'ESP32 Tracker' --emoji '📍'
```

Replace the port with your board's port. This command installs dependencies,
checks the board, saves its original flash, handles Apple login and local key
preparation, creates the two CloudKit records, builds and uploads the firmware,
verifies the board's key derivation over serial, and fetches location reports.
Passwords and verification/passcodes are entered interactively in the terminal.
Add `--verify-ble` to also require a Linux Bluetooth adapter to receive the beacon.

The installer overwrites the selected board's firmware. Its private backup is
`private/installer-flash-before.bin`. The accompanying `installer-board.json`
binds that backup to the board's hardware MAC and SHA-256. A different board or
changed backup is refused. Registered keys/record IDs are reused when resuming;
partial failures do not silently create another tracker. The installer removes
local Apple session tokens on success, errors, and handled interruptions. A
resumed installer asks you to log in again; tracker keys and backups are retained.
Manual commands can retain a session; run `scripts/logout.sh` to remove it.
This local logout does not revoke sessions on Apple's servers. An uncatchable
termination or power loss can prevent cleanup; run `scripts/logout.sh` afterward.

Find My's final display still needs checking on the iPhone/iPad. Zero location
reports immediately after flashing are not necessarily an error.
**Allow roughly 30 minutes for the first location to appear in Find My.** This
delay was observed in testing; it is not a guaranteed maximum, and longer delays
are possible. Keep the tracker powered near a participating Apple device.

The following sections describe the same workflow as separate commands for
manual operation and troubleshooting.

## 1. Install dependencies

Extract this project into its own directory and open a terminal there:

```bash
cd esp32-findmy-public
chmod +x scripts/*.sh
scripts/setup.sh
```

The setup script downloads a pinned revision of
[os-findmy-e](https://github.com/sacca97/os-findmy-e), installs the Python
requirements into `.venv/`, and uses the upstream downloader to obtain CoreADI
from Apple's iTunes download. The downloader verifies its SHA-256 checksum.
Apple's libraries are **not distributed with this project**. The patches in
`patches/` adjust login diagnostic output and set the local HTTP-429 cooldown
to five minutes. There is no automatic login retry; Apple's actual rate-limit
duration may differ.

By default, **all account data is stored in `private/`**. To use another private
location, set `ESP32_FINDMY_STATE` to the same directory before every command.
The project's `.gitignore` cannot protect an arbitrary external directory;
never copy that directory into a repository.

## 2. Sign in locally

```bash
scripts/login.sh
```

On its first run, the login helper provisions a new emulated machine before
requesting your Apple account credentials. Later runs reuse that same machine.
If an existing identity is incomplete or missing while a saved session exists,
the helper stops rather than silently creating a replacement.

Enter your Apple account, password, and a fresh verification code only in your
local terminal. By default, the helper requests an SMS code for the first
trusted phone number on the account.

The password and device passcode are not saved. **Session tokens and the
emulated machine identity are saved.** These are credentials that allow later
account access; protect them accordingly.

The emulated machine may appear in your Apple account's device list. Its
identity is reused for subsequent requests rather than regenerated on every run.

## 3. Prepare your tracker locally

```bash
scripts/register.sh prepare --name 'ESP32 Tracker' --emoji '📍'
```

This step asks for the Apple account password again to obtain a fresh recovery
token. The password is kept only in memory. Select your own device and enter
its **screen-unlock passcode** — not an SMS code or SIM PIN.

There is one recovery attempt and no automatic passcode retry. A failed attempt
creates `private/recovery-blocked.json` to prevent further automatic attempts.
See [Troubleshooting](docs/TROUBLESHOOTING.md) before trying again.

The recovery flow reads the keychain without adding a new member to its trust
circle. It does not copy existing accessory keys. Instead, it generates new
P-224 keys, rolling secrets, UUIDs, and hardware/serial identifiers for your own
tracker. **No new CloudKit records are written during preparation.** Running
`prepare` again does not overwrite an existing registration or its keys.

The product profile uses values from public test exports:
`vendorId=76`, `productId=21760`, `roleId=999`, and identifier prefix `2001`.
Consequently, Find My may display the item as **AirTag/Apple**. This does not
register a custom manufacturer. The stored model text is `ESP32`, and the stored
version text is `1.0`; these fields do not change the ESP32 hardware. The stored
battery level is a fixed placeholder, not a measured battery percentage.
See [Design and validation](docs/DESIGN.md).

## 4. Create the two prepared records

```bash
scripts/register.sh apply
scripts/register.sh status
```

`apply` creates only the two new record IDs recorded in the local journal and
then fetches them again to verify the result. It does not write existing
records. If creation fails partway through, the tool attempts to remove its own
partially created pair. The journal remains available for a later targeted
removal.

Reopen Find My on your iPhone or iPad and look for the new item under **Items**.
The AirTag profile is intended to allow editing its name and emoji, but the
actual result must be confirmed in Apple's app. No location is expected until
the ESP32 is broadcasting and a nearby Apple device has reported it.

## 5. Back up, build, and flash the ESP32

Identify the correct serial port:

```bash
ls -l /dev/serial/by-id/
```

If necessary, add your user to your distribution's serial-access group and
start a new login session. On many Linux distributions, that group is called
`dialout`. Check the board and flash size before proceeding:

```bash
uvx --from esptool==5.6.0 esptool --port /dev/ttyUSB0 flash-id
umask 077
mkdir -p private
chmod 700 private
uvx --from esptool==5.6.0 esptool --port /dev/ttyUSB0 --baud 460800 read-flash 0 0x400000 private/flash-before.bin
```

Replace `/dev/ttyUSB0` with your board's port. `0x400000` is the size of the
**4 MB board used in testing**; adjust it for a different flash size. Keep this
backup private.

Build and upload:

```bash
scripts/build.sh
scripts/build.sh --target upload --upload-port /dev/ttyUSB0
```

The build generates `firmware/include/device_secrets.h` from your own tracker
keys. **That header and the resulting BIN/ELF files contain private tracking
keys. Never publish them or attach them to GitHub releases.** Uploading replaces
the selected board's bootloader, partition table, and application firmware.

After power-up, the tracker starts automatically. It broadcasts approximately
once per second and rotates its primary key every 15 minutes. The current index
and seed are stored in NVS. While power is disconnected, key rotation pauses;
after restarting, it resumes from the saved state. The PC does not need to stay
on for the ESP32 to broadcast.

## 6. Verify the beacon and fetch locations

For optional verification, use a Linux BLE adapter and make sure no other
program has the serial port open. After using the one-command installer, run
`scripts/login.sh` before fetching reports: its automatic logout has removed
the account session. Serial/BLE verification itself needs no Apple login:

```bash
.venv/bin/python host/verify.py --port /dev/ttyUSB0
scripts/fetch.sh

# Optional: include precise coordinates in the output
scripts/fetch.sh --show-location
```

`verify.py` resets the board, checks the current and next key derivations against
FindMy.py, and receives the exact expected BLE payload. Checking the next key
does **not** observe a complete, timed 15-minute rollover. Receiving a BLE beacon
does not prove that an Apple device has uploaded a location report.

A location report requires a participating Apple device within Bluetooth range.
There is no guaranteed reporting interval. Fetching reports does not trigger an
upload, and Find My may take time to display reports that are already available.

**Precision Finding/UWB and playing a sound are not implemented in this
firmware**, even if Find My displays controls associated with the AirTag profile.

For battery operation, see the [power review](docs/POWER.md). No measured battery
life or validated low-power profile is claimed. The [source/export review](docs/RELEASE-REVIEW.md)
describes the privacy checks and remaining release work.

## Remove the item or restore the board

To remove this project's own registered pair, sign in again if the installer
has already logged out:

```bash
scripts/login.sh
scripts/register.sh remove
scripts/logout.sh
```

This targets only the two IDs in the local journal, including after a name or
emoji change in Find My. Unexpected key or association changes cause removal
to be refused. Existing devices are not removed. The saved session must still
be valid.

Keep the local registration journal until removal has been confirmed. Deleting
it first loses the record-ID mapping needed for targeted cleanup. Removing the
item does not erase the ESP32 or revoke your Apple session.

To restore the original backup made by the one-command installer (replace
the port with the correct board's port):

```bash
uvx --from esptool==5.6.0 esptool --port /dev/ttyUSB0 --baud 460800 write-flash 0 private/installer-flash-before.bin
```

If you instead followed the manual backup steps above, use
`private/flash-before.bin`. Restoring either backup overwrites the board's firmware.
After manual location queries, run `scripts/logout.sh` to remove saved sessions.


Read [Security](SECURITY.md) before sharing logs or troubleshooting data.

## License and credits

The project's own code is MIT-licensed. Dependencies retain their respective
licenses; see [Third-party components](THIRD_PARTY.md).

This is an independent experiment and is not affiliated with or endorsed by
Apple. Apple, AirTag, and Find My are trademarks of their respective owners.
