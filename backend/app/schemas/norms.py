from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from backend.app.schemas.base import ORMModel


class NormBase(ORMModel):
    norm_id: str
    title: str
    section: str
    scope: str
    detector_type: str
    check_type: str
    default_severity: str
    norm_text: str
    code_applicability: bool = True
    is_active: bool = True
    version: int = 1


class NormCreate(NormBase):
    pass


class NormUpdate(ORMModel):
    title: str | None = None
    section: str | None = None
    scope: str | None = None
    detector_type: str | None = None
    check_type: str | None = None
    default_severity: str | None = None
    norm_text: str | None = None
    code_applicability: bool | None = None
    is_active: bool | None = None
    version: int | None = None


class NormRead(NormBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
