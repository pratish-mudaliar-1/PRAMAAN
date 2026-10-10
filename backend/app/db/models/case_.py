"""app/db/models/case_.py — Case management models.

Cases are opened when one or more flags meet the case-creation policy.
Every status transition is recorded as an immutable CaseEvent.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Case(Base):
    """An investigation case grouping related flags for a centre.

    Status flow:
        OPEN → ASSIGNED → INSPECTION_REQUESTED → TC_RESPONDED → CLOSED
        Any state → CLOSED (with reason)
    """

    __tablename__ = "case"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    centre_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("centre.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    case_number: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN", index=True)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="MEDIUM")
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Assignment
    assigned_to: Mapped[str | None] = mapped_column(String(256), comment="Assigned user subject (opaque ID)")
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # SLA
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sla_breached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Closure
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closure_reason: Mapped[str | None] = mapped_column(Text)

    # Legal hold
    legal_hold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    events: Mapped[list["CaseEvent"]] = relationship(
        back_populates="case", cascade="all, delete-orphan", order_by="CaseEvent.occurred_at"
    )
    tc_responses: Mapped[list["TCResponse"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )


class CaseEvent(Base):
    """Immutable audit trail for each case status transition."""

    __tablename__ = "case_event"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case.id", ondelete="CASCADE"), nullable=False, index=True
    )

    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    actor: Mapped[str] = mapped_column(String(256), nullable=False, comment="User subject (opaque)")
    note: Mapped[str | None] = mapped_column(Text)

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case: Mapped["Case"] = relationship(back_populates="events")


class TCResponse(Base):
    """Training centre response to a case or inspection request.

    Attachments are stored in S3; only s3_keys are stored here.
    """

    __tablename__ = "tc_response"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case.id", ondelete="CASCADE"), nullable=False, index=True
    )

    responder: Mapped[str] = mapped_column(String(256), nullable=False, comment="User subject (opaque)")
    response_text: Mapped[str | None] = mapped_column(Text)
    attachment_s3_keys: Mapped[list[str] | None] = mapped_column(JSONB)

    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case: Mapped["Case"] = relationship(back_populates="tc_responses")
