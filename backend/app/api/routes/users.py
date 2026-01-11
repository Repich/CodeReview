from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_admin, get_current_user, get_db
from backend.app.core.security import hash_password
from backend.app.models.enums import UserRole
from backend.app.models.user import UserAccount
from backend.app.schemas.users import UserCreate, UserRead, UserStatusUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(
    current_admin: UserAccount = Depends(get_current_admin),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    email: str | None = Query(default=None),
    status: str | None = Query(default=None),
    role: UserRole | None = Query(default=None),
) -> list[UserAccount]:
    query = db.query(UserAccount).order_by(UserAccount.created_at.desc())
    if email:
        query = query.filter(UserAccount.email.ilike(f"%{email}%"))
    if status:
        query = query.filter(UserAccount.status == status)
    if role:
        query = query.filter(UserAccount.role == role)
    return query.offset(offset).limit(limit).all()


@router.post("", response_model=UserRead, status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_admin: UserAccount = Depends(get_current_admin),
) -> UserAccount:
    existing = db.query(UserAccount).filter(UserAccount.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")
    user = UserAccount(
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        role=payload.role or UserRole.USER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/status", response_model=UserRead)
def update_user_status(
    user_id: uuid.UUID,
    payload: UserStatusUpdate,
    db: Session = Depends(get_db),
    current_admin: UserAccount = Depends(get_current_admin),
) -> UserAccount:
    if current_admin.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot change your own status")
    user = db.get(UserAccount, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.status = payload.status
    db.commit()
    db.refresh(user)
    return user


@router.get("/me", response_model=UserRead)
def read_me(current_user: UserAccount = Depends(get_current_user)) -> UserAccount:
    return current_user
