from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from backend.app.schemas.base import ORMModel


class LLMLogEntry(ORMModel):
    io_log_id: uuid.UUID
    created_at: datetime
    artifact_type: str
    data: dict[str, Any]
