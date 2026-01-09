from __future__ import annotations

import uuid
from datetime import datetime

from backend.app.schemas.base import ORMModel


class AccessLogRead(ORMModel):
    id: int
    created_at: datetime
    user_id: uuid.UUID | None = None
    user_email: str | None = None
    ip_address: str
    country_code: str | None = None
    method: str
    path: str
    status_code: int
    duration_ms: int
    user_agent: str | None = None
    block_reason: str | None = None
