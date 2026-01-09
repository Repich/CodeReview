from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.app.core.config import get_settings


def _ensure_dir() -> Path:
    settings = get_settings()
    path = Path(settings.artifact_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_sources(run_id: str, sources: list[dict[str, Any]]) -> tuple[str, str, int]:
    """Persist JSON with source units. Returns (relative_path, checksum, size)."""
    target_dir = _ensure_dir()
    file_name = f"{run_id}_sources.json"
    file_path = target_dir / file_name
    payload = json.dumps(sources, ensure_ascii=False, indent=2)
    file_path.write_text(payload, encoding="utf-8")
    checksum = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    rel_path = file_name
    return rel_path, checksum, len(payload.encode("utf-8"))


def load_sources(relative_path: str) -> list[dict[str, Any]]:
    target_dir = _ensure_dir()
    payload = (target_dir / relative_path).read_text(encoding="utf-8")
    return json.loads(payload)


def save_llm_log(run_id: str, index: int, payload: dict[str, Any]) -> tuple[str, int]:
    target_dir = _ensure_dir()
    file_name = f"{run_id}_llm_{index}.json"
    file_path = target_dir / file_name
    data = json.dumps(payload, ensure_ascii=False, indent=2)
    file_path.write_text(data, encoding="utf-8")
    return file_name, len(data.encode("utf-8"))


def load_json(relative_path: str) -> dict[str, Any]:
    target_dir = _ensure_dir()
    payload = (target_dir / relative_path).read_text(encoding="utf-8")
    return json.loads(payload)


def delete_artifact(relative_path: str) -> None:
    target_dir = _ensure_dir()
    file_path = target_dir / relative_path
    try:
        file_path.unlink()
    except FileNotFoundError:
        pass


def delete_run_artifacts(run_id: str) -> None:
    target_dir = _ensure_dir()
    pattern = f"{run_id}_*"
    for path in target_dir.glob(pattern):
        try:
            path.unlink()
        except FileNotFoundError:
            continue
