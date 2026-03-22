from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.core.config import get_settings
from backend.app.core.security import create_access_token, hash_password, verify_password
from backend.app.models.enums import UserRole, WalletTransactionType
from backend.app.models.user import UserAccount
from backend.app.schemas.auth import LoginPayload, RegisterPayload, TokenResponse
from backend.app.services import billing
from backend.app.services import auth_security, captcha

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginPayload, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    settings = get_settings()
    client_ip_obj = auth_security.get_client_ip(request, settings)
    client_ip = str(client_ip_obj) if client_ip_obj else None
    auth_security.enforce_rate_limit(
        db=db,
        ip_address=client_ip,
        path=f"{settings.api_prefix}/auth/login",
        window_minutes=settings.auth_failed_login_window_minutes,
        max_attempts=settings.auth_failed_login_limit,
        status_codes=(401, 403),
    )
    user = db.query(UserAccount).filter(UserAccount.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="User is disabled")
    if user.role == UserRole.ADMIN:
        auth_security.enforce_admin_local(request, settings, client_ip_obj, db=db)
    request.state.current_user = user
    token = create_access_token(str(user.id), user.role.value)
    return TokenResponse(access_token=token)


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterPayload, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    settings = get_settings()
    client_ip_obj = auth_security.get_client_ip(request, settings)
    client_ip = str(client_ip_obj) if client_ip_obj else None
    auth_security.enforce_rate_limit(
        db=db,
        ip_address=client_ip,
        path=f"{settings.api_prefix}/auth/register",
        window_minutes=settings.registration_rate_window_minutes,
        max_attempts=settings.registration_rate_limit,
        status_codes=None,
    )
    if payload.website and payload.website.strip():
        raise HTTPException(status_code=400, detail="Registration blocked")
    if settings.registration_captcha_enabled and settings.turnstile_secret_key:
        if not captcha.verify_turnstile(payload.captcha_token, client_ip):
            raise HTTPException(status_code=400, detail="Captcha verification failed")
    existing = db.query(UserAccount).filter(UserAccount.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")
    user = UserAccount(
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        role=UserRole.USER,
    )
    db.add(user)
    db.flush()
    if settings.registration_bonus_points > 0:
        billing.adjust_balance(
            db,
            user,
            amount=settings.registration_bonus_points,
            source="signup_bonus",
            txn_type=WalletTransactionType.CREDIT,
            context={"reason": "welcome_bonus"},
        )
    db.commit()
    db.refresh(user)
    request.state.current_user = user
    token = create_access_token(str(user.id), user.role.value)
    return TokenResponse(access_token=token)
