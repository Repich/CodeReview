from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from backend.app.schemas.base import ORMModel


class ModelOption(BaseModel):
    provider: Literal["internal", "deepseek", "openai"]
    model: str = Field(..., min_length=1, max_length=255)


class ModelLabConfigRead(ORMModel):
    enabled: bool
    default_sample_size: int
    max_sample_size: int
    max_models: int
    max_paid_target_models: int
    max_paid_target_runs: int
    max_expert_models: int
    max_expert_calls: int


class ModelLabDiscoverRequest(BaseModel):
    api_base: str = Field(..., min_length=1, max_length=500)
    api_key: str = Field(..., min_length=1, max_length=5000)


class ModelLabDiscoverResponse(ORMModel):
    models: list[str]


class ModelLabSessionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    api_base: str = Field(..., min_length=1, max_length=500)
    api_key: str = Field(..., min_length=1, max_length=5000)
    internal_models: list[str] = Field(default_factory=list, min_length=1)
    baseline_models: list[ModelOption] = Field(
        default_factory=lambda: [
            ModelOption(provider="deepseek", model="deepseek-chat"),
            ModelOption(provider="openai", model="gpt-5-mini"),
        ]
    )
    expert_models: list[ModelOption] = Field(
        default_factory=lambda: [
            ModelOption(provider="deepseek", model="deepseek-chat"),
            ModelOption(provider="openai", model="gpt-5-mini"),
        ]
    )
    sample_size: int = Field(default=10, ge=1, le=200)
    include_open_world: bool = False
    use_all_norms: bool = True
    disable_patterns: bool = True


class ModelLabSessionRead(ORMModel):
    id: uuid.UUID
    created_by: uuid.UUID
    title: str | None = None
    status: str
    target_models: list[dict] | None = None
    expert_models: list[dict] | None = None
    sample_size: int
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ModelLabCaseRead(ORMModel):
    id: uuid.UUID
    session_id: uuid.UUID
    source_run_id: uuid.UUID
    review_run_id: uuid.UUID
    target_provider: str
    target_model: str
    status: str
    duration_ms: int | None = None
    findings_count: int | None = None
    ai_findings_count: int | None = None
    open_world_count: int | None = None
    score_overall: float | None = None
    score_summary: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ModelLabJudgementRead(ORMModel):
    id: uuid.UUID
    case_id: uuid.UUID
    expert_provider: str
    expert_model: str
    overall_score: float
    criteria: dict | None = None
    summary: str | None = None
    created_at: datetime


class ModelLabLeaderboardRow(ORMModel):
    provider: str
    model: str
    cases: int
    avg_score: float


class ModelLabSessionDetail(ORMModel):
    session: ModelLabSessionRead
    cases: list[ModelLabCaseRead]
    judgements: list[ModelLabJudgementRead]
    leaderboard: list[ModelLabLeaderboardRow]


class ModelLabEvaluateRequest(BaseModel):
    experts: list[ModelOption] | None = None
