"""Safety guards for one-command flashing and resumable registration."""
import hashlib
import json
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
from common import WorkflowError
import install


class InstallerTests(unittest.TestCase):
    def test_interrupted_read_retries_and_commits_only_complete_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            board = {'mac': 'board', 'flash_bytes': 8}
            calls = []
            def read(command):
                calls.append(command)
                pending = Path(command[-1])
                self.assertFalse(pending.exists())
                pending.write_bytes(b'partial' if len(calls) == 1 else b'complete')
                if len(calls) == 1:
                    raise subprocess.CalledProcessError(2, command)
            with patch.object(install, 'STATE', state), patch.object(install, 'run', side_effect=read), patch.object(install.time, 'sleep'):
                install.ensure_backup(board, 'port')
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0][calls[0].index('--baud') + 1], '1500000')
            self.assertEqual(calls[1][calls[1].index('--baud') + 1], '115200')
            self.assertEqual((state / 'installer-flash-before.bin').read_bytes(), b'complete')
            self.assertTrue((state / 'installer-board.json').exists())

    def test_failed_read_is_bounded_and_never_commits_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            def fail(command):
                Path(command[-1]).write_bytes(b'partial')
                raise subprocess.CalledProcessError(2, command)
            with patch.object(install, 'STATE', state), patch.object(install, 'run', side_effect=fail) as run, patch.object(install.time, 'sleep'):
                with self.assertRaises(subprocess.CalledProcessError):
                    install.ensure_backup({'mac': 'board', 'flash_bytes': 8}, 'port')
                self.assertEqual(run.call_count, 2)
            self.assertEqual(list(state.iterdir()), [])

    def test_supported_board_and_wrong_family(self):
        valid = 'Chip type: ESP32-D0WD-V3 (revision v3.1)\nDetected flash size: 4MB\nMAC: aa:bb:cc:dd:ee:ff\n'
        board = install.parse_chip(valid)
        self.assertEqual(board['flash_bytes'], 4194304)
        for text in (valid.replace('ESP32-D0WD-V3', 'ESP32-S3'), valid.replace('4MB', '8MB'), 'Incomplete response'):
            with self.assertRaises(WorkflowError): install.parse_chip(text)

    def test_wrong_board_cannot_reuse_a_backup(self):
        expected = {'mac': 'board-one', 'flash_bytes': 4194304}
        with self.assertRaises(WorkflowError):
            install.check_same_board(expected, {'mac': 'board-two', 'flash_bytes': 4194304})

    def test_resume_never_duplicates_registered_or_failed_records(self):
        self.assertEqual(install.registration_action(None), 'prepare')
        self.assertEqual(install.registration_action({'status': 'prepared', 'creation_attempted': [], 'protection_mode': 'fresh-experimental', 'fresh_protection_version': 2}), 'apply')
        self.assertEqual(install.registration_action({'status': 'created_verified', 'creation_attempted': ['one', 'two'], 'protection_mode': 'fresh-experimental', 'fresh_protection_version': 2}), 'reuse')
        for manifest in ({'status': 'prepared', 'creation_attempted': ['one']}, {'status': 'removed', 'creation_attempted': ['one', 'two']}):
            with self.assertRaises(WorkflowError): install.registration_action(manifest)

    def test_valid_backup_reused_without_running_any_command(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            data = b'original firmware'
            board = {'mac': 'test-board', 'flash_bytes': len(data)}
            (state / 'installer-flash-before.bin').write_bytes(data)
            (state / 'installer-board.json').write_text(json.dumps({**board, 'sha256': hashlib.sha256(data).hexdigest()}))
            with patch.object(install, 'STATE', state), patch.object(install, 'run') as run:
                install.ensure_backup(board, 'test-port')
                run.assert_not_called()
                (state / 'installer-flash-before.bin').write_bytes(b'changed')
                with self.assertRaises(WorkflowError): install.ensure_backup(board, 'test-port')

    def test_unbound_backup_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            path = state / 'installer-flash-before.bin'; path.write_bytes(b'preserve')
            with patch.object(install, 'STATE', state), patch.object(install, 'run') as run:
                with self.assertRaises(WorkflowError): install.ensure_backup({'mac': 'board', 'flash_bytes': 8}, 'port')
                run.assert_not_called()
                self.assertEqual(path.read_bytes(), b'preserve')
