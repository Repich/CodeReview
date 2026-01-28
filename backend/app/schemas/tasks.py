from __future__ import annotations

import uuid
from pydantic import BaseModel, ConfigDict, Field
from typing import Any

from backend.app.models.enums import FindingSeverity


class LineRangePayload(BaseModel):
    start: int = Field(ge=1)
    end: int = Field(ge=1)

    model_config = ConfigDict(extra="forbid")


class SourceUnitPayload(BaseModel):
    path: str
    name: str
    content: str
    module_type: str
    change_ranges: list[LineRangePayload] | None = None
    model_config = ConfigDict(extra="ignore")


class AnalysisTaskResponse(BaseModel):
    review_run_id: uuid.UUID
    sources: list[SourceUnitPayload]
    settings: dict | None = None
    context: dict | None = None


class AnalysisFindingPayload(BaseModel):
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
    context: dict | None = None


class AISuggestionPayload(BaseModel):
    norm_id: str | None = None
    section: str | None = None
    category: str | None = None
    severity: str | None = None
    norm_text: str
    source_reference: str | None = None
    evidence: list[dict[str, str | None]] | None = None
    llm_raw_response: dict | None = None


class AnalysisResultPayload(BaseModel):
    engine_version: str
    detectors_version: str
    norms_version: str
    duration_ms: int
    findings: list[AnalysisFindingPayload]
    ai_findings: list[AISuggestionPayload] | None = None
    llm_prompt_version: str | None = None
    llm_logs: list["LLMDiagnosticPayload"] | None = None
    metrics: dict[str, Any] | None = None
    evaluation_report: dict[str, Any] | None = None


class LLMDiagnosticPayload(BaseModel):
    prompt: str
    response: str
    context_files: list[str]
    source_paths: list[str]
    static_findings: list[dict] = []
    created_at: str
    prompt_version: str | None = None
    unit_id: str | None = None
    unit_name: str | None = None
