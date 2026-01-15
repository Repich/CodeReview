from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from backend.app.schemas.base import ORMModel


class LLMLogEntry(ORMModel):
    io_log_id: uuid.UUID
    created_at: datetime
    artifact_type: str
    data: dict[str, Any]


class LLMPlaygroundRequest(BaseModel):
    system_prompt: str = Field(..., min_length=1)
    user_prompt: str = Field(..., min_length=1)
    temperature: float = Field(0.0, ge=0.0, le=2.0)
    use_reasoning: bool = False
    model: str | None = None


class LLMPlaygroundResponse(BaseModel):
    model: str
    response: str
