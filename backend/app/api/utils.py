from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.models.enums import UserRole
from backend.app.models.review_run import ReviewRun
from backend.app.models.user import UserAccount


def ensure_run_access(db: Session, review_run_id: uuid.UUID, current_user: UserAccount) -> ReviewRun:
    review_run = db.get(ReviewRun, review_run_id)
    if not review_run:
        raise HTTPException(status_code=404, detail="Review run not found")
    if current_user.role != UserRole.ADMIN and review_run.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied for this run")
    return review_run
