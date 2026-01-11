from __future__ import annotations

from datetime import datetime

from backend.app.schemas.base import ORMModel


class CaddyAccessLogRead(ORMModel):
    id: int
    created_at: datetime
    host: str | None
    method: str | None
    uri: str | None
    status_code: int | None
    duration_ms: int | None
    size_bytes: int | None
    remote_ip: str | None
    user_agent: str | None
    referer: str | None
    raw: dict | None
