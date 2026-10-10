"""tests/unit/test_api_mvp_features.py — Unit tests for newly implemented MVP API endpoints."""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.jwt import create_dev_token
from app.db.models.audit import AuditLog
from app.db.models.camera_integrity import CameraIntegrityState, CameraReference, SceneObservation
from app.db.models.centre import Camera, Centre, Zone
from app.db.models.device import Device, DeviceStatusEnum
from app.db.models.evidence import Evidence
from app.db.models.ghost import GhostAssessment
from app.db.models.session_ import Batch, Session
from app.db.models.threshold import ThresholdProfile
from app.main import create_app


@pytest_asyncio.fixture
async def sample_mvp_data(sqlite_session: AsyncSession) -> dict[str, Any]:
    now = datetime.now(UTC)

    centre = Centre(
        id=uuid.uuid4(),
        name="Bengaluru Tech Institute",
        code="CTR-BLR-01",
        state_code="KA",
        district="Bengaluru Urban",
        scheme_code="PMKVY-4.0",
        latitude=12.9716,
        longitude=77.5946,
        is_active=True,
    )
    sqlite_session.add(centre)

    zone = Zone(
        id=uuid.uuid4(),
        centre_id=centre.id,
        zone_code="Z-LAB-01",
        zone_type="LAB",
        coverage_factor=1.0,
    )
    sqlite_session.add(zone)

    device = Device(
        id=uuid.uuid4(),
        centre_id=centre.id,
        zone_id=zone.id,
        serial_number="PRM-EDGE-BLR-001",
        public_key=b"\x01" * 32,
        public_key_b64url="AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE",
        status=DeviceStatusEnum.ACTIVE,
        is_active=True,
        firmware_version="v2.4.1",
        model_version="yolo11-pramaan-v2",
        last_heartbeat_at=now,
        last_telemetry={"cpu_percent": 34.5, "queue_depth": 0, "free_disk_mb": 14200},
    )
    sqlite_session.add(device)

    camera = Camera(
        id=uuid.uuid4(),
        centre_id=centre.id,
        camera_code="CAM-BLR-01",
        location_description="Main Classroom Lab",
        is_active=True,
    )

    sqlite_session.add(camera)
    zone.camera_id = camera.id

    cam_state = CameraIntegrityState(
        camera_id=camera.id,
        state="SWAP_SUSPECTED",
        since=now - timedelta(hours=1),
        last_transition_at=now - timedelta(hours=1),
        consecutive_suspicious=4,
        confidence=0.88,
    )
    sqlite_session.add(cam_state)

    obs = SceneObservation(
        id=uuid.uuid4(),
        camera_id=camera.id,
        ts=now - timedelta(minutes=10),
        fused_similarity=0.32,
        orb_inliers=14,
        inlier_ratio=0.18,
        classification="SWAPPED",
        source="server_verified",
    )
    sqlite_session.add(obs)

    batch = Batch(
        id=uuid.uuid4(),
        centre_id=centre.id,
        batch_code="BATCH-BLR-01",
        trade_code="Data Entry Operator",
        scheme_code="PMKVY-4.0",
        batch_start_date=now - timedelta(days=30),
        batch_end_date=now + timedelta(days=60),
    )
    sqlite_session.add(batch)


    ghost_assessment = GhostAssessment(
        id=uuid.uuid4(),
        batch_id=batch.id,
        centre_id=centre.id,
        window_start="2026-09-01",
        window_end="2026-10-04",
        state="SUSPECTED_GHOST",
        eligible_days=25,
        ghost_days=18,
        nodata_days=1,
        untrusted_days=0,
        ghost_score=0.72,
        explanation={"persistence": 0.85, "magnitude": 0.76},
        computed_at=now,
    )
    sqlite_session.add(ghost_assessment)

    thresholds = ThresholdProfile(
        id=uuid.uuid4(),
        scheme_code=None,
        state_code=None,
        version=1,
        is_active=True,
        t_green=0.80,
        t_amber=0.50,
        repeat_n=2,
        min_feed_health_fraction=0.50,
        item_absent_min_windows=3,
        item_absent_min_days=2,
        phash_hamming_threshold=10,
        approval_note="National standard v1",
    )
    sqlite_session.add(thresholds)

    evidence = Evidence(
        id=uuid.uuid4(),
        device_id=device.id,
        zone_id=zone.id,
        s3_key="evidence/blr/frame_001.jpg",
        content_type="image/jpeg",
        size_bytes=245000,
        captured_at=now,
        is_near_duplicate=False,
    )
    sqlite_session.add(evidence)

    await sqlite_session.commit()
    return {
        "centre": centre,
        "zone": zone,
        "device": device,
        "camera": camera,
        "batch": batch,
        "ghost_assessment": ghost_assessment,
        "evidence": evidence,
    }


