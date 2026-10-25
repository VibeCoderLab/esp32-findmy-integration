"""Exercise the reviewed SDK patch and refuse unsafe dependency sources offline."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
from install_findmy import unpack, apply_reviewed_patch
from common import WorkflowError
from findmy.cloudkit.client import AsyncCloudKitClient
from findmy.cloudkit.constants import OperationType, ResultCode
from findmy.cloudkit.proto import cloudkit_pb2 as ck
import findmy.cloudkit.client as sdk


class TransportTests(unittest.IsolatedAsyncioTestCase):
    def client(self, response):
        client = object.__new__(AsyncCloudKitClient)
        client._info = None
        client._container = 'synthetic-container'
        client._account = SimpleNamespace(dsid='synthetic', service_tokens={'mmeAuthToken': 'synthetic', 'cloudKitToken': 'synthetic'})
        client._cloudkit_headers = AsyncMock(return_value={})
        client._http = SimpleNamespace(post=AsyncMock(return_value=response))
        return client

    async def test_open_container_preserves_retry_after_without_response_body(self):
        response = SimpleNamespace(status_code=429, headers={'Retry-After': '90'})
        client = self.client(response)
        with self.assertRaises(Exception) as caught:
            await client.open_container()
        self.assertEqual(caught.exception.http_status, 429)
        self.assertEqual(caught.exception.retry_after_header, '90')
        client._http.post.assert_awaited_once()

    async def test_record_operation_preserves_401_and_429(self):
        for status in (401, 429):
            client = self.client(SimpleNamespace(status_code=status, headers={'Retry-After': '60'}))
            client.open_container = AsyncMock(return_value=SimpleNamespace(database_gateway_url='https://example.invalid', user_id='synthetic'))
            request = ck.RequestOperation(request=ck.Operation(type=OperationType.RECORD_SAVE_TYPE))
            with self.assertRaises(Exception) as caught:
                await client._post_operation('/synthetic', request)
            self.assertEqual(caught.exception.http_status, status)
            if status == 429:
                self.assertEqual(caught.exception.retry_after_header, '60')
            client._http.post.assert_awaited_once()

    async def test_partial_record_results_are_rejected_before_parsing_success(self):
        for operation in (OperationType.RECORD_SAVE_TYPE, OperationType.RECORD_DELETE_TYPE, OperationType.RECORD_RETRIEVE_CHANGES_TYPE):
            client = self.client(SimpleNamespace(status_code=200, ok=True, content=b'synthetic'))
            client.open_container = AsyncMock(return_value=SimpleNamespace(database_gateway_url='https://example.invalid', user_id='synthetic'))
            result = ck.ResponseOperation(); result.result.code = ResultCode.PARTIAL
            with patch.object(sdk, 'decode_delimited', return_value=[result]):
                with self.assertRaisesRegex(Exception, 'Incomplete CloudKit'):
                    await client._post_operation('/synthetic', ck.RequestOperation(request=ck.Operation(type=operation)))


class SourceArchiveTests(unittest.TestCase):
    def test_archive_rejects_traversal_and_symlinks_before_extracting(self):
        for entry in ('FindMy.py-test/../../outside', '/outside', 'other-root/file'):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory); archive = root / 'source.zip'
                with zipfile.ZipFile(archive, 'w') as target:
                    target.writestr(entry, 'synthetic')
                destination = root / 'out'; destination.mkdir()
                with self.assertRaises(WorkflowError): unpack(archive, destination, 'test')
                self.assertEqual(list(destination.iterdir()), [])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); archive = root / 'source.zip'
            info = zipfile.ZipInfo('FindMy.py-test/link'); info.external_attr = 0o120777 << 16
            with zipfile.ZipFile(archive, 'w') as target: target.writestr(info, 'outside')
            with self.assertRaises(WorkflowError): unpack(archive, root, 'test')

    def test_unreviewed_patch_path_is_never_executed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); patch_file = root / 'change.patch'
            patch_file.write_text('--- a/unreviewed\n+++ b/unreviewed\n')
            with patch('install_findmy.subprocess.run') as run:
                with self.assertRaises(WorkflowError):
                    apply_reviewed_patch(root, patch_file, ['a/expected', 'b/expected'])
                run.assert_not_called()
