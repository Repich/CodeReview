"""add companies and user company link

Revision ID: 20260115120000
Revises: 20260113190000
Create Date: 2026-01-15 12:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260115120000"
down_revision = "20260113190000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
    )

    op.add_column("user_accounts", sa.Column("company_id", postgresql.UUID(as_uuid=True)))
    op.create_foreign_key(
        "fk_user_accounts_company_id",
        "user_accounts",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_user_accounts_company_id", "user_accounts", ["company_id"])


def downgrade() -> None:
    op.drop_index("ix_user_accounts_company_id", table_name="user_accounts")
    op.drop_constraint("fk_user_accounts_company_id", "user_accounts", type_="foreignkey")
    op.drop_column("user_accounts", "company_id")
    op.drop_table("companies")
