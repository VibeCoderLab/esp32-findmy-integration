import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('source_export', Path(__file__).resolve().parents[1] / 'scripts/export.py')
export = importlib.util.module_from_spec(spec); spec.loader.exec_module(export)

class ExportTests(unittest.TestCase):
    def test_private_and_build_files_are_not_exported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'README.md').write_text('Public source')
            for name in ('private/login.json', '.deps/state.json', 'firmware/include/device_secrets.h', 'firmware/.pio/firmware.bin'):
                path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('excluded')
            self.assertEqual([p.relative_to(root).as_posix() for p in export.files(root)], ['README.md'])

    def test_common_secret_shapes_are_rejected(self):
        values = [b'person' + b'@' + b'example.invalid', b'/' + b'home/' + b'example/private/',
                  b'{"searchPartyToken":"' + b'x' * 40 + b'"}',
                  b'MASTER_KEY[28]={' + b','.join(str(i).encode() for i in range(28)) + b'};']
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / 'README.md'
            for value in values:
                path.write_bytes(value)
                with self.assertRaises(RuntimeError): export.audit([path], root)

    def test_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); target = root / 'outside'; target.write_text('content')
            (root / 'README.md').symlink_to(target)
            with self.assertRaises(RuntimeError): export.files(root)

    def test_symlink_directory_cannot_export_private_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private = root / 'private'; private.mkdir()
            (private / 'sensitive.py').write_text('excluded')
            (root / 'host').symlink_to(private, target_is_directory=True)
            with self.assertRaises(RuntimeError): export.files(root)
