# Credentials and tracking keys

## Private credentials

Do not publish these in issues, screenshots, chat transcripts, or repositories:

- `private/`, including `login.json`, `session.json`, the machine identity,
  `tracker.private.json`, CloudKit files, and the registration journal.
- `firmware/include/device_secrets.h`, compiled firmware, or flash/NVS backups.
- Apple account passwords, screen-unlock passcodes, verification codes, or
  precise locations.

Session tokens are account credentials. Restrictive file permissions do not
protect against other programs running as the same user. Deleting local files
does not revoke a session that has already been copied. For complete retirement,
also review/remove the emulated device identity in your Apple account. This
project does not implement an automatic server-side logout.

The one-command installer deletes `login.json`, `session.json`, and `auth/`
on success, failure, and handled interrupts. `scripts/logout.sh` performs the
same local cleanup for manual workflows. Machine provisioning, tracker keys,
registration journals, and backups remain private and are retained. SIGKILL,
power loss, or filesystem errors can prevent cleanup; run logout manually then.

The `remove` command deletes only the project's two accessory records. It does
not delete keychain recovery identities or other devices from your account.

For bug reports, share version numbers, the error type, and the failing step.
Location queries omit coordinates unless explicitly requested. Login output may
still contain personal device or phone information; redact it before sharing.
SMS and trusted-device verification codes are entered without terminal echo by
the public login launcher. Private JSON state is atomically replaced with mode
0600; this does not protect against software running under the same user account.

## Scope of recovered credentials

Recovery reconstructs an existing device's private keychain identity in memory;
it does not join a new peer to the trust circle. The pinned SDK retrieves EC keys
from both the Manatee and ProtectedCloudStorage views. This is broader than only
the BeaconStore signing key. The application selects that key by the zone's
published identity reference, but this selection does not restrict what a
compromised process could access. Python does not guarantee erasure of secret
objects from memory. No sandbox or server-enforced least-privilege credential is
provided by this project.

CloudKit snapshots read the zone's encrypted records, including types unrelated
to the new tracker. The application does not decrypt those unrelated records in
the default workflow. Its two-record write/delete checks are application guards,
not restrictions attached to the account tokens. The Apple framework runs under
an emulator with the user's permissions; emulation is not a security sandbox.

## Interrupted operations and service limits

The recovery-attempt marker is committed before sending the device passcode
proof. Cancellation or a lost response leaves the outcome unknown and blocks
another attempt. Only a successful recovery removes this marker. Inspect it with
`register.sh recovery-status`; explicitly authorizing a manual retry does not
establish that Apple has reset any attempt counter.

Journal and machine-state writes use private temporary files, fsync and atomic
replacement. Machine access has a process lock. A marker detects interrupted
multi-file machine-store updates and prevents reuse of a possibly mixed state.
These measures cannot make a multi-file update or a remote CloudKit transaction
atomic, recover lost hardware, or guarantee durability on every filesystem.

Cloud record listings must explicitly finish; partial, truncated or looping
responses are rejected. A failed registration retains both its primary failure
and cleanup failure as sanitized classes/status codes. `cleanup_pending` means
remote records may remain. Authentication failures and HTTP 429 do not trigger
another remote cleanup request automatically. Keep the journal, resolve the
service/session problem, then deliberately run `register.sh remove`.

Per-user GSA login and per-service CloudKit/keychain/report pause files live under
`$XDG_STATE_HOME/esp32-findmy` (default `~/.local/state/esp32-findmy`). They hold
status/timing information, not credentials. Five minutes is the fallback only;
a usable server retry interval is respected. They are local request guards, not
a guarantee about Apple's rate limits, and cannot coordinate other programs.
A 401 stops the operation without an automatic login.

## Dependencies

Python 3.12 dependencies and build helpers have hash-locked files. The pinned
FindMy source archive is separately hash-verified and built without network
build isolation after reviewed patches. The locally produced wheel is hashed
before installation. Hashes establish the selected bytes, not that dependencies
are harmless. PlatformIO downloads its separately versioned platform/toolchain;
the Python lockfiles do not hash-lock that firmware toolchain or system tools.
