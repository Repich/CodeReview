"""add open world candidates table

Revision ID: 20260215190000
Revises: 20260122120000
Create Date: 2026-02-15 19:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260215190000"
down_revision = "20260122120000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "open_world_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "review_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("review_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("section", sa.String(length=255)),
        sa.Column("severity", sa.String(length=50)),
        sa.Column("confidence", sa.Float()),
        sa.Column("description", sa.Text()),
        sa.Column("norm_text", sa.Text()),
        sa.Column("mapped_norm_id", sa.String(length=255)),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("llm_raw_response", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("accepted_norm_id", sa.String(length=255)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_open_world_candidates_review_run_id",
        "open_world_candidates",
        ["review_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_open_world_candidates_review_run_id", table_name="open_world_candidates")
    op.drop_table("open_world_candidates")
