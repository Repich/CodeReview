from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from backend.app.api.deps import get_current_user
from backend.app.schemas.changelog import ChangelogRead

router = APIRouter(prefix="/changelog", tags=["changelog"])


def _read_changelog() -> tuple[str, datetime]:
    changelog_path = None
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "CHANGELOG.md"
        if candidate.exists():
            changelog_path = candidate
            break
    if changelog_path is None:
        raise HTTPException(status_code=404, detail="Changelog not found")
    content = changelog_path.read_text(encoding="utf-8")
    updated_at = datetime.fromtimestamp(changelog_path.stat().st_mtime, tz=timezone.utc)
    return content, updated_at


@router.get("", response_model=ChangelogRead)
def get_changelog(_: object = Depends(get_current_user)) -> ChangelogRead:
    content, updated_at = _read_changelog()
    return ChangelogRead(content=content, updated_at=updated_at)
