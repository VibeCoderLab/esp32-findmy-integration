"""An interrupted journal write must preserve the previous file and permissions."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
from common import write_json


class PrivateJsonTests(unittest.TestCase):
    def test_replace_tightens_existing_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'journal.json'
            path.write_text('{}');path.chmod(0o644)
            write_json(path,{'status':'verified'})
            self.assertEqual(json.loads(path.read_text()),{'status':'verified'})
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            self.assertEqual(len(list(Path(directory).iterdir())),1)

    def test_partial_json_or_failed_replace_preserves_previous_journal(self):
        for failure in ('dump','replace'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'journal.json';path.write_text('{"status":"old"}')
                def interrupted(value,stream,**kwargs):
                    stream.write('{"partial":')
                    raise OSError('simulated interruption')
                target='common.json.dump' if failure=='dump' else 'common.os.replace'
                with patch(target,side_effect=interrupted if failure=='dump' else OSError('simulated failure')):
                    with self.assertRaises(OSError):write_json(path,{'status':'new'})
                self.assertEqual(json.loads(path.read_text()),{'status':'old'})
                self.assertEqual(len(list(Path(directory).iterdir())),1)

    def test_replacing_symlink_does_not_modify_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);outside=root/'keep.json';outside.write_text('{"keep":true}')
            path=root/'journal.json';path.symlink_to(outside)
            write_json(path,{'status':'new'})
            self.assertFalse(path.is_symlink())
            self.assertEqual(json.loads(outside.read_text()),{'keep':True})
