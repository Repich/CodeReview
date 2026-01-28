from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from backend.app.models.enums import ReviewStatus
from backend.app.schemas.base import ORMModel
from backend.app.schemas.tasks import SourceUnitPayload, LineRangePayload


class ReviewRunBase(ORMModel):
    external_ref: str | None = None
    project_id: str | None = None
    input_hash: str | None = None
    engine_version: str | None = None
    detectors_version: str | None = None
    norms_version: str | None = None
    llm_prompt_version: str | None = None
    initiator: str | None = None
    source_type: str | None = None
    context: dict | None = None
    cost_points: int | None = None


class SourceChangePayload(ORMModel):
    path: str
    ranges: list["LineRangePayload"]


class ReviewRunCreate(ReviewRunBase):
    sources: list[SourceUnitPayload] | None = None
    changes: list[SourceChangePayload] | None = None


class ReviewRunUpdate(ORMModel):
    status: ReviewStatus | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    context: dict | None = None


class ReviewRunEvaluationRequest(ORMModel):
    selection_runs: int = Field(default=5, ge=2, le=20)


class ReviewRunRead(ReviewRunBase):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    user_email: str | None = None
    user_name: str | None = None
    status: ReviewStatus
    queued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
