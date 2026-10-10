"""app/db/repositories/flag.py — Flag and IntegrityEvent repositories."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select

from app.db.models.flag import Flag, IntegrityEvent
from app.db.repositories.base import BaseRepository


class FlagRepository(BaseRepository[Flag]):
    model = Flag

    async def get_by_key(self, flag_key: str) -> Flag | None:
        result = await self._session.execute(
            select(Flag).where(Flag.flag_key == flag_key)
        )
        return result.scalar_one_or_none()

    async def upsert_by_key(self, flag: Flag) -> tuple[Flag, bool]:
        """Insert or update a flag by flag_key. Returns (flag, created)."""
        existing = await self.get_by_key(flag.flag_key)
        if existing:
            # Update mutable fields; never change flag_key or created_at
            existing.severity = flag.severity
            existing.description = flag.description
            existing.risk_score = flag.risk_score
            existing.window_end = flag.window_end
            await self._session.flush()
            return existing, False
        self._session.add(flag)
        await self._session.flush()
        return flag, True

    async def list_for_centre(
        self,
        centre_id: uuid.UUID,
        *,
        status: str | None = None,
        flag_type: str | None = None,
        limit: int = 100,
        cursor: uuid.UUID | None = None,
    ) -> list[Flag]:
        q = select(Flag).where(Flag.centre_id == centre_id)
        if status:
            q = q.where(Flag.status == status)
        if flag_type:
            q = q.where(Flag.flag_type == flag_type)
        if cursor:
            q = q.where(Flag.id > cursor)
        q = q.order_by(Flag.id).limit(limit)
        result = await self._session.execute(q)
        return list(result.scalars().all())


class IntegrityEventRepository(BaseRepository[IntegrityEvent]):
    model = IntegrityEvent

    async def list_for_device(
        self, device_id: uuid.UUID, *, limit: int = 50
    ) -> list[IntegrityEvent]:
        result = await self._session.execute(
            select(IntegrityEvent)
            .where(IntegrityEvent.device_id == device_id)
            .order_by(IntegrityEvent.occurred_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
