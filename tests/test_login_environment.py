"""Interactive login never inherits caller-provided Apple credentials."""
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'host'))
import login


class LoginEnvironmentTests(unittest.TestCase):
    def test_login_guard_precedes_provisioning_and_password_overrides_are_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            upstream=Path(directory);(upstream/'auth_probe.py').touch();order=[]
            guard=SimpleNamespace(guard=lambda:order.append('guard'))
            def command(args,**kwargs):
                self.assertIn('--no-save-password',args)
                self.assertNotIn('APPLE_ID',kwargs['env'])
                self.assertNotIn('APPLE_PASSWORD',kwargs['env'])
                return 0
            with patch.object(login,'UPSTREAM',upstream),patch.object(login,'private_directory'),patch.object(login,'ensure_machine',side_effect=lambda:order.append('machine')),patch.object(login.subprocess,'call',side_effect=command),patch.dict(sys.modules,{'cooldown':guard}),patch.dict(os.environ,{'APPLE_ID':'synthetic-account','APPLE_PASSWORD':'synthetic-password'}),patch.object(sys,'argv',['login.py']):
                self.assertEqual(login.main(),0)
            self.assertEqual(order,['guard','machine'])
