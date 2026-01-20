from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.app.db.base import Base
from backend.app.models.user import UserAccount


class SuggestedNorm(Base):
    __tablename__ = "suggested_norms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_accounts.id", ondelete="CASCADE"), nullable=False
    )
    section: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    text_raw: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    llm_prompt: Mapped[str | None] = mapped_column(Text)
    llm_response: Mapped[str | None] = mapped_column(Text)
    duplicate_of: Mapped[list[str] | None] = mapped_column(JSONB)

    generated_norm_id: Mapped[str | None] = mapped_column(String(255))
    generated_title: Mapped[str | None] = mapped_column(String(500))
    generated_section: Mapped[str | None] = mapped_column(String(255))
    generated_scope: Mapped[str | None] = mapped_column(String(255))
    generated_detector_type: Mapped[str | None] = mapped_column(String(255))
    generated_check_type: Mapped[str | None] = mapped_column(String(255))
    generated_severity: Mapped[str | None] = mapped_column(String(50))
    generated_version: Mapped[int | None] = mapped_column(Integer)
    generated_text: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), server_onupdate=func.now(), nullable=False
    )

    author = relationship(UserAccount)
    votes = relationship("SuggestedNormVote", back_populates="norm", cascade="all, delete-orphan")


class SuggestedNormVote(Base):
    __tablename__ = "suggested_norm_votes"
    __table_args__ = (UniqueConstraint("norm_id", "voter_id", name="uq_norm_vote"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    norm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suggested_norms.id", ondelete="CASCADE"), nullable=False
    )
    voter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_accounts.id", ondelete="CASCADE"), nullable=False
    )
    vote: Mapped[int] = mapped_column(Integer, nullable=False)  # +1 / -1
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    norm = relationship(SuggestedNorm, back_populates="votes")
    voter = relationship(UserAccount)
