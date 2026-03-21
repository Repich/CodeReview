"""add temporary external admin access grants

Revision ID: 20260321150000
Revises: 20260321120000
Create Date: 2026-03-21 15:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260321150000"
down_revision = "20260321120000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_external_access_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "opened_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("opened_from_ip", sa.String(length=64)),
        sa.Column("reason", sa.Text()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "revoked_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_accounts.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_admin_external_access_grants_expires_at",
        "admin_external_access_grants",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_admin_external_access_grants_revoked_at",
        "admin_external_access_grants",
        ["revoked_at"],
        unique=False,
    )
    op.create_index(
        "ix_admin_external_access_grants_created_at",
        "admin_external_access_grants",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_admin_external_access_grants_created_at", table_name="admin_external_access_grants")
    op.drop_index("ix_admin_external_access_grants_revoked_at", table_name="admin_external_access_grants")
    op.drop_index("ix_admin_external_access_grants_expires_at", table_name="admin_external_access_grants")
    op.drop_table("admin_external_access_grants")
