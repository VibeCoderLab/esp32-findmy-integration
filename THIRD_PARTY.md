# Third-party components and provenance

This repository's own project code is MIT-licensed. Dependencies are downloaded
separately and retain their respective license terms.

| Component | Purpose | Source |
|---|---|---|
| os-findmy-e, commit `374d83854f657a7fdca45f813387d99d491db0e2` | Linux login and Mac Anisette helpers | https://github.com/sacca97/os-findmy-e |
| FindMy.py fork, commit `7969003ca785658369b650f75d9e7ca519566bf6` | CloudKit, recovery, keys, and reports | https://github.com/parawanderer/FindMy.py |
| Anisette 1.2.4 | Authentication dependency | https://pypi.org/project/Anisette/ |
| Arduino-ESP32 / ESP-IDF / mbedTLS | ESP32 framework, BLE, and cryptography | https://github.com/espressif/arduino-esp32 |
| PlatformIO espressif32 6.12.0 | Toolchain and board configuration | https://github.com/platformio/platform-espressif32 |
| pyserial / bleak | Serial and BLE verification | https://pypi.org/project/pyserial/ and https://pypi.org/project/bleak/ |
| CoreADI from Apple iTunes | Emulation runtime dependency | Obtained by os-findmy-e; not distributed here |

`patches/auth-output.patch`, `patches/cooldown.patch` and
`patches/machine-state.patch` modify the MIT-licensed
login helper and cooldown module from os-findmy-e. Its original copyright and license notice is included unchanged in
`patches/LICENSE.os-findmy-e`. Complete third-party projects are not bundled
into this source export.

The experimental PCS writer follows the structures and wrapping behavior
implemented/tested by the pinned MIT-licensed FindMy.py fork, calling its reader,
KDF and field-encryption APIs for verification. Its upstream license is included
as `patches/LICENSE.FindMy.txt`. This does not imply upstream or Apple endorsement
of newly generated envelopes.

Additional protocol research used the PCS implementation in the
[stek29 RustPush fork](https://github.com/stek29/rustpush/blob/82dc6f8342176e4f9171b62354cbdd13eaa18b38/src/icloud/pcs.rs)
as a reference. That project uses the Server Side Public License and is not
bundled here. Its implementation was not copied into this project. Outer-signature
coverage was independently verified against the owner's existing signed records;
the writer uses the pinned FindMy.py signing-data builder and cryptography APIs.

The descriptive AirTag product values come from public OpenTagViewer test
exports. No accessory keys, names, locations, or serial identifiers from those
exports are reused.

Apple, AirTag, and Find My are trademarks of their respective owners. This
independent experiment is not supported or endorsed by Apple.

The FindMy commit above is obtained as the source archive in `sources.lock.json`.
`patches/findmy-packaging.patch` corrects package discovery so its CloudKit,
keychain and utility subpackages are included in a fresh wheel.
`patches/cloudkit-status.patch` preserves HTTP 401/429 classifications and
Retry-After values and rejects partial record sync/save/delete results.
These patches do not change the pinned commit or the upstream license.

`requirements.lock` fixes the transitive Python runtime dependencies, including
esptool and PlatformIO. `requirements-build.lock` fixes the Python wheel-build
helpers. `requirements.txt` and `requirements-build.txt` are maintenance inputs;
setup installs from the lockfiles. FindMy itself is built separately from its
hash-verified source, without dependency fetching or build isolation. System
packages, uv and PlatformIO's downloaded firmware toolchains remain outside
these Python hash locks. Lock refreshes require a new review and functional test.
