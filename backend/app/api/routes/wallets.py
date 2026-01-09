from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_admin, get_current_user, get_db
from backend.app.models.enums import WalletTransactionType
from backend.app.models.user import UserAccount, Wallet, WalletTransaction
from backend.app.schemas.users import WalletAdjustPayload, WalletRead, WalletTransactionRead
from backend.app.services import billing

router = APIRouter(prefix="/wallets", tags=["wallets"])


@router.get("/me", response_model=WalletRead)
def get_my_wallet(current_user=Depends(get_current_user), db: Session = Depends(get_db)) -> Wallet:
    wallet = billing.get_or_create_wallet(db, current_user)
    db.commit()
    db.refresh(wallet)
    return wallet


@router.get("/transactions", response_model=list[WalletTransactionRead])
def list_transactions(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    wallet = billing.get_or_create_wallet(db, current_user)
    db.commit()
    return (
        db.query(WalletTransaction)
        .filter(WalletTransaction.wallet_id == wallet.id)
        .order_by(WalletTransaction.created_at.desc())
        .limit(limit)
        .all()
    )


@router.post("/adjust", response_model=WalletTransactionRead)
def adjust_wallet(
    payload: WalletAdjustPayload,
    db: Session = Depends(get_db),
    current_admin: UserAccount = Depends(get_current_admin),
):
    if not payload.user_id and not payload.user_email:
        raise HTTPException(status_code=400, detail="user_id or user_email is required")
    user = None
    if payload.user_id:
        user = db.get(UserAccount, payload.user_id)
    elif payload.user_email:
        user = db.query(UserAccount).filter(UserAccount.email == payload.user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    txn_type = WalletTransactionType.CREDIT if payload.amount > 0 else WalletTransactionType.DEBIT
    txn = billing.adjust_balance(
        db,
        user,
        amount=abs(payload.amount),
        source="manual_adjustment",
        txn_type=txn_type,
        context={"reason": payload.reason},
    )
    db.commit()
    db.refresh(txn)
    return txn
