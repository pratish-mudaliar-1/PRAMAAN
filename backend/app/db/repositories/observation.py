"""app/db/repositories/observation.py — Observation repository with time-range queries."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, func, select

from app.db.models.observation import Observation
from app.db.repositories.base import BaseRepository


class ObservationRepository(BaseRepository[Observation]):
    model = Observation

    async def get_by_record_hash(self, record_hash: str) -> Observation | None:
        result = await self._session.execute(
            select(Observation).where(Observation.record_hash == record_hash)
        )
        return result.scalar_one_or_none()

    async def list_for_session_window(
        self,
        zone_id: uuid.UUID,
        start: datetime,
        end: datetime,
        *,
        device_id: uuid.UUID | None = None,
    ) -> list[Observation]:
        """Return observations within a session window for a zone."""
        q = select(Observation).where(
            Observation.zone_id == zone_id,
            Observation.minute_ts >= start,
            Observation.minute_ts < end,
        )
        if device_id:
            q = q.where(Observation.device_id == device_id)
        q = q.order_by(Observation.minute_ts)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def p90_persons_in_window(
        self,
        zone_id: uuid.UUID,
        start: datetime,
        end: datetime,
    ) -> float | None:
        """Compute P90 of persons_p90 values in a session window.

        Returns None if no observations with valid feed health exist.
        This is a convenience method; the domain layer still owns the
        full reconciliation logic and calls this for real DB-backed data.
        """
        result = await self._session.execute(
            select(
                func.percentile_cont(0.90)
                .within_group(Observation.persons_p90)
                .label("p90")
            ).where(
                Observation.zone_id == zone_id,
                Observation.minute_ts >= start,
                Observation.minute_ts < end,
                Observation.feed_health > 0.0,
                Observation.persons_p90.is_not(None),
            )
        )
        return result.scalar_one_or_none()

    async def avg_feed_health(
        self, zone_id: uuid.UUID, start: datetime, end: datetime
    ) -> float | None:
        result = await self._session.execute(
            select(func.avg(Observation.feed_health)).where(
                Observation.zone_id == zone_id,
                Observation.minute_ts >= start,
                Observation.minute_ts < end,
            )
        )
        return result.scalar_one_or_none()

    async def last_by_device(self, device_id: uuid.UUID) -> Observation | None:
        result = await self._session.execute(
            select(Observation)
            .where(Observation.device_id == device_id)
            .order_by(Observation.minute_ts.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
