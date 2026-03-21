#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import sys
import traceback
import uuid
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from worker.app.main import serialize_result
from worker.app.models import AnalysisTask, SourceUnit
from worker.app.services.analyzer import Analyzer

LOG = logging.getLogger("model_lab_internal_runner")


def _normalize_api_base(value: str) -> str:
    base = value.strip().rstrip("/")
    if not base:
        raise ValueError("base URL is empty")
    if base.endswith("/api"):
        return base
    return f"{base}/api"


def _build_task(payload: dict[str, Any]) -> AnalysisTask:
    sources: list[SourceUnit] = []
    for item in payload.get("sources") or []:
        ranges = []
        for rng in item.get("change_ranges") or []:
            if isinstance(rng, dict) and "start" in rng and "end" in rng:
                ranges.append((int(rng["start"]), int(rng["end"])))
        sources.append(
            SourceUnit(
                path=str(item["path"]),
                name=str(item.get("name") or item["path"]),
                content=str(item.get("content") or ""),
                module_type=str(item.get("module_type") or "CommonModule"),
                change_ranges=ranges,
            )
        )
    return AnalysisTask(
        review_run_id=uuid.UUID(str(payload["review_run_id"])),
        sources=sources,
        settings=payload.get("settings"),
        context=payload.get("context"),
    )


def _extract_error_message(exc: Exception) -> str:
    message = f"{type(exc).__name__}: {exc}"
    details = traceback.format_exc(limit=5)
    full = f"{message}\n{details}".strip()
    return full[:3900]


def _login(client: httpx.Client, *, email: str, password: str) -> str:
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    response.raise_for_status()
    payload = response.json()
    token = str(payload.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("Login succeeded but access_token is missing")
    return token


def _fetch_next_task(client: httpx.Client, session_id: str) -> dict[str, Any] | None:
    response = client.get(f"/admin/model-lab/sessions/{session_id}/internal-next-task")
    if response.status_code == 204:
        return None
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected task payload")
    return payload


def _submit_result(client: httpx.Client, run_id: uuid.UUID, payload: dict[str, Any]) -> None:
    response = client.post(f"/review-runs/{run_id}/results", json=payload)
    response.raise_for_status()


def _mark_failed(client: httpx.Client, run_id: uuid.UUID, error_message: str) -> None:
    response = client.post(
        f"/admin/model-lab/review-runs/{run_id}/fail",
        json={"error_message": error_message},
    )
    response.raise_for_status()


def run(args: argparse.Namespace) -> int:
    api_base = _normalize_api_base(args.base_url)
    verify_ssl = not args.insecure
    timeout = httpx.Timeout(connect=15.0, read=600.0, write=600.0, pool=30.0)
    with httpx.Client(base_url=api_base, timeout=timeout, verify=verify_ssl) as client:
        token = args.token.strip() if args.token else ""
        if not token:
            if not args.email or not args.password:
                raise RuntimeError("Provide --token or --email with --password")
            token = _login(client, email=args.email, password=args.password)
        client.headers["Authorization"] = f"Bearer {token}"

        analyzer = Analyzer()
        processed = 0
        failed = 0
        while True:
            if args.max_tasks and processed + failed >= args.max_tasks:
                break
            task_payload = _fetch_next_task(client, args.session_id)
            if not task_payload:
                break
            task = _build_task(task_payload)
            LOG.info("Processing run %s (%s sources)", task.review_run_id, len(task.sources))
            try:
                result = analyzer.run(task)
                out_payload = serialize_result(result)
                _submit_result(client, task.review_run_id, out_payload)
                processed += 1
                LOG.info("Submitted results for run %s", task.review_run_id)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                message = _extract_error_message(exc)
                LOG.exception("Run %s failed, marking as failed", task.review_run_id)
                try:
                    _mark_failed(client, task.review_run_id, message)
                except Exception:  # noqa: BLE001
                    LOG.exception("Unable to mark run %s as failed on server", task.review_run_id)
                    return 2
        LOG.info("Done: processed=%s failed=%s", processed, failed)
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="One-off internal Model Lab runner")
    parser.add_argument("--base-url", required=True, help="CodeReview base URL, e.g. https://codereview.1cretail.ru")
    parser.add_argument("--session-id", required=True, help="Model Lab session UUID")
    parser.add_argument("--token", default="", help="JWT token (admin)")
    parser.add_argument("--email", default="", help="Admin email for /auth/login")
    parser.add_argument("--password", default="", help="Admin password for /auth/login")
    parser.add_argument("--max-tasks", type=int, default=0, help="Stop after N processed+failed tasks")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification")
    parser.add_argument("--log-level", default="INFO", help="DEBUG/INFO/WARNING/ERROR")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    try:
        uuid.UUID(args.session_id)
    except ValueError as exc:
        raise SystemExit(f"Invalid --session-id: {exc}") from exc
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
