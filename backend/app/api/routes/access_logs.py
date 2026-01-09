from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_admin, get_db
from backend.app.models.access_log import AccessLog
from backend.app.schemas.access_logs import AccessLogRead

router = APIRouter(prefix="/admin/access-logs", tags=["admin"])


@router.get("", response_model=list[AccessLogRead])
def list_access_logs(
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    ip: str | None = Query(default=None),
    user_id: uuid.UUID | None = Query(default=None),
    path_query: str | None = Query(default=None, alias="path"),
) -> list[AccessLogRead]:
    query = db.query(AccessLog).order_by(AccessLog.created_at.desc())
    if ip:
        query = query.filter(AccessLog.ip_address == ip)
    if user_id:
        query = query.filter(AccessLog.user_id == user_id)
    if path_query:
        query = query.filter(AccessLog.path.ilike(f"%{path_query}%"))
    entries = query.limit(limit).all()
    results: list[AccessLogRead] = []
    for entry in entries:
        results.append(
            AccessLogRead(
                id=entry.id,
                created_at=entry.created_at,
                user_id=entry.user_id,
                user_email=entry.user.email if entry.user else None,
                ip_address=entry.ip_address,
                country_code=entry.country_code,
                method=entry.method,
                path=entry.path,
                status_code=entry.status_code,
                duration_ms=entry.duration_ms,
                user_agent=entry.user_agent,
                block_reason=entry.block_reason,
            )
        )
    return results
