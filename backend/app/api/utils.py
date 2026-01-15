from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from backend.app.models.enums import UserRole
from backend.app.models.review_run import ReviewRun
from backend.app.models.user import UserAccount


def ensure_run_access(
    db: Session,
    review_run_id: uuid.UUID,
    current_user: UserAccount,
    require_owner: bool = False,
) -> ReviewRun:
    review_run = (
        db.query(ReviewRun)
        .options(joinedload(ReviewRun.user))
        .filter(ReviewRun.id == review_run_id)
        .first()
    )
    if not review_run:
        raise HTTPException(status_code=404, detail="Review run not found")
    if current_user.role != UserRole.ADMIN:
        if review_run.user_id == current_user.id:
            return review_run
        if require_owner:
            raise HTTPException(status_code=403, detail="Access denied for this run")
        if (
            current_user.company_id
            and review_run.user
            and review_run.user.company_id == current_user.company_id
        ):
            return review_run
        raise HTTPException(status_code=403, detail="Access denied for this run")
    return review_run
