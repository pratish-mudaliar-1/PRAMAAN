"""app/db/models/user.py — User and RoleBinding models.

Users are authenticated via external OIDC. This table stores the local profile
and role-to-resource bindings. No passwords are stored.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    """Local user profile. Linked to external OIDC identity via `subject`."""

    __tablename__ = "user"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject: Mapped[str] = mapped_column(
        String(256), nullable=False, unique=True, index=True,
        comment="OIDC sub claim — opaque external identifier"
    )
    # Display info (not used for access decisions)
    display_name: Mapped[str | None] = mapped_column(String(256))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    role_bindings: Mapped[list["RoleBinding"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class RoleBinding(Base):
    """Grants a role to a user, optionally scoped to a centre or state.

    The combination (user, role, centre_id, state_code) must be unique.
    """

    __tablename__ = "role_binding"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment="national_admin | state_officer | inspector | training_centre | auditor"
    )
    # Resource scope (null = unscoped; checked by policy layer)
    centre_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    state_code: Mapped[str | None] = mapped_column(String(8))

    granted_by: Mapped[str | None] = mapped_column(String(256), comment="User subject (opaque)")
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="role_bindings")

    __table_args__ = (
        UniqueConstraint("user_id", "role", "centre_id", "state_code"),
    )
