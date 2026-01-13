from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_admin, get_db
from backend.app.models.audit import AuditLog
from backend.app.models.enums import AuditEventType, ReviewStatus
from backend.app.models.review_run import ReviewRun
from backend.app.models.user import UserAccount
from backend.app.schemas.review_runs import ReviewRunRead

router = APIRouter(prefix="/admin/review-runs", tags=["admin"])


@router.post("/{review_run_id}/force-fail", response_model=ReviewRunRead)
def force_fail_review_run(
    review_run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_admin: UserAccount = Depends(get_current_admin),
) -> ReviewRun:
    review_run = db.get(ReviewRun, review_run_id)
    if not review_run:
        raise HTTPException(status_code=404, detail="Review run not found")
    if review_run.status == ReviewStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="Нельзя завершить уже выполненный запуск")
    review_run.status = ReviewStatus.FAILED
    review_run.finished_at = datetime.utcnow()
    db.add(review_run)
    db.add(
        AuditLog(
            review_run_id=review_run.id,
            event_type=AuditEventType.RUN_FAILED,
            actor=current_admin.email,
            payload={"reason": "forced_by_admin"},
        )
    )
    db.commit()
    db.refresh(review_run)
    return review_run


@router.post("/{review_run_id}/requeue", response_model=ReviewRunRead)
def requeue_review_run(
    review_run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_admin: UserAccount = Depends(get_current_admin),
) -> ReviewRun:
    review_run = db.get(ReviewRun, review_run_id)
    if not review_run:
        raise HTTPException(status_code=404, detail="Review run not found")
    if review_run.status == ReviewStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="Нельзя поставить в очередь завершенный запуск")
    if review_run.status == ReviewStatus.FAILED:
        raise HTTPException(
            status_code=409,
            detail="Используйте перезапуск для завершенных или ошибочных запусков",
        )
    review_run.status = ReviewStatus.QUEUED
    review_run.queued_at = datetime.utcnow()
    review_run.started_at = None
    review_run.finished_at = None
    db.add(review_run)
    db.commit()
    db.refresh(review_run)
    return review_run
