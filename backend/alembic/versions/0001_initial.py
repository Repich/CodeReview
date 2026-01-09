"""Initial schema"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    review_status = sa.Enum(
        "queued", "running", "completed", "failed", name="review_status"
    )
    finding_severity = sa.Enum(
        "critical", "major", "minor", "info", name="finding_severity"
    )
    feedback_verdict = sa.Enum(
        "tp", "fp", "fn", "skip", name="feedback_verdict"
    )
    audit_event_type = sa.Enum(
        "run_created",
        "worker_started",
        "worker_completed",
        "detector_finished",
        "run_failed",
        name="audit_event_type",
    )
    io_direction = sa.Enum("in", "out", name="io_direction")


    op.create_table(
        "norms",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("norm_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("section", sa.String(length=255), nullable=False),
        sa.Column("scope", sa.String(length=255), nullable=False),
        sa.Column("detector_type", sa.String(length=255), nullable=False),
        sa.Column("check_type", sa.String(length=255), nullable=False),
        sa.Column("default_severity", sa.String(length=50), nullable=False),
        sa.Column("norm_text", sa.Text(), nullable=False),
        sa.Column("code_applicability", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("version", sa.Integer(), server_default=sa.text("1")),
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

    op.create_table(
        "review_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("external_ref", sa.String(length=255)),
        sa.Column("project_id", sa.String(length=255)),
        sa.Column("status", review_status, nullable=False, server_default="queued"),
        sa.Column("input_hash", sa.String(length=128)),
        sa.Column("engine_version", sa.String(length=50)),
        sa.Column("detectors_version", sa.String(length=50)),
        sa.Column("norms_version", sa.String(length=50)),
        sa.Column("llm_prompt_version", sa.String(length=50)),
        sa.Column("initiator", sa.String(length=255)),
        sa.Column("source_type", sa.String(length=50)),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column(
            "queued_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "llm_prompt_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("version_tag", sa.String(length=50)),
        sa.Column("prompt_body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_table(
        "findings",
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
        sa.Column(
            "norm_db_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("norms.id", ondelete="SET NULL"),
        ),
        sa.Column("norm_id", sa.String(length=255), nullable=False),
        sa.Column("detector_id", sa.String(length=255), nullable=False),
        sa.Column("severity", finding_severity, nullable=False),
        sa.Column("file_path", sa.String(length=1000)),
        sa.Column("line_start", sa.Integer()),
        sa.Column("line_end", sa.Integer()),
        sa.Column("column_start", sa.Integer()),
        sa.Column("column_end", sa.Integer()),
        sa.Column("message", sa.String(length=2000), nullable=False),
        sa.Column("recommendation", sa.String(length=2000)),
        sa.Column("code_snippet", sa.Text()),
        sa.Column("finding_hash", sa.String(length=128)),
        sa.Column("engine_version", sa.String(length=50)),
        sa.Column("trace_id", sa.String(length=128)),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("llm_raw_response", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_table(
        "feedback",
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
        sa.Column(
            "finding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("findings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reviewer", sa.String(length=255), nullable=False),
        sa.Column("verdict", feedback_verdict, nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_table(
        "audit_logs",
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
        ),
        sa.Column("event_type", audit_event_type, nullable=False),
        sa.Column("actor", sa.String(length=255)),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_table(
        "io_logs",
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
        sa.Column("direction", io_direction, nullable=False),
        sa.Column("artifact_type", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=1000), nullable=False),
        sa.Column("checksum", sa.String(length=128)),
        sa.Column("size_bytes", sa.BigInteger()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("io_logs")
    op.drop_table("audit_logs")
    op.drop_table("feedback")
    op.drop_table("findings")
    op.drop_table("llm_prompt_versions")
    op.drop_table("review_runs")
    op.drop_table("norms")

    op.execute("DROP TYPE IF EXISTS io_direction")
    op.execute("DROP TYPE IF EXISTS audit_event_type")
    op.execute("DROP TYPE IF EXISTS feedback_verdict")
    op.execute("DROP TYPE IF EXISTS finding_severity")
    op.execute("DROP TYPE IF EXISTS review_status")
