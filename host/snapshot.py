"""Fetch complete zone snapshots; partial sync is never evidence of absence."""
from common import WorkflowError
from service_limits import request
from findmy.cloudkit.constants import OperationType, ResultCode, SYNC_STATUS_COMPLETE, PATH_RECORD_SYNC
from findmy.cloudkit.records import records_from_changes


async def complete_records(store, max_pages=100):
    client = store.client
    await request('cloudkit', lambda: client.open_container())
    token = None
    seen_tokens = set()
    changes = []
    for _ in range(max_pages):
        operation = client._build_request(OperationType.RECORD_RETRIEVE_CHANGES_TYPE)
        payload = operation.retrieve_changes_request
        payload.zone_identifier.CopyFrom(client._zone_identifier('BeaconStore'))
        if token is not None:
            payload.sync_continuation_token = token
        response = await request('cloudkit', lambda: client._post_operation(PATH_RECORD_SYNC, operation))
        if response.result.code != ResultCode.SUCCESS:
            raise WorkflowError('CloudKit returned a partial or unsuccessful snapshot; absence is not confirmed.')
        if not response.HasField('retrieve_changes_response'):
            raise WorkflowError('CloudKit snapshot response is missing; absence is not confirmed.')
        page = response.retrieve_changes_response
        changes.extend(page.record_change)
        if page.HasField('status') and page.status == SYNC_STATUS_COMPLETE:
            records = records_from_changes(changes, 'BeaconStore')
            names = [record.name for record in records]
            if any(not name for name in names) or len(names) != len(set(names)):
                raise WorkflowError('CloudKit snapshot has ambiguous record identities; no completeness claim made.')
            return records
        next_token = page.sync_continuation_token if page.HasField('sync_continuation_token') else None
        if not next_token or next_token in seen_tokens:
            raise WorkflowError('CloudKit sync is incomplete and cannot advance; absence is not confirmed.')
        seen_tokens.add(next_token)
        token = next_token
    raise WorkflowError('CloudKit snapshot page limit reached before completion; absence is not confirmed.')
