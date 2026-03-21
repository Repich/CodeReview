from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass


@dataclass
class _SecretRecord:
    value: str
    expires_at: float


_LOCK = threading.Lock()
_SECRETS: dict[str, _SecretRecord] = {}


def put_secret(value: str, ttl_seconds: int) -> str:
    ref = uuid.uuid4().hex
    expires_at = time.time() + max(60, ttl_seconds)
    with _LOCK:
        _cleanup_locked()
        _SECRETS[ref] = _SecretRecord(value=value, expires_at=expires_at)
    return ref


def get_secret(ref: str | None) -> str | None:
    if not ref:
        return None
    with _LOCK:
        _cleanup_locked()
        record = _SECRETS.get(ref)
        if not record:
            return None
        return record.value


def drop_secret(ref: str | None) -> None:
    if not ref:
        return
    with _LOCK:
        _SECRETS.pop(ref, None)


def _cleanup_locked() -> None:
    now = time.time()
    expired = [key for key, record in _SECRETS.items() if record.expires_at <= now]
    for key in expired:
        _SECRETS.pop(key, None)
