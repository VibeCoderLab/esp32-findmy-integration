# Source and export review

## Historical review — 24 October 2026

## Privacy scope and result

The review covered the publishable source, the generated ZIP, tracked/staged paths
and known sensitive values from local test state. No owner's known account name,
email address, device serial, account identifier, precise location, machine ID,
service token or tracker key was found in the reviewed export. Private values
were compared locally in memory and are not part of this report or the project.

The ZIP is constructed from allowlisted source paths and was compared byte for
byte with those paths. Private/dependency/virtual-environment directories, logs,
protobuf account snapshots, generated key headers, firmware binaries and flash
backups are excluded. The MAC address literal in the installer test is a synthetic
fixture, not the owner's board address. Product IDs and the AirTag profile are
generic protocol/product metadata; each installation creates its own identities.

This result applies to the reviewed source export, not an arbitrary working
installation. Local debugging directories intentionally retain private material.
Do not upload those directories or compiled firmware. There were no Git commits
or configured local Git author details at the time of review; future author
metadata is separate from the source-export contents.

## Changes made during review

- Private JSON writes now use a mode-0600 temporary file, flush/fsync and atomic
  replacement. An interrupted serialization or failed replacement preserves the
  previous journal. This does not make the entire multi-file/cloud workflow an
  atomic transaction.
- The login launcher hides SMS and trusted-device verification-code input. The
  pinned upstream helper and its network/authentication flow are unchanged.
- Tests cover interrupted writes, existing permissions, symlinks, hidden input,
  argument forwarding and launcher cleanup.

The firmware was not changed or flashed, and the review made no Apple-account
requests. Existing BLE/native behavior and automatic installer logout are retained.

## Final package verification

The current default creates fresh, zone-signed PCS envelopes without accessory
record templates. The legacy template mode requires an explicit option. Both
command-line defaults and overrides were checked without account requests.
The pinned dependency patches apply cleanly and are recognized as already
applied on a repeated setup; the local HTTP-429 guard expires after 300 seconds.

All 49 offline tests passed both in the source directory and in a clean ZIP
extraction, including local logout on success, failure and interruption. A
firmware build from the clean extraction succeeded using disposable,
unregistered demo keys. No board was flashed and no Apple account was accessed
for these checks. The firmware used 39,116 bytes of RAM and 1,101,437 bytes of
application flash in that build; these sizes do not measure power consumption.

The English and German READMEs were reconciled with the English prompts,
fresh-envelope default, local cooldown, automatic logout, manual re-login,
installer backup filename and fixed battery-level placeholder. Local document
links, shell/Python syntax, ZIP integrity, source equality and checksum were
checked. Project and upstream MIT notices are included; downloaded dependencies
retain their own licenses as described in THIRD_PARTY.md. This is a technical
source review, not a certification of all dependencies or account compatibility.

Publish the contents of the clean source ZIP rather than a working installation
or its pre-existing Git index. The ZIP excludes account state, build outputs,
generated keys and local-only research notes.

## Open work and limitations

- See [battery-operation review](POWER.md): savings need measurements and a separate
  hardware-tested build. CPU/light-sleep support cannot be inferred from a smaller
  binary or a delay in loop().
- The key schedule pauses across complete power loss and restarts its timer on
  boot. Sleep/reset support needs explicit timekeeping work before a battery mode.
- A fresh-ZIP run of the corrected zone-signed path was confirmed for one account,
  including name/emoji editing and eventual native location. Empty-account setup,
  other users and other ESP32 families remain unvalidated.
- Native nearby search, sound playback and UWB Precision Finding are not
  supported. Successful registration and location reporting do not establish
  those capabilities.
- At the time of the 24 October review, only top-level dependencies were pinned.
  The later local review below adds transitive Python locks; CI remains separate.

No GitHub publication, commit or firmware rollout was performed by this review.

## Local security review — 25 October 2026

Changes are local and have not been committed or published. No Apple account
request, board access or flash operation was performed for these checks.

- Require explicit, complete CloudKit record-sync snapshots. Reject partial
  operation results, missing/repeated continuation tokens and page exhaustion.
