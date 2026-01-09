from __future__ import annotations

import uuid
from datetime import datetime

from backend.app.models.enums import AuditEventType, IODirection
from backend.app.schemas.base import ORMModel


class AuditLogBase(ORMModel):
    review_run_id: uuid.UUID | None = None
    event_type: AuditEventType
    actor: str | None = None
    payload: dict | None = None


class AuditLogCreate(AuditLogBase):
    pass


class AuditLogRead(AuditLogBase):
    id: uuid.UUID
    created_at: datetime


class IOLogBase(ORMModel):
    review_run_id: uuid.UUID
    direction: IODirection
    artifact_type: str
    storage_path: str
    checksum: str | None = None
    size_bytes: int | None = None


class IOLogCreate(IOLogBase):
    pass


class IOLogRead(IOLogBase):
    id: uuid.UUID
    created_at: datetime
