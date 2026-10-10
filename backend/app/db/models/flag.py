"""app/db/models/flag.py — Flag, FlagInputSnapshot and IntegrityEvent models.

A Flag is a lead for human review, never an automatic penalty.
Every flag stores the complete input snapshot so it can be reproduced from stored data.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Flag(Base):
    """A potential compliance issue identified by the reconciliation engine.

    flag_type examples: ATTENDANCE_RED, ATTENDANCE_AMBER_REPEAT,
                        GHOST_BATCH, ITEM_ABSENT, DEVICE_OFFLINE,
                        INTEGRITY_CHAIN_BREAK, EVIDENCE_DUPLICATE.
    status: OPEN, UNDER_REVIEW, CLOSED_CONFIRMED, CLOSED_DISMISSED.
    """

    __tablename__ = "flag"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Scoping
    centre_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("centre.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("session.id", ondelete="SET NULL"), index=True
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("zone.id", ondelete="SET NULL"), index=True
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("device.id", ondelete="SET NULL"), index=True
    )

    # Identity key for idempotent upsert
    flag_key: Mapped[str] = mapped_column(
        String(256), nullable=False, unique=True, index=True,
        comment="Deterministic key for upsert — reprocessing never duplicates flags"
    )

    flag_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="MEDIUM")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN", index=True)

    # Explainability (human-readable, no PII)
    rule_name: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Risk component (Phase 4)
    risk_score: Mapped[float | None] = mapped_column(Float)

    # Window
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Case linkage
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case.id", ondelete="SET NULL"), index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    input_snapshot: Mapped["FlagInputSnapshot | None"] = relationship(
        back_populates="flag", cascade="all, delete-orphan", uselist=False
    )


class FlagInputSnapshot(Base):
    """Immutable snapshot of inputs and thresholds used to generate a flag.

    Enables exact reproducibility: re-run the rule against this snapshot
    to verify the flag without access to the live observation data.
    """

    __tablename__ = "flag_input_snapshot"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("flag.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # Exactly the inputs fed to the rule
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    thresholds: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(64))

    # Evidence links (S3 keys or observation IDs — not raw images)
    evidence_links: Mapped[list[str] | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    flag: Mapped["Flag"] = relationship(back_populates="input_snapshot")


class IntegrityEvent(Base):
    """Records chain breaks, replay attempts, clock skew, and duplicate evidence.

    These are facts about the data pipeline's integrity, not violations.
    Every integrity event has a case-creation policy (configurable).
    """

    __tablename__ = "integrity_event"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("device.id", ondelete="SET NULL"), index=True
    )
    centre_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("centre.id", ondelete="SET NULL"), index=True
    )

    event_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
        comment="CHAIN_BREAK | REPLAY | CLOCK_SKEW | EVIDENCE_DUPLICATE | DEVICE_OFFLINE | CAMERA_MOVED"
    )
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="MEDIUM")

    # Structured detail — no PII
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # The record that triggered this event
    record_hash: Mapped[str | None] = mapped_column(String(64))

    flag_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("flag.id", ondelete="SET NULL")
    )

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
