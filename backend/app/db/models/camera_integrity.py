"""app/db/models/camera_integrity.py — Camera integrity data models.

Tables:
  camera_reference          — registered baseline views per camera
  scene_observation         — per-keyframe comparison results (TimescaleDB hypertable on ts)
  camera_integrity_state    — current state machine state per camera (one row per camera)
  camera_state_event        — append-only transition log
  rebaseline_request        — two-person approval workflow for baseline updates
  camera_maintenance_window — alert-suppression windows (evidence never deleted)

Privacy: keyframes are redacted at the edge before upload. The server stores
only compressed feature descriptors and perceptual hashes — no raw biometrics.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CameraReference(Base):
    """A registered baseline view for a camera.

    Multiple active references per camera are allowed (e.g. day vs night).
    Features are serialised ORB keypoints+descriptors as a compressed numpy .npz
    blob for server-side reproducibility. The original keyframe is stored in S3.

    lighting_tag: day | night | lights_on | lights_off | unknown
    """

    __tablename__ = "camera_reference"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("camera.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Storage
    s3_key: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Path to redacted keyframe in MinIO evidence bucket"
    )

    # Precomputed vision features (server-side, for deterministic replay)
    features_blob: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        comment="Compressed numpy .npz: ORB keypoints (serialised) + descriptors (float32)"
    )
    phash_hex: Mapped[str | None] = mapped_column(
        String(16),
        comment="64-bit pHash as 16-char hex"
    )
    hsv_histogram_blob: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        comment="Compressed numpy .npz: 3x32-bin HSV histogram as float32"
    )

    # Geometry hints
    mask_polygons: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        comment="Static regions to INCLUDE in comparison"
    )
    redaction_mask: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        comment="Blurred/excluded regions from edge redaction"
    )

    # Lighting context
    lighting_tag: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown",
        comment="day | night | lights_on | lights_off | unknown"
    )

    # Approval trail (auto-capture path: approved_by = 'system:autocapture')
    approved_by: Mapped[str | None] = mapped_column(
        String(256), comment="User subject (opaque) or 'system:autocapture'"
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text)

    # Active flag — multiple active references per camera (different lighting)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Algorithm version that extracted these features (for cache invalidation)
    algorithm_version: Mapped[str] = mapped_column(
        String(32), nullable=False, default="v1"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scene_observations: Mapped[list["SceneObservation"]] = relationship(
        back_populates="reference", foreign_keys="SceneObservation.reference_id"
    )


class SceneObservation(Base):
    """One keyframe comparison result — the atomic evidence unit.

    This table becomes a TimescaleDB hypertable on ts (see timescale.py).
    source: edge_reported (metrics sent inside observation record)
          | server_verified (server downloaded keyframe and recomputed)
    """

    __tablename__ = "scene_observation"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("camera.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
        comment="UTC timestamp of this keyframe (partition key for hypertable)"
    )
    source: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment="edge_reported | server_verified"
    )

    # Reference used for comparison
    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("camera_reference.id", ondelete="SET NULL"), index=True
    )

    # Evidence keyframe (the frame that was compared)
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence.id", ondelete="SET NULL"), index=True
    )

    # Server-computed metrics (nullable: edge_reported rows may lack them)
    phash_dist: Mapped[int | None] = mapped_column(Integer)
    orb_inliers: Mapped[int | None] = mapped_column(Integer)
    inlier_ratio: Mapped[float | None] = mapped_column(Float)
    ssim_masked: Mapped[float | None] = mapped_column(Float)
    hist_distance: Mapped[float | None] = mapped_column(Float)
    fused_similarity: Mapped[float | None] = mapped_column(Float)

    # Homography decomposition
    transform_params: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, comment="{tx_px, ty_px, rotation_deg, scale, inlier_count}"
    )

    # Classification
    classification: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNKNOWN",
        comment="STABLE | LIGHTING_CHANGE | OCCLUDED | MOVED | SWAPPED | UNKNOWN"
    )

    algorithm_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")

    reference: Mapped["CameraReference | None"] = relationship(
        back_populates="scene_observations", foreign_keys=[reference_id]
    )


class CameraIntegrityState(Base):
    """Current integrity state for one camera (one row per camera).

    State machine:
      STABLE -> DRIFT_SUSPECTED -> SWAP_SUSPECTED -> SWAP_CONFIRMED
      STABLE -> DRIFT_SUSPECTED -> MOVED_CONFIRMED
      Any confirmed state -> RESOLVED (after recovery evidence)
      Any state -> REBASELINED (after approved rebaseline)

    first_suspected_at: change-point estimate used to retroactively mark
    zone observations as UNTRUSTED.
    """

    __tablename__ = "camera_integrity_state"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("camera.id", ondelete="RESTRICT"),
        nullable=False, unique=True, index=True
    )

    state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="STABLE",
        comment="STABLE|DRIFT_SUSPECTED|SWAP_SUSPECTED|SWAP_CONFIRMED|MOVED_CONFIRMED|RESOLVED|REBASELINED"
    )
    since: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_suspected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_transition_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Hysteresis counters (persisted for crash-recovery)
    consecutive_suspicious: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consecutive_stable: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    confidence: Mapped[float | None] = mapped_column(Float)
    explanation: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    algorithm_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CameraStateEvent(Base):
    """Append-only log of camera integrity state transitions. Never deleted."""

    __tablename__ = "camera_state_event"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("camera.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    from_state: Mapped[str | None] = mapped_column(String(32))
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    transitioned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    metrics_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    cause: Mapped[str] = mapped_column(
        String(64), nullable=False, default="evaluation",
        comment="evaluation | retroactive | maintenance_window | rebaseline | manual"
    )
    triggered_by: Mapped[str] = mapped_column(
        String(256), nullable=False, default="system"
    )


class RebaselineRequest(Base):
    """Request to update a camera's reference baseline.

    Requires two-person approval: one inspector AND one state_officer.
    Legitimate camera relocation MUST go through this workflow.
    """

    __tablename__ = "rebaseline_request"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("camera.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    requested_by: Mapped[str] = mapped_column(String(256), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending",
        comment="pending | inspector_approved | state_officer_approved | approved | rejected"
    )

    # Two-person approval trail
    inspector_approved_by: Mapped[str | None] = mapped_column(String(256))
    inspector_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state_officer_approved_by: Mapped[str | None] = mapped_column(String(256))
    state_officer_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Rejection
    rejected_by: Mapped[str | None] = mapped_column(String(256))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    new_reference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("camera_reference.id", ondelete="SET NULL")
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CameraMaintenanceWindow(Base):
    """Planned maintenance window — alerts suppressed, evidence never deleted."""

    __tablename__ = "camera_maintenance_window"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("camera.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
