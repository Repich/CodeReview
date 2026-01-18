"""add teacher role

Revision ID: 20260116100000
Revises: 20260115120000
Create Date: 2026-01-16 10:00:00

"""
from __future__ import annotations

from alembic import op

revision = "20260116100000"
down_revision = "20260115120000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'teacher'")


def downgrade() -> None:
    # Postgres enums do not support removing values safely.
    pass
