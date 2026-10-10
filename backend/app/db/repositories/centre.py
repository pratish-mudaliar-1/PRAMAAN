"""app/db/repositories/centre.py — Centre, Camera, Zone and SanctionedLayout repositories."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, or_, select

from app.db.models.centre import Camera, Centre, SanctionedLayout, Zone
from app.db.repositories.base import BaseRepository


class CentreRepository(BaseRepository[Centre]):
    model = Centre

    async def get_by_code(self, code: str) -> Centre | None:
        result = await self._session.execute(
            select(Centre).where(Centre.code == code)
        )
        return result.scalar_one_or_none()

    async def list_by_state(
        self,
        state_code: str,
        *,
        limit: int = 100,
        cursor: uuid.UUID | None = None,
        active_only: bool = True,
    ) -> list[Centre]:
        q = select(Centre).where(Centre.state_code == state_code)
        if active_only:
            q = q.where(Centre.is_active.is_(True))
        if cursor:
            q = q.where(Centre.id > cursor)
        q = q.order_by(Centre.id).limit(limit)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def list_by_ids(self, centre_ids: list[uuid.UUID]) -> list[Centre]:
        result = await self._session.execute(
            select(Centre).where(Centre.id.in_(centre_ids))
        )
        return list(result.scalars().all())

    async def get_zones(self, centre_id: uuid.UUID) -> list[Zone]:
        result = await self._session.execute(
            select(Zone).where(Zone.centre_id == centre_id, Zone.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def get_sanctioned_layout(
        self, centre_id: uuid.UUID, *, active_on: Any = None
    ) -> list[SanctionedLayout]:
        from datetime import UTC, datetime
        ts = active_on or datetime.now(UTC)
        result = await self._session.execute(
            select(SanctionedLayout).where(
                SanctionedLayout.centre_id == centre_id,
                SanctionedLayout.effective_from <= ts,
                or_(
                    SanctionedLayout.effective_to.is_(None),
                    SanctionedLayout.effective_to >= ts,
                ),
            )
        )
        return list(result.scalars().all())
