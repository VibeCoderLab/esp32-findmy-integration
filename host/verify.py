"""Reset the own ESP32, compare current/next key hashes, then receive its BLE beacon."""
import argparse
import asyncio
import hashlib
import re
import serial
from bleak import BleakScanner
from common import tracker

async def verify(port_name, ble=True):
    accessory = tracker()
    with serial.Serial(port_name, 115200, timeout=.2) as port:
        port.dtr = False
        port.rts = True
        await asyncio.sleep(.1)
        port.rts = False
        await asyncio.sleep(3)
        port.write(b'STATUS\nNEXTCHECK\n')
        await asyncio.sleep(2)
        output = port.read_all().decode(errors='replace')
    actual = re.findall(r'^BEACON index=(\d+) hash=([0-9a-f]+) advertising=1', output, re.M)
    next_key = re.search(r'NEXT_CHECK BEACON index=(\d+) hash=([0-9a-f]+)', output)
    if not actual or not next_key:
        raise RuntimeError('No working beacon/self-test reported. Check the local serial output.')
    index, digest = actual[-1]
    next_index, next_digest = next_key.groups()
    key = accessory._primary_key_at(int(index))
    if not hashlib.sha256(key.adv_key_bytes).hexdigest().startswith(digest):
        raise RuntimeError('Current firmware key does not match.')
    expected_next = accessory._primary_key_at(int(next_index))
    if int(next_index) != int(index) + 1 or not hashlib.sha256(expected_next.adv_key_bytes).hexdigest().startswith(next_digest):
        raise RuntimeError('Next firmware key does not match.')
    if not ble:
        print('Serial verification passed: current and next keys match; BLE advertising reported active.')
        print('No local Bluetooth reception test requested.')
        return
    hits = []
    def seen(device, advertisement):
        if device.address.upper() == key.mac_address.upper() and advertisement.manufacturer_data.get(76) == key.of_data():
            hits.append(advertisement.rssi)
    async with BleakScanner(detection_callback=seen):
        await asyncio.sleep(15)
    if not hits:
        raise RuntimeError('No matching BLE packet received. Check the Bluetooth adapter and range.')
    print('Current/next keys match. Exact MAC address and BLE payload received.')
    print('RSSI:', hits[-1], 'dBm. This does not confirm an upload by Apple devices.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--serial-only', action='store_true', help='Check firmware status and keys only; no Linux BLE adapter required.')
    args = parser.parse_args()
    asyncio.run(verify(args.port, ble=not args.serial_only))
