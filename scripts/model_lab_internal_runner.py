#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import tempfile
import threading
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


class ServerApiClient:
    def login(self, *, email: str, password: str) -> str:  # pragma: no cover - interface
        raise NotImplementedError

    def fetch_next_task(self, session_id: str) -> dict[str, Any] | None:  # pragma: no cover - interface
        raise NotImplementedError

    def submit_result(self, run_id: uuid.UUID, payload: dict[str, Any]) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def mark_failed(self, run_id: uuid.UUID, error_message: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def set_token(self, token: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class HttpxServerApiClient(ServerApiClient):
    def __init__(self, *, api_base: str, verify_ssl: bool) -> None:
        timeout = httpx.Timeout(connect=15.0, read=600.0, write=600.0, pool=30.0)
        self.client = httpx.Client(base_url=api_base, timeout=timeout, verify=verify_ssl)

    def close(self) -> None:
        self.client.close()

    def set_token(self, token: str) -> None:
        self.client.headers["Authorization"] = f"Bearer {token}"

    def login(self, *, email: str, password: str) -> str:
        response = self.client.post(
            "/auth/login",
            json={"email": email, "password": password},
        )
        response.raise_for_status()
        payload = response.json()
        token = str(payload.get("access_token") or "").strip()
        if not token:
            raise RuntimeError("Login succeeded but access_token is missing")
        return token

    def fetch_next_task(self, session_id: str) -> dict[str, Any] | None:
        response = self.client.get(f"/admin/model-lab/sessions/{session_id}/internal-next-task")
        if response.status_code == 204:
            return None
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Unexpected task payload")
        return payload

    def submit_result(self, run_id: uuid.UUID, payload: dict[str, Any]) -> None:
        response = self.client.post(f"/review-runs/{run_id}/results", json=payload)
        response.raise_for_status()

    def mark_failed(self, run_id: uuid.UUID, error_message: str) -> None:
        response = self.client.post(
            f"/admin/model-lab/review-runs/{run_id}/fail",
            json={"error_message": error_message},
        )
        response.raise_for_status()


class CurlServerApiClient(ServerApiClient):
    def __init__(
        self,
        *,
        api_base: str,
        verify_ssl: bool,
        proxy_url: str | None,
        proxy_negotiate: bool,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.verify_ssl = verify_ssl
        self.proxy_url = (proxy_url or "").strip() or None
        self.proxy_negotiate = proxy_negotiate
        self.token = ""

    def close(self) -> None:
        return None

    def set_token(self, token: str) -> None:
        self.token = token

    def _curl_request(
        self,
        *,
        method: str,
        path: str,
        payload_obj: dict[str, Any] | None = None,
    ) -> tuple[int, str]:
        url = f"{self.api_base}{path}"
        cmd = ["/usr/bin/curl", "-sS", "-X", method.upper(), url]
        cmd.extend(["--connect-timeout", "20", "--max-time", "1800"])
        if not self.verify_ssl:
            cmd.append("-k")
        if self.proxy_url:
            cmd.extend(["-x", self.proxy_url])
        if self.proxy_negotiate:
            cmd.extend(["--proxy-negotiate", "-u", ":"])
        cmd.extend(["-H", "Content-Type: application/json"])
        if self.token:
            cmd.extend(["-H", f"Authorization: Bearer {self.token}"])
        data_file: tempfile.NamedTemporaryFile | None = None
        try:
            if payload_obj is not None:
                data_file = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False)
                json.dump(payload_obj, data_file, ensure_ascii=False)
                data_file.flush()
                data_file.close()
                cmd.extend(["--data-binary", f"@{data_file.name}"])
            cmd.extend(["-w", "\n__HTTP_STATUS__:%{http_code}"])
            proc = subprocess.run(cmd, capture_output=True, text=True)
        finally:
            if data_file is not None:
                try:
                    Path(data_file.name).unlink(missing_ok=True)
                except Exception:  # noqa: BLE001
                    pass
        if proc.returncode != 0:
            raise RuntimeError(f"curl failed ({proc.returncode}): {proc.stderr.strip()}")
        stdout = proc.stdout
        marker = "\n__HTTP_STATUS__:"
        if marker not in stdout:
            raise RuntimeError(f"curl malformed response: {stdout[:400]}")
        body, status_part = stdout.rsplit(marker, 1)
        try:
            status_code = int(status_part.strip())
        except ValueError as exc:  # noqa: PERF203
            raise RuntimeError(f"curl status parse failed: {status_part}") from exc
        return status_code, body

    def login(self, *, email: str, password: str) -> str:
        status, body = self._curl_request(
            method="POST",
            path="/auth/login",
            payload_obj={"email": email, "password": password},
        )
        if status >= 400:
            raise RuntimeError(f"Login failed ({status}): {body[:400]}")
        payload = json.loads(body or "{}")
        token = str(payload.get("access_token") or "").strip()
        if not token:
            raise RuntimeError("Login succeeded but access_token is missing")
        return token

    def fetch_next_task(self, session_id: str) -> dict[str, Any] | None:
        status, body = self._curl_request(
            method="GET",
            path=f"/admin/model-lab/sessions/{session_id}/internal-next-task",
        )
        if status == 204:
            return None
        if status >= 400:
            raise RuntimeError(f"Fetch task failed ({status}): {body[:500]}")
        payload = json.loads(body or "{}")
        if not isinstance(payload, dict):
            raise RuntimeError("Unexpected task payload")
        return payload

    def submit_result(self, run_id: uuid.UUID, payload: dict[str, Any]) -> None:
        status, body = self._curl_request(
            method="POST",
            path=f"/review-runs/{run_id}/results",
            payload_obj=payload,
        )
        if status >= 400:
            raise RuntimeError(f"Submit result failed ({status}): {body[:500]}")

    def mark_failed(self, run_id: uuid.UUID, error_message: str) -> None:
        status, body = self._curl_request(
            method="POST",
            path=f"/admin/model-lab/review-runs/{run_id}/fail",
            payload_obj={"error_message": error_message},
        )
        if status >= 400:
            raise RuntimeError(f"Mark failed failed ({status}): {body[:500]}")

def _build_server_client(args: argparse.Namespace, *, api_base: str, verify_ssl: bool) -> ServerApiClient:
    if args.server_transport == "curl":
        return CurlServerApiClient(
            api_base=api_base,
            verify_ssl=verify_ssl,
            proxy_url=args.proxy_url,
            proxy_negotiate=args.proxy_negotiate,
        )
    return HttpxServerApiClient(api_base=api_base, verify_ssl=verify_ssl)


def _run_worker_loop(
    *,
    worker_id: int,
    args: argparse.Namespace,
    api_base: str,
    verify_ssl: bool,
    token: str,
    stop_event: threading.Event,
    counters: dict[str, int | bool],
    counters_lock: threading.Lock,
) -> None:
    client = _build_server_client(args, api_base=api_base, verify_ssl=verify_ssl)
    client.set_token(token)
    analyzer = Analyzer()
    try:
        while not stop_event.is_set():
            with counters_lock:
                done = int(counters["processed"]) + int(counters["failed"])
                if args.max_tasks and done >= args.max_tasks:
                    stop_event.set()
                    return
            task_payload = client.fetch_next_task(args.session_id)
            if not task_payload:
                return
            task = _build_task(task_payload)
            LOG.info("[w%s] Processing run %s (%s sources)", worker_id, task.review_run_id, len(task.sources))
            try:
                result = analyzer.run(task)
                out_payload = serialize_result(result)
                client.submit_result(task.review_run_id, out_payload)
                with counters_lock:
                    counters["processed"] = int(counters["processed"]) + 1
                LOG.info("[w%s] Submitted results for run %s", worker_id, task.review_run_id)
            except Exception as exc:  # noqa: BLE001
                with counters_lock:
                    counters["failed"] = int(counters["failed"]) + 1
                message = _extract_error_message(exc)
                LOG.exception("[w%s] Run %s failed, marking as failed", worker_id, task.review_run_id)
                try:
                    client.mark_failed(task.review_run_id, message)
                except Exception:  # noqa: BLE001
                    LOG.exception("[w%s] Unable to mark run %s as failed on server", worker_id, task.review_run_id)
                    with counters_lock:
                        counters["fatal_error"] = True
                    stop_event.set()
                    return
    finally:
        try:
            client.close()
        except Exception:  # noqa: BLE001
            pass


def run(args: argparse.Namespace) -> int:
    api_base = _normalize_api_base(args.base_url)
    verify_ssl = not args.insecure
    bootstrap_client = _build_server_client(args, api_base=api_base, verify_ssl=verify_ssl)
    try:
        token = args.token.strip() if args.token else ""
        if not token:
            if not args.email or not args.password:
                raise RuntimeError("Provide --token or --email with --password")
            token = bootstrap_client.login(email=args.email, password=args.password)
    finally:
        try:
            bootstrap_client.close()
        except Exception:  # noqa: BLE001
            pass

    workers = max(1, int(args.workers))
    counters: dict[str, int | bool] = {"processed": 0, "failed": 0, "fatal_error": False}
    counters_lock = threading.Lock()
    stop_event = threading.Event()
    threads: list[threading.Thread] = []

    for idx in range(workers):
        thread = threading.Thread(
            target=_run_worker_loop,
            kwargs={
                "worker_id": idx + 1,
                "args": args,
                "api_base": api_base,
                "verify_ssl": verify_ssl,
                "token": token,
                "stop_event": stop_event,
                "counters": counters,
                "counters_lock": counters_lock,
            },
            name=f"model-lab-runner-{idx + 1}",
            daemon=False,
        )
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    processed = int(counters["processed"])
    failed = int(counters["failed"])
    LOG.info("Done: processed=%s failed=%s workers=%s", processed, failed, workers)
    return 2 if bool(counters["fatal_error"]) else 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="One-off internal Model Lab runner")
    parser.add_argument("--base-url", required=True, help="CodeReview base URL, e.g. https://codereview.1cretail.ru")
    parser.add_argument("--session-id", required=True, help="Model Lab session UUID")
    parser.add_argument("--token", default="", help="JWT token (admin)")
    parser.add_argument("--email", default="", help="Admin email for /auth/login")
    parser.add_argument("--password", default="", help="Admin password for /auth/login")
    parser.add_argument("--max-tasks", type=int, default=0, help="Stop after N processed+failed tasks")
    parser.add_argument("--workers", type=int, default=1, help="Parallel workers for internal cases (default: 1)")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification")
    parser.add_argument(
        "--server-transport",
        choices=("httpx", "curl"),
        default="httpx",
        help="Transport for CodeReview server API calls",
    )
    parser.add_argument("--proxy-url", default="", help="Proxy URL for --server-transport curl")
    parser.add_argument(
        "--proxy-negotiate",
        action="store_true",
        help="Use --proxy-negotiate -u : for curl transport",
    )
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
