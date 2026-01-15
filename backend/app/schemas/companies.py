from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from backend.app.schemas.base import ORMModel


class CompanyCreate(ORMModel):
    name: str = Field(min_length=1, max_length=255)


class CompanyRead(ORMModel):
    id: uuid.UUID
    name: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
