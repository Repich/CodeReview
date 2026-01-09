from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from backend.app.models.enums import AIFindingStatus
from backend.app.schemas.base import ORMModel


class EvidenceEntry(ORMModel):
    file: str | None = None
    lines: str | None = None
    reason: str | None = None


class AIFindingBase(ORMModel):
    norm_id: str | None = None
    section: str | None = None
    category: str | None = None
    severity: str | None = None
    norm_text: str
    source_reference: str | None = None
    evidence: list[EvidenceEntry] | None = None
    status: AIFindingStatus


class AIFindingCreate(AIFindingBase):
    review_run_id: uuid.UUID
    llm_raw_response: dict[str, Any] | None = None


class AIFindingUpdate(ORMModel):
    status: AIFindingStatus | None = None


class AIFindingRead(AIFindingBase):
    id: uuid.UUID
    review_run_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    llm_raw_response: dict[str, Any] | None = None
    norm_source_reference: str | None = None
    norm_source_excerpt: str | None = None


class AIFindingList(ORMModel):
    total: int
    items: list[AIFindingRead]
