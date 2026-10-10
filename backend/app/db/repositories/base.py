"""app/db/repositories/base.py — Generic typed repository base class."""
from __future__ import annotations

import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic CRUD base.  All DB I/O uses the injected session; no new sessions created here."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: uuid.UUID) -> ModelT | None:
        return await self._session.get(self.model, id)

    async def get_all(self, *, limit: int = 100, offset: int = 0) -> list[ModelT]:
        result = await self._session.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def add(self, entity: ModelT) -> ModelT:
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def delete(self, entity: ModelT) -> None:
        await self._session.delete(entity)
        await self._session.flush()

    async def count(self) -> int:
        from sqlalchemy import func
        result = await self._session.execute(
            select(func.count()).select_from(self.model)  # type: ignore[arg-type]
        )
        return result.scalar_one()
