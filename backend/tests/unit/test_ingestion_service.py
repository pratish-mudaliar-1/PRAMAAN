"""tests/unit/test_ingestion_service.py — Ingestion service unit tests using SQLite.

Tests the ObservationIngestionService in isolation — no real Postgres required.
Uses the SQLite in-memory session from conftest.py and real (non-mocked) signing keys.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import ObservationBatchRequest, ObservationRecord
from app.core.clock import FrozenClock
from app.core.config import get_settings
from app.core.security.device_key import (
    DeviceSigningKey,
    canonical_json,
    compute_record_hash,
)
from app.db.models.centre import Centre, Zone
from app.db.models.device import Device, DeviceStatusEnum


def make_signed_record(
    key: DeviceSigningKey,
    zone_id: uuid.UUID,
    minute_ts: datetime,
    prev_hash: str | None = None,
    session_id: uuid.UUID | None = None,
    *,
    tamper: bool = False,
) -> dict[str, Any]:
    ts = minute_ts.replace(second=0, microsecond=0, tzinfo=UTC if not minute_ts.tzinfo else minute_ts.tzinfo)
    payload = {
        "minute_ts": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "zone_id": str(zone_id),
        "session_id": str(session_id) if session_id else None,
        "persons_min": 20,
        "persons_median": 22.5,
        "persons_p90": 25.0,
        "persons_max": 30,
        "item_counts": dict[str, int](),
        "feed_health": 1.0,
        "frames_used": 60,
        "model_version": "test-v1",
        "prev_hash": prev_hash,
    }
    record_hash, sig = key.sign(payload)
    return {
        **payload,
        "record_hash": "b" * 64 if tamper else record_hash,
        "signature": sig,
    }


@pytest_asyncio.fixture
async def setup_device(sqlite_session: AsyncSession) -> tuple[Any, Any, DeviceSigningKey]:
    """Insert a centre, zone, and active device."""
    centre = Centre(
        name="Test Centre 01",
        code="CTR-01",
        state_code="KA",
        district="BLR",
        scheme_code="PMKVY",
    )
    sqlite_session.add(centre)
    await sqlite_session.flush()

    zone = Zone(
        centre_id=centre.id,
        zone_code="ZONE-A",
        zone_type="classroom",
        coverage_factor=1.0,
    )
    sqlite_session.add(zone)
    await sqlite_session.flush()

    key = DeviceSigningKey.from_seed(b"\xAB" * 32)
    device = Device(
        centre_id=centre.id,
        zone_id=zone.id,
        serial_number="TEST-SN-001",
        public_key=key.public_key_bytes,
        public_key_b64url=key.public_key_b64url,
        status=DeviceStatusEnum.ACTIVE,
        model_version="test-v1",
        enrollment_token_hash="hash-of-token",
    )
    sqlite_session.add(device)
    await sqlite_session.flush()

    return device, zone, key


@pytest.mark.asyncio
async def test_valid_record_is_accepted(setup_device: tuple[Any, Any, DeviceSigningKey], sqlite_session: AsyncSession) -> None:
    device, zone, key = setup_device
    ts = datetime(2024, 6, 15, 9, 0, 0, tzinfo=UTC)
    record_data = make_signed_record(key, zone.id, ts)
    batch = ObservationBatchRequest(
        device_id=device.id,
        records=[ObservationRecord(**record_data)],
    )
    from app.services.ingestion import ObservationIngestionService
    svc = ObservationIngestionService(sqlite_session, get_settings(), clock=FrozenClock(ts))
    result = await svc.process_batch(batch)
    assert result.accepted == 1
    assert result.rejected == 0


@pytest.mark.asyncio
async def test_duplicate_record_is_idempotent(setup_device: tuple[Any, Any, DeviceSigningKey], sqlite_session: AsyncSession) -> None:
    device, zone, key = setup_device
    ts = datetime(2024, 6, 15, 9, 0, 0, tzinfo=UTC)
    record_data = make_signed_record(key, zone.id, ts)
    batch = ObservationBatchRequest(
        device_id=device.id,
        records=[ObservationRecord(**record_data)],
    )
    from app.services.ingestion import ObservationIngestionService
    svc = ObservationIngestionService(sqlite_session, get_settings(), clock=FrozenClock(ts))
    r1 = await svc.process_batch(batch)
    r2 = await svc.process_batch(batch)
    assert r1.accepted == 1
    assert r2.accepted == 1   # idempotent — accepted again without error


@pytest.mark.asyncio
async def test_tampered_hash_is_rejected(setup_device: tuple[Any, Any, DeviceSigningKey], sqlite_session: AsyncSession) -> None:
    device, zone, key = setup_device
    ts = datetime(2024, 6, 15, 9, 5, 0, tzinfo=UTC)
    record_data = make_signed_record(key, zone.id, ts, tamper=True)
    batch = ObservationBatchRequest(
        device_id=device.id,
        records=[ObservationRecord(**record_data)],
    )
    from app.services.ingestion import ObservationIngestionService
    svc = ObservationIngestionService(sqlite_session, get_settings(), clock=FrozenClock(ts))
    result = await svc.process_batch(batch)
    assert result.rejected == 1
    assert result.results[0].reason is not None
    assert "hash" in result.results[0].reason.lower() or "mismatch" in result.results[0].reason.lower()


@pytest.mark.asyncio
async def test_unknown_device_raises(sqlite_session: AsyncSession) -> None:
    from app.core.errors import AuthenticationError
    from app.services.ingestion import ObservationIngestionService
    ts = datetime(2024, 6, 15, 9, 0, 0, tzinfo=UTC)
    key = DeviceSigningKey()
    zone_id = uuid.uuid4()
    rec = make_signed_record(key, zone_id, ts)
    batch = ObservationBatchRequest(
        device_id=uuid.uuid4(),  # unknown
        records=[ObservationRecord(**rec)],
    )
    svc = ObservationIngestionService(sqlite_session, get_settings(), clock=FrozenClock(ts))
    with pytest.raises(AuthenticationError):
        await svc.process_batch(batch)


@pytest.mark.asyncio
async def test_ingestion_triggers_session_reconciliation(
    setup_device: tuple[Any, Any, DeviceSigningKey],
    sqlite_session: AsyncSession,
) -> None:
    from app.db.models.session_ import Batch, Session
    from app.services.ingestion import ObservationIngestionService
    from unittest.mock import AsyncMock, patch

    device, zone, key = setup_device
    ts = datetime(2024, 6, 15, 9, 0, 0, tzinfo=UTC)

    # 1. Create batch and session
    batch_record = Batch(
        centre_id=device.centre_id,
        batch_code="B-RECON-01",
        scheme_code="PMKVY",
        enrolled_count=25,
        batch_start_date=ts.date(),
        batch_end_date=ts.date(),
    )
    sqlite_session.add(batch_record)
    await sqlite_session.flush()

    session_record = Session(
        batch_id=batch_record.id,
        zone_id=zone.id,
        scheduled_start=ts - timedelta(minutes=10),
        scheduled_end=ts + timedelta(minutes=50),
        claimed_count=25,
        trainer_count=1,
    )
    sqlite_session.add(session_record)
    await sqlite_session.flush()

    # 2. Build observation with session_id
    record_data = make_signed_record(key, zone.id, ts, session_id=session_record.id)
    obs_batch = ObservationBatchRequest(
        device_id=device.id,
        records=[ObservationRecord(**record_data)],
    )

    with patch("app.jobs.enqueue_session_reconciliation", new_callable=AsyncMock) as mock_enqueue:
        svc = ObservationIngestionService(sqlite_session, get_settings(), clock=FrozenClock(ts))
        res = await svc.process_batch(obs_batch)
        assert res.accepted == 1
        mock_enqueue.assert_awaited_once_with(session_record.id)

