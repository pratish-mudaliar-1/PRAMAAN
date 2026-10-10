"""app/db/models/observation.py — Observation hypertable (TimescaleDB).

Each row is one minute-level aggregate from one device/zone.
The table is created as a TimescaleDB hypertable partitioned by minute_ts.

No faces, no identities, no biometrics — only aggregate person counts
computed by the edge device's privacy-preserving analytics model.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, SmallInteger,
    String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Observation(Base):
    """Minute-level aggregate observation from an edge device.

    Columns:
      persons_min/median/p90/max — aggregate person count statistics over ~frames_used frames
      item_counts — JSONB map of {item_class: count} as observed
      feed_health — 0.0–1.0 fraction of frames that were usable
      frames_used — how many frames contributed to this aggregate
      model_version — edge analytics model version (for reproducibility)
      record_hash — SHA-256 of canonical payload JSON (for deduplication and audit)
      prev_hash — hash of the previous accepted record (hash chain)
      signature — base64url Ed25519 signature by the device private key
    """

    __tablename__ = "observation"

    # Note: for TimescaleDB hypertable the primary key must include the
    # time dimension column (minute_ts). We use a composite PK.
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    minute_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
        comment="UTC minute bucket for this observation (partition key)"
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("device.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    zone_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("zone.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("session.id", ondelete="SET NULL"), index=True
    )

    # Aggregate person counts (no individual identities)
    persons_min: Mapped[int | None] = mapped_column(SmallInteger)
    persons_median: Mapped[float | None] = mapped_column(Float)
    persons_p90: Mapped[float | None] = mapped_column(Float)
    persons_max: Mapped[int | None] = mapped_column(SmallInteger)

    # Infrastructure item counts (JSONB: {"workbench": 12, "pc": 10, ...})
    item_counts: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Feed quality
    feed_health: Mapped[float] = mapped_column(Float, nullable=False, default=1.0,
        comment="Fraction 0.0–1.0 of frames usable in this minute")
    frames_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Provenance
    model_version: Mapped[str | None] = mapped_column(String(64))
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    signature: Mapped[str] = mapped_column(Text, nullable=False)

    # Integrity flags
    chain_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    clock_skew_ms: Mapped[int | None] = mapped_column(Integer)

    # Camera integrity trust — set by camera integrity service
    # TRUSTED: camera state is STABLE or RESOLVED for this window
    # UNTRUSTED: camera swap/move confirmed covering this timestamp
    # DEGRADED: camera in DRIFT_SUSPECTED or SWAP_SUSPECTED (use with caution)
    trust: Mapped[str] = mapped_column(
        String(16), nullable=False, default="TRUSTED",
        comment="TRUSTED | UNTRUSTED | DEGRADED — set by camera integrity service"
    )

    # Optional edge-reported scene metrics (stored but not trusted alone)
    scene_score_edge: Mapped[float | None] = mapped_column(
        Float, comment="Edge-reported fused similarity [0,1]; server independently recomputes"
    )
    orb_inliers_edge: Mapped[int | None] = mapped_column(
        Integer, comment="Edge-reported ORB RANSAC inlier count"
    )
    phash_dist_edge: Mapped[int | None] = mapped_column(
        Integer, comment="Edge-reported pHash Hamming distance"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    device: Mapped["Device"] = relationship(back_populates="observations")  # type: ignore[name-defined]  # noqa: F821
