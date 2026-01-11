"""add caddy access logs

Revision ID: 20260110120000
Revises: 20260107160000
Create Date: 2026-01-10 12:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260110120000"
down_revision = "20260107160000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "caddy_access_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("host", sa.String(length=255)),
        sa.Column("method", sa.String(length=16)),
        sa.Column("uri", sa.String(length=1000)),
        sa.Column("status_code", sa.Integer()),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("size_bytes", sa.BigInteger()),
        sa.Column("remote_ip", sa.String(length=45)),
        sa.Column("user_agent", sa.String(length=255)),
        sa.Column("referer", sa.String(length=1000)),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text())),
    )
    op.create_index("ix_caddy_access_logs_created_at", "caddy_access_logs", ["created_at"])
    op.create_index("ix_caddy_access_logs_host", "caddy_access_logs", ["host"])
    op.create_index("ix_caddy_access_logs_remote_ip", "caddy_access_logs", ["remote_ip"])
    op.create_index("ix_caddy_access_logs_status_code", "caddy_access_logs", ["status_code"])


def downgrade() -> None:
    op.drop_index("ix_caddy_access_logs_status_code", table_name="caddy_access_logs")
    op.drop_index("ix_caddy_access_logs_remote_ip", table_name="caddy_access_logs")
    op.drop_index("ix_caddy_access_logs_host", table_name="caddy_access_logs")
    op.drop_index("ix_caddy_access_logs_created_at", table_name="caddy_access_logs")
    op.drop_table("caddy_access_logs")
