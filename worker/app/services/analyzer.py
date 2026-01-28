from __future__ import annotations

from time import perf_counter
from typing import Iterable

from worker.app import detectors as _detectors  # noqa: F401 ensures detector modules register
from worker.app.config import get_settings
from worker.app.detectors.base import DetectorContext
from worker.app.detectors.registry import default_registry
from worker.app.models import AnalysisResult, AnalysisTask, DetectorFinding
from worker.app.services.cognitive_complexity import compute_cognitive_complexity
from worker.app.services.llm_client import generate_ai_suggestions


class Analyzer:
    def __init__(self, detectors: Iterable = None) -> None:
        self.detectors = list(detectors or default_registry.all())
        self.settings = get_settings()

    def run(self, task: AnalysisTask) -> AnalysisResult:
        start = perf_counter()
        findings: list[DetectorFinding] = []
        range_map = {
            source.path: list(source.change_ranges or []) for source in task.sources
        }
        for source in task.sources:
            ctx = DetectorContext(source=source)
            for detector in self.detectors:
                findings.extend(detector.detect(ctx))
        findings = self._filter_findings(findings, range_map)
        llm_result = generate_ai_suggestions(task, findings)
        metrics = compute_cognitive_complexity(task.sources)
        llm_context_value = {
            "enabled": bool(llm_result),
            "prompt_version": llm_result.prompt_version if llm_result else None,
        }
        for finding in findings:
            if finding.context is None:
                finding.context = {}
            finding.context.setdefault("llm", llm_context_value)
        duration_ms = int((perf_counter() - start) * 1000)
        return AnalysisResult(
            review_run_id=task.review_run_id,
            findings=findings,
            engine_version=self.settings.engine_version,
            detectors_version=self.settings.detectors_version,
            norms_version=self.settings.norms_version,
            duration_ms=duration_ms,
            metrics=metrics,
            ai_suggestions=llm_result.suggestions if llm_result else [],
            llm_prompt_version=llm_result.prompt_version if llm_result else None,
            llm_logs=llm_result.log_entries if llm_result else [],
            evaluation_report=llm_result.evaluation_report if llm_result else None,
        )

    @staticmethod
    def _filter_findings(
        findings: list[DetectorFinding], range_map: dict[str, list[tuple[int, int]]]
    ) -> list[DetectorFinding]:
        if not any(range_map.values()):
            return findings
        filtered: list[DetectorFinding] = []
        for finding in findings:
            ranges = range_map.get(finding.file_path or "")
            if not ranges:
                filtered.append(finding)
                continue
            if finding.line is None:
                continue
            if any(start <= finding.line <= end for start, end in ranges):
                filtered.append(finding)
        return filtered
