from __future__ import annotations

from pydantic import Field, field_validator

from backend.app.schemas.base import ORMModel


def _sanitize_email(value: str) -> str:
    value = value.strip()
    if "@" not in value or value.startswith("@") or value.endswith("@"):
        raise ValueError("Invalid email")
    return value


class LoginPayload(ORMModel):
    email: str
    password: str = Field(min_length=6)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _sanitize_email(value)


class RegisterPayload(ORMModel):
    email: str
    password: str = Field(min_length=6)
    name: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _sanitize_email(value)


class TokenResponse(ORMModel):
    access_token: str
    token_type: str = "bearer"
