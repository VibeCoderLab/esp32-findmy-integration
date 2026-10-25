"""Exercise the exact helper delivered by the reviewed upstream patch."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]

def helper_source():
    lines=(ROOT/'patches/machine-state.patch').read_text().splitlines(True)
    collect=False;source=[]
    for line in lines:
        if line.startswith('+++ b/tools/machoadi/atomic_state.py'):
            collect=True;continue
        if collect and line.startswith('+'):
            source.append(line[1:])
    return ''.join(source)


class MachineStateTests(unittest.TestCase):
    def setUp(self):
        self.module=types.ModuleType('review_atomic_state')
        exec(compile(helper_source(),'atomic_state.py','exec'),self.module.__dict__)
    def test_failed_atomic_replace_keeps_previous_blob(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'blob';path.write_bytes(b'previous')
            with patch.object(self.module.os,'replace',side_effect=OSError('synthetic interruption')):
                with self.assertRaises(OSError):self.module.atomic_write(path,b'new')
            self.assertEqual(path.read_bytes(),b'previous')
            self.assertEqual(list(Path(directory).iterdir()),[path])
    def test_successful_store_commit_is_private_and_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            state=Path(directory)
            self.module.save_store(state,{'first.pb':b'one','second.pb':b'two'})
            self.assertFalse((state/'.store-update.pending').exists())
            self.assertEqual((state/'store/second.pb').read_bytes(),b'two')
            self.assertEqual((state/'store/first.pb').stat().st_mode & 0o777,0o600)
    def test_interrupted_generation_is_never_loaded_as_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            state=Path(directory);original=self.module.atomic_write
            def interrupt(path,data):
                if Path(path).name=='second.pb':raise OSError('synthetic crash')
                return original(path,data)
            with patch.object(self.module,'atomic_write',side_effect=interrupt):
                with self.assertRaises(OSError):self.module.save_store(state,{'first.pb':b'new','second.pb':b'new'})
            self.assertTrue((state/'.store-update.pending').exists())
            with self.assertRaises(RuntimeError):self.module.lock_state(state)
    def test_second_process_owner_cannot_mutate_same_machine_concurrently(self):
        with tempfile.TemporaryDirectory() as directory:
            first=self.module.lock_state(directory)
            try:
                with self.assertRaises(BlockingIOError):self.module.lock_state(directory)
            finally:first.close()
            self.module.lock_state(directory).close()
    def test_path_traversal_rejected_before_marker_or_write(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):self.module.save_store(Path(directory),{'../outside':b'no'})
            self.assertFalse((Path(directory)/'.store-update.pending').exists())
