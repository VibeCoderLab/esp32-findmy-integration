# v0.1.1 — Reliability and installation fixes

This update hardens the experimental Linux installer and its account-state
handling. The existing Find My integration and ESP32 firmware behavior are
retained. No Mac, physical AirTag or accessory encryption template is required;
an existing BeaconStore zone and recoverable account keys are still needed.

- Reject incomplete CloudKit results and retain actionable cleanup journals.
- Stop automatic remote cleanup on authentication/rate-limit failures.
- Persist recovery-attempt blocks before requests; add safe manual retry tools.
- Protect machine-state writes and fix the resync/header lock conflict.
- Hash-lock Python dependencies and fix fresh packaging of the pinned FindMy SDK.
- Add a read-only diagnostic command and expand tests/security documentation.

83 offline tests and a disposable-key firmware build passed. A fresh setup on
the original account passed item display, name/emoji editing, eventual native
location, targeted removal and local logout. Other accounts and empty-account
setup remain unverified. Native location may take longer than 30 minutes;
nearby search, UWB and sound playback remain unsupported. Reboot/power-loss
key-schedule limitations are unchanged. See CHANGELOG.md and SECURITY.md.

## Downloads and verification

Download `esp32-findmy-integration-v0.1.1.zip` and its `.sha256` file into the
same directory, then run:

```bash
sha256sum -c esp32-findmy-integration-v0.1.1.zip.sha256
unzip esp32-findmy-integration-v0.1.1.zip
cd esp32-findmy-public
```

Follow README.md. The uploaded ZIP contains allowlisted source only; account
state, downloaded dependencies, generated tracker keys, binaries and backups
are excluded. GitHub's automatically generated source archives are separate
files and do not match this uploaded ZIP's checksum.

Existing installations: retain the complete private state, registration journal
and board backup. Never put these in a repository or create new tracker IDs just
to update host tools. This release does not require reflashing a working tracker.
Review manual commands and troubleshooting before using existing state; the
one-command installer performs board backup and flashing.
