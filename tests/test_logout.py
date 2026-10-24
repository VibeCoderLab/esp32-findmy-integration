"""Local session cleanup across successful, failed and interrupted installers."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'host'))
import install
from logout import logout


class LogoutTests(unittest.TestCase):
    def test_cleanup_preserves_machine_tracker_and_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            for name in ('login.json', 'session.json', 'tracker.private.json', 'registration.json', 'installer-flash-before.bin'):
                (state / name).write_text('test')
            for name in ('auth', 'machine'):
                (state / name).mkdir()
                (state / name / 'identity.json').write_text('test')
            logout(state, quiet=True)
            logout(state, quiet=True)
            self.assertEqual({p.name for p in state.iterdir()}, {'machine', 'tracker.private.json', 'registration.json', 'installer-flash-before.bin'})

    def test_cleanup_does_not_follow_auth_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); state = root / 'private'; state.mkdir()
            outside = root / 'outside'; outside.mkdir()
            (outside / 'keep').write_text('test')
            (state / 'auth').symlink_to(outside, target_is_directory=True)
            logout(state, quiet=True)
            self.assertTrue((outside / 'keep').exists())
            self.assertFalse((state / 'auth').is_symlink())

    def test_python_entry_cleans_up_on_success_failure_and_interrupt(self):
        for failure in (None, RuntimeError('test'), KeyboardInterrupt()):
            with self.subTest(failure=type(failure).__name__):
                with patch.object(install, 'install', side_effect=failure), patch.object(install, 'logout') as cleanup:
                    if failure is None:
                        install.run_install(object())
                    else:
                        with self.assertRaises(type(failure)):
                            install.run_install(object())
                    cleanup.assert_called_once_with(quiet=True)

    def test_shell_cleans_up_even_when_dependency_setup_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ('scripts', 'host', 'private'):
                (root / folder).mkdir()
            for name in ('host/logout.py', 'host/common.py', 'scripts/install.sh'):
                shutil.copy2(ROOT / name, root / name)
            setup = root / 'scripts/setup.sh'
            setup.write_text('#!/bin/sh\nexit 17\n'); setup.chmod(0o700)
            for name in ('login.json', 'session.json', 'tracker.private.json'):
                (root / 'private' / name).write_text('test')
            import os
            env = os.environ.copy(); env.pop('ESP32_FINDMY_STATE', None)
            result = subprocess.run(['bash', str(root / 'scripts/install.sh'), '--port', 'test'], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 17)
            self.assertFalse((root / 'private/login.json').exists())
            self.assertFalse((root / 'private/session.json').exists())
            self.assertTrue((root / 'private/tracker.private.json').exists())
