# Battery operation and power optimization

No battery-current measurements have been taken for this firmware. There is no
validated battery profile or battery-life claim. The tested beacon behavior is
unchanged: one advertising event approximately every second, +3 dBm configured
advertising power, and primary-key rotation every 15 minutes.

## What is already economical

Wi-Fi is not initialized. Classic Bluetooth controller memory is released, and
the controller is started in BLE-only mode. Public-key derivation runs at key
rotation, not once per transmitted packet. The PC-side Python login/emulation
tools do not run on the ESP32 and do not consume its battery after setup.

The installed Arduino ESP32 SDK configuration used for the tested build enables
Bluetooth ORIG modem sleep. Espressif documents that this mode starts enabled
with the corresponding configuration. Adding esp_bt_sleep_enable() would not by
itself establish another saving.
[Controller documentation](https://docs.espressif.com/projects/esp-idf/en/v4.4.7/esp32/api-reference/bluetooth/controller_vhci.html#_CPPv419esp_bt_sleep_enablev)

## Current constraints

The esp32dev board definition requests a 240 MHz CPU. Its selected precompiled
SDK does not enable CONFIG_PM_ENABLE or FreeRTOS tickless idle, and selects the
main crystal as the Bluetooth low-power clock. Automatic CPU light sleep is
therefore not an application-level toggle in this build. In this ESP32/IDF
configuration Bluetooth also retains a no-light-sleep lock unless the supported
external 32 kHz clock option is used. Changing SDK headers alone does not rebuild
the underlying libraries.
[Power-management documentation](https://docs.espressif.com/projects/esp-idf/en/v4.4.7/esp32/api-reference/system/power_management.html)

Explicit deep sleep powers the radio down. Rebooting for every beacon is not a
drop-in optimization: the current firmware stores the seed/index at rotation and
restarts the 15-minute timer on boot. Frequent resets could keep reusing a key.
A sleep implementation needs elapsed-time accounting and rollover/reset tests.
Complete power loss also pauses the current schedule; this limitation is already
documented in the README.
[Sleep-mode documentation](https://docs.espressif.com/projects/esp-idf/en/v4.4.7/esp32/api-reference/system/sleep_modes.html)

## Recommended experiment order

| Experiment | Potential benefit | Required validation |
|---|---|---|
| Measure the unchanged board | Establish actual average and peak current | Measure at the real battery input, including regulator and board loads |
| Separate 80 MHz build | Reduce CPU active consumption | BLE reception, serial checks, timed rotation, restart and native location |
| Lower advertising power | Reduce transmit energy | Repeat range and location tests; reception range can shrink |
| Longer advertising interval | Fewer radio events | Measure detection/reporting delay; occasional passers-by may miss it |
| Rebuilt SDK with suitable power management | Reduce CPU idle consumption | Confirm clock/hardware support and BLE timing across sleep |
| Lower-quiescent-current board hardware | Avoid regulator, LED and USB-bridge overhead | Measure the actual board; SoC datasheet sleep figures are not whole-board figures |

An 80 MHz build or a host-stack port is a candidate, not a measured improvement.
Smaller flash/RAM usage does not directly imply lower average current. Do not
change several variables at once or advertise battery life before measuring it.

Estimate runtime from usable capacity and average current measured on the same
battery side of the power conversion. Include idle board loads, conversion losses
and the intended operating conditions. The current classic ESP32 build does not
establish support for another ESP32 chip family.
