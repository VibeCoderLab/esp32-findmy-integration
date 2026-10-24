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
