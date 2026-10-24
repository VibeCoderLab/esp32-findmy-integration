# Source and export review — 24 October 2026

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
- Dependencies have pinned top-level revisions, but a complete transitive Python
  lockfile and automated CI are still candidates for reproducibility work.

No GitHub publication, commit or firmware rollout was performed by this review.
