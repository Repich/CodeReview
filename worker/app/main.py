from __future__ import annotations

import argparse
import json
import sys
import uuid
import time
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

from worker.app.config import get_settings
from worker.app.models import AnalysisResult, AnalysisTask, SourceUnit
from worker.app.queue.base import InMemoryQueue
from worker.app.services.analyzer import Analyzer
from worker.app.services.backend_client import BackendClient


def load_task_from_json(path: Path) -> AnalysisTask:
    data = json.loads(path.read_text(encoding="utf-8"))
    sources = [
        SourceUnit(
            path=item["path"],
            name=item.get("name", item["path"]),
            content=item["content"],
            module_type=item.get("module_type", "CommonModule"),
            change_ranges=[
                (rng["start"], rng["end"]) for rng in item.get("change_ranges", []) if rng
            ],
        )
        for item in data["sources"]
    ]
    return AnalysisTask(
        review_run_id=uuid.UUID(data.get("review_run_id", str(uuid.uuid4()))),
        sources=sources,
        settings=data.get("settings"),
    )


def sample_task() -> AnalysisTask:
    content = """\
    Процедура ВыполнитьОпасныйКод()
        НачатьТранзакцию();
        Выполнить("Сообщить(\"Hello\")");
        ЗафиксироватьТранзакцию();
    КонецПроцедуры
    """
    return AnalysisTask(
        review_run_id=uuid.uuid4(),
        sources=[
            SourceUnit(
                path="CommonModules/DangerousModule.bsl",
                name="DangerousModule",
                content=content,
                module_type="CommonModule",
            )
        ],
        settings={},
    )


def serialize_result(result: AnalysisResult) -> dict[str, Any]:
    return {
        "engine_version": result.engine_version,
        "detectors_version": result.detectors_version,
        "norms_version": result.norms_version,
        "duration_ms": result.duration_ms,
        "metrics": result.metrics,
        "llm_prompt_version": result.llm_prompt_version,
        "findings": [
            {
                "norm_id": finding.norm_id,
                "detector_id": finding.detector_id,
                "severity": finding.severity,
                "file_path": finding.file_path,
                "line_start": finding.line,
                "line_end": finding.line,
                "column_start": None,
                "column_end": None,
                "message": finding.message,
                "recommendation": finding.recommendation,
                "code_snippet": finding.snippet,
                "context": finding.context,
            }
            for finding in result.findings
        ],
        "ai_findings": [
            {
                "norm_id": suggestion.norm_id,
                "section": suggestion.section,
                "category": suggestion.category,
                "severity": suggestion.severity,
                "norm_text": suggestion.norm_text,
                "source_reference": suggestion.source_reference,
                "evidence": suggestion.evidence,
                "llm_raw_response": suggestion.llm_raw_response,
            }
            for suggestion in result.ai_suggestions
        ],
        "llm_logs": [
            {
                "prompt": log.prompt,
                "response": log.response,
                "context_files": log.context_files,
                "source_paths": log.source_paths,
                "static_findings": log.static_findings,
                "created_at": log.created_at,
                "prompt_version": log.prompt_version,
                "unit_id": log.unit_id,
                "unit_name": log.unit_name,
                "redaction_report": log.redaction_report,
            }
            for log in result.llm_logs
        ],
    }


def process_offline_tasks(tasks: list[AnalysisTask]) -> None:
    queue = InMemoryQueue(tasks)
    analyzer = Analyzer()
    while task := queue.fetch():
        result = analyzer.run(task)
        payload = serialize_result(result)
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")


def process_backend_tasks(once: bool) -> None:
    analyzer = Analyzer()
    client = BackendClient()
    settings = get_settings()
    while True:
        task = client.fetch_task()
        if not task:
            if once:
                break
            time.sleep(settings.poll_interval_seconds)
            continue
        result = analyzer.run(task)
        payload = serialize_result(result)
        client.submit_results(task.review_run_id, payload)
        if once:
            break


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="CodeReview worker")
    parser.add_argument("--input", type=Path, help="Path to JSON task", required=False)
    parser.add_argument("--sample", action="store_true", help="Run built-in sample task")
    parser.add_argument("--once", action="store_true", help="Fetch only one task from backend")
    args = parser.parse_args(argv)

    if args.input:
        process_offline_tasks([load_task_from_json(args.input)])
    elif args.sample:
        process_offline_tasks([sample_task()])
    else:
        process_backend_tasks(once=args.once)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
