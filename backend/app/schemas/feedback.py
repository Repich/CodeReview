from __future__ import annotations

import uuid
from datetime import datetime

from backend.app.models.enums import FeedbackVerdict
from backend.app.schemas.base import ORMModel


class FeedbackBase(ORMModel):
    reviewer: str
    verdict: FeedbackVerdict
    comment: str | None = None


class FeedbackCreate(FeedbackBase):
    review_run_id: uuid.UUID
    finding_id: uuid.UUID


class FeedbackRead(FeedbackBase):
    id: uuid.UUID
    created_at: datetime
    review_run_id: uuid.UUID
    finding_id: uuid.UUID


class FeedbackList(ORMModel):
    total: int
    items: list[FeedbackRead]