- Preserve original and cleanup failures separately. Keep `cleanup_pending`
  until complete snapshots confirm removal. Check both owned records before
  deleting either; refuse unexpected key/association changes.
- Do not issue remote rollback after 401/429. Preserve status/Retry-After, record
  per-service pauses and require manual login/cleanup. Five minutes remains a
  local fallback. Shared per-user pause state replaces the GSA `/tmp` marker.
- Persist the recovery block before sending a proof, including cancellation and
  unknown outcomes. Add safe local diagnostics and explicit manual retry release.
- Fsync journal parent directories. Atomically replace machine blobs and identity
  files under a process lock. Detect interrupted multi-file store updates and
  refuse reuse; do not claim automatic recovery or counter rollback.
- Hash-lock Python 3.12 runtime/build dependencies and separately verify the
  pinned FindMy source. Correct its package discovery for fresh wheel builds;
  preserve the exact upstream revision rather than switching versions.
- Remove inherited Apple-ID/password environment overrides from interactive
  login. Preserve automatic local session cleanup. Document the broad scope of
  recovered device identities, keychain-view keys and saved service tokens.

The offline test suite exercises complete/partial snapshots, cleanup failures,
401/429 behavior, recovery cancellation/checkpoint failures, SDK transport status
propagation, machine-store interruptions/locks, unsafe source archives and the
existing installer/export/cryptography checks. These checks use synthetic keys
and mocked transport, not a live Apple service.

The updated workflow must pass the [functional test plan](FUNCTIONAL-TEST.md)
before publication. In particular, stricter record responses and changed machine
persistence are not proven compatible merely by local tests. Least-privilege
keychain retrieval, guaranteed memory erasure, server-side session revocation,
empty-account support and full emulator isolation are not implemented.

Validation of this local revision: 78 offline tests passed in the working source
and again in a byte-for-byte verified clean ZIP extraction. Python dependency
consistency checks passed. All helper patches applied cleanly to the pinned
upstream revision and were recognized on a repeated patch check. Shell/Python
syntax and source whitespace checks passed (unified patch context lines retain
the whitespace required by their format).

A firmware build from clean exported source with disposable, unregistered keys
succeeded: 39,116 bytes RAM and 1,101,437 bytes application flash. No firmware
source change or power-saving behavior is claimed. The private test keys and
build directory were discarded. The export allowlist audit and additional
personal-identifier/API-key pattern checks passed. These checks reduce risk;
they are not proof that arbitrary future edits contain no private information.

### First live-test correction: resync/header lock conflict

The first interactive test stopped before login because a long-lived Resyncer
instance held the same machine lock needed by the header subprocess. The
machine remains locked during actual reads/mutations, but Resyncer now opens and
closes a fresh instance for each operation. Synchronization reloads the latest
store before use and releases its lock on both success and exceptions. Failed
machine initialization also closes its lock. No marker or account state was
removed to bypass this error.

Two offline integration tests use the patched classes with synthetic CoreADI
and state: an idle Resyncer permits a real header-like subprocess to acquire the
lock, and synchronization reloads current data while excluding concurrent access
and releases the lock after failure. All 80 offline tests pass with the patched
upstream available. These two integration tests require scripts/setup.sh; they
are skipped when the upstream checkout is absent. The live login still needs to
be retried by the user; no Apple request was made to validate this correction.

### Completed interactive validation and v0.1.1 preparation

The corrected setup completed on the original account. The user confirmed item
visibility, editable name/emoji and eventual native location. Read-only diagnosis
found both cloud records identical to the prepared local encrypted records and
seven decryptable reports. The user then removed the pair: a complete CloudKit
snapshot confirmed absence, the user confirmed disappearance in Find My, and
local logout completed. No other account has been validated by this test.

The native location appeared after more than 30 minutes. A passive scan observed
a one-index lag following a user-reported reboot; this does not establish that
the lag caused the display delay. No timing/firmware fix was included in this
release. All 83 offline tests passed. These final results supersede the earlier
pending-live-test statements above for the original account only.

Version 0.1.1 is prepared locally as a maintenance release with CHANGELOG.md,
VERSION, release notes, an allowlisted source ZIP and a matching SHA-256 file.
No commit, tag, push or GitHub publication was performed during preparation.
