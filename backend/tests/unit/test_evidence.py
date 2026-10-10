"""tests/unit/test_evidence.py — Evidence domain, perceptual hash, and REST endpoint tests."""
from __future__ import annotations

import io
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import pytest
import pytest_asyncio
from PIL import Image
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db_session
from app.core.security.device_key import DeviceSigningKey
from app.db.models.centre import Centre, Zone
from app.db.models.device import Device, DeviceStatusEnum
from app.domain.evidence import (
    compute_phash_from_bytes,
    compute_phash_from_image,
    hamming_distance,
    is_near_duplicate,
)
from app.main import create_app


# ── Domain Pure Function Tests ───────────────────────────────────────────────

def test_hamming_distance_exact_matches() -> None:
    h1 = 0x123456789ABCDEF0
    assert hamming_distance(h1, h1) == 0
    assert is_near_duplicate(h1, h1, threshold=0) is True


def test_hamming_distance_differing_bits() -> None:
    h1 = 0b00000000
    h2 = 0b00000101  # 2 bits different
    assert hamming_distance(h1, h2) == 2
    assert is_near_duplicate(h1, h2, threshold=2) is True
    assert is_near_duplicate(h1, h2, threshold=1) is False


def test_compute_phash_from_pil_image() -> None:
    # Create simple 100x100 RGB image
    img = Image.new("RGB", (100, 100), color=(128, 128, 128))
    phash_hex, phash_int = compute_phash_from_image(img)
    assert len(phash_hex) == 16
    assert isinstance(phash_int, int)
    assert phash_int >= 0


def test_compute_phash_from_bytes() -> None:
    img = Image.new("RGB", (64, 64), color=(200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    b = buf.getvalue()

    phash_hex, phash_int = compute_phash_from_bytes(b)
    assert len(phash_hex) == 16
    assert int(phash_hex, 16) == phash_int


# ── REST Endpoint Tests ──────────────────────────────────────────────────────

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
async def seeded_device(sqlite_session: AsyncSession) -> Device:
    centre = Centre(
        name="Bengaluru Central TC",
        code="CTR-BLR-01",
        state_code="KA",
        district="Bengaluru",
        scheme_code="PMKVY",
    )
    sqlite_session.add(centre)
    await sqlite_session.flush()

    zone = Zone(
        centre_id=centre.id,
        zone_code="ZONE-101",
        zone_type="workshop",
    )
    sqlite_session.add(zone)
    await sqlite_session.flush()

    key = DeviceSigningKey()
    device = Device(
        centre_id=centre.id,
        zone_id=zone.id,
        serial_number="EDGE-EVID-001",
        public_key=key.public_key_bytes,
        public_key_b64url=key.public_key_b64url,
        status=DeviceStatusEnum.ACTIVE,
        is_active=True,
    )
    sqlite_session.add(device)
    await sqlite_session.flush()
    return device


@pytest.mark.asyncio
async def test_evidence_presign_and_complete_cycle(
    client_and_session: AsyncClient,
    seeded_device: Device,
) -> None:
    # 1. Presign upload
    presign_payload = {
        "device_id": str(seeded_device.id),
        "content_type": "image/jpeg",
        "size_bytes": 102400,
    }
    res = await client_and_session.post("/v1/evidence/presign", json=presign_payload)
    assert res.status_code == 201
    data = res.json()
    evidence_id = data["evidence_id"]
    assert "upload_url" in data
    assert "key" in data["fields"]

    # 2. Complete upload
    complete_payload = {
        "evidence_id": evidence_id,
        "sha256_hex": "e" * 64,
    }
    comp_res = await client_and_session.post(
        f"/v1/evidence/complete?phash_hex=0123456789abcdef",
        json=complete_payload,
    )
    assert comp_res.status_code == 200
    comp_data = comp_res.json()
    assert comp_data["evidence_id"] == evidence_id
    assert comp_data["phash_hex"] == "0123456789abcdef"
    assert comp_data["is_near_duplicate"] is False


@pytest.mark.asyncio
async def test_evidence_near_duplicate_detection(
    client_and_session: AsyncClient,
    seeded_device: Device,
) -> None:
    # 1. Presign and complete first evidence with phash A
    res1 = await client_and_session.post(
        "/v1/evidence/presign",
        json={"device_id": str(seeded_device.id), "size_bytes": 50000},
    )
    id1 = res1.json()["evidence_id"]
    await client_and_session.post(
        "/v1/evidence/complete?phash_hex=0000000000000000",
        json={"evidence_id": id1, "sha256_hex": "1" * 64},
    )

    # 2. Presign and complete second evidence with 2-bit flip (within threshold 5)
    res2 = await client_and_session.post(
        "/v1/evidence/presign",
        json={"device_id": str(seeded_device.id), "size_bytes": 50000},
    )
    id2 = res2.json()["evidence_id"]
    comp2 = await client_and_session.post(
        "/v1/evidence/complete?phash_hex=0000000000000003",
        json={"evidence_id": id2, "sha256_hex": "2" * 64},
    )
    assert comp2.status_code == 200
    data2 = comp2.json()
    assert data2["is_near_duplicate"] is True
    assert data2["duplicate_of_id"] == id1
