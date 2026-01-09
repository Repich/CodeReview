"""add user auth columns and default admin

Revision ID: 20260103160000
Revises: 20260103125304
Create Date: 2026-01-03 16:00:00

"""
from __future__ import annotations

import uuid

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
    password_hash = (
        "pbkdf2_sha256$200000$11e2a5cdd376047ab257201160cfc496$"
        "5aa90d04e75e4ca9833a4c779548a79e95723427ab41de21ba951812007d6251"
    )
    admin_id = str(uuid.uuid4())
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO user_accounts (id, email, name, status, password_hash, role)
            SELECT
                CAST(:id AS uuid),
                CAST(:email AS VARCHAR(255)),
                CAST(:name AS VARCHAR(255)),
                'active',
                CAST(:password_hash AS VARCHAR(255)),
                'admin'
            WHERE NOT EXISTS (
                SELECT 1 FROM user_accounts WHERE email = CAST(:email AS VARCHAR(255))
            )
            """
        ),
        {
            "id": admin_id,
            "email": "admin@localhost",
            "name": "Administrator",
            "password_hash": password_hash,
        },
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM user_accounts WHERE email = :email"),
        {"email": "admin@localhost"},
    )
    op.drop_column("user_accounts", "role")
    op.drop_column("user_accounts", "password_hash")
    role_enum = sa.Enum("user", "admin", name="user_role")
    role_enum.drop(op.get_bind(), checkfirst=True)
