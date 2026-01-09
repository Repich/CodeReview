from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.app.db.session import get_session
from backend.app.models.enums import UserRole
from backend.app.models.user import UserAccount
from backend.app.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

def get_db() -> Session:
    yield from get_session()


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
        token = request.query_params.get("token")
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
    request.state.current_user = user
    return user


def get_current_admin(current_user: UserAccount = Depends(get_current_user)) -> UserAccount:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user
