from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_db
from backend.app.api.utils import ensure_run_access
from backend.app.core.config import get_settings
from backend.app.models.audit import AuditLog, IOLog
from backend.app.models.enums import UserRole
from backend.app.models.review_run import ReviewRun
from backend.app.models.user import UserAccount
from backend.app.schemas.audit import (
    AuditLogCreate,
    AuditLogRead,
    IOLogCreate,
    IOLogRead,
)

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs", response_model=list[AuditLogRead])
def list_audit_logs(
    review_run_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> list[AuditLogRead]:
    query = db.query(AuditLog).join(ReviewRun, ReviewRun.id == AuditLog.review_run_id)
    if review_run_id:
        query = query.filter(AuditLog.review_run_id == review_run_id)
    if current_user.role != UserRole.ADMIN:
        if current_user.company_id:
            query = query.join(UserAccount, UserAccount.id == ReviewRun.user_id).filter(
                UserAccount.company_id == current_user.company_id
            )
        else:
            query = query.filter(ReviewRun.user_id == current_user.id)
    return query.order_by(AuditLog.created_at.desc()).all()


@router.post("/logs", response_model=AuditLogRead, status_code=201)
def create_audit_log(
    payload: AuditLogCreate, db: Session = Depends(get_db)
) -> AuditLog:
    record = AuditLog(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/io", response_model=list[IOLogRead])
def list_io_logs(
    review_run_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
) -> list[IOLogRead]:
    query = db.query(IOLog).join(ReviewRun, ReviewRun.id == IOLog.review_run_id)
    if review_run_id:
        query = query.filter(IOLog.review_run_id == review_run_id)
    if current_user.role != UserRole.ADMIN:
        if current_user.company_id:
            query = query.join(UserAccount, UserAccount.id == ReviewRun.user_id).filter(
                UserAccount.company_id == current_user.company_id
            )
        else:
            query = query.filter(ReviewRun.user_id == current_user.id)
    return query.order_by(IOLog.created_at.desc()).all()


@router.post("/io", response_model=IOLogRead, status_code=201)
def create_io_log(payload: IOLogCreate, db: Session = Depends(get_db)) -> IOLog:
    record = IOLog(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/io/{io_log_id}/download")
def download_artifact(
    io_log_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_user),
):
    record = db.get(IOLog, io_log_id)
    if not record:
        raise HTTPException(status_code=404, detail="Artifact not found")
    ensure_run_access(db, record.review_run_id, current_user)
    settings = get_settings()
    artifact_path = Path(settings.artifact_dir) / record.storage_path
    if not artifact_path.exists():
        raise HTTPException(status_code=404, detail="Artifact file missing")
    filename = artifact_path.name
    return FileResponse(artifact_path, media_type="application/octet-stream", filename=filename)
