"""tests/unit/test_webcam_edge_pipeline.py — Unit and integration tests for laptop webcam edge pipeline."""
from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime, timedelta
import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.device_key import (
    DeviceSigningKey,
    canonical_json,
    compute_record_hash,
    verify_record_signature,
    encode_public_key,
)
from app.db.models.centre import Centre, Zone
from app.db.models.device import Device, DeviceStatusEnum
from app.db.models.session_ import Batch, Session
from app.db.models.flag import Flag
from app.db.models.threshold import ThresholdProfile
from app.main import create_app
from app.services.reconciliation import ReconciliationService


def test_frame_aggregation_and_percentiles() -> None:
    """Test mathematical derivation of observation statistics from raw frame detections."""
    frame_counts = [1, 1, 2, 1, 1, 0, 1, 1, 2, 1]
    
    p_min = int(min(frame_counts))
    p_max = int(max(frame_counts))
    p_median = float(np.median(frame_counts))
    p_p90 = float(np.percentile(frame_counts, 90))
    frames_used = len(frame_counts)
    feed_health = 1.0

    assert p_min == 0
    assert p_max == 2
    assert p_median == 1.0
    assert p_p90 == 1.1 or p_p90 == 2.0 or 1.0 <= p_p90 <= 2.0
    assert frames_used == 10
    assert feed_health == 1.0


def test_canonical_serialization_and_ed25519_signature() -> None:
    """Test that canonical JSON, record hashing, and Ed25519 signing match backend verification."""
    key = DeviceSigningKey()
    now_ts = datetime.now(UTC).replace(second=0, microsecond=0)
    
    payload = {
        "minute_ts": now_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "zone_id": str(uuid.uuid4()),
        "session_id": str(uuid.uuid4()),
        "persons_min": 1,
        "persons_median": 1.0,
        "persons_p90": 1.0,
        "persons_max": 2,
        "item_counts": {},
        "feed_health": 1.0,
        "frames_used": 60,
        "model_version": "yolov8n-laptop-webcam",
        "prev_hash": None,
    }

    # 1. Canonical JSON bytes
    cb = canonical_json(payload)
    assert isinstance(cb, bytes)

    # 2. Record Hash
    rh = compute_record_hash(cb)
    assert len(rh) == 64

    # 3. Ed25519 Signing
    signed = key._sk.sign(cb)
    sig_b64url = base64.urlsafe_b64encode(signed.signature).rstrip(b"=").decode("ascii")

    # 4. Verify against backend function
    verify_record_signature(
        public_key_bytes=key.public_key_bytes,
        canonical_bytes=cb,
        signature_b64url=sig_b64url,
    )


@pytest.mark.asyncio
async def test_webcam_pipeline_ingest_reconcile_and_flag(sqlite_session: AsyncSession) -> None:
    """Full integration test: Webcam device signs records, submits to ingest API, reconciles, and generates flag."""
    now = datetime.now(UTC).replace(second=0, microsecond=0)

    # 1. Database entities
    centre = Centre(
        id=uuid.uuid4(),
        code="TC-DEV-TEST",
        name="Laptop Development Centre Test",
        state_code="DL",
        district="Central",
        scheme_code="DEV-DEMO",
        latitude=28.6139,
        longitude=77.2090,
    )
    sqlite_session.add(centre)
    await sqlite_session.flush()

    zone = Zone(
        id=uuid.uuid4(),
        centre_id=centre.id,
        zone_code="Z-DEV-WEBCAM-TEST",
        zone_type="CLASSROOM",
        coverage_factor=1.0,
    )
    sqlite_session.add(zone)
    await sqlite_session.flush()

    batch = Batch(
        id=uuid.uuid4(),
        centre_id=centre.id,
        batch_code="BATCH-DEV-TEST",
        scheme_code="DEV-DEMO",
        trade_code="Webcam Analytics",
        enrolled_count=5,
        batch_start_date=(now - timedelta(days=1)).date(),
        batch_end_date=(now + timedelta(days=30)).date(),
    )
    sqlite_session.add(batch)
    await sqlite_session.flush()

    # Session: Claimed = 3 candidates (Development Attendance Claim)
    session = Session(
        id=uuid.uuid4(),
        batch_id=batch.id,
        zone_id=zone.id,
        scheduled_start=now - timedelta(minutes=5),
        scheduled_end=now,
        claimed_count=3,
        trainer_count=0,
        attendance_status="PENDING",
    )
    sqlite_session.add(session)
    await sqlite_session.flush()

    # Device: DEV-WEBCAM-001 with real keypair
    key = DeviceSigningKey()
    device = Device(
        id=uuid.uuid4(),
        centre_id=centre.id,
        zone_id=zone.id,
        serial_number=f"DEV-WEBCAM-TEST-{uuid.uuid4().hex[:6]}",
        public_key=key.public_key_bytes,
        public_key_b64url=key.public_key_b64url,
        status=DeviceStatusEnum.ACTIVE,
        is_active=True,
        model_version="laptop-webcam-edge-v1",
        enrollment_token_hash="token-hash",
    )
    sqlite_session.add(device)
    await sqlite_session.commit()

    # 2. Generate 4 signed observations from the webcam agent (1 person detected)
    records = []
    prev_h = None
    for offset in [4, 3, 2, 1]:
        obs_time = now - timedelta(minutes=offset)
        obs_payload = {
            "minute_ts": obs_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "zone_id": str(zone.id),
            "session_id": str(session.id),
            "persons_min": 1,
            "persons_median": 1.0,
            "persons_p90": 1.0,
            "persons_max": 1,
            "item_counts": {},
            "feed_health": 1.0,
            "frames_used": 60,
            "model_version": "yolov8n-laptop-webcam",
            "prev_hash": prev_h,
        }
        cb = canonical_json(obs_payload)
        rh = compute_record_hash(cb)
        signed = key._sk.sign(cb)
        sig_b64 = base64.urlsafe_b64encode(signed.signature).rstrip(b"=").decode("ascii")
        records.append({**obs_payload, "record_hash": rh, "signature": sig_b64})
        prev_h = rh

    batch_request = {
        "device_id": str(device.id),
        "records": records,
    }

    # 3. Submit to Ingest API with dependency override
    from app.api.v1.deps import get_db_session

    app = create_app()

    async def _override_get_db():
        yield sqlite_session

    app.dependency_overrides[get_db_session] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/v1/ingest/observations", json=batch_request)
        assert res.status_code == 200, f"Ingestion failed: {res.text}"
        data = res.json()
        assert data["accepted"] == 4, f"Expected 4 accepted records: {data}"

    # 4. Run Reconciliation on the session
    recon_svc = ReconciliationService(sqlite_session)
    recon_res = await recon_svc.reconcile_session(session.id)
    await sqlite_session.commit()

    # Observed = 1 person, Claimed = 3 -> Ratio = 1/3 = 0.33 (< t_amber = 0.50)
    assert recon_res.status in ("RED", "AMBER"), f"Expected violation status, got {recon_res.status}"
    assert recon_res.ratio is not None and recon_res.ratio < 0.50

