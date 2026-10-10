"""app/services/ingestion.py — Observation ingestion orchestration service.

This layer sits between the router and the domain/db layers.
It owns transaction boundaries, publishes events, and enforces:
  - Idempotency (IngestDedupe)
  - Device authentication
  - Ed25519 signature verification
  - Hash-chain continuity
  - Timestamp plausibility
  - Schema strictness (handled by Pydantic before this layer)
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import ObservationBatchRequest, ObservationRecord, RecordResult
from app.core.clock import AbstractClock, system_clock
from app.core.config import Settings
from app.core.errors import AuthenticationError, IntegrityError
from app.core.logging import get_logger
from app.core.security.device_key import canonical_json, compute_record_hash, verify_record_signature, decode_public_key
from app.db.models.device import Device, DeviceStatusEnum
from app.db.models.flag import IntegrityEvent
from app.db.models.observation import Observation
from app.db.models.session_ import IngestDedupe
from app.db.repositories.device import DeviceRepository
from app.db.repositories.flag import IntegrityEventRepository
from app.db.repositories.observation import ObservationRepository
from app.db.repositories.session_ import IngestDedupeRepository, SessionRepository

logger = get_logger(__name__)


class IngestionResult:
    def __init__(self) -> None:
        self.results: list[RecordResult] = []
        self.accepted = 0
        self.rejected = 0
        self.affected_sessions: set[uuid.UUID] = set()

    def accept(self, record_hash: str) -> None:
        self.results.append(RecordResult(record_hash=record_hash, accepted=True))
        self.accepted += 1

    def reject(self, record_hash: str, reason: str) -> None:
        self.results.append(RecordResult(record_hash=record_hash, accepted=False, reason=reason))
        self.rejected += 1


class ObservationIngestionService:
    """Orchestrates the full ingestion pipeline for one batch."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        clock: AbstractClock = system_clock,
    ) -> None:
        self._session = session
        self._cfg = settings
        self._clock = clock

        self._devices = DeviceRepository(session)
        self._obs = ObservationRepository(session)
        self._dedupe = IngestDedupeRepository(session)
        self._sessions = SessionRepository(session)
        self._integrity = IntegrityEventRepository(session)

    async def process_batch(self, batch: ObservationBatchRequest) -> IngestionResult:
        result = IngestionResult()

        # 1. Load device once for the whole batch
        device = await self._devices.get_by_id(batch.device_id)
        if not device:
            raise AuthenticationError(f"Device {batch.device_id} not found")
        if device.status == DeviceStatusEnum.REVOKED:
            raise AuthenticationError(f"Device {batch.device_id} is revoked")
        if device.status == DeviceStatusEnum.SUSPENDED:
            raise AuthenticationError(f"Device {batch.device_id} is suspended")
        if not device.is_active:
            raise AuthenticationError(f"Device {batch.device_id} is inactive")

        public_key = device.public_key

        # 2. Process records (sort by minute_ts for chain validation)
        sorted_records = sorted(batch.records, key=lambda r: r.minute_ts)

        for record in sorted_records:
            rh = record.record_hash
            try:
                sess_id = await self._process_one(device, public_key, record, result)
                if sess_id:
                    result.affected_sessions.add(sess_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("record_rejected", record_hash=rh, error=str(exc))
                result.reject(rh, str(exc))

        # 3. Update device last_seen
        await self._devices.update_last_seen(device)
        await self._session.commit()

        # 4. Enqueue reconciliation for affected sessions
        if result.affected_sessions:
            from app.jobs import enqueue_session_reconciliation
            for sid in result.affected_sessions:
                try:
                    await enqueue_session_reconciliation(sid)
                except Exception as recon_err:  # noqa: BLE001
                    logger.warning("reconciliation_enqueue_failed", session_id=str(sid), error=str(recon_err))

        return result

    async def _process_one(
        self,
        device: Device,
        public_key: bytes,
        record: ObservationRecord,
        result: IngestionResult,
    ) -> uuid.UUID | None:
        rh = record.record_hash
        now = self._clock.utcnow()

        # ── Idempotency check ────────────────────────────────────────────────
        if await self._dedupe.exists(device.id, rh):
            result.accept(rh)  # already processed — idempotent success
            return record.session_id

        # ── Verify canonical hash matches payload ────────────────────────────
        payload_for_hash = record.model_dump(
            exclude={"record_hash", "signature"},
            mode="json",
        )
        cb = canonical_json(payload_for_hash)
        expected_hash = compute_record_hash(cb)
        if expected_hash != rh:
            result.reject(rh, f"record_hash mismatch: expected {expected_hash}")
            return

        # ── Ed25519 signature verification ────────────────────────────────────
        try:
            verify_record_signature(
                public_key_bytes=public_key,
                canonical_bytes=cb,
                signature_b64url=record.signature,
            )
        except ValueError as exc:
            await self._store_integrity_event(device, "SIGNATURE_INVALID", rh, {"error": str(exc)})
            result.reject(rh, f"signature_invalid: {exc}")
            return

        # ── Timestamp plausibility ────────────────────────────────────────────
        skew_window = timedelta(seconds=self._cfg.auth.device_clock_skew_window_seconds)
        ts = record.minute_ts
        if not ts.tzinfo:
            from datetime import timezone
            ts = ts.replace(tzinfo=timezone.utc)
        skew_ms = int((now - ts).total_seconds() * 1000)
        if abs(now - ts) > skew_window:
            await self._store_integrity_event(device, "CLOCK_SKEW", rh, {"skew_ms": skew_ms})
            result.reject(rh, f"clock_skew: {skew_ms}ms outside ±{skew_window.total_seconds()}s")
            return

        # ── Hash-chain continuity ─────────────────────────────────────────────
        chain_ok = True
        if device.last_accepted_hash and record.prev_hash != device.last_accepted_hash:
            chain_ok = False
            await self._store_integrity_event(
                device, "CHAIN_BREAK", rh,
                {"expected_prev": device.last_accepted_hash, "got_prev": record.prev_hash}
            )
            logger.warning(
                "chain_break", device_id=str(device.id),
                expected=device.last_accepted_hash, got=record.prev_hash
            )
            # Chain breaks are stored but NOT rejected — observation is still accepted
            # with chain_ok=False for downstream analysis

        # ── Find active session ───────────────────────────────────────────────
        session_id: uuid.UUID | None = record.session_id
        if session_id is None:
            active_session = await self._sessions.get_active_at(record.zone_id, ts)
            if active_session:
                session_id = active_session.id

        # ── Write observation ─────────────────────────────────────────────────
        obs = Observation(
            minute_ts=ts,
            device_id=device.id,
            zone_id=record.zone_id,
            session_id=session_id,
            persons_min=record.persons_min,
            persons_median=record.persons_median,
            persons_p90=record.persons_p90,
            persons_max=record.persons_max,
            item_counts=record.item_counts,
            feed_health=record.feed_health,
            frames_used=record.frames_used,
            model_version=record.model_version,
            record_hash=rh,
            prev_hash=record.prev_hash,
            signature=record.signature,
            chain_ok=chain_ok,
            clock_skew_ms=skew_ms,
        )
        self._session.add(obs)
        await self._session.flush()

        # ── Update device hash chain ──────────────────────────────────────────
        new_seq = device.last_accepted_seq + 1
        await self._devices.update_hash_chain(device, new_hash=rh, new_seq=new_seq)

        # ── Record dedupe entry ───────────────────────────────────────────────
        await self._dedupe.record(device.id, rh, obs.id)

        result.accept(rh)
        logger.info("observation_accepted", device_id=str(device.id), record_hash=rh, chain_ok=chain_ok)
        return session_id

    async def _store_integrity_event(
        self, device: Device, event_type: str, record_hash: str, detail: dict[str, Any]
    ) -> None:
        evt = IntegrityEvent(
            device_id=device.id,
            centre_id=device.centre_id,
            event_type=event_type,
            severity="HIGH" if event_type in ("CHAIN_BREAK", "REPLAY") else "MEDIUM",
            detail=detail,
            record_hash=record_hash,
        )
        self._session.add(evt)
        await self._session.flush()
