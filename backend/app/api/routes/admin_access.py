from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_admin, get_db
from backend.app.core.config import get_settings
from backend.app.models.user import UserAccount
from backend.app.schemas.admin_access import (
    AdminExternalAccessEnableRequest,
    AdminExternalAccessState,
)
from backend.app.services import admin_access, auth_security

router = APIRouter(prefix="/admin/access-control", tags=["admin-access-control"])


@router.get("/external-admin", response_model=AdminExternalAccessState)
def get_external_admin_access_state(
    current_admin: UserAccount = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> AdminExternalAccessState:
    _ = current_admin
    return admin_access.build_state(db)


@router.post("/external-admin", response_model=AdminExternalAccessState)
def enable_external_admin_access(
    payload: AdminExternalAccessEnableRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: UserAccount = Depends(get_current_admin),
) -> AdminExternalAccessState:
    settings = get_settings()
    ip_obj = auth_security.get_client_ip(request, settings)
    ip_value = str(ip_obj) if ip_obj else None
    return admin_access.enable_external_admin_access(
        db,
        opened_by=current_admin.id,
        opened_from_ip=ip_value,
        duration_hours=payload.duration_hours,
        reason=payload.reason,
    )


@router.delete("/external-admin", response_model=AdminExternalAccessState)
def disable_external_admin_access(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: UserAccount = Depends(get_current_admin),
) -> AdminExternalAccessState:
    settings = get_settings()
    ip_obj = auth_security.get_client_ip(request, settings)
    ip_value = str(ip_obj) if ip_obj else None
    return admin_access.disable_external_admin_access(
        db,
        revoked_by=current_admin.id,
        revoked_from_ip=ip_value,
    )
