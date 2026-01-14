"""add reviewer comment to ai findings

Revision ID: 20260113190000
Revises: 20260110120000
Create Date: 2026-01-13 19:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260113190000"
down_revision = "20260110120000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_findings", sa.Column("reviewer_comment", sa.Text()))


def downgrade() -> None:
    op.drop_column("ai_findings", "reviewer_comment")
