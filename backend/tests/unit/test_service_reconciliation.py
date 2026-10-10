"""tests/unit/test_service_reconciliation.py — Reconciliation service and admin API tests."""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db_session
from app.core.clock import FrozenClock
from app.core.security.jwt import create_dev_token
from app.db.models.centre import Centre, Zone
from app.db.models.device import Device, DeviceStatusEnum
from app.db.models.flag import Flag, FlagInputSnapshot
from app.db.models.observation import Observation
from app.db.models.session_ import Batch, Session
from app.main import create_app
from app.services.reconciliation import ReconciliationService


@pytest_asyncio.fixture
async def setup_session_data(sqlite_session: AsyncSession) -> tuple[Centre, Zone, Batch, Session, Device]:
    centre = Centre(
        name="Mangaluru Skill Academy",
        code="CTR-MNG-01",
        state_code="KA",
        district="Dakshina Kannada",
        scheme_code="PMKVY",
    )
    sqlite_session.add(centre)
    await sqlite_session.flush()

    zone = Zone(
        centre_id=centre.id,
        zone_code="LAB-01",
        zone_type="practical_lab",
        coverage_factor=1.0,
    )
    sqlite_session.add(zone)
    await sqlite_session.flush()

    device = Device(
        centre_id=centre.id,
        zone_id=zone.id,
        serial_number="EDGE-MNG-001",
        public_key=b"\x01" * 32,
        public_key_b64url="AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE",
        status=DeviceStatusEnum.ACTIVE,
        is_active=True,
    )
    sqlite_session.add(device)
    await sqlite_session.flush()

    batch = Batch(
        centre_id=centre.id,
        batch_code="BATCH-MNG-001",
        scheme_code="PMKVY",
        enrolled_count=30,
        batch_start_date=datetime(2024, 6, 1, tzinfo=UTC).date(),
        batch_end_date=datetime(2024, 8, 31, tzinfo=UTC).date(),
    )
    sqlite_session.add(batch)
    await sqlite_session.flush()

    start = datetime(2024, 6, 15, 9, 0, 0, tzinfo=UTC)
    end = datetime(2024, 6, 15, 11, 0, 0, tzinfo=UTC)

    session = Session(
        batch_id=batch.id,
        zone_id=zone.id,
        scheduled_start=start,
        scheduled_end=end,
        claimed_count=30,
        trainer_count=1,
    )
    sqlite_session.add(session)
    await sqlite_session.flush()

    return centre, zone, batch, session, device


@pytest.mark.asyncio
async def test_reconciliation_service_green_session(
    sqlite_session: AsyncSession,
    setup_session_data: tuple[Centre, Zone, Batch, Session, Device],
) -> None:
    centre, zone, batch, session, device = setup_session_data

    # Add healthy observations (30 persons observed consistently)
    base_ts = session.scheduled_start
    for i in range(120):
        ts = base_ts + timedelta(minutes=i)
        obs = Observation(
            minute_ts=ts,
            device_id=device.id,
            zone_id=zone.id,
            session_id=session.id,
            persons_p90=30.0,
            feed_health=1.0,
            frames_used=60,
            record_hash=f"hash-{i:04d}" + "0" * 55,
            signature="test-sig",
        )
        sqlite_session.add(obs)
    await sqlite_session.flush()

    svc = ReconciliationService(sqlite_session, clock=FrozenClock(session.scheduled_end))
    result = await svc.reconcile_session(session.id)

    assert result.status == "GREEN"
    assert result.ratio is not None and result.ratio >= 0.80
    assert session.attendance_status == "GREEN"


@pytest.mark.asyncio
async def test_reconciliation_service_red_creates_flag(
    sqlite_session: AsyncSession,
    setup_session_data: tuple[Centre, Zone, Batch, Session, Device],
) -> None:
    centre, zone, batch, session, device = setup_session_data

    # Add observations with low count (only 5 persons seen out of 30 claimed)
    base_ts = session.scheduled_start
    for i in range(120):
        ts = base_ts + timedelta(minutes=i)
        obs = Observation(
            minute_ts=ts,
            device_id=device.id,
            zone_id=zone.id,
            session_id=session.id,
            persons_p90=5.0,
            feed_health=1.0,
            frames_used=60,
            record_hash=f"red-hash-{i:04d}" + "0" * 51,
            signature="test-sig",
        )
        sqlite_session.add(obs)
    await sqlite_session.flush()

    svc = ReconciliationService(sqlite_session, clock=FrozenClock(session.scheduled_end))
    result = await svc.reconcile_session(session.id)

    assert result.status == "AMBER"
    assert session.attendance_status == "AMBER"

    # Verify flag and snapshot created in DB
    from sqlalchemy import select
    flag = (await sqlite_session.execute(select(Flag).where(Flag.session_id == session.id))).scalar_one_or_none()
    assert flag is not None
    assert flag.severity == "AMBER"
    assert flag.flag_type == "ATTENDANCE_AMBER_REPEAT"
    assert flag.status == "OPEN"


    snapshot = (await sqlite_session.execute(select(FlagInputSnapshot).where(FlagInputSnapshot.flag_id == flag.id))).scalar_one_or_none()
    assert snapshot is not None
    assert snapshot.inputs["claimed_count"] == 30


# ── Admin API Tests ──────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client_and_session(sqlite_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _override_get_db() -> Any:
        yield sqlite_session

    app.dependency_overrides[get_db_session] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_admin_reevaluate_rbac(
    client_and_session: AsyncClient,
    setup_session_data: tuple[Centre, Zone, Batch, Session, Device],
) -> None:
    centre, _, _, session, _ = setup_session_data

    # 1. Unauthenticated request -> 401
    res1 = await client_and_session.post("/v1/admin/reevaluate", json={})
    assert res1.status_code == 401

    # 2. Centre manager role (not allowed) -> 403
    tc_token = create_dev_token(subject="user-tc", roles=["centre_manager"], secret="test-secret-key")
    res2 = await client_and_session.post(
        "/v1/admin/reevaluate",
        json={"centre_id": str(centre.id)},
        headers={"Authorization": f"Bearer {tc_token}"},
    )
    assert res2.status_code == 403

    # 3. National admin role -> 200
    admin_token = create_dev_token(subject="user-admin", roles=["national_admin"], secret="test-secret-key")
    res3 = await client_and_session.post(
        "/v1/admin/reevaluate",
        json={"centre_id": str(centre.id)},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res3.status_code == 200
    data = res3.json()
    assert data["evaluated_sessions"] >= 1
    assert "status_breakdown" in data
