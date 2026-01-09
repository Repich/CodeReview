"""user wallets

Revision ID: 20260103125304
Revises: 0001_initial
Create Date: 2026-01-03 12:53:04

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260103125304"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    wallet_txn_type = sa.Enum("debit", "credit", name="wallet_txn_type")
    op.create_table(
        "user_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255)),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="active"),
        sa.Column("auth_provider", sa.String(length=100)),
        sa.Column("auth_sub", sa.String(length=255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "wallets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("balance", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=20), nullable=False, server_default="points"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user_accounts.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "wallet_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("wallet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("txn_type", wallet_txn_type, nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("context", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"], ondelete="CASCADE"),
    )

    op.add_column("review_runs", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("review_runs", sa.Column("cost_points", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_review_runs_user_accounts",
        "review_runs",
        "user_accounts",
        ["user_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_review_runs_user_accounts", "review_runs", type_="foreignkey")
    op.drop_column("review_runs", "cost_points")
    op.drop_column("review_runs", "user_id")

    op.drop_table("wallet_transactions")
    op.drop_table("wallets")
    op.drop_table("user_accounts")

    wallet_txn_type = sa.Enum("debit", "credit", name="wallet_txn_type")
    wallet_txn_type.drop(op.get_bind(), checkfirst=True)
