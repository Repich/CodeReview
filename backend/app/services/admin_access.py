from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.app.models.admin_access import AdminExternalAccessGrant
from backend.app.schemas.admin_access import AdminExternalAccessState

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_active_external_access_grant(db: Session) -> AdminExternalAccessGrant | None:
    now = _utcnow()
    return (
        db.query(AdminExternalAccessGrant)
        .filter(
            AdminExternalAccessGrant.revoked_at.is_(None),
            AdminExternalAccessGrant.expires_at > now,
        )
        .order_by(AdminExternalAccessGrant.expires_at.desc())
        .first()
    )


def is_external_admin_access_enabled(db: Session) -> bool:
    return get_active_external_access_grant(db) is not None


def build_state(db: Session) -> AdminExternalAccessState:
    grant = get_active_external_access_grant(db)
    if not grant:
        return AdminExternalAccessState(enabled=False)
    now = _utcnow()
    remaining_minutes = max(0, math.ceil((grant.expires_at - now).total_seconds() / 60))
    return AdminExternalAccessState(
        enabled=True,
        expires_at=grant.expires_at,
        opened_by=grant.opened_by,
        opened_from_ip=grant.opened_from_ip,
        opened_at=grant.created_at,
        reason=grant.reason,
        remaining_minutes=remaining_minutes,
    )


def enable_external_admin_access(
    db: Session,
    *,
    opened_by: uuid.UUID,
    opened_from_ip: str | None,
    duration_hours: int = 8,
    reason: str | None = None,
) -> AdminExternalAccessState:
    now = _utcnow()
    active = get_active_external_access_grant(db)
    if active:
        active.revoked_at = now
        active.revoked_by = opened_by
        db.add(active)
    grant = AdminExternalAccessGrant(
        opened_by=opened_by,
        opened_from_ip=opened_from_ip,
        reason=(reason or "").strip() or None,
        expires_at=now + timedelta(hours=max(1, duration_hours)),
    )
    db.add(grant)
    db.commit()
    logger.info(
        "External admin access enabled by %s from ip=%s for %s hours (grant_id=%s, expires_at=%s)",
        opened_by,
        opened_from_ip or "-",
        max(1, duration_hours),
        grant.id,
        grant.expires_at.isoformat(),
    )
    return build_state(db)


def disable_external_admin_access(
    db: Session,
    *,
    revoked_by: uuid.UUID,
    revoked_from_ip: str | None,
) -> AdminExternalAccessState:
    now = _utcnow()
    active = get_active_external_access_grant(db)
    if not active:
        logger.info(
            "External admin access disable requested by %s from ip=%s but no active grant",
            revoked_by,
            revoked_from_ip or "-",
        )
        return AdminExternalAccessState(enabled=False)
    active.revoked_at = now
    active.revoked_by = revoked_by
    db.add(active)
    db.commit()
    logger.info(
        "External admin access disabled by %s from ip=%s (grant_id=%s)",
        revoked_by,
        revoked_from_ip or "-",
        active.id,
    )
    return AdminExternalAccessState(enabled=False)
