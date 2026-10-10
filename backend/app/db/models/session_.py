"""app/db/models/session_.py — Batch, Session and ingest deduplication models.

Privacy note: attendance is aggregate counts per batch-session only.
No individual names, Aadhaar numbers, or person identifiers are stored.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Batch(Base):
    """A training batch at a centre.

    Aggregate enrollment count only — no names or IDs of trainees.
    """

    __tablename__ = "batch"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    centre_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("centre.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_code: Mapped[str] = mapped_column(String(128), nullable=False)
    scheme_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    trade_code: Mapped[str | None] = mapped_column(String(64))

    # Aggregate count only — no individual records
    enrolled_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    batch_start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    batch_end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_ref: Mapped[str | None] = mapped_column(
        String(256), comment="External system reference (no PII)"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sessions: Mapped[list["Session"]] = relationship(back_populates="batch", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("centre_id", "batch_code"),
    )


class Session(Base):
    """A scheduled training session within a batch for a specific zone.

    claimed_count: aggregate number claimed present (from attendance system — no names).
    trainer_count: number of trainers (aggregate, from trainer-attendance system).
    """

    __tablename__ = "session"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("batch.id", ondelete="CASCADE"), nullable=False, index=True
    )
    zone_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("zone.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Attendance (aggregate counts only — from external attendance system)
    claimed_count: Mapped[int | None] = mapped_column(
        Integer, comment="Aggregate count from attendance system; None = PENDING"
    )
    trainer_count: Mapped[int | None] = mapped_column(
        Integer, comment="Aggregate trainer count; None = PENDING"
    )

    # Reconciliation output
    attendance_status: Mapped[str | None] = mapped_column(
        String(16),
        comment="GREEN | AMBER | RED | NO_DATA | PENDING"
    )
    attendance_ratio: Mapped[float | None] = mapped_column(
        comment="Observed / (k * claimed) ratio; null if not yet computed"
    )
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # External reference (no PII)
    source_ref: Mapped[str | None] = mapped_column(String(256))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    batch: Mapped["Batch"] = relationship(back_populates="sessions")


class IngestDedupe(Base):
    """Idempotency cache for observation ingestion.

    Keyed by (device_id, record_hash); prevents double-processing on retries.
    Rows are retained for a configurable window (default 7 days) then expired.
    """

    __tablename__ = "ingest_dedupe"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("device.id", ondelete="CASCADE"), nullable=False
    )
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    observation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    __table_args__ = (
        UniqueConstraint("device_id", "record_hash", name="uq_dedupe_device_hash"),
    )
