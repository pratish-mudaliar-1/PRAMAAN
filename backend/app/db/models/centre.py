"""app/db/models/centre.py — Training centre, camera, zone and sanctioned layout models."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, Numeric,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Centre(Base):
    """A government-recognised training centre (TC).

    Privacy: no trainee names or personal identifiers are stored here.
    """

    __tablename__ = "centre"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    state_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    district: Mapped[str] = mapped_column(String(128), nullable=False)
    scheme_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Accreditation / registration number (not a person identifier)
    registration_no: Mapped[str | None] = mapped_column(String(128))
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    cameras: Mapped[list["Camera"]] = relationship(back_populates="centre", cascade="all, delete-orphan")
    zones: Mapped[list["Zone"]] = relationship(back_populates="centre", cascade="all, delete-orphan")
    layouts: Mapped[list["SanctionedLayout"]] = relationship(back_populates="centre", cascade="all, delete-orphan")


class Camera(Base):
    """A camera device installed at a centre.

    Cameras are associated with one or more zones via Zone.camera_id.
    One physical camera may cover multiple zones (but each zone has one primary camera).
    """

    __tablename__ = "camera"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    centre_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("centre.id", ondelete="CASCADE"), nullable=False, index=True
    )
    camera_code: Mapped[str] = mapped_column(String(64), nullable=False)
    location_description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    installed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    centre: Mapped["Centre"] = relationship(back_populates="cameras")

    __table_args__ = (
        UniqueConstraint("centre_id", "camera_code"),
    )


class Zone(Base):
    """A spatial zone within a centre (classroom, lab, workshop, etc.).

    polygon: list of [x,y] coordinate pairs (relative to floor plan image, or lat/lon).
    coverage_factor: k — fraction of sanctioned count expected to be visible in this zone.
    """

    __tablename__ = "zone"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    centre_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("centre.id", ondelete="CASCADE"), nullable=False, index=True
    )
    camera_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("camera.id", ondelete="SET NULL")
    )
    zone_code: Mapped[str] = mapped_column(String(64), nullable=False)
    zone_type: Mapped[str] = mapped_column(String(64), nullable=False)   # e.g. classroom, lab, workshop
    polygon: Mapped[dict[str, Any] | None] = mapped_column(JSONB)          # [[x,y], ...]
    coverage_factor: Mapped[float] = mapped_column(
        Numeric(4, 3), nullable=False, default=1.0,
        comment="k: fraction of sanctioned count visible in this zone (initial hypothesis, calibrate in pilot)"
    )
    multi_camera_strategy: Mapped[str] = mapped_column(
        String(16), nullable=False, default="max",
        comment="max | dedupe — how to combine multiple cameras on one zone"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    centre: Mapped["Centre"] = relationship(back_populates="zones")

    __table_args__ = (
        UniqueConstraint("centre_id", "zone_code"),
    )


class SanctionedLayout(Base):
    """Sanctioned infrastructure inventory per zone per item class.

    Records what the scheme mandates; compared against observed item counts.
    critical=True means absence triggers a RED flag (not just AMBER).
    """

    __tablename__ = "sanctioned_layout"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    centre_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("centre.id", ondelete="CASCADE"), nullable=False, index=True
    )
    zone_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("zone.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_class: Mapped[str] = mapped_column(String(128), nullable=False)
    sanctioned_count: Mapped[int] = mapped_column(Integer, nullable=False)
    critical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    centre: Mapped["Centre"] = relationship(back_populates="layouts")

    __table_args__ = (
        UniqueConstraint("zone_id", "item_class", "effective_from"),
    )
