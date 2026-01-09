from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from worker.app.utils.context import compute_line_contexts


@dataclass
class SourceUnit:
    path: str
    name: str
    content: str
    module_type: str
    change_ranges: list[tuple[int, int]] | None = None
    line_contexts: dict[int, str] = field(init=False, repr=False)
    _context_set: set[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.line_contexts = compute_line_contexts(self.content)
        self._context_set = set(self.line_contexts.values())
        if self.change_ranges is None:
            self.change_ranges = []

    @property
    def has_server_sections(self) -> bool:
        """True if module contains any server or unspecified blocks."""
        return not self._context_set.issubset({"client"})

    def is_server_line(self, line_no: int) -> bool:
        """Return True if the given line executes on the server or context is unknown."""
        return self.line_contexts.get(line_no, "unspecified") != "client"


@dataclass
class AnalysisTask:
    review_run_id: uuid.UUID
    sources: list[SourceUnit]
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DetectorFinding:
    norm_id: str
    detector_id: str
    severity: str
    message: str
    recommendation: str
    file_path: str
    line: int
    context: dict[str, Any]
    snippet: str | None = None


@dataclass
class AnalysisResult:
    review_run_id: uuid.UUID
    findings: list[DetectorFinding]
    engine_version: str
    detectors_version: str
    norms_version: str
    duration_ms: int
    ai_suggestions: list["AISuggestion"] = field(default_factory=list)
    llm_prompt_version: str | None = None
    llm_logs: list["LLMDiagnostic"] = field(default_factory=list)


@dataclass
class AISuggestion:
    norm_id: str | None
    section: str | None
    category: str | None
    norm_text: str
    source_reference: str | None
    severity: str | None
    evidence: list[dict[str, Any]] | None = None
    llm_raw_response: dict[str, Any] | None = None


@dataclass
class LLMDiagnostic:
    prompt: str
    response: str
    context_files: list[str]
    source_paths: list[str]
    static_findings: list[dict[str, Any]]
    created_at: str
    prompt_version: str | None = None
    unit_id: str | None = None
    unit_name: str | None = None
