# Changelog

## 0.1.1 — 2026-10-25

### Fixed

- Reject incomplete CloudKit snapshots and partial record operations instead of
  treating partial results as evidence of successful creation or removal.
- Preserve registration and cleanup failures separately, retaining a recoverable
  journal when cleanup is incomplete. Stop remote rollback after HTTP 401/429.
- Checkpoint recovery attempts before sending a proof; preserve blocks after
  cancellation and provide explicit, local-only manual retry release.
- Save machine state with private atomic writes and detect interrupted store
  updates. Scope machine locks so login/resync does not block its own headers.
- Correct package discovery in the pinned FindMy source for fresh installations.
- Ignore inherited Apple-ID/password overrides in the interactive login path.

### Added

- Hash-locked Python 3.12 runtime/build dependencies and a separately verified
  source archive for the pinned FindMy commit.
- Per-service request pauses with supported server retry intervals, a five-minute
  fallback and no automatic login retry.
- Read-only registration/report diagnosis without key or coordinate output.
- Failure-path tests, an end-to-end test plan and expanded credential-scope docs.

### Validation and limits

- 83 offline tests passed. A disposable-key firmware build succeeded.
- A fresh installation was tested on the original account: native item display,
  name/emoji editing, eventual location, targeted removal and local logout passed.
- One account is not evidence of general compatibility or empty-account support.
- Native location can appear more than 30 minutes after setup. The cause of the
  observed delay was not established. Reboots restart the key-rotation timer;
  power loss pauses the schedule. Firmware timing behavior is unchanged.
- Native nearby search, UWB Precision Finding and sound playback are unsupported.

## 0.1.0

Initial experimental release of the Linux setup and ESP32 firmware for an item
in Apple Find My, using fresh zone-signed record envelopes without an existing
accessory encryption template.
