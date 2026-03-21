"""add model lab benchmark tables

Revision ID: 20260321120000
Revises: 20260215190000
Create Date: 2026-03-21 12:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260321120000"
down_revision = "20260215190000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_lab_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255)),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="running"),
        sa.Column("target_models", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("expert_models", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("internal_api_base", sa.String(length=500)),
        sa.Column("internal_secret_ref", sa.String(length=128)),
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("error_message", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
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
        "ix_model_lab_sessions_created_by",
        "model_lab_sessions",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        "ix_model_lab_sessions_status",
        "model_lab_sessions",
        ["status"],
        unique=False,
    )

    op.create_table(
        "model_lab_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("model_lab_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("review_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "review_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("review_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_provider", sa.String(length=50), nullable=False),
        sa.Column("target_model", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="queued"),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("findings_count", sa.Integer()),
        sa.Column("ai_findings_count", sa.Integer()),
        sa.Column("open_world_count", sa.Integer()),
        sa.Column("score_overall", sa.Float()),
        sa.Column("score_summary", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text()),
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
    op.create_index("ix_model_lab_cases_session_id", "model_lab_cases", ["session_id"], unique=False)
    op.create_index("ix_model_lab_cases_review_run_id", "model_lab_cases", ["review_run_id"], unique=True)
    op.create_index("ix_model_lab_cases_status", "model_lab_cases", ["status"], unique=False)

    op.create_table(
        "model_lab_judgements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("model_lab_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("expert_provider", sa.String(length=50), nullable=False),
        sa.Column("expert_model", sa.String(length=255), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("criteria", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("summary", sa.Text()),
        sa.Column("raw_response", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_model_lab_judgements_case_id", "model_lab_judgements", ["case_id"], unique=False)
    op.create_index(
        "ix_model_lab_judgements_case_expert",
        "model_lab_judgements",
        ["case_id", "expert_provider", "expert_model"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_model_lab_judgements_case_expert", table_name="model_lab_judgements")
    op.drop_index("ix_model_lab_judgements_case_id", table_name="model_lab_judgements")
    op.drop_table("model_lab_judgements")

    op.drop_index("ix_model_lab_cases_status", table_name="model_lab_cases")
    op.drop_index("ix_model_lab_cases_review_run_id", table_name="model_lab_cases")
    op.drop_index("ix_model_lab_cases_session_id", table_name="model_lab_cases")
    op.drop_table("model_lab_cases")

    op.drop_index("ix_model_lab_sessions_status", table_name="model_lab_sessions")
    op.drop_index("ix_model_lab_sessions_created_by", table_name="model_lab_sessions")
    op.drop_table("model_lab_sessions")
