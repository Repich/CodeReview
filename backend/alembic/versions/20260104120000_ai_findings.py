"""add ai findings table

Revision ID: 20260104120000
Revises: 20260103160000
Create Date: 2026-01-04 12:00:00

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260104120000"
down_revision = "20260103160000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_type t
                JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE t.typname = 'ai_finding_status'
            ) THEN
                CREATE TYPE ai_finding_status AS ENUM ('suggested', 'pending', 'confirmed', 'rejected');
            END IF;
        END$$;
        """
    )
    ai_status = postgresql.ENUM(
        "suggested",
        "pending",
        "confirmed",
        "rejected",
        name="ai_finding_status",
        create_type=False,
    )

    op.create_table(
        "ai_findings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "review_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("review_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", ai_status, nullable=False, server_default="suggested"),
        sa.Column("norm_id", sa.String(length=255)),
        sa.Column("section", sa.String(length=255)),
        sa.Column("category", sa.String(length=255)),
        sa.Column("severity", sa.String(length=50)),
        sa.Column("norm_text", sa.Text(), nullable=False),
        sa.Column("source_reference", sa.String(length=500)),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
        ),
        sa.Column(
            "llm_raw_response",
            postgresql.JSONB(astext_type=sa.Text()),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("ai_findings")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_type t
                JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE t.typname = 'ai_finding_status'
            ) THEN
                DROP TYPE ai_finding_status;
            END IF;
        END$$;
        """
    )
