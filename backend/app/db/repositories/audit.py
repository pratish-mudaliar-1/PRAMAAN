"""app/db/repositories/audit.py — Append-only audit log repository."""
from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.models.audit import AuditLog
from app.db.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditLog]):
    model = AuditLog

    async def _get_last_row_hash(self) -> str:
        result = await self._session.execute(
            select(AuditLog.row_hash).order_by(AuditLog.occurred_at.desc()).limit(1)
        )
        last = result.scalar_one_or_none()
        return last or ("0" * 64)

    async def append(
        self,
        *,
        actor: str,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        request_id: str | None = None,
        ip_hash: str | None = None,
        detail: dict | None = None,  # type: ignore[type-arg]
    ) -> AuditLog:
        """Append a new audit log row with a computed hash chain link.

        No row is ever updated after insertion.
        """
        prev_hash = await self._get_last_row_hash()
        now = datetime.now(UTC).isoformat()
        raw = f"{prev_hash}|{actor}|{action}|{resource_type}|{resource_id or ''}|{now}"
        row_hash = hashlib.sha256(raw.encode()).hexdigest()

        entry = AuditLog(
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            ip_hash=ip_hash,
            detail=detail,
            row_hash=row_hash,
            prev_hash=prev_hash,
            occurred_at=datetime.now(UTC),
        )
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def list_for_resource(
        self,
        resource_type: str,
        resource_id: str,
        *,
        limit: int = 100,
        cursor: uuid.UUID | None = None,
    ) -> list[AuditLog]:
        q = select(AuditLog).where(
            AuditLog.resource_type == resource_type,
            AuditLog.resource_id == resource_id,
        )
        if cursor:
            q = q.where(AuditLog.id > cursor)
        q = q.order_by(AuditLog.occurred_at).limit(limit)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def verify_chain(self) -> bool:
        """Verify the continuity of the entire audit log SHA-256 hash chain."""
        q = select(AuditLog).order_by(AuditLog.occurred_at.asc())
        result = await self._session.execute(q)
        rows = list(result.scalars().all())
        if not rows:
            return True
        for i in range(1, len(rows)):
            if rows[i].prev_hash != rows[i - 1].row_hash:
                return False
        return True

