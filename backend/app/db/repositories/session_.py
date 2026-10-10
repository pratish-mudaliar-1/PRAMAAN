"""app/db/repositories/session_.py — Batch and Session repositories."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, select

from app.db.models.session_ import Batch, IngestDedupe, Session
from app.db.repositories.base import BaseRepository


class BatchRepository(BaseRepository[Batch]):
    model = Batch

    async def get_by_code(self, centre_id: uuid.UUID, batch_code: str) -> Batch | None:
        result = await self._session.execute(
            select(Batch).where(Batch.centre_id == centre_id, Batch.batch_code == batch_code)
        )
        return result.scalar_one_or_none()


class SessionRepository(BaseRepository[Session]):
    model = Session

    async def get_active_at(
        self,
        zone_id: uuid.UUID,
        ts: datetime,
    ) -> Session | None:
        """Return the session active (scheduled_start <= ts < scheduled_end) for a zone."""
        result = await self._session.execute(
            select(Session).where(
                Session.zone_id == zone_id,
                Session.scheduled_start <= ts,
                Session.scheduled_end > ts,
            )
        )
        return result.scalar_one_or_none()

    async def list_pending_reconciliation(self) -> list[Session]:
        """Sessions whose status is PENDING and whose window has ended."""
        from datetime import UTC
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(Session).where(
                Session.attendance_status == "PENDING",
                Session.scheduled_end < now,
            )
        )
        return list(result.scalars().all())

    async def list_for_batch(self, batch_id: uuid.UUID) -> list[Session]:
        result = await self._session.execute(
            select(Session).where(Session.batch_id == batch_id).order_by(Session.scheduled_start)
        )
        return list(result.scalars().all())


class IngestDedupeRepository(BaseRepository[IngestDedupe]):
    model = IngestDedupe

    async def exists(self, device_id: uuid.UUID, record_hash: str) -> bool:
        result = await self._session.execute(
            select(IngestDedupe.id).where(
                IngestDedupe.device_id == device_id,
                IngestDedupe.record_hash == record_hash,
            )
        )
        return result.scalar_one_or_none() is not None

    async def record(
        self,
        device_id: uuid.UUID,
        record_hash: str,
        observation_id: uuid.UUID | None = None,
    ) -> IngestDedupe:
        entry = IngestDedupe(
            device_id=device_id,
            record_hash=record_hash,
            observation_id=observation_id,
        )
        self._session.add(entry)
        await self._session.flush()
        return entry
