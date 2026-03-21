from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.app.db.base import Base


class ModelLabSession(Base):
    __tablename__ = "model_lab_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=text("'running'"), default="running"
    )
    target_models: Mapped[list[dict] | None] = mapped_column(JSONB)
    expert_models: Mapped[list[dict] | None] = mapped_column(JSONB)
    settings: Mapped[dict | None] = mapped_column(JSONB)
    internal_api_base: Mapped[str | None] = mapped_column(String(500))
    internal_secret_ref: Mapped[str | None] = mapped_column(String(128))
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=10, server_default="10")
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ModelLabCase(Base):
    __tablename__ = "model_lab_cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("model_lab_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("review_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    review_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("review_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    target_model: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=text("'queued'"), default="queued"
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    findings_count: Mapped[int | None] = mapped_column(Integer)
    ai_findings_count: Mapped[int | None] = mapped_column(Integer)
    open_world_count: Mapped[int | None] = mapped_column(Integer)
    score_overall: Mapped[float | None] = mapped_column(Float)
    score_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ModelLabJudgement(Base):
    __tablename__ = "model_lab_judgements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("model_lab_cases.id", ondelete="CASCADE"),
        nullable=False,
    )
    expert_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    expert_model: Mapped[str] = mapped_column(String(255), nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    criteria: Mapped[dict | None] = mapped_column(JSONB)
    summary: Mapped[str | None] = mapped_column(Text)
    raw_response: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
