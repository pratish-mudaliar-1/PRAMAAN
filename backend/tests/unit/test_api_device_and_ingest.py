"""tests/unit/test_api_device_and_ingest.py — API integration tests for device enrollment and observation ingestion."""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db_session
from app.core.security.device_key import DeviceSigningKey
from app.db.models.centre import Centre, Zone
from app.db.models.device import Device, DeviceStatusEnum
from app.main import create_app
from tests.contract_client.client import ContractClient


@pytest_asyncio.fixture
async def client_and_session(sqlite_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _override_get_db() -> Any:
        yield sqlite_session

    app.dependency_overrides[get_db_session] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def seeded_centre(sqlite_session: AsyncSession) -> tuple[Centre, Zone]:
    centre = Centre(
        name="Hubballi Skill Centre",
        code="CTR-HUB-01",
        state_code="KA",
        district="Dharwad",
        scheme_code="PMKVY-4.0",
    )
    sqlite_session.add(centre)
    await sqlite_session.flush()

    zone = Zone(
        centre_id=centre.id,
        zone_code="LAB-101",
        zone_type="computer_lab",
        coverage_factor=1.0,
    )
    sqlite_session.add(zone)
    await sqlite_session.flush()
    return centre, zone


# ── Device Enrollment Tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_device_enrollment_success(
    client_and_session: AsyncClient,
    seeded_centre: tuple[Centre, Zone],
) -> None:
    centre, zone = seeded_centre
    key = DeviceSigningKey()

    payload = {
        "serial_number": "EDGE-CAM-HUB-001",
        "centre_id": str(centre.id),
        "zone_id": str(zone.id),
        "public_key_b64url": key.public_key_b64url,
        "enrollment_token": "admin-secret-token-123",
        "model_version": "pramaan-edge-v1.0",
        "firmware_version": "v2.4.1",
    }

    res = await client_and_session.post("/v1/device/enroll", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["serial_number"] == "EDGE-CAM-HUB-001"
    assert data["status"] == "ACTIVE"
    assert "device_id" in data


@pytest.mark.asyncio
async def test_device_enrollment_duplicate_serial_fails(
    client_and_session: AsyncClient,
    seeded_centre: tuple[Centre, Zone],
) -> None:
    centre, zone = seeded_centre
    key = DeviceSigningKey()

    payload = {
        "serial_number": "EDGE-CAM-HUB-002",
        "centre_id": str(centre.id),
        "zone_id": str(zone.id),
        "public_key_b64url": key.public_key_b64url,
        "enrollment_token": "token-1",
    }

    res1 = await client_and_session.post("/v1/device/enroll", json=payload)
    assert res1.status_code == 201

    res2 = await client_and_session.post("/v1/device/enroll", json=payload)
    assert res2.status_code == 409
    assert res2.headers["content-type"] == "application/problem+json"


@pytest.mark.asyncio
async def test_device_enrollment_unknown_centre_fails(
    client_and_session: AsyncClient,
) -> None:
    key = DeviceSigningKey()
    payload = {
        "serial_number": "EDGE-CAM-UNKNOWN-001",
        "centre_id": str(uuid.uuid4()),
        "public_key_b64url": key.public_key_b64url,
        "enrollment_token": "token-1",
    }
    res = await client_and_session.post("/v1/device/enroll", json=payload)
    assert res.status_code == 404


# ── Ingestion Tests ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ingest_observations_batch_success(
    client_and_session: AsyncClient,
    seeded_centre: tuple[Centre, Zone],
) -> None:
    centre, zone = seeded_centre
    key = DeviceSigningKey.from_seed(b"\x11" * 32)

    # 1. Enroll device
    enroll_payload = {
        "serial_number": "EDGE-CAM-INGEST-01",
        "centre_id": str(centre.id),
        "zone_id": str(zone.id),
        "public_key_b64url": key.public_key_b64url,
        "enrollment_token": "token-ingest-1",
    }
    enroll_res = await client_and_session.post("/v1/device/enroll", json=enroll_payload)
    assert enroll_res.status_code == 201
    device_id = uuid.UUID(enroll_res.json()["device_id"])

    # 2. Build batch using ContractClient
    contract_client = ContractClient(device_id, seed=b"\x11" * 32)
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    record1 = contract_client.build_record(zone_id=zone.id, minute_ts=now)
    record2 = contract_client.build_record(zone_id=zone.id, minute_ts=now)

    batch_payload = {
        "device_id": str(device_id),
        "records": [record1, record2],
    }

    # 3. Post batch
    res = await client_and_session.post("/v1/ingest/observations", json=batch_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["accepted"] == 2
    assert data["rejected"] == 0
    assert len(data["results"]) == 2


@pytest.mark.asyncio
async def test_device_heartbeat(
    client_and_session: AsyncClient,
    seeded_centre: tuple[Centre, Zone],
) -> None:
    centre, zone = seeded_centre
    key = DeviceSigningKey()
    enroll_res = await client_and_session.post(
        "/v1/device/enroll",
        json={
            "serial_number": "EDGE-CAM-HB-01",
            "centre_id": str(centre.id),
            "public_key_b64url": key.public_key_b64url,
            "enrollment_token": "token-hb",
        },
    )
    device_id = enroll_res.json()["device_id"]

    hb_res = await client_and_session.post(
        "/v1/device/heartbeat",
        json={
            "device_id": device_id,
            "cpu_percent": 24.5,
            "queue_depth": 0,
            "free_disk_mb": 14200,
        },
    )
    assert hb_res.status_code == 200
    assert hb_res.json()["acknowledged"] is True
