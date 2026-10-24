"""Run the pinned login helper with hidden SMS/trusted-device code input."""
import builtins
import getpass
from pathlib import Path
import runpy
import sys


def code_input(original, prompt=''):
    if prompt in ('SMS code: ', '2FA code: '):
        return getpass.getpass(prompt)
    return original(prompt)


def main():
    target = Path(sys.argv[1]).resolve()
    sys.argv = [str(target), *sys.argv[2:]]
    sys.path.insert(0, str(target.parent))
    original = builtins.input
    builtins.input = lambda prompt='': code_input(original, prompt)
    try:
        runpy.run_path(str(target), run_name='__main__')
    finally:
        builtins.input = original


if __name__ == '__main__':
    main()
