"""Read own reports; coordinates are opt-in so ordinary logs contain no position."""
import argparse
import asyncio
from common import account, tracker, WorkflowError
from service_limits import request

async def main(show_location):
    accessory = tracker()
    value = account()
    try:
        reports = await request('reports', lambda: value.fetch_location_history(accessory))
        print('Decrypted location reports:', len(reports))
        if reports:
            newest = max(reports, key=lambda report: report.timestamp)
            print('Newest report:', newest.timestamp.isoformat())
            if show_location:
                print(f'Location: {newest.latitude:.6f}, {newest.longitude:.6f}')
        else:
            print('No reports yet. An Apple device must receive and report the BLE beacon.')
    finally:
        await value.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--show-location', action='store_true')
    try:
        asyncio.run(main(parser.parse_args().show_location))
    except WorkflowError as error:
        raise SystemExit(str(error)) from None
