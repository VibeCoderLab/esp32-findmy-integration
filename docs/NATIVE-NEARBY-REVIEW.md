# Initial review: nearby finding inside Apple's Find My

## Scope and result

This review used source inspection and public protocol/product documentation.
No Apple account login, CloudKit request, firmware flash or reset of the running
unregistered-beacon test was performed for this review. Reading public Apple
support/developer pages is separate from contacting account services.

**Native non-UWB nearby guidance exists for supported AirPods. That does not
establish that a generic ESP32 accessory can use it.** No working native
Bluetooth-only nearby-finding implementation has been established for this
project. Precision Finding with distance and direction needs UWB hardware absent
from the classic ESP32 used here.

## Evidence

| Finding | Evidence | What it does not establish |
|---|---|---|
| Find My has nearby guidance for supported AirPods, with precise case finding separately described for UWB models | [Apple AirPods User Guide](https://support.apple.com/en-ge/guide/airpods/dev8e8b93d71/web) | Availability for arbitrary third-party item records |
| Apple's public Nearby Interaction accessory interface uses UWB | [Nearby Interaction](https://developer.apple.com/documentation/nearbyinteraction) | A Bluetooth-only route to that framework or native Find My UI |
| ESP firmware advertises without accepting connections | `firmware/src/main.cpp`: `ADV_TYPE_NONCONN_IND`, no GATT server registration | Any native connection, owner authentication or finding-command support |
| Host verification checks key hashes and advertisement bytes/RSSI | `host/verify.py` | Native nearby-search operation |
| Pinned FindMy.py provides key schedules, advertisement parsing and report access | `findmy/accessory.py`, `findmy/scanner/scanner.py` | An implemented Apple nearby-search handshake; the `current_mac_addresses` example is not a sound/finding implementation |

## Missing protocol work

The ESP would need an appropriate connectable BLE service and whatever
identity, pairing/authentication, capability and request/response behavior iOS
expects for the supported nearby-finding path. The exact AirPods requirements
and applicability to an item-class ESP32 are unresolved. Merely changing a
model/product field, adding a service UUID or exposing an arbitrary RSSI value
does not demonstrate compatibility. RSSI itself is measured by the receiving
phone, not supplied as a distance by the ESP.

Apple makes the full Find My accessory specifications available through its
[MFi program](https://developer.apple.com/find-my/). Public user documentation
describes features, not the complete Bluetooth handshake. A general Bluetooth
warmer/colder UI for arbitrary Find My accessories has not been established.

## Next experiment and validation limits

A useful next step is a controlled local protocol trace of a supported native
search, with the owner's consent, or an instrumented test peripheral. A normal
Linux Bluetooth HCI log records that adapter's traffic; it is not automatically
an over-the-air capture of an unrelated iPhone-to-accessory connection. Suitable
capture hardware or instrumentation is needed for that link.

Successful location reporting does not establish native nearby guidance.
Changing the configured item to an AirPods profile solely to expose a search
button does not demonstrate a working search protocol.

Current release capabilities: location reporting is supported; native nearby
search, sound playback and UWB Precision Finding are not supported.
