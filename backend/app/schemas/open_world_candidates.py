from __future__ import annotations

import uuid
from datetime import datetime

from backend.app.schemas.base import ORMModel


class OpenWorldEvidenceEntry(ORMModel):
    file: str | None = None
    lines: str | None = None
    reason: str | None = None


class OpenWorldCandidateRead(ORMModel):
    id: uuid.UUID
    review_run_id: uuid.UUID
    title: str
    section: str | None = None
    severity: str | None = None
    confidence: float | None = None
    description: str | None = None
    norm_text: str | None = None
    mapped_norm_id: str | None = None
    status: str
    accepted_norm_id: str | None = None
    evidence: list[OpenWorldEvidenceEntry] | None = None
    llm_raw_response: dict | None = None
    created_at: datetime
    updated_at: datetime
    mapped_norm_source_reference: str | None = None
    mapped_norm_source_excerpt: str | None = None


class OpenWorldCandidateList(ORMModel):
    total: int
    items: list[OpenWorldCandidateRead]


class OpenWorldCandidateAccept(ORMModel):
    norm_id: str | None = None
    title: str | None = None
    section: str | None = None
    norm_text: str | None = None
    scope: str | None = None
