from __future__ import annotations

import uuid
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.models.enums import WalletTransactionType
from backend.app.models.user import UserAccount, Wallet, WalletTransaction


def get_or_create_wallet(db: Session, user: UserAccount) -> Wallet:
    wallet = user.wallet
    if wallet is None:
        wallet = Wallet(user_id=user.id, balance=0)
        db.add(wallet)
        db.flush()
    return wallet


def adjust_balance(
    db: Session,
    user: UserAccount,
    amount: int,
    source: str,
    txn_type: WalletTransactionType,
    context: Optional[dict] = None,
) -> WalletTransaction:
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    wallet = get_or_create_wallet(db, user)
    if txn_type == WalletTransactionType.DEBIT and wallet.balance < amount:
        raise HTTPException(status_code=402, detail="Insufficient balance")
    if txn_type == WalletTransactionType.DEBIT:
        wallet.balance -= amount
    else:
        wallet.balance += amount
    txn = WalletTransaction(
        wallet_id=wallet.id,
        txn_type=txn_type,
        source=source,
        amount=amount,
        context=context,
    )
    db.add(wallet)
    db.add(txn)
    return txn


def charge_for_run(db: Session, user: UserAccount, cost: int, run_id: uuid.UUID) -> WalletTransaction:
    return adjust_balance(
        db,
        user,
        amount=cost,
        source="review_run",
        txn_type=WalletTransactionType.DEBIT,
        context={"run_id": str(run_id)},
    )
