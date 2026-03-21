from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from backend.app.schemas.base import ORMModel


class AdminExternalAccessEnableRequest(BaseModel):
    duration_hours: int = Field(default=8, ge=1, le=24)
    reason: str | None = Field(default=None, max_length=2000)


class AdminExternalAccessState(ORMModel):
    enabled: bool
    expires_at: datetime | None = None
    opened_by: uuid.UUID | None = None
    opened_from_ip: str | None = None
    opened_at: datetime | None = None
    reason: str | None = None
    remaining_minutes: int | None = None
