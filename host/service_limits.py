"""Local, per-service request guards. Never retry or log response bodies."""
from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import fcntl
import json
import math
import os
from pathlib import Path
import re
import time

from common import WorkflowError, write_json

LIMITS = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'esp32-findmy' / 'service-limits.json'
FALLBACK_SECONDS = 300


class ServicePaused(WorkflowError):
    http_status = 429


class SessionExpired(WorkflowError):
    http_status = 401


def status_code(error):
    for field in ('http_status', 'status', 'status_code'):
        value = getattr(error, field, None)
        if isinstance(value, int) and 100 <= value <= 599:
            return value
    if type(error).__name__ == 'UnauthorizedError':
        return 401
    client = getattr(error, 'client_error', None)
    if client in (11, 12):
        return 401
    if client == 6:
        return 429
    text = str(error)
    if text == 'CloudKit is throttling this account':
        return 429
    match = re.search(r'\bHTTP\s*[:=]?\s*([1-5][0-9]{2})\b', text, re.I)
    return int(match.group(1)) if match else None


def error_info(error):
    # Classes/status numbers only, never exception text, URLs, headers or secrets.
    name = type(error).__name__
    data = {'type': name if re.fullmatch(r'[A-Za-z_]{1,64}', name) else 'Exception'}
    status = status_code(error)
    if status is not None:
        data['http_status'] = status
    return data


def retry_seconds(error, now=None):
    now = time.time() if now is None else now
    value = getattr(error, 'retry_after', None)
    if value is None:
        value = getattr(error, 'retry_after_header', None)
    if value is not None:
        try:
            seconds = float(value)
            if 0 <= seconds <= 365 * 86400:
                return max(1, seconds), 'server'
        except (TypeError, ValueError):
            try:
                stamp = parsedate_to_datetime(str(value))
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=timezone.utc)
                return max(1, stamp.timestamp() - now), 'server'
            except (TypeError, ValueError, OverflowError):
                pass
    return FALLBACK_SECONDS, 'local-fallback'


@contextmanager
def limit_state():
    LIMITS.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    LIMITS.parent.chmod(0o700)
    fd = os.open(LIMITS.with_suffix('.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if LIMITS.exists():
            try:
                data = json.loads(LIMITS.read_text())
                if not isinstance(data, dict):
                    raise ValueError
            except (OSError, ValueError):
                raise WorkflowError('Local service-pause state is unreadable; no request sent. Review it before continuing.') from None
        else:
            data = {}
        yield data


def guard(service):
    with limit_state() as data:
        entry = data.get(service, {})
        try:
            until = float(entry.get('until', 0))
            if not math.isfinite(until):
                raise ValueError
            left = until - time.time()
        except (AttributeError, TypeError, ValueError):
            raise WorkflowError('Invalid local service pause; no request sent.') from None
    if left > 0:
        raise ServicePaused(f'{service}: local request guard active for about {int(left) + 1} more seconds. No request sent; no automatic retry.')


def pause(service, error):
    now = time.time()
    seconds, source = retry_seconds(error, now)
    with limit_state() as data:
        previous = data.get(service, {}).get('until', 0)
        data[service] = {'until': max(float(previous), now + seconds), 'source': source, 'http_status': 429}
        write_json(LIMITS, data)
    return seconds, source


async def request(service, operation):
    guard(service)
    try:
        return await operation()
    except Exception as error:
        status = status_code(error)
        if status == 429:
            try:
                seconds, source = pause(service, error)
            except (OSError, WorkflowError, ValueError):
                raise ServicePaused(f'{service}: rate limited; local pause could not be recorded. Stop and review local state. No automatic retry.') from None
            raise ServicePaused(f'{service}: rate limited. Pause recorded for {int(seconds)} seconds ({source}); no automatic retry.') from None
        if status == 401:
            raise SessionExpired(f'{service}: account session rejected. Sign in manually after reviewing the failure; no automatic login or cleanup request.') from None
        raise
