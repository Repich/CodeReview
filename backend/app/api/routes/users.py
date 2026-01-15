from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_admin, get_current_user, get_db
from backend.app.core.security import hash_password
from backend.app.models.company import Company
from backend.app.models.enums import UserRole
from backend.app.models.user import UserAccount, Wallet
from backend.app.schemas.users import UserCompanyUpdate, UserCreate, UserRead, UserStatusUpdate

router = APIRouter(prefix="/users", tags=["users"])


def _build_user_read(
    user: UserAccount,
    wallet: Wallet | None = None,
    company: Company | None = None,
) -> UserRead:
    return UserRead(
        id=user.id,
        email=user.email,
        name=user.name,
        status=user.status,
        role=user.role,
        created_at=user.created_at,
        wallet_balance=wallet.balance if wallet else None,
        wallet_currency=wallet.currency if wallet else None,
        company_id=company.id if company else user.company_id,
        company_name=company.name if company else user.company_name,
    )


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
    query = (
        db.query(UserAccount, Wallet, Company)
        .outerjoin(Wallet, Wallet.user_id == UserAccount.id)
        .outerjoin(Company, Company.id == UserAccount.company_id)
        .order_by(UserAccount.created_at.desc())
    )
    if email:
        query = query.filter(UserAccount.email.ilike(f"%{email}%"))
    if status:
        query = query.filter(UserAccount.status == status)
    if role:
        query = query.filter(UserAccount.role == role)
    rows = query.offset(offset).limit(limit).all()
    return [_build_user_read(user, wallet, company) for user, wallet, company in rows]


@router.post("", response_model=UserRead, status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_admin: UserAccount = Depends(get_current_admin),
) -> UserAccount:
    existing = db.query(UserAccount).filter(UserAccount.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")
    company = None
    if payload.company_id:
        company = db.get(Company, payload.company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
    user = UserAccount(
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        role=payload.role or UserRole.USER,
        company_id=company.id if company else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    if company:
        user.company = company
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


@router.patch("/{user_id}/company", response_model=UserRead)
def update_user_company(
    user_id: uuid.UUID,
    payload: UserCompanyUpdate,
    db: Session = Depends(get_db),
    current_admin: UserAccount = Depends(get_current_admin),
) -> UserAccount:
    user = db.get(UserAccount, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.company_id is None:
        user.company = None
        user.company_id = None
    else:
        company = db.get(Company, payload.company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        user.company = company
        user.company_id = company.id
    db.commit()
    db.refresh(user)
    return user


@router.get("/me", response_model=UserRead)
def read_me(current_user: UserAccount = Depends(get_current_user)) -> UserAccount:
    return current_user
