"""tests/integration/test_e2e_backend_lifecycle.py — Complete End-to-End backend lifecycle test."""
from __future__ import annotations

import base64
import hashlib
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any

import nacl.signing
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db_session
from app.core.config import get_settings
from app.core.security.device_key import DeviceSigningKey
from app.core.security.jwt import create_dev_token
from app.db.models.centre import Centre, Zone
from app.db.models.session_ import Batch, Session
from app.main import create_app


@pytest_asyncio.fixture
async def e2e_client_and_db(sqlite_session: AsyncSession) -> AsyncGenerator[tuple[AsyncClient, AsyncSession], None]:
    app = create_app()

    async def _override_get_db() -> Any:
        yield sqlite_session

    app.dependency_overrides[get_db_session] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, sqlite_session


@pytest.mark.asyncio
async def test_complete_backend_e2e_lifecycle(
    e2e_client_and_db: tuple[AsyncClient, AsyncSession],
) -> None:
    client, db = e2e_client_and_db
    settings = get_settings()
    dev_secret = settings.auth.dev_jwt_secret.get_secret_value()

    # 1. Health checks
    health_res = await client.get("/v1/healthz")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "ok"

    admin_token = create_dev_token(
        subject="admin-1",
        roles=["national_admin"],
        secret=dev_secret,
        issuer=settings.auth.oidc_issuer,
        audience=settings.auth.jwt_audience,
    )

    # 2. Setup Centre, Zone, and Batch
    centre = Centre(
        name="Bengaluru Aerospace Academy",
        code="CTR-BLR-AERO-01",
        state_code="KA",
        district="Bengaluru Urban",
        scheme_code="PMKVY",
    )
    db.add(centre)
    await db.flush()

    zone = Zone(
        centre_id=centre.id,
        zone_code="AERO-LAB-1",
        zone_type="practical_lab",
        coverage_factor=1.0,
    )
    db.add(zone)
    await db.flush()

    now = datetime.now(UTC).replace(second=0, microsecond=0)
    batch = Batch(
        centre_id=centre.id,
        batch_code="BATCH-AERO-2024-01",
        scheme_code="PMKVY",
        enrolled_count=20,
        batch_start_date=(now - timedelta(days=30)).date(),
        batch_end_date=(now + timedelta(days=60)).date(),
    )
    db.add(batch)
    await db.flush()

    start_time = now - timedelta(minutes=2)
    end_time = now + timedelta(hours=2)

    session = Session(
        batch_id=batch.id,
        zone_id=zone.id,
        scheduled_start=start_time,
        scheduled_end=end_time,
        claimed_count=20,
        trainer_count=1,
    )
    db.add(session)
    await db.flush()

    # 3. Device Enrollment (with DeviceSigningKey)
    key = DeviceSigningKey()

    enroll_payload = {
        "centre_id": str(centre.id),
        "zone_id": str(zone.id),
        "serial_number": "EDGE-BLR-AERO-001",
        "public_key_b64url": key.public_key_b64url,
        "enrollment_token": "admin-secret-token-123",
        "firmware_version": "v1.4.0",
        "model_version": "EdgeVision-AI-100",
    }
    enroll_res = await client.post(
        "/v1/device/enroll",
        json=enroll_payload,
    )
    assert enroll_res.status_code == 201
    enroll_data = enroll_res.json()
    device_id = uuid.UUID(enroll_data["device_id"])
    assert enroll_data["status"] == "ACTIVE"

    # 4. Device Heartbeat
    heartbeat_payload = {
        "device_id": str(device_id),
        "queue_depth": 0,
        "cpu_percent": 24.5,
        "temperature_celsius": 48.0,
        "free_disk_mb": 4096,
    }
    hb_res = await client.post(
        "/v1/device/heartbeat",
        json=heartbeat_payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert hb_res.status_code == 200
    assert hb_res.json()["acknowledged"] is True

    # 5. Ingest Signed Observations Batch
    records = []
    prev_h = None
    for i in range(5):
        ts = start_time + timedelta(minutes=i)
        payload = {
            "minute_ts": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "zone_id": str(zone.id),
            "session_id": str(session.id),
            "persons_min": 20,
            "persons_median": 22.5,
            "persons_p90": 25.0,
            "persons_max": 30,
            "item_counts": dict[str, int](),
            "feed_health": 1.0,
            "frames_used": 60,
            "model_version": "EdgeVision-AI-100",
            "prev_hash": prev_h,
        }
        rec_hash, sig = key.sign(payload)
        records.append({
            **payload,
            "record_hash": rec_hash,
            "signature": sig,
        })
        prev_h = rec_hash

    ingest_res = await client.post(
        "/v1/ingest/observations",
        json={"device_id": str(device_id), "records": records},
    )
    assert ingest_res.status_code == 200
    ingest_data = ingest_res.json()
    assert ingest_data["accepted"] == 5, f"Rejection reasons: {ingest_data['results']}"
    assert ingest_data["rejected"] == 0

    # 6. Query Centres & Risk
    centres_res = await client.get("/v1/centres", headers={"Authorization": f"Bearer {admin_token}"})
    assert centres_res.status_code == 200
    assert len(centres_res.json()["items"]) >= 1

    risk_res = await client.get(f"/v1/centres/{centre.id}/risk", headers={"Authorization": f"Bearer {admin_token}"})
    assert risk_res.status_code == 200
    assert "risk_score" in risk_res.json()

    # 7. Query Sessions
    sessions_res = await client.get("/v1/sessions", headers={"Authorization": f"Bearer {admin_token}"})
    assert sessions_res.status_code == 200
    assert len(sessions_res.json()["items"]) >= 1

    # 8. Evidence Presign URL and Duplicate Detection
    presign_res = await client.post(
        "/v1/evidence/presign",
        json={
            "device_id": str(device_id),
            "session_id": str(session.id),
            "zone_id": str(zone.id),
            "content_type": "image/jpeg",
            "size_bytes": 10240,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert presign_res.status_code == 201
    assert "upload_url" in presign_res.json()
    evidence_id = presign_res.json()["evidence_id"]

    dummy_sha256 = hashlib.sha256(b"dummy image bytes").hexdigest()
    complete_res = await client.post(
        "/v1/evidence/complete",
        json={"evidence_id": evidence_id, "sha256_hex": dummy_sha256},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert complete_res.status_code == 200
    assert complete_res.json()["is_near_duplicate"] is False

    # 9. Case Management Lifecycle
    create_case_res = await client.post(
        "/v1/cases",
        json={
            "centre_id": str(centre.id),
            "title": "Routine compliance review for Bengaluru Aerospace",
            "description": "Standard inspection case",
            "priority": "LOW",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_case_res.status_code == 200
    case_id = create_case_res.json()["id"]

    # Add case transition event
    trans_res = await client.post(
        f"/v1/cases/{case_id}/events",
        json={"to_status": "EXPLANATION_REQUESTED", "note": "Requested monthly log sheet"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert trans_res.status_code == 200

    # Training centre responds
    tc_token = create_dev_token(
        subject="tc-mgr",
        roles=["training_centre"],
        centre_ids=[str(centre.id)],
        secret=dev_secret,
        issuer=settings.auth.oidc_issuer,
        audience=settings.auth.jwt_audience,
    )
    respond_res = await client.post(
        f"/v1/cases/{case_id}/respond",
        json={
            "response_text": "Attached biometric logs for scheduled batch hours.",
            "attachment_s3_keys": ["evidence/biometric_audit_log.pdf"],
        },
        headers={"Authorization": f"Bearer {tc_token}"},
    )
    assert respond_res.status_code == 200

    # Verify case state updated
    case_detail_res = await client.get(f"/v1/cases/{case_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert case_detail_res.status_code == 200
    assert case_detail_res.json()["status"] == "TC_RESPONDED"
    assert len(case_detail_res.json()["tc_responses"]) == 1