@pytest_asyncio.fixture
async def client_and_session(sqlite_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _override_get_db() -> Any:
        yield sqlite_session

    from app.api.v1.deps import get_db_session
    app.dependency_overrides[get_db_session] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_camera_apis(
    client_and_session: AsyncClient,
    sample_mvp_data: dict[str, Any],
) -> None:
    cam = sample_mvp_data["camera"]
    token = create_dev_token(subject="admin-1", roles=["national_admin"], secret="test-secret-key")

    # 1. List cameras
    res = await client_and_session.get("/v1/cameras", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) >= 1
    assert data["items"][0]["camera_code"] == "CAM-BLR-01"
    assert data["items"][0]["current_state"] == "SWAP_SUSPECTED"

    # 2. Get camera detail
    res_det = await client_and_session.get(f"/v1/cameras/{cam.id}", headers={"Authorization": f"Bearer {token}"})
    assert res_det.status_code == 200
    assert res_det.json()["camera_code"] == "CAM-BLR-01"
    assert res_det.json()["observations_count"] >= 1

    # 3. Get camera observations
    res_obs = await client_and_session.get(f"/v1/cameras/{cam.id}/observations", headers={"Authorization": f"Bearer {token}"})
    assert res_obs.status_code == 200
    assert len(res_obs.json()) >= 1
    assert res_obs.json()[0]["classification"] == "SWAPPED"

    # 4. Rebaseline camera
    res_reb = await client_and_session.post(
        f"/v1/cameras/{cam.id}/rebaseline",
        json={"reason": "Camera re-mounted after physical room partition adjustment"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_reb.status_code == 200
    assert res_reb.json()["new_state"] == "STABLE"
    assert res_reb.json()["rebaselined"] is True


@pytest.mark.asyncio
async def test_ghost_apis(
    client_and_session: AsyncClient,
    sample_mvp_data: dict[str, Any],
) -> None:
    ga = sample_mvp_data["ghost_assessment"]
    token = create_dev_token(subject="admin-1", roles=["national_admin"], secret="test-secret-key")

    # 1. List ghost assessments
    res = await client_and_session.get("/v1/ghost-assessments", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) >= 1
    assert data["items"][0]["state"] == "SUSPECTED_GHOST"
    assert data["items"][0]["ghost_days"] == 18

    # 2. Get ghost assessment detail
    res_det = await client_and_session.get(f"/v1/ghost-assessments/{ga.id}", headers={"Authorization": f"Bearer {token}"})
    assert res_det.status_code == 200
    assert res_det.json()["state"] == "SUSPECTED_GHOST"

    # 3. List batches
    res_b = await client_and_session.get("/v1/batches", headers={"Authorization": f"Bearer {token}"})
    assert res_b.status_code == 200
    assert len(res_b.json()["items"]) >= 1
    assert res_b.json()["items"][0]["ghost_state"] == "SUSPECTED_GHOST"


@pytest.mark.asyncio
async def test_device_apis(
    client_and_session: AsyncClient,
    sample_mvp_data: dict[str, Any],
) -> None:
    dev = sample_mvp_data["device"]
    token = create_dev_token(subject="admin-1", roles=["national_admin"], secret="test-secret-key")

    # 1. List devices
    res = await client_and_session.get("/v1/devices", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) >= 1
    assert data["items"][0]["serial_number"] == "PRM-EDGE-BLR-001"
    assert data["items"][0]["health_status"] == "HEALTHY"

    # 2. Update device status
    res_stat = await client_and_session.post(
        f"/v1/devices/{dev.id}/status?new_status=OFFLINE",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_stat.status_code == 200
    assert res_stat.json()["status"] == "OFFLINE"


@pytest.mark.asyncio
async def test_threshold_and_audit_apis(
    client_and_session: AsyncClient,
    sample_mvp_data: dict[str, Any],
) -> None:
    token = create_dev_token(subject="admin-1", roles=["national_admin"], secret="test-secret-key")

    # 1. Get thresholds
    res_t = await client_and_session.get("/v1/thresholds", headers={"Authorization": f"Bearer {token}"})
    assert res_t.status_code == 200
    assert res_t.json()["t_green"] == 0.80
    assert res_t.json()["t_amber"] == 0.50

    # 2. Update thresholds
    res_up = await client_and_session.put(
        "/v1/thresholds",
        json={
            "t_green": 0.85,
            "t_amber": 0.55,
            "repeat_n": 3,
            "min_feed_health_fraction": 0.60,
            "item_absent_min_windows": 4,
            "item_absent_min_days": 3,
            "phash_hamming_threshold": 12,
            "approval_note": "Calibrated based on pilot field audit",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_up.status_code == 200
    assert res_up.json()["t_green"] == 0.85
    assert res_up.json()["version"] == 2

    # 3. Query audit log
    res_a = await client_and_session.get("/v1/audit-log", headers={"Authorization": f"Bearer {token}"})
    assert res_a.status_code == 200
    assert len(res_a.json()["items"]) >= 1
    actions = [row["action"] for row in res_a.json()["items"]]
    assert "THRESHOLD_UPDATE" in actions


@pytest.mark.asyncio
async def test_evidence_view_api(
    client_and_session: AsyncClient,
    sample_mvp_data: dict[str, Any],
) -> None:
    ev = sample_mvp_data["evidence"]
    token = create_dev_token(subject="admin-1", roles=["national_admin"], secret="test-secret-key")

    # 1. List evidence
    res = await client_and_session.get("/v1/evidence", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert len(res.json()["items"]) >= 1

    # 2. Get evidence view
    res_v = await client_and_session.get(f"/v1/evidence/{ev.id}/view", headers={"Authorization": f"Bearer {token}"})
    assert res_v.status_code == 200
    view_data = res_v.json()
    assert "view_url" in view_data
    assert "evidence/blr/frame_001.jpg" in view_data["view_url"]
    assert view_data["expires_in_seconds"] == 300
