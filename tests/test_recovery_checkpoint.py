"""Recovery is blocked before sending, including interrupted/unknown outcomes."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'host'))
import register
import install
import service_limits
from common import WorkflowError


class RecoveryCheckpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.state=Path(self.tmp.name)
        self.old=service_limits.LIMITS;service_limits.LIMITS=self.state/'limits/state.json'
    async def asyncTearDown(self):
        service_limits.LIMITS=self.old;self.tmp.cleanup()
    async def attempt(self,error,write_failure=False):
        account=SimpleNamespace(_password=None,close=AsyncMock())
        async def recover(record,code):
            journal=json.loads((self.state/'recovery-blocked.json').read_text())
            self.assertIn('pending',journal['reason'])
            self.assertFalse(journal['automatic_retries'])
            raise error
        device=SimpleNamespace(describe=lambda:'Synthetic device')
        session=SimpleNamespace(recovery_options=AsyncMock(return_value=SimpleNamespace(recoverable=[device])),
            recover=AsyncMock(side_effect=recover),close=AsyncMock())
        with patch.object(register,'STATE',self.state),patch.object(register,'private_directory'),patch.object(register,'account',return_value=account),patch.object(register,'cloud_account',return_value=object()),patch.object(register.AsyncKeychainSession,'open',new=AsyncMock(return_value=session)),patch.object(register.getpass,'getpass',return_value='synthetic-secret'),patch('builtins.input',return_value='0'):
            if write_failure:
                with patch.object(register,'write_json',side_effect=OSError('synthetic disk failure')):
                    with self.assertRaises(OSError):await register.prepare('Test','📍')
                session.recover.assert_not_awaited()
            elif isinstance(error,Exception):
                with self.assertRaises(WorkflowError):await register.prepare('Test','📍')
            else:
                with self.assertRaises(type(error)):await register.prepare('Test','📍')
        self.assertIsNone(account._password)
        account.close.assert_awaited_once();session.close.assert_awaited_once()
        return session
    async def test_keyboard_interrupt_leaves_unknown_outcome_block(self):
        session=await self.attempt(KeyboardInterrupt())
        self.assertEqual(session.recover.await_count,1)
        data=json.loads((self.state/'recovery-blocked.json').read_text())
        self.assertIn('unknown',data['reason'])
    async def test_rejection_keeps_only_safe_status_details(self):
        await self.attempt(RuntimeError('HTTP 409 status -6015 synthetic-private-response'))
        data=(self.state/'recovery-blocked.json').read_text()
        self.assertNotIn('synthetic-private-response',data)
        self.assertNotIn('synthetic-secret',data)
        self.assertEqual(json.loads(data)['details']['http_status'],409)
    async def test_failed_checkpoint_sends_no_passcode(self):
        await self.attempt(RuntimeError(),write_failure=True)
    def test_blocked_recovery_stops_before_login_or_board_probe(self):
        (self.state/'recovery-blocked.json').write_text('{}')
        with patch.object(install,'STATE',self.state),patch.object(install,'private_directory'),patch.object(install,'run') as run,patch.object(install,'inspect_board') as probe:
            with self.assertRaises(WorkflowError):install.install(SimpleNamespace(fresh_protection=True))
            run.assert_not_called();probe.assert_not_called()
