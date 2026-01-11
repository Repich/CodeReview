from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field, field_validator

from backend.app.schemas.base import ORMModel
from backend.app.models.enums import UserRole, WalletTransactionType
from backend.app.schemas.auth import _sanitize_email


class UserCreate(ORMModel):
    email: str
    password: str = Field(min_length=6)
    name: str | None = None
    role: UserRole | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _sanitize_email(value)


class UserRead(ORMModel):
    id: uuid.UUID
    email: str
    name: str | None
    status: str
    role: UserRole
    created_at: datetime


class UserStatusUpdate(ORMModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"active", "disabled"}:
            raise ValueError("Invalid status")
        return normalized


class WalletRead(ORMModel):
    id: uuid.UUID
    balance: int
    currency: str


class WalletTransactionRead(ORMModel):
    id: uuid.UUID
    wallet_id: uuid.UUID
    txn_type: WalletTransactionType
    source: str
    amount: int
    context: dict | None
    created_at: datetime


class WalletAdjustPayload(ORMModel):
    user_id: uuid.UUID | None = None
    user_email: str | None = None
    amount: int
    reason: str

    @field_validator("user_email")
    @classmethod
    def validate_user_email(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _sanitize_email(value)
