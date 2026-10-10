"""app/db/models/threshold.py — Configurable threshold profiles.

Thresholds live in the DB, not in code. They are versioned with an approval trail.
A ThresholdProfile can be scoped to (scheme_code, state_code) with a fallback chain:
  specific state+scheme → scheme-only → national default
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ThresholdProfile(Base):
    """A versioned, scoped set of reconciliation and flag thresholds.

    Scope resolution order (most specific wins):
        1. scheme_code + state_code (both set)
        2. scheme_code only (state_code null)
        3. national default (both null)

    All numeric defaults are labelled "initial hypothesis, calibrate in pilot"
    in docs/THRESHOLDS.md and here in column comments.
    """

    __tablename__ = "threshold_profile"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Scope
    scheme_code: Mapped[str | None] = mapped_column(String(64), index=True)
    state_code: Mapped[str | None] = mapped_column(String(8), index=True)

    # Version / approval
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved_by: Mapped[str | None] = mapped_column(String(256), comment="User subject (opaque)")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approval_note: Mapped[str | None] = mapped_column(Text)

    # ── Attendance thresholds (initial hypothesis; calibrate in pilot) ─────────
    t_green: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.80,
        comment="[initial hypothesis] Minimum ratio for GREEN status"
    )
    t_amber: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.50,
        comment="[initial hypothesis] Minimum ratio for AMBER (below → AMBER or RED)"
    )
    repeat_n: Mapped[int] = mapped_column(
        Integer, nullable=False, default=2,
        comment="[initial hypothesis] Sessions below t_amber to trigger RED"
    )

    # Feed health
    min_feed_health_fraction: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.50,
        comment="[initial hypothesis] Minimum feed health fraction for reconciliation"
    )

    # Infrastructure persistence
    item_absent_min_windows: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3,
        comment="[initial hypothesis] Unoccluded windows without detection to flag ABSENT"
    )
    item_absent_min_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=2,
        comment="[initial hypothesis] Distinct days across which ABSENT windows must span"
    )

    # Evidence near-duplicate
    phash_hamming_threshold: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10,
        comment="[initial hypothesis] Hamming distance ≤ this is a near-duplicate"
    )

    # Extra threshold values stored as JSONB for future extensibility
    extra: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("scheme_code", "state_code", "version"),
    )
