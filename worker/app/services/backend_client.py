from __future__ import annotations

import uuid
from typing import Any

import httpx

from worker.app.config import get_settings
from worker.app.models import AnalysisTask, SourceUnit


class BackendClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = httpx.Client(base_url=self.settings.backend_api_url, timeout=30)

    def fetch_task(self) -> AnalysisTask | None:
        response = self.client.get("/review-runs/next-task")
        if response.status_code == 204:
            return None
        response.raise_for_status()
        payload = response.json()
        sources = [
            SourceUnit(
                path=item["path"],
                name=item.get("name", item["path"]),
                content=item["content"],
                module_type=item.get("module_type", "CommonModule"),
                change_ranges=[
                    (rng["start"], rng["end"])
                    for rng in (item.get("change_ranges") or [])
                    if rng is not None
                ],
            )
            for item in payload.get("sources", [])
        ]
        return AnalysisTask(
            review_run_id=uuid.UUID(payload["review_run_id"]),
            sources=sources,
            settings=payload.get("settings"),
            context=payload.get("context"),
        )

    def submit_results(self, run_id: uuid.UUID, data: dict[str, Any]) -> None:
        response = self.client.post(f"/review-runs/{run_id}/results", json=data)
        response.raise_for_status()
