"""Remove this installation's local Apple account sessions, retaining tracker keys."""
import argparse
import shutil

from common import STATE


def logout(state=None, quiet=False):
    state = STATE if state is None else state
    removed = False
    for name in ('login.json', 'session.json', 'auth'):
        path = state / name
        if path.is_symlink() or path.is_file():
            path.unlink()
            removed = True
        elif path.is_dir():
            shutil.rmtree(path)
            removed = True
    if not quiet or removed:
        print('Logged out locally: saved Apple account sessions removed. Tracker keys and backup are retained.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--quiet', action='store_true')
    logout(quiet=parser.parse_args().quiet)
