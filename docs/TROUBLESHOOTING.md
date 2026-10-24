# Troubleshooting

- **Apple HTTP 429:** A five-minute local cooldown blocks further requests after
  a rate-limit response. There is no automatic login retry; rerun the command
  manually after the cooldown. Five minutes is a local setting, not a promised
  server recovery time. Without a `Retry-After` header, Apple's wait time is unknown.

- **Could not resolve host / Apple download failed:** DNS or network access
  failed before Apple login or flashing. The download retries three times;
  only an archive with the pinned SHA-256 is accepted. Incomplete downloads
  are discarded. Check the connection and rerun the same installer command.

- **No USB port:** Check the data cable, USB-UART driver, and serial-access group
  permissions. Close any serial monitor before using the port with another tool.
- **Packet content transfer stopped:** This is a serial-transfer failure. The
  installer tries a backup at 1500000 baud, waits after resets, and retries an
  interrupted backup once at 115200 baud. Firmware upload uses 2000000 baud;
  if your board cannot upload reliably at that speed, lower `upload_speed` in
  `firmware/platformio.ini` to 230400 or 115200 before retrying.
  A 4-MB backup can take several minutes at the fallback speed. Keep the same private
  state and rerun the installer; it reuses verified backups and registrations.
  If it still fails, try a short data cable and a direct USB port without a hub.
- **No verification code:** The login requests an SMS to the first trusted phone
  number. Apple may limit logins or SMS requests; avoid repeated rapid attempts.
- **Recovery rejected:** Use the selected device's screen-unlock passcode. A wrong
  passcode and a protocol problem may produce the same rejection. Do not guess
  passcode variations. The guard blocks automatic retries. Only after checking
  the cause and correct passcode, deliberately move `recovery-blocked.json` out
  of the private state directory and make at most one new manual attempt.
  Recovery attempts may be limited.
- **Missing BeaconStore zone / zone identity:** The default mode generates new
  record envelopes but still needs an existing zone and recoverable keys. It
  does not create a new zone or keychain trust structure.
- **No PCS template:** This applies to explicit legacy `--template-protection`
  mode only. The default mode does not need accessory encryption templates.
- **HTTP 401 / expired session:** Keep the same machine state and run
  `scripts/login.sh` again. Do not regenerate the entire state directory.
- **Login requested on every installer run:** This is expected. The installer
  deletes local account sessions when it exits. It retains the tracker keys,
  registration journal and machine provisioning, so resuming does not create
  a second tracker. Manual `scripts/login.sh` retains its session until you run
  `scripts/logout.sh`.
- **Missing machine identity:** Current versions automatically provision a new
  machine on the first `scripts/login.sh` run. If you are using an older export,
  update the login helper. Existing sessions need their original machine state;
  an incomplete identity/store is deliberately not overwritten.
- **Zero location reports:** Verify BLE reception locally, then keep the powered
  tracker within reach of participating Apple devices. Find My may update late.
  Allow roughly 30 minutes for the first location to appear; longer delays are
  possible. Reports can already be available before the app displays them.
  A key rollover does not force a location report.
- **Already prepared:** Do not overwrite the registration or its keys. Use
  `scripts/register.sh status`, or `remove` when appropriate. Starting with a new
  state directory would create a new identity and could leave earlier records
  behind without their journal.
- **Missing firmware key header:** Run `prepare`, then `scripts/build.sh`.
  For an offline build only, generate disposable keys with
  `.venv/bin/python host/key_header.py --demo` and run
  `uvx --from platformio==6.2.0 pio run -d firmware` directly. Those demo keys are
  not registered in any account. Delete the generated header afterward.
- **The item is displayed as AirTag:** This may follow from the known product
  class being used. It does not register your own manufacturer in Apple's catalog.

Do not attach unredacted logs or any files from `private/` to issues.
