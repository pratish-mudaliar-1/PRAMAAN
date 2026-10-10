"""tests/unit/test_camera_and_ghost_pipeline.py — Unit tests for camera integrity and ghost batch pipelines."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import FrozenClock
from app.db.models.camera_integrity import CameraIntegrityState, SceneObservation
from app.db.models.centre import Camera, Centre, Zone
from app.db.models.flag import Flag
from app.db.models.ghost import GhostAssessment
from app.db.models.session_ import Batch, Session
from app.domain.camera_integrity import CameraIntegrityThresholds
from app.services.camera_integrity import CameraIntegrityService
from app.services.ghost_batch import GhostBatchDetectionService


@pytest.mark.asyncio
async def test_camera_integrity_service_evaluates_stable(
    sqlite_session: AsyncSession,
) -> None:
    centre = Centre(name="Belagavi TC", code="CTR-BEL-01", state_code="KA", district="Belagavi", scheme_code="PMKVY")
    sqlite_session.add(centre)
    await sqlite_session.flush()

    camera = Camera(centre_id=centre.id, camera_code="CAM-01", is_active=True)
    sqlite_session.add(camera)
    await sqlite_session.flush()

    now = datetime(2024, 6, 15, 10, 0, 0, tzinfo=UTC)
    # Add 10 stable scene observations
    for i in range(10):
        obs = SceneObservation(
            camera_id=camera.id,
            ts=now - timedelta(minutes=10 - i),
            source="server_verified",
            classification="STABLE",
            fused_similarity=0.90,
            inlier_ratio=0.80,
            orb_inliers=60,
            phash_dist=2,
        )
        sqlite_session.add(obs)
    await sqlite_session.flush()

    svc = CameraIntegrityService(sqlite_session, clock=FrozenClock(now))
    result = await svc.evaluate_camera(camera.id)

    assert result.current_state == "STABLE"
    assert result.transitioned is False


@pytest.mark.asyncio
async def test_ghost_batch_detection_service(
    sqlite_session: AsyncSession,
) -> None:
    centre = Centre(name="Shivamogga TC", code="CTR-SHV-01", state_code="KA", district="Shivamogga", scheme_code="PMKVY")
    sqlite_session.add(centre)
    await sqlite_session.flush()

    zone = Zone(centre_id=centre.id, zone_code="CLASS-01", zone_type="classroom")
    sqlite_session.add(zone)
    await sqlite_session.flush()

    batch = Batch(
        centre_id=centre.id,
        batch_code="BATCH-GHOST-01",
        scheme_code="PMKVY",
        enrolled_count=30,
    )
    sqlite_session.add(batch)
    await sqlite_session.flush()

    now = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)

    # Add 2 sessions with claimed 30 but ratio 0.05 (< 0.20)
    for i in range(2):
        s = Session(
            batch_id=batch.id,
            zone_id=zone.id,
            scheduled_start=now - timedelta(days=2 - i, hours=2),
            scheduled_end=now - timedelta(days=2 - i),
            claimed_count=30,
            attendance_status="RED",
            attendance_ratio=0.05,
        )
        sqlite_session.add(s)
    await sqlite_session.flush()

    svc = GhostBatchDetectionService(sqlite_session, clock=FrozenClock(now))
    result = await svc.assess_batch(batch.id)

    assert result.is_ghost_pattern is True
    assert result.state == "SUSPECTED_GHOST"
    assert result.ghost_sessions_count == 2

    # Check Flag created
    from sqlalchemy import select
    flag = (await sqlite_session.execute(select(Flag).where(Flag.centre_id == centre.id))).scalar_one_or_none()
    assert flag is not None
    assert flag.flag_type in ("GHOST_BATCH", "GHOST_BATCH_PATTERN")
    assert flag.severity == "RED"
