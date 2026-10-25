"""Credential-free recovery diagnostics and an explicit local retry release."""
import json
from pathlib import Path
import re
import uuid


def safe_details(error):
    # Never persist or display the original exception text, response or headers.
    text = str(error)
    name = type(error).__name__
    known = {'RecoveryError','EscrowError','TimeoutError','ClientConnectorError',
             'ClientResponseError','ConnectionError','OSError','ValueError',
             'RuntimeError','UnhandledProtocolError','AuthenticationError',
             'ServicePaused','SessionExpired'}
    details = {'error_type': name if name in known else 'UnexpectedError'}
    status = getattr(error, 'http_status', getattr(error, 'status', None))
    if not isinstance(status, int) or not 100 <= status <= 599:
        match = re.search(r'\bHTTP\s*[:=]?\s*([1-5][0-9]{2})\b', text, re.I)
        status = int(match.group(1)) if match else None
    if status is not None:
        details['http_status'] = status
    match = re.search(r'\bstatus\s*[:=]?\s*(-[0-9]{1,8})\b', text, re.I)
    if match:
        details['service_status'] = int(match.group(1))
    if status == 429:
        details['category'] = 'rate_limited'
    elif status == 409 or details.get('service_status') == -6015:
        details['category'] = 'recovery_rejected'
    elif status is not None and status >= 500:
        details['category'] = 'service_unavailable'
    elif name in {'TimeoutError','ClientConnectorError','ConnectionError','OSError'}:
        details['category'] = 'connection_error'
    else:
        details['category'] = 'unknown'
    return details


def summary(record):
    details = record.get('details', {}) if isinstance(record, dict) else {}
    if not isinstance(details, dict):
        details = {}
    labels = []
    name = details.get('error_type')
    if isinstance(name, str) and re.fullmatch(r'[A-Za-z]{1,40}', name):
        labels.append('Error type: ' + name)
    for field, label in [('http_status','HTTP'),('service_status','Service status')]:
        value = details.get(field)
        if isinstance(value, int) and not isinstance(value, bool) and -99999999 <= value <= 99999999:
            labels.append(f'{label}: {value}')
    hints = {
        'rate_limited': 'The service rate-limited the request. No retry was sent automatically.',
        'recovery_rejected': 'The recovery proof was rejected. This does not distinguish an incorrect passcode from an incompatible or intermittent exchange.',
        'service_unavailable': 'The service reported a server error; this does not establish a passcode problem.',
        'connection_error': 'The connection failed or timed out; this does not establish a passcode problem.',
        'unknown': 'The exact cause could not be determined safely.'}
    if labels:
        return '\n'.join(labels + [hints.get(details.get('category'), hints['unknown'])])
    return 'The previous version saved no error class or status code. The exact cause of that attempt is unavailable.'


def release_retry(state):
    """Called only after the user explicitly authorizes one new manual attempt."""
    state = Path(state)
    marker = state / 'recovery-blocked.json'
    if marker.is_symlink() or not marker.is_file():
        raise ValueError('No regular recovery failure record exists.')
    history = state / 'history'
    if history.is_symlink():
        raise ValueError('Recovery history must not be a symbolic link.')
    history.mkdir(mode=0o700, exist_ok=True)
    destination = history / ('recovery-' + uuid.uuid4().hex + '.json')
    marker.replace(destination)
    destination.chmod(0o600)
    from common import fsync_directory
    fsync_directory(history)
    fsync_directory(state)
    return destination
