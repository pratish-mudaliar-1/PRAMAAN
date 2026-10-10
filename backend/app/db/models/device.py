"""app/db/models/device.py — Edge device registration and status model."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Integer, LargeBinary,
    String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DeviceStatusEnum(str, enum.Enum):
    PENDING = "PENDING"       # enrolled, awaiting first heartbeat
    ACTIVE = "ACTIVE"         # healthy, sending observations
    OFFLINE = "OFFLINE"       # missed heartbeats during scheduled session
    SUSPENDED = "SUSPENDED"   # manually suspended by admin
    REVOKED = "REVOKED"       # key revoked; all subsequent records rejected


class Device(Base):
    """An edge video-analytics device installed at a training centre.

    public_key stores the 32-byte raw Ed25519 public key.
    Records signed with a revoked device key are rejected and logged.
    """

    __tablename__ = "device"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    centre_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("centre.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("zone.id", ondelete="SET NULL"), index=True
    )
    camera_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("camera.id", ondelete="SET NULL"), index=True,
        comment="Physical camera this device is attached to (1-to-1 for now)"
    )

    # Identity / authentication
    serial_number: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    public_key: Mapped[bytes] = mapped_column(
        LargeBinary(32), nullable=False,
        comment="32-byte raw Ed25519 public key"
    )
    public_key_b64url: Mapped[str] = mapped_column(String(64), nullable=False)
    enrollment_token_hash: Mapped[str | None] = mapped_column(
        String(64), comment="SHA-256 of one-time enrollment token; nulled after use"
    )

    # Status
    status: Mapped[DeviceStatusEnum] = mapped_column(
        Enum(DeviceStatusEnum), nullable=False, default=DeviceStatusEnum.PENDING
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Versioning
    model_version: Mapped[str | None] = mapped_column(String(64))
    config_version: Mapped[str | None] = mapped_column(String(64))
    firmware_version: Mapped[str | None] = mapped_column(String(64))

    # Liveness
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Telemetry snapshot from last heartbeat
    last_telemetry: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Revocation
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocation_reason: Mapped[str | None] = mapped_column(Text)

    # Hash-chain continuity
    last_accepted_hash: Mapped[str | None] = mapped_column(
        String(64), comment="SHA-256 hex of last accepted observation record"
    )
    last_accepted_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    observations: Mapped[list["Observation"]] = relationship(back_populates="device")  # type: ignore[name-defined]  # noqa: F821
