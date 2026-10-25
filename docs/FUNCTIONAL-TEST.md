# Functional test before publishing local changes

The security-review changes have offline tests. They still require a fresh,
interactive end-to-end run against Apple. A unit test or successful readback is
not evidence that Find My accepts a new record.

## 1. Start from a clean extraction

Use only the clean source ZIP. Do not copy `private/`, `.deps/`, `.venv/`, machine
identities or tracker headers from another installation. Use the intended second
ESP32 only; disconnect other boards. Keep the original working tracker's state
and firmware untouched. Use your own account and enter credentials only in the
local terminal. Check the selected USB port before starting.

From the extracted directory:

```bash
unset ESP32_FINDMY_STATE
chmod +x scripts/*.sh
./scripts/install.sh --port /dev/ttyUSB0 --name 'ESP32 Review-Test' --emoji '🧪' --verify-ble
```

Adjust the port. `--verify-ble` requires a working Linux Bluetooth adapter.
Normal setup downloads dependencies and Apple's runtime; installation then
backs up and overwrites this board. It creates one new pair of cloud records.
The installer must not silently reuse another installation's credentials or
registration. Existing per-user service pauses remain effective.

Expected checks:

- Dependency source/hash checks and wheel build succeed from the clean ZIP.
- A verified, board-bound original flash backup is saved before flashing.
- Login, device selection and the selected device's screen-unlock passcode work.
  Do not deliberately submit a wrong passcode to test error handling.
- Fresh PCS preparation needs no existing accessory encryption template.
- Two new records are read back using a complete snapshot. Existing baseline
  records remain unchanged. A resumed installation reuses these same two IDs.
- Firmware build/upload succeeds; serial key checks and exact BLE payload match.
- On normal exit, `login.json`, `session.json` and `auth/` are removed locally.
  Tracker keys, registration journal, machine identity and flash backup remain.

## 2. Validate on the iPhone or iPad

Reopen Find My and check the uniquely named new item. Change its name and emoji,
then verify the changes persist. Keep the ESP32 powered near a participating
Apple device and wait for a location. Roughly 30 minutes was observed previously;
this is not a maximum. Record only pass/fail and elapsed time, never coordinates.

Disconnect/reconnect the ESP32's power and confirm that BLE broadcasts resume.
A fresh location upload after power cycling has no guaranteed delay. Nearby
search, UWB and sound playback are not acceptance criteria: they are unsupported.

## 3. Check status and targeted removal

After the installer has logged out, sign in deliberately using the same private
state, inspect the registration and remove only this test item:

```bash
./scripts/login.sh
./scripts/register.sh status
./scripts/register.sh remove
./scripts/logout.sh
```

Removal must succeed even after the name/emoji edits. It must be confirmed by a
complete final snapshot. Confirm in Find My that this test item disappears and
that the original tracker and genuine devices remain. Retain the private journal
and backup until all checks pass. Removing the item does not stop the ESP32's
BLE transmissions; disconnect its power or restore its original firmware.

## If a step fails

Stop at the first unexplained failure. Keep the same private directory and
journal. Do not regenerate IDs, remove state or repeatedly log in. Share only the
step, error classification/status and sanitized output.

A recovery interruption/rejection leaves a local block; use `recovery-status`
before explicitly permitting one manual retry as described in Troubleshooting.
A 401 requires a deliberate login. A 429 respects the service pause. Neither
failure automatically retries remote cleanup. `cleanup_pending` means the test
records may still exist; finish targeted removal after resolving the cause.
Do not induce live 401/429 responses or kill a live recovery to test these paths;
the offline failure tests cover them without consuming Apple attempts.

Publish only after setup, native display/edit/location and targeted removal all
pass. A success on the original account does not validate empty accounts or
other users' accounts.
