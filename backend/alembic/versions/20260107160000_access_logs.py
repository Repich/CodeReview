"""add access logs table

Revision ID: 20260107160000
Revises: 20260105143000_add_norm_source_fields
Create Date: 2026-01-07 16:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260107160000"
down_revision = "20260105143000_add_norm_source_fields"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "access_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("user_accounts.id"), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("block_reason", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_access_logs_created_at", "access_logs", ["created_at"])
    op.create_index("ix_access_logs_user_id", "access_logs", ["user_id"])


def downgrade():
    op.drop_index("ix_access_logs_user_id", table_name="access_logs")
    op.drop_index("ix_access_logs_created_at", table_name="access_logs")
    op.drop_table("access_logs")
