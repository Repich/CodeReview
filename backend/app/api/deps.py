from __future__ import annotations

import secrets
import uuid

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.db.session import get_session
from backend.app.models.enums import UserRole
from backend.app.models.user import UserAccount
from backend.app.core.security import decode_access_token
from backend.app.services import auth_security

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

def get_db() -> Session:
    yield from get_session()


def _is_valid_worker_token(candidate: str | None) -> bool:
    if not candidate:
        return False
    expected = get_settings().worker_api_token
    return secrets.compare_digest(candidate, expected)


def require_worker_token(
    x_worker_token: str | None = Header(default=None, alias="X-Worker-Token"),
) -> None:
    if not _is_valid_worker_token(x_worker_token):
        raise HTTPException(status_code=401, detail="Worker authentication required")


def _extract_bearer_from_header(auth_header: str | None) -> str | None:
    if not auth_header:
        return None
    if not auth_header.lower().startswith("bearer "):
        return None
    return auth_header.split(" ", 1)[1].strip() or None


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> UserAccount:
    if not token:
        token = _extract_bearer_from_header(request.headers.get("Authorization"))
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = decode_access_token(token)
    except Exception as exc:  # jwt raises multiple exception types
        raise HTTPException(status_code=401, detail="Invalid authentication token") from exc
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication token") from exc
    user = db.get(UserAccount, user_uuid)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="User disabled")
    if user.role == UserRole.ADMIN:
        settings = get_settings()
        auth_security.enforce_admin_local(request, settings, db=db)
    request.state.current_user = user
    return user


def get_current_admin(current_user: UserAccount = Depends(get_current_user)) -> UserAccount:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user


def require_worker_or_admin(
    request: Request,
    x_worker_token: str | None = Header(default=None, alias="X-Worker-Token"),
    db: Session = Depends(get_db),
) -> None:
    if _is_valid_worker_token(x_worker_token):
        return
    try:
        user = get_current_user(request=request, token=None, db=db)
    except HTTPException as exc:
        raise HTTPException(status_code=401, detail="Worker or admin authentication required") from exc
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Worker or admin privileges required")


def get_current_teacher(current_user: UserAccount = Depends(get_current_user)) -> UserAccount:
    if current_user.role not in {UserRole.ADMIN, UserRole.TEACHER}:
        raise HTTPException(status_code=403, detail="Teacher privileges required")
    return current_user
