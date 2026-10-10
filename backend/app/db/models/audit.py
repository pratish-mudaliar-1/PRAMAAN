"""app/db/models/audit.py — Immutable audit log with hash chain.

The audit_log table is append-only. No rows are ever updated or deleted.
Each row hashes the previous row's hash to form an integrity chain,
making tamper detection possible without an external ledger.

Privacy: the `actor` field stores the opaque user subject only.
         The `detail` JSONB must never contain names, Aadhaar, or other PII.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    """Append-only audit log row."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Who / what
    actor: Mapped[str] = mapped_column(String(256), nullable=False, comment="User subject or 'system'")
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(128))

    # Context
    request_id: Mapped[str | None] = mapped_column(String(64))
    ip_hash: Mapped[str | None] = mapped_column(
        String(64), comment="SHA-256 of client IP — not the raw IP (privacy)"
    )

    # Structured detail (no PII)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Hash chain for tamper detection
    row_hash: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="SHA-256(prev_hash || actor || action || resource_type || resource_id || occurred_at)"
    )
    prev_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, default="0" * 64,
        comment="Hash of the previous audit_log row; '0'*64 for the first row"
    )

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
