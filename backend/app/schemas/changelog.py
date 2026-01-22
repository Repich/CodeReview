from __future__ import annotations

from datetime import datetime

from backend.app.schemas.base import ORMModel


class ChangelogRead(ORMModel):
    content: str
    updated_at: datetime
