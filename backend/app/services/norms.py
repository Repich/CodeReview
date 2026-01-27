from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import yaml
from sqlalchemy.orm import Session

from backend.app.models.norm import Norm


def _load_norm_catalog() -> dict[str, dict[str, Any]]:
    current = Path(__file__).resolve().parent
    for candidate in [current] + list(current.parents):
        norms_path = candidate / "norms.yaml"
        custom_path = candidate / "custom_norms.yaml"
        if norms_path.exists() or custom_path.exists():
            entries: list[dict[str, Any]] = []
            if norms_path.exists():
                data = yaml.safe_load(norms_path.read_text(encoding="utf-8")) or {}
                entries.extend(_extract_norm_entries(data))
            if custom_path.exists():
                data = yaml.safe_load(custom_path.read_text(encoding="utf-8")) or {}
                entries.extend(_extract_norm_entries(data))
            return {entry.get("norm_id"): entry for entry in entries if entry.get("norm_id")}
    return {}


def load_norm_catalog_entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = _extract_norm_entries(data)
    return [entry for entry in entries if entry.get("norm_id")]


def load_custom_norms(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = _extract_norm_entries(data)
    return [entry for entry in entries if entry.get("norm_id")]


def save_custom_norms(path: Path, entries: list[dict[str, Any]]) -> None:
    payload = {"norms": entries}
    data = yaml.safe_dump(
        payload,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=120,
    )
    path.write_text(data, encoding="utf-8")


def _extract_norm_entries(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        entries = data.get("norms", [])
    elif isinstance(data, list):
        entries = data
    else:
        entries = []
    return [entry for entry in entries if isinstance(entry, dict)]


def filter_norm_catalog_entries(
    entries: Iterable[dict[str, Any]],
    query: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    items = list(entries)
    if query:
        lowered = query.lower()
        items = [
            entry
            for entry in items
            if lowered in str(entry.get("norm_id", "")).lower()
            or lowered in str(entry.get("title", "")).lower()
            or lowered in str(entry.get("section", "")).lower()
        ]
    items.sort(key=lambda entry: str(entry.get("norm_id", "")))
    return items[:limit]


def build_norm_lookup(db: Session, norm_ids: set[str]) -> dict[str, dict[str, str | None]]:
    if not norm_ids:
        return {}
    lookup: dict[str, dict[str, str | None]] = {}
    norms = db.query(Norm).filter(Norm.norm_id.in_(norm_ids)).all()
    for norm in norms:
        lookup[norm.norm_id] = {
            "title": norm.title,
            "text": norm.norm_text,
            "section": norm.section,
            "source_reference": norm.source_reference,
            "source_excerpt": norm.source_excerpt,
        }
    missing = norm_ids - lookup.keys()
    if not missing:
        return lookup
    catalog = _load_norm_catalog()
    for norm_id in missing:
        entry = catalog.get(norm_id)
        if entry:
            lookup[norm_id] = {
                "title": entry.get("title"),
                "text": entry.get("norm_text"),
                "section": entry.get("section"),
                "source_reference": entry.get("source_reference") or entry.get("source_standard"),
                "source_excerpt": entry.get("source_excerpt"),
            }
    return lookup
