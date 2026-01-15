from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath
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


def _sanitize_source_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    parts = [part for part in PurePosixPath(normalized).parts if part not in ("", ".", "..")]
    if not parts:
        return "source"
    return "/".join(parts)


def _dedupe_source_path(value: str, index: int, used: set[str]) -> str:
    if value not in used:
        used.add(value)
        return value
    if "." in value:
        base, ext = value.rsplit(".", 1)
        candidate = f"{base}_{index}.{ext}"
    else:
        candidate = f"{value}_{index}"
    used.add(candidate)
    return candidate


def save_sources_raw(run_id: str, sources: list[dict[str, Any]]) -> tuple[str, str, int]:
    """Persist raw source contents as a zip archive. Returns (relative_path, checksum, size)."""
    target_dir = _ensure_dir()
    file_name = f"{run_id}_sources_raw.zip"
    file_path = target_dir / file_name
    used_names: set[str] = set()
    with zipfile.ZipFile(file_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, source in enumerate(sources, start=1):
            raw_name = source.get("path") or source.get("name") or f"source_{index}"
            safe_name = _sanitize_source_path(str(raw_name))
            safe_name = _dedupe_source_path(safe_name, index, used_names)
            content = source.get("content") or ""
            archive.writestr(safe_name, content)
    data = file_path.read_bytes()
    checksum = hashlib.sha256(data).hexdigest()
    return file_name, checksum, len(data)


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
