"""app/db/models/ghost.py — Ghost batch detection data models.

Tables:
  ghost_assessment   — one live assessment per batch (upserted on re-evaluation)
  ghost_state_event  — append-only transition log

A ghost batch pattern: centre claims high attendance while trusted observations
show consistently low physical occupancy across multiple days.

These are leads for human review — never automatic penalties.
All thresholds live in ThresholdProfile.extra (JSONB), not in code.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class GhostAssessment(Base):
    """Live ghost-batch assessment for one batch.

    One row per batch — upserted on every re-evaluation (idempotent).
    Historical snapshots are captured in ghost_state_event on transitions.

    state machine:
      NORMAL -> WATCH -> SUSPECTED_GHOST -> ESCALATED
      ESCALATED/SUSPECTED_GHOST -> RESOLVED (after R consecutive healthy eligible days)

    per_day_detail: list of per-IST-day records:
      [{
        "date": "2024-06-15",          # IST date string
        "claimed": 35,                 # claimed_count from session
        "o_hat": 8.2,                  # observed P90 hat (from reconciliation)
        "ratio": 0.23,                 # o_hat / (k * claimed)
        "status": "GHOST",             # GHOST | HEALTHY | NO_DATA | UNTRUSTED | PENDING
        "evidence_quality": 0.85,      # fraction of scheduled window with trusted data
        "session_id": "<uuid>"
      }, ...]

    explanation: structured breakdown of ghost_score components:
      {
        "persistence": 0.75,
        "magnitude": 0.82,
        "consistency": 0.60,
        "evidence_quality": 0.90,
        "cusum_score": 3.2,
        "weights": [0.35, 0.30, 0.20, 0.15],
        "threshold_profile_id": "<uuid>",
        "algorithm_version": "v1"
      }
    """

    __tablename__ = "ghost_assessment"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("batch.id", ondelete="RESTRICT"),
        nullable=False, unique=True, index=True,
        comment="One live assessment per batch"
    )
    centre_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("centre.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    # Window (IST local dates)
    window_start: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="IST date string YYYY-MM-DD — first day evaluated"
    )
    window_end: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="IST date string YYYY-MM-DD — last day evaluated"
    )

    # Day counts
    eligible_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ghost_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    nodata_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    untrusted_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Per-day detail (structured JSONB, see docstring)
    per_day_detail: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )

    # Ghost score [0, 1] — null until eligible_days >= D_min
    ghost_score: Mapped[float | None] = mapped_column(Float)

    # State machine
    state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="NORMAL",
        comment="NORMAL | WATCH | SUSPECTED_GHOST | ESCALATED | RESOLVED"
    )

    # Hysteresis counters
    hysteresis_ok_streak: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Consecutive healthy eligible days since last bad day"
    )

    # Structured explanation (see docstring)
    explanation: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    algorithm_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Case linkage (created at SUSPECTED_GHOST per policy)
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case.id", ondelete="SET NULL"), index=True
    )

    state_events: Mapped[list["GhostStateEvent"]] = relationship(
        back_populates="assessment",
        order_by="GhostStateEvent.transitioned_at",
        cascade="all, delete-orphan",
    )


class GhostStateEvent(Base):
    """Append-only log of ghost assessment state transitions.

    Records the metrics snapshot and cause for every state change,
    including reprocessing transitions caused by late data or
    retroactive camera-trust updates.
    """

    __tablename__ = "ghost_state_event"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("batch.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ghost_assessment.id", ondelete="SET NULL"), index=True
    )

    from_state: Mapped[str | None] = mapped_column(String(32))
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)

    transitioned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Full metrics at transition time (ghost_score, component breakdown, day counts)
    metrics_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    cause: Mapped[str] = mapped_column(
        String(64), nullable=False, default="evaluation",
        comment="evaluation | late_data | retroactive_camera_untrust | reprocessing | manual"
    )

    assessment: Mapped["GhostAssessment | None"] = relationship(back_populates="state_events")
