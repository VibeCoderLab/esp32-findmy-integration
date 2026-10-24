"""Interrupted or corrupt downloads cannot become cached Apple archives."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
from common import WorkflowError
from fetch_coreadi import verified_download


class DownloadTests(unittest.TestCase):
    def test_valid_cache_needs_no_network(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'archive'; path.write_bytes(b'valid')
            runner = Mock()
            verified_download('https://example.invalid/file', path, hashlib.sha256(b'valid').hexdigest(), runner)
            runner.assert_not_called()

    def test_success_replaces_bad_cache_only_after_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'archive'; path.write_bytes(b'incomplete')
            def run(command, **kwargs):
                self.assertEqual(path.read_bytes(), b'incomplete')
                self.assertIn('--retry-all-errors', command)
                Path(command[command.index('-o') + 1]).write_bytes(b'valid')
            verified_download('https://example.invalid/file', path, hashlib.sha256(b'valid').hexdigest(), run)
            self.assertEqual(path.read_bytes(), b'valid')
            self.assertFalse(path.with_suffix('.pending').exists())

    def test_corrupt_or_failed_download_leaves_no_partial_archive(self):
        for fails in (False, True):
            with self.subTest(network_error=fails), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'archive'
                def run(command, **kwargs):
                    Path(command[command.index('-o') + 1]).write_bytes(b'partial')
                    if fails:
                        raise subprocess.CalledProcessError(6, command)
                with self.assertRaises(WorkflowError):
                    verified_download('https://example.invalid/file', path, hashlib.sha256(b'valid').hexdigest(), run)
                self.assertEqual(list(Path(directory).iterdir()), [])
