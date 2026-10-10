"""app/db/repositories/evidence.py — Evidence repository."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from app.db.models.evidence import Evidence
from app.db.repositories.base import BaseRepository
from app.domain.evidence import hamming_distance


class EvidenceRepository(BaseRepository[Evidence]):
    model = Evidence

    async def get_by_s3_key(self, s3_key: str) -> Evidence | None:
        result = await self._session.execute(
            select(Evidence).where(Evidence.s3_key == s3_key)
        )
        return result.scalar_one_or_none()

    async def list_by_device(
        self, device_id: uuid.UUID, *, limit: int = 100
    ) -> list[Evidence]:
        result = await self._session.execute(
            select(Evidence)
            .where(Evidence.device_id == device_id)
            .order_by(Evidence.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def find_near_duplicate(
        self,
        device_id: uuid.UUID,
        phash_int: int,
        *,
        threshold: int = 5,
        limit: int = 50,
    ) -> Evidence | None:
        """Find the closest existing evidence record within the Hamming distance threshold."""
        # Query recent evidence for this device with valid phash_int
        result = await self._session.execute(
            select(Evidence)
            .where(
                Evidence.device_id == device_id,
                Evidence.phash_int.is_not(None),
            )
            .order_by(Evidence.created_at.desc())
            .limit(limit)
        )
        records = list(result.scalars().all())

        best_match: Evidence | None = None
        best_distance = threshold + 1

        for rec in records:
            if rec.phash_int is not None:
                dist = hamming_distance(phash_int, rec.phash_int)
                if dist <= threshold and dist < best_distance:
                    best_distance = dist
                    best_match = rec

        return best_match
