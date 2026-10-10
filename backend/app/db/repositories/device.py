"""app/db/repositories/device.py — Device repository."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from app.db.models.device import Device, DeviceStatusEnum
from app.db.repositories.base import BaseRepository


class DeviceRepository(BaseRepository[Device]):
    model = Device

    async def get_by_serial(self, serial_number: str) -> Device | None:
        result = await self._session.execute(
            select(Device).where(Device.serial_number == serial_number)
        )
        return result.scalar_one_or_none()

    async def get_active_by_id(self, device_id: uuid.UUID) -> Device | None:
        result = await self._session.execute(
            select(Device).where(
                Device.id == device_id,
                Device.status == DeviceStatusEnum.ACTIVE,
                Device.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def list_by_centre(
        self, centre_id: uuid.UUID, *, active_only: bool = True
    ) -> list[Device]:
        q = select(Device).where(Device.centre_id == centre_id)
        if active_only:
            q = q.where(Device.is_active.is_(True))
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def update_last_seen(self, device: Device) -> Device:
        from datetime import UTC, datetime
        device.last_seen_at = datetime.now(UTC)
        await self._session.flush()
        return device

    async def update_hash_chain(
        self, device: Device, *, new_hash: str, new_seq: int
    ) -> Device:
        device.last_accepted_hash = new_hash
        device.last_accepted_seq = new_seq
        await self._session.flush()
        return device

    async def record_heartbeat(
        self, device: Device, telemetry: dict[str, Any] | None = None
    ) -> Device:
        from datetime import UTC, datetime
        now = datetime.now(UTC)
        device.last_heartbeat_at = now
        device.last_seen_at = now
        if telemetry:
            device.last_telemetry = telemetry
        await self._session.flush()
        return device
