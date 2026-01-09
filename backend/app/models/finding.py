from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.app.db.base import Base
from backend.app.models.enums import FindingSeverity
from backend.app.models.utils import enum_values


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    review_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_runs.id", ondelete="CASCADE"), nullable=False
    )
    norm_db_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("norms.id", ondelete="SET NULL"), nullable=True
    )
    norm_id: Mapped[str] = mapped_column(String(255), nullable=False)
    detector_id: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[FindingSeverity] = mapped_column(
        Enum(
            FindingSeverity,
            name="finding_severity",
            values_callable=enum_values,
        ),
        nullable=False,
    )
    file_path: Mapped[str | None] = mapped_column(String(1000))
    line_start: Mapped[int | None] = mapped_column(Integer)
    line_end: Mapped[int | None] = mapped_column(Integer)
    column_start: Mapped[int | None] = mapped_column(Integer)
    column_end: Mapped[int | None] = mapped_column(Integer)
    message: Mapped[str] = mapped_column(String(2000))
    recommendation: Mapped[str | None] = mapped_column(String(2000))
    code_snippet: Mapped[str | None] = mapped_column(Text)
    finding_hash: Mapped[str | None] = mapped_column(String(128))
    engine_version: Mapped[str | None] = mapped_column(String(50))
    trace_id: Mapped[str | None] = mapped_column(String(128))
    context: Mapped[dict | None] = mapped_column(JSONB)
    llm_raw_response: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    review_run = relationship("ReviewRun", backref="findings")
