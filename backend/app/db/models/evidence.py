"""app/db/models/evidence.py — Redacted evidence keyframe metadata.

S3 objects contain JPEG keyframes that have been pre-processed by the edge device
to remove faces (privacy by design). The server stores only metadata and a
perceptual hash for near-duplicate detection — never raw biometric data.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Evidence(Base):
    """Metadata for a redacted keyframe stored in S3.

    s3_key: path within the evidence bucket.
    phash: 64-bit perceptual hash (dHash) stored as hex string for near-duplicate search.
    phash_int: integer representation for bit-level Hamming distance computation in Postgres.
    """

    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("device.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("zone.id", ondelete="SET NULL"), index=True
    )
    flag_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("flag.id", ondelete="SET NULL"), index=True
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("session.id", ondelete="SET NULL"), index=True
    )

    # S3 storage
    s3_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False, default="image/jpeg")
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    # Perceptual hash for near-duplicate detection (no biometric data)
    phash_hex: Mapped[str | None] = mapped_column(
        String(16), index=True, comment="64-bit dHash as 16-char hex"
    )
    phash_int: Mapped[int | None] = mapped_column(
        comment="Integer form of phash for Postgres BIT-level Hamming distance"
    )

    # Integrity
    sha256_hex: Mapped[str | None] = mapped_column(String(64))

    # Duplicate detection result
    is_near_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    # Legal hold (prevents deletion by retention job)
    legal_hold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
