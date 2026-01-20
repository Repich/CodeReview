"""add suggested norms tables

Revision ID: 20260119130000
Revises: 20260116100000_add_teacher_role
Create Date: 2026-01-19 13:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260119130000_add_suggested_norms"
down_revision = "20260116100000_add_teacher_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "suggested_norms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section", sa.String(length=255), nullable=False),
        sa.Column("severity", sa.String(length=50), nullable=False),
        sa.Column("text_raw", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("llm_prompt", sa.Text()),
        sa.Column("llm_response", sa.Text()),
        sa.Column("duplicate_of", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("generated_norm_id", sa.String(length=255)),
        sa.Column("generated_title", sa.String(length=500)),
        sa.Column("generated_section", sa.String(length=255)),
        sa.Column("generated_scope", sa.String(length=255)),
        sa.Column("generated_detector_type", sa.String(length=255)),
        sa.Column("generated_check_type", sa.String(length=255)),
        sa.Column("generated_severity", sa.String(length=50)),
        sa.Column("generated_version", sa.Integer()),
        sa.Column("generated_text", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), server_onupdate=sa.func.now(), nullable=False),
    )
    op.create_table(
        "suggested_norm_votes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("norm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suggested_norms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("voter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vote", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("norm_id", "voter_id", name="uq_norm_vote"),
    )


def downgrade() -> None:
    op.drop_table("suggested_norm_votes")
    op.drop_table("suggested_norms")
