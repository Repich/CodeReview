from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from backend.app.models.norm import Norm


def _load_norm_catalog() -> dict[str, dict[str, Any]]:
    current = Path(__file__).resolve().parent
    for candidate in [current] + list(current.parents):
        potential = candidate / "norms.yaml"
        if potential.exists():
            data = yaml.safe_load(potential.read_text(encoding="utf-8")) or {}
            entries = data.get("norms", [])
            return {entry.get("norm_id"): entry for entry in entries if entry.get("norm_id")}
    return {}


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
