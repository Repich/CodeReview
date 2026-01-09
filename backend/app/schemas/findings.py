from __future__ import annotations

import uuid
from datetime import datetime

from backend.app.models.enums import FindingSeverity
from backend.app.schemas.base import ORMModel


class FindingBase(ORMModel):
    norm_id: str
    detector_id: str
    severity: FindingSeverity
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    column_start: int | None = None
    column_end: int | None = None
    message: str
    recommendation: str | None = None
    code_snippet: str | None = None
    engine_version: str | None = None
    trace_id: str | None = None
    context: dict | None = None


class FindingCreate(FindingBase):
    review_run_id: uuid.UUID
    norm_db_id: uuid.UUID | None = None
    llm_raw_response: dict | None = None


class FindingRead(FindingBase):
    id: uuid.UUID
    review_run_id: uuid.UUID
    created_at: datetime
    llm_raw_response: dict | None = None
    norm_title: str | None = None
    norm_text: str | None = None
    norm_section: str | None = None
    norm_source_reference: str | None = None
    norm_source_excerpt: str | None = None


class FindingList(ORMModel):
    total: int
    items: list[FindingRead]
