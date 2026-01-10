from __future__ import annotations

from datetime import datetime, timedelta
from ipaddress import IPv4Address, IPv6Address
from typing import Iterable, Optional

from fastapi import HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.models.access_log import AccessLog
from backend.app.utils.request_ip import extract_client_ip, ip_in_cidrs


def get_client_ip(request: Request, settings: Settings) -> Optional[IPv4Address | IPv6Address]:
    return extract_client_ip(request, settings.trusted_proxy_depth)


def enforce_admin_local(
    request: Request,
    settings: Settings,
    ip_obj: Optional[IPv4Address | IPv6Address] = None,
) -> None:
    if not settings.admin_local_only:
        return
    ip_obj = ip_obj or get_client_ip(request, settings)
    if not ip_obj or not ip_in_cidrs(ip_obj, settings.admin_allowed_cidrs):
        raise HTTPException(status_code=403, detail="Admin access allowed only from local network")


def enforce_rate_limit(
    *,
    db: Session,
    ip_address: Optional[str],
    path: str,
    window_minutes: int,
    max_attempts: int,
    status_codes: Iterable[int] | None = None,
) -> None:
    if not ip_address or max_attempts <= 0 or window_minutes <= 0:
        return
    since = datetime.utcnow() - timedelta(minutes=window_minutes)
    query = db.query(func.count(AccessLog.id)).filter(
        AccessLog.ip_address == ip_address,
        AccessLog.path == path,
        AccessLog.created_at >= since,
    )
    if status_codes:
        query = query.filter(AccessLog.status_code.in_(list(status_codes)))
    attempts = query.scalar() or 0
    if attempts >= max_attempts:
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
