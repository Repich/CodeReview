from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from backend.app.schemas.base import ORMModel


class SuggestedNormCreate(ORMModel):
    section: str = Field(..., min_length=1, max_length=255)
    severity: str = Field(..., pattern="^(critical|major|minor|info)$")
    text: str = Field(..., min_length=10)


class SuggestedNormLLMResult(ORMModel):
    duplicate: bool
    duplicate_norm_ids: list[str] = []
    norm_id: str | None = None
    title: str | None = None
    section: str | None = None
    scope: str | None = None
    detector_type: str | None = None
    check_type: str | None = None
    default_severity: str | None = None
    version: int | None = None
    norm_text: str | None = None
    raw_response: str | None = None


class SuggestedNormRead(ORMModel):
    id: uuid.UUID
    author_id: uuid.UUID
    section: str
    severity: str
    text_raw: str
    status: str
    duplicate_of: list[str] | None = None
    duplicate_titles: dict[str, str | None] | None = None
    generated_norm_id: str | None = None
    generated_title: str | None = None
    generated_section: str | None = None
    generated_scope: str | None = None
    generated_detector_type: str | None = None
    generated_check_type: str | None = None
    generated_severity: str | None = None
    generated_version: int | None = None
    generated_text: str | None = None
    created_at: datetime
    updated_at: datetime
    vote_score: int = 0
    user_vote: int | None = None


class SuggestedNormListResponse(ORMModel):
    items: list[SuggestedNormRead]
    total: int


class SuggestedNormVoteCreate(ORMModel):
    vote: int = Field(..., description="+1 или -1")
