from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)


def verify_turnstile(token: str | None, remote_ip: str | None = None) -> bool:
    settings = get_settings()
    secret = settings.turnstile_secret_key
    if not secret:
        return True
    if not token:
        return False
    payload = {
        "secret": secret,
        "response": token,
    }
    if remote_ip:
        payload["remoteip"] = remote_ip
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(settings.turnstile_verify_url, data=data)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            body = response.read().decode("utf-8")
        result = json.loads(body)
    except Exception as exc:
        logger.warning("Turnstile verification failed: %s", exc)
        return False
    return bool(result.get("success"))
