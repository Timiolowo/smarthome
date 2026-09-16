"""Small, in-memory audio status snapshot shared with the local dashboard."""
from threading import Lock
from time import time

_lock = Lock()
_status = {'state': 'OFFLINE', 'message': 'Voice listener is not running', 'timings': {}}


def publish(**fields):
    with _lock:
        _status.update(fields, updated_at=time())


def timing(stage, seconds):
    with _lock:
        _status['timings'][stage] = round(seconds * 1000)


def snapshot():
    with _lock:
        return {**_status, 'timings': dict(_status['timings'])}
