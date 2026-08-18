"""add user authentication columns

Revision ID: 20260103160000
Revises: 20260103125304
Create Date: 2026-01-03 16:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260103160000"
down_revision = "20260103125304"
branch_labels = None
depends_on = None


def upgrade() -> None:
    role_enum = sa.Enum("user", "admin", name="user_role")
    role_enum.create(op.get_bind(), checkfirst=True)
    op.add_column("user_accounts", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.add_column(
        "user_accounts",
        sa.Column("role", role_enum, nullable=False, server_default="user"),
    )


def downgrade() -> None:
    op.drop_column("user_accounts", "role")
    op.drop_column("user_accounts", "password_hash")
    role_enum = sa.Enum("user", "admin", name="user_role")
    role_enum.drop(op.get_bind(), checkfirst=True)
