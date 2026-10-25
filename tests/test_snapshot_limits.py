"""Wire-level complete snapshot checks and per-service pause behavior."""
import asyncio
from datetime import datetime, timezone
from email.utils import format_datetime
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'host'))
from snapshot import complete_records
from common import WorkflowError
import service_limits as limits
from findmy.cloudkit.proto import cloudkit_pb2 as ck
from findmy.cloudkit.constants import ResultCode,SYNC_STATUS_COMPLETE,OperationType


def page(complete,token=None):
    value=ck.ResponseOperation();value.result.code=ResultCode.SUCCESS
    value.retrieve_changes_response.status=SYNC_STATUS_COMPLETE if complete else 1
    if token is not None:value.retrieve_changes_response.sync_continuation_token=token
    return value


class SnapshotTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=limits.LIMITS
        limits.LIMITS=Path(self.tmp.name)/'limits/state.json'
    async def asyncTearDown(self):
        limits.LIMITS=self.old;self.tmp.cleanup()
    def store(self,pages):
        client=SimpleNamespace(open_container=AsyncMock(),_post_operation=AsyncMock(side_effect=pages))
        client._build_request=lambda operation:ck.RequestOperation(request=ck.Operation(type=int(operation)))
        client._zone_identifier=lambda name:ck.RecordZoneIdentifier(value=ck.Identifier(name=name))
        return SimpleNamespace(client=client)
    async def test_all_pages_are_read_until_explicit_completion(self):
        store=self.store([page(False,b'first'),page(True)])
        self.assertEqual(await complete_records(store),[])
        self.assertEqual(store.client._post_operation.await_count,2)
        sent=store.client._post_operation.await_args_list[1].args[1]
        self.assertEqual(sent.retrieve_changes_request.sync_continuation_token,b'first')
    async def test_missing_or_repeated_token_is_an_error(self):
        for pages in [[page(False)],[page(False,b'a'),page(False,b'a')]]:
            with self.assertRaises(WorkflowError):await complete_records(self.store(pages))
    async def test_page_limit_is_an_error_not_a_partial_result(self):
        with self.assertRaises(WorkflowError):await complete_records(self.store([page(False,b'a'),page(False,b'b')]),max_pages=2)
    async def test_partial_response_cannot_be_a_complete_snapshot(self):
        response=page(True);response.result.code=ResultCode.PARTIAL
        with self.assertRaises(WorkflowError):await complete_records(self.store([response]))
    async def test_missing_payload_is_an_error(self):
        response=ck.ResponseOperation();response.result.code=ResultCode.SUCCESS
        with self.assertRaises(WorkflowError):await complete_records(self.store([response]))
    async def test_throttle_records_pause_and_next_call_sends_nothing(self):
        error=RuntimeError('synthetic private response');error.http_status=429;error.retry_after=120
        call=AsyncMock(side_effect=error)
        with self.assertRaises(limits.ServicePaused):await limits.request('cloudkit',call)
        call.reset_mock()
        with self.assertRaises(limits.ServicePaused):await limits.request('cloudkit',call)
        call.assert_not_awaited()
        other=AsyncMock(return_value='separate-service')
        self.assertEqual(await limits.request('reports',other),'separate-service')
        data=limits.LIMITS.read_text();self.assertNotIn('synthetic private',data)
    async def test_401_never_retries_or_calls_login(self):
        error=RuntimeError('synthetic secret');error.http_status=401
        call=AsyncMock(side_effect=error)
        with self.assertRaises(limits.SessionExpired):await limits.request('cloudkit',call)
        self.assertEqual(call.await_count,1)
    def test_numeric_date_and_missing_retry_after(self):
        now=1700000000;error=RuntimeError()
        error.retry_after_header='17';self.assertEqual(limits.retry_seconds(error,now),(17,'server'))
        error.retry_after_header=format_datetime(datetime.fromtimestamp(now+90,timezone.utc),usegmt=True)
        self.assertEqual(limits.retry_seconds(error,now),(90,'server'))
        error.retry_after_header='invalid';self.assertEqual(limits.retry_seconds(error,now),(300,'local-fallback'))
