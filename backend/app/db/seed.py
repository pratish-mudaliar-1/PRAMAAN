"""app/db/seed.py — Comprehensive Database seeder for demo & local development.

Populates realistic, connected data across all 28 tables:
centres with coordinates, cameras with baselines and observation trends,
batches, sessions, edge devices with telemetry, ghost assessments,
threshold profiles, audit trail with hash chains, and evidence metadata.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit import AuditLog
from app.db.models.camera_integrity import (
    CameraIntegrityState,
    CameraReference,
    CameraStateEvent,
    SceneObservation,
)
from app.db.models.case_ import Case, CaseEvent, TCResponse
from app.db.models.centre import Camera, Centre, SanctionedLayout, Zone
from app.db.models.device import Device, DeviceStatusEnum
from app.db.models.evidence import Evidence
from app.db.models.flag import Flag, FlagInputSnapshot
from app.db.models.ghost import GhostAssessment, GhostStateEvent
from app.db.models.session_ import Batch, Session
from app.db.models.threshold import ThresholdProfile
from app.db.repositories.audit import AuditRepository

logger = logging.getLogger(__name__)


async def seed_dev_database(session: AsyncSession) -> None:
    """Populate database with rich, connected demo data across all modules."""
    now = datetime.now(UTC)

    # ── 1. Centres ───────────────────────────────────────────────────────────
    centres_data = [
        {
            "name": "Delhi Institute of Skill Development",
            "code": "TC-DL-001",
            "state_code": "DL",
            "district": "New Delhi",
            "scheme_code": "PMKVY-4.0",
            "registration_no": "REG-2023-DL-0981",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "is_active": True,
        },
        {
            "name": "Mumbai Advanced Vocational Academy",
            "code": "TC-MH-002",
            "state_code": "MH",
            "district": "Mumbai Suburban",
            "scheme_code": "DDU-GKY",
            "registration_no": "REG-2022-MH-4421",
            "latitude": 19.0760,
            "longitude": 72.8777,
            "is_active": True,
        },
        {
            "name": "Bengaluru Tech Training Hub",
            "code": "TC-KA-003",
            "state_code": "KA",
            "district": "Bengaluru Urban",
            "scheme_code": "PMKVY-4.0",
            "registration_no": "REG-2023-KA-1120",
            "latitude": 12.9716,
            "longitude": 77.5946,
            "is_active": True,
        },
        {
            "name": "Lucknow Skill & Employment Centre",
            "code": "TC-UP-004",
            "state_code": "UP",
            "district": "Lucknow",
            "scheme_code": "SANKALP",
            "registration_no": "REG-2021-UP-8842",
            "latitude": 26.8467,
            "longitude": 80.9462,
            "is_active": True,
        },
        {
            "name": "Jaipur Solar & Electric Training Centre",
            "code": "TC-RJ-005",
            "state_code": "RJ",
            "district": "Jaipur",
            "scheme_code": "PMKVY-4.0",
            "registration_no": "REG-2023-RJ-3312",
            "latitude": 26.9124,
            "longitude": 75.7873,
            "is_active": True,
        },
        {
            "name": "Chennai Industrial Automation Lab",
            "code": "TC-TN-006",
            "state_code": "TN",
            "district": "Chennai",
            "scheme_code": "STRIVE",
            "registration_no": "REG-2022-TN-7754",
            "latitude": 13.0827,
            "longitude": 80.2707,
            "is_active": True,
        },
    ]

    existing_centres = (await session.execute(select(Centre))).scalars().all()
    centres_by_code: dict[str, Centre] = {c.code: c for c in existing_centres}

    for c_data in centres_data:
        code = c_data["code"]
        if code in centres_by_code:
            c = centres_by_code[code]
            c.latitude = c_data["latitude"]
            c.longitude = c_data["longitude"]
            c.name = c_data["name"]
        else:
            c = Centre(id=uuid.uuid4(), **c_data)
            session.add(c)
            await session.flush()
            centres_by_code[code] = c

    c_dl = centres_by_code["TC-DL-001"]
    c_mh = centres_by_code["TC-MH-002"]
    c_ka = centres_by_code["TC-KA-003"]
    c_up = centres_by_code["TC-UP-004"]
    c_rj = centres_by_code["TC-RJ-005"]
    c_tn = centres_by_code["TC-TN-006"]

    # ── 2. Cameras & Zones ───────────────────────────────────────────────────
    camera_configs = [
        (c_dl, "CAM-DL-01-A", "Main Classroom 101 ceiling mount facing entry", "Z-DL-CR-101", "CLASSROOM", 1.0),
        (c_dl, "CAM-DL-01-B", "Hardware Lab 102 corner mount", "Z-DL-LAB-102", "LAB", 0.9),
        (c_mh, "CAM-MH-01", "Advanced Welding Workshop overhead", "Z-MH-WS-01", "WORKSHOP", 1.0),
        (c_mh, "CAM-MH-02", "Theory Classroom B", "Z-MH-CR-02", "CLASSROOM", 0.95),
        (c_ka, "CAM-KA-01", "Software Lab 301 front wall", "Z-KA-LAB-301", "LAB", 1.0),
        (c_up, "CAM-UP-01", "Electronics Repair Lab north corner", "Z-UP-LAB-01", "LAB", 0.85),
        (c_rj, "CAM-RJ-01", "Solar PV Installation Yard", "Z-RJ-YD-01", "OUTDOOR_YARD", 0.9),
        (c_tn, "CAM-TN-01", "Robotics & PLC Automation Cell", "Z-TN-ROB-01", "LAB", 1.0),
    ]

    cameras_by_code: dict[str, Camera] = {}
    zones_by_code: dict[str, Zone] = {}

    for centre, cam_code, loc_desc, zone_code, z_type, cov in camera_configs:
        existing_cam = (
            await session.execute(
                select(Camera).where(Camera.centre_id == centre.id, Camera.camera_code == cam_code)
            )
        ).scalar_one_or_none()

        if not existing_cam:
            cam = Camera(
                id=uuid.uuid4(),
                centre_id=centre.id,
                camera_code=cam_code,
                location_description=loc_desc,
                is_active=True,
            )
            session.add(cam)
            await session.flush()
        else:
            cam = existing_cam
        cameras_by_code[cam_code] = cam

        existing_zone = (
            await session.execute(
                select(Zone).where(Zone.centre_id == centre.id, Zone.zone_code == zone_code)
            )
        ).scalar_one_or_none()

        if not existing_zone:
            zone = Zone(
                id=uuid.uuid4(),
                centre_id=centre.id,
                camera_id=cam.id,
                zone_code=zone_code,
                zone_type=z_type,
                coverage_factor=cov,
                is_active=True,
            )
            session.add(zone)
            await session.flush()
        else:
            zone = existing_zone
        zones_by_code[zone_code] = zone

    # ── 3. Edge Devices ───────────────────────────────────────────────────────
    devices_data = [
        (c_dl, zones_by_code["Z-DL-CR-101"], cameras_by_code["CAM-DL-01-A"], "EDGE-DL-001", DeviceStatusEnum.ACTIVE, now - timedelta(minutes=2), {"queue_depth": 0, "bytes_sent_today": 348000, "fps": 15}),
        (c_dl, zones_by_code["Z-DL-LAB-102"], cameras_by_code["CAM-DL-01-B"], "EDGE-DL-002", DeviceStatusEnum.ACTIVE, now - timedelta(minutes=4), {"queue_depth": 3, "bytes_sent_today": 290000, "fps": 15}),
        (c_mh, zones_by_code["Z-MH-WS-01"], cameras_by_code["CAM-MH-01"], "EDGE-MH-001", DeviceStatusEnum.ACTIVE, now - timedelta(minutes=1), {"queue_depth": 0, "bytes_sent_today": 412000, "fps": 15}),
        (c_ka, zones_by_code["Z-KA-LAB-301"], cameras_by_code["CAM-KA-01"], "EDGE-KA-001", DeviceStatusEnum.ACTIVE, now - timedelta(minutes=3), {"queue_depth": 0, "bytes_sent_today": 325000, "fps": 15}),
        (c_up, zones_by_code["Z-UP-LAB-01"], cameras_by_code["CAM-UP-01"], "EDGE-UP-001", DeviceStatusEnum.OFFLINE, now - timedelta(days=3), {"queue_depth": 1420, "bytes_sent_today": 0, "backlog": True}),
        (c_rj, zones_by_code["Z-RJ-YD-01"], cameras_by_code["CAM-RJ-01"], "EDGE-RJ-001", DeviceStatusEnum.ACTIVE, now - timedelta(minutes=8), {"queue_depth": 0, "bytes_sent_today": 195000, "fps": 10}),
        (c_tn, zones_by_code["Z-TN-ROB-01"], cameras_by_code["CAM-TN-01"], "EDGE-TN-001", DeviceStatusEnum.ACTIVE, now - timedelta(minutes=2), {"queue_depth": 0, "bytes_sent_today": 275000, "fps": 15}),
    ]

    devices_by_serial: dict[str, Device] = {}
    for centre, zone, cam, serial, status_val, hb_time, telemetry in devices_data:
        existing_dev = (
            await session.execute(select(Device).where(Device.serial_number == serial))
        ).scalar_one_or_none()

        if not existing_dev:
            raw_key = hashlib.sha256(serial.encode()).digest()
            dev = Device(
                id=uuid.uuid4(),
                centre_id=centre.id,
                zone_id=zone.id,
                camera_id=cam.id,
                serial_number=serial,
                public_key=raw_key,
                public_key_b64url=hashlib.sha256(raw_key).hexdigest()[:43],
                status=status_val,
                is_active=True,
                model_version="yolov8-pramaan-v2.1",
                firmware_version="edge-fw-1.4.0",
                last_seen_at=hb_time,
                last_heartbeat_at=hb_time,
                last_telemetry=telemetry,
            )
            session.add(dev)
            await session.flush()
        else:
            dev = existing_dev
            dev.last_seen_at = hb_time
            dev.last_heartbeat_at = hb_time
            dev.last_telemetry = telemetry
            dev.status = status_val
        devices_by_serial[serial] = dev

    # ── 4. Camera Baselines & Integrity States ────────────────────────────────
    camera_integrity_configs = [
        ("CAM-DL-01-A", "STABLE", 0.88, 9, 9, "SAME_VIEW"),
        ("CAM-DL-01-B", "STABLE", 0.84, 8, 8, "SAME_VIEW"),
        ("CAM-MH-01", "SWAP_SUSPECTED", 0.19, 2, 9, "SUSPECTED_SWAP"),
        ("CAM-MH-02", "STABLE", 0.91, 10, 10, "SAME_VIEW"),
        ("CAM-KA-01", "DRIFT_SUSPECTED", 0.54, 5, 9, "VIEW_DRIFTED"),
        ("CAM-UP-01", "STABLE", 0.82, 8, 9, "SAME_VIEW"),
        ("CAM-RJ-01", "STABLE", 0.79, 7, 8, "SAME_VIEW"),
        ("CAM-TN-01", "STABLE", 0.93, 12, 12, "SAME_VIEW"),
    ]

    for cam_code, state_val, cur_sim, anchors_found, anchors_tot, classification in camera_integrity_configs:
        cam = cameras_by_code[cam_code]

        # Camera reference baseline v1
        existing_ref = (
            await session.execute(
                select(CameraReference).where(CameraReference.camera_id == cam.id, CameraReference.version == 1)
            )
        ).scalar_one_or_none()

        if not existing_ref:
            ref = CameraReference(
                id=uuid.uuid4(),
                camera_id=cam.id,
                version=1,
                s3_key=f"baselines/{cam_code}/v1_day.npz",
                lighting_tag="DAY",
                active=True,
                approved_by="officer-regional",
                phash_hex=hashlib.sha256(cam_code.encode()).hexdigest()[:16],
            )
            session.add(ref)
            await session.flush()
        else:
            ref = existing_ref

        # Camera integrity state
        existing_cis = (
            await session.execute(
                select(CameraIntegrityState).where(CameraIntegrityState.camera_id == cam.id)
            )
        ).scalar_one_or_none()

        if not existing_cis:
            cis = CameraIntegrityState(
                camera_id=cam.id,
                state=state_val,
                since=now - timedelta(hours=2 if state_val != "STABLE" else 24),
                last_transition_at=now - timedelta(hours=2 if state_val != "STABLE" else 24),
                consecutive_suspicious=4 if state_val == "SWAP_SUSPECTED" else (2 if state_val == "DRIFT_SUSPECTED" else 0),
                consecutive_stable=15 if state_val == "STABLE" else 0,
                confidence=0.92,
            )
            session.add(cis)
            await session.flush()
        else:
            existing_cis.state = state_val
            existing_cis.updated_at = now - timedelta(minutes=5)

        # Generate 12 recent SceneObservation points for timeline charts
        has_obs = (
            await session.execute(
                select(SceneObservation).where(SceneObservation.camera_id == cam.id).limit(1)
            )
        ).scalar_one_or_none()

        if not has_obs:
            for step in range(12):
                obs_time = now - timedelta(minutes=(12 - step) * 10)
                sim_noise = 0.02 * (step % 3 - 1)
                sim_point = max(0.05, min(0.98, (0.22 if state_val == "SWAP_SUSPECTED" and step > 4 else cur_sim) + sim_noise))
                so = SceneObservation(
                    camera_id=cam.id,
                    ts=obs_time,
                    source="server_verified",
                    reference_id=ref.id,
                    fused_similarity=sim_point,
                    ssim_masked=sim_point * 0.95,
                    orb_inliers=2 if (state_val == "SWAP_SUSPECTED" and step > 4) else anchors_found,
                    classification="SWAPPED" if (state_val == "SWAP_SUSPECTED" and step > 4) else ("MOVED" if state_val == "DRIFT_SUSPECTED" else "STABLE"),
                )
                session.add(so)

    # ── 5. Batches & Sessions ────────────────────────────────────────────────
    batch_configs = [
        (c_dl, "BATCH-DL-EL-01", "PMKVY-4.0", "Electrician Level 4", 30),
        (c_dl, "BATCH-DL-IT-02", "PMKVY-4.0", "IT Helpdesk Specialist", 25),
        (c_mh, "BATCH-MH-WELD-01", "DDU-GKY", "Arc & MIG Welder", 28),
        (c_ka, "BATCH-KA-JAVA-01", "PMKVY-4.0", "Junior Software Developer", 32),
        (c_up, "BATCH-UP-ELEC-01", "SANKALP", "Field Technician Electronics", 24),
        (c_rj, "BATCH-RJ-SOLAR-01", "PMKVY-4.0", "Solar Panel Installation Technician", 26),
    ]

    batches_by_code: dict[str, Batch] = {}
    for centre, b_code, scheme, trade, enrolled in batch_configs:
        existing_batch = (
            await session.execute(
                select(Batch).where(Batch.centre_id == centre.id, Batch.batch_code == b_code)
            )
        ).scalar_one_or_none()

        if not existing_batch:
            b = Batch(
                id=uuid.uuid4(),
                centre_id=centre.id,
                batch_code=b_code,
                scheme_code=scheme,
                trade_code=trade,
                enrolled_count=enrolled,
                batch_start_date=now.date() - timedelta(days=60),
                batch_end_date=now.date() + timedelta(days=30),
                is_active=True,
            )
            session.add(b)
            await session.flush()
        else:
            b = existing_batch
        batches_by_code[b_code] = b

    # Sessions
    session_configs = [
        (batches_by_code["BATCH-DL-EL-01"], zones_by_code["Z-DL-CR-101"], now - timedelta(hours=4), now - timedelta(hours=2), 28, 1, "RED", 0.14),
        (batches_by_code["BATCH-DL-EL-01"], zones_by_code["Z-DL-CR-101"], now - timedelta(days=1, hours=4), now - timedelta(days=1, hours=2), 28, 1, "RED", 0.11),
        (batches_by_code["BATCH-DL-IT-02"], zones_by_code["Z-DL-LAB-102"], now - timedelta(hours=3), now - timedelta(hours=1), 24, 1, "AMBER", 0.58),
        (batches_by_code["BATCH-MH-WELD-01"], zones_by_code["Z-MH-WS-01"], now - timedelta(hours=5), now - timedelta(hours=3), 26, 1, "GREEN", 0.92),
        (batches_by_code["BATCH-KA-JAVA-01"], zones_by_code["Z-KA-LAB-301"], now - timedelta(hours=4), now - timedelta(hours=2), 30, 1, "GREEN", 0.88),
        (batches_by_code["BATCH-UP-ELEC-01"], zones_by_code["Z-UP-LAB-01"], now - timedelta(hours=6), now - timedelta(hours=4), 22, 1, "NO_DATA", None),
    ]

    seeded_sessions: list[Session] = []
    for batch, zone, s_start, s_end, claimed, trainer, status_val, ratio in session_configs:
        existing_sess = (
            await session.execute(
                select(Session).where(
                    Session.batch_id == batch.id,
                    Session.scheduled_start == s_start,
                )
            )
        ).scalar_one_or_none()

        if not existing_sess:
            sess = Session(
                id=uuid.uuid4(),
                batch_id=batch.id,
                zone_id=zone.id,
                scheduled_start=s_start,
                scheduled_end=s_end,
                claimed_count=claimed,
                trainer_count=trainer,
                attendance_status=status_val,
                attendance_ratio=ratio,
                last_evaluated_at=s_end + timedelta(minutes=15),
            )
            session.add(sess)
            await session.flush()
            seeded_sessions.append(sess)
        else:
            seeded_sessions.append(existing_sess)

    # ── 6. Ghost Assessments ─────────────────────────────────────────────────
    b_dl = batches_by_code["BATCH-DL-EL-01"]
    existing_ga = (
        await session.execute(select(GhostAssessment).where(GhostAssessment.batch_id == b_dl.id))
    ).scalar_one_or_none()

    per_day_detail = [
        {"date": (now - timedelta(days=12 - i)).strftime("%Y-%m-%d"), "claimed": 28, "o_hat": 3.5 if i < 9 else 22.0, "ratio": 0.12 if i < 9 else 0.78, "status": "GHOST" if i < 9 else "HEALTHY", "evidence_quality": 0.92}
        for i in range(12)
    ]

    if not existing_ga:
        ga = GhostAssessment(
            id=uuid.uuid4(),
            batch_id=b_dl.id,
            centre_id=c_dl.id,
            window_start=now - timedelta(days=15),
            window_end=now,
            eligible_days=12,
            ghost_days=9,
            nodata_days=1,
            untrusted_days=0,
            ghost_score=78.0,
            state="SUSPECTED_GHOST",
            explanation={
                "persistence": 0.75,
                "magnitude": 0.82,
                "consistency": 0.60,
                "evidence_quality": 0.90,
                "cusum_score": 3.2,
                "weights": [0.35, 0.30, 0.20, 0.15],
            },
            per_day_detail=per_day_detail,
            algorithm_version="v2.0",
            computed_at=now - timedelta(hours=1),
        )
        session.add(ga)
        await session.flush()

    # Clean batch assessment for Mumbai
    b_mh = batches_by_code["BATCH-MH-WELD-01"]
    existing_ga_mh = (
        await session.execute(select(GhostAssessment).where(GhostAssessment.batch_id == b_mh.id))
    ).scalar_one_or_none()
    if not existing_ga_mh:
        ga_mh = GhostAssessment(
            id=uuid.uuid4(),
            batch_id=b_mh.id,
            centre_id=c_mh.id,
            window_start=now - timedelta(days=15),
            window_end=now,
            eligible_days=10,
            ghost_days=0,
            nodata_days=0,
            untrusted_days=0,
            ghost_score=12.0,
            state="NORMAL",
            explanation={"persistence": 0.0, "magnitude": 0.05, "consistency": 0.20, "evidence_quality": 0.98},
            per_day_detail=[{"date": (now - timedelta(days=10 - i)).strftime("%Y-%m-%d"), "claimed": 26, "o_hat": 24.5, "ratio": 0.94, "status": "HEALTHY", "evidence_quality": 0.98} for i in range(10)],
            algorithm_version="v2.0",
            computed_at=now - timedelta(hours=2),
        )
        session.add(ga_mh)
        await session.flush()

    # ── 7. Flags & Snapshots (Canonical Vocabulary) ───────────────────────────
    existing_flags = (await session.execute(select(Flag))).scalars().all()
    if not existing_flags:
        f1 = Flag(
            id=uuid.uuid4(),
            centre_id=c_dl.id,
            session_id=seeded_sessions[0].id if seeded_sessions else None,
            zone_id=zones_by_code["Z-DL-CR-101"].id,
            flag_key="FLAG-2024-DL-GHOST-01",
            flag_type="GHOST_BATCH",
            severity="HIGH",
            status="OPEN",
            rule_name="GHOST_BATCH_DETECTION",
            rule_version="1.2.0",
            description="Observed headcount ~3-4 across consecutive sessions while 28 trainees claimed present. Severe anomaly detected.",
            risk_score=0.88,
            window_start=now - timedelta(hours=4),
            window_end=now - timedelta(hours=2),
        )
        session.add(f1)
        await session.flush()

        snap1 = FlagInputSnapshot(
            id=uuid.uuid4(),
            flag_id=f1.id,
            inputs={"claimed_count": 28, "observed_p90": 4.0, "consecutive_low_sessions": 2, "feed_health": 0.95},
            thresholds={"t_green": 0.80, "t_amber": 0.50, "ghost_threshold": 0.20},
            model_version="yolov8-pramaan-v2.1",
        )
        session.add(snap1)

        f2 = Flag(
            id=uuid.uuid4(),
            centre_id=c_up.id,
            session_id=None,
            zone_id=zones_by_code["Z-UP-LAB-01"].id,
            flag_key="FLAG-2024-UP-ATTN-02",
            flag_type="ATTENDANCE_AMBER_REPEAT",
            severity="MEDIUM",
            status="UNDER_REVIEW",
            rule_name="ATTENDANCE_DISCREPANCY_REPEAT",
            rule_version="1.0.0",
            description="Repeated attendance deficit: observed 14 vs claimed 24 (58% ratio) over 3 consecutive training windows.",
            risk_score=0.58,
            window_start=now - timedelta(hours=3),
            window_end=now - timedelta(hours=1),
        )
        session.add(f2)
        await session.flush()

        snap2 = FlagInputSnapshot(
            id=uuid.uuid4(),
            flag_id=f2.id,
            inputs={"claimed_count": 24, "observed_p90": 14.0, "repeat_count": 3},
            thresholds={"t_green": 0.80, "t_amber": 0.50},
            model_version="yolov8-pramaan-v2.1",
        )
        session.add(snap2)

        f3 = Flag(
            id=uuid.uuid4(),
            centre_id=c_mh.id,
            session_id=None,
            zone_id=zones_by_code["Z-MH-WS-01"].id,
            flag_key="FLAG-2024-MH-CAM-03",
            flag_type="CAMERA_SWAP_SUSPECTED",
            severity="HIGH",
            status="OPEN",
            rule_name="CAMERA_INTEGRITY_DRIFT",
            rule_version="2.1.0",
            description="Perceptual hash shift > 35% from sanctioned baseline layout. Camera angle or optical field altered.",
            risk_score=0.74,
            window_start=now - timedelta(hours=6),
            window_end=now - timedelta(hours=5),
        )
        session.add(f3)

        f4 = Flag(
            id=uuid.uuid4(),
            centre_id=c_dl.id,
            session_id=seeded_sessions[1].id if len(seeded_sessions) > 1 else None,
            zone_id=zones_by_code["Z-DL-CR-101"].id,
            flag_key="FLAG-2024-DL-RED-04",
            flag_type="ATTENDANCE_RED",
            severity="HIGH",
            status="OPEN",
            rule_name="ATTENDANCE_RED_RATIO",
            rule_version="2.0.0",
            description="Observed ratio 0.11 < 0.50 threshold across scheduled training core window.",
            risk_score=0.89,
            window_start=now - timedelta(days=1, hours=4),
            window_end=now - timedelta(days=1, hours=2),
        )
        session.add(f4)
        await session.flush()

    # ── 8. Cases & Investigation Events ──────────────────────────────────────
    existing_case = (await session.execute(select(Case).limit(1))).scalar_one_or_none()
    if not existing_case:
        case1 = Case(
            id=uuid.uuid4(),
            centre_id=c_dl.id,
            case_number="CASE-2024-DL-001",
            status="OPEN",
            priority="HIGH",
            title="Suspicious ghost attendance pattern in Electrician Level 4 batch",
            description="Consecutive sessions show less than 15% physical occupancy while full attendance is claimed in portal.",
            assigned_to="inspector-delhi-north",
            assigned_at=now - timedelta(hours=2),
            sla_due_at=now + timedelta(days=2),
        )
        session.add(case1)
        await session.flush()

        ev1 = CaseEvent(
            id=uuid.uuid4(),
            case_id=case1.id,
            from_status=None,
            to_status="OPEN",
            actor="dev-national-admin",
            note="Auto-escalated from high-severity ghost batch flag. Assigned to Delhi North inspection unit.",
            occurred_at=now - timedelta(hours=2),
        )
        session.add(ev1)
        await session.flush()

        resp1 = TCResponse(
            id=uuid.uuid4(),
            case_id=case1.id,
            responder="tc-principal@delhiskill.in",
            response_text="Trainees were attending practical demonstration in workshop adjacent to classroom during this scheduled window.",
            submitted_at=now - timedelta(hours=1),
        )
        session.add(resp1)

    # ── 9. Threshold Profile (Active National Default) ───────────────────────
    existing_tp = (await session.execute(select(ThresholdProfile).limit(1))).scalar_one_or_none()
    if not existing_tp:
        tp = ThresholdProfile(
            id=uuid.uuid4(),
            scheme_code=None,
            state_code=None,
            version=1,
            is_active=True,
            approved_by="director-general-msde",
            approved_at=now - timedelta(days=30),
            approval_note="National baseline calibration for PMKVY 4.0 & DDU-GKY schemes.",
            t_green=0.80,
            t_amber=0.50,
            repeat_n=2,
            min_feed_health_fraction=0.50,
            extra={
                "camera_drift_threshold": 0.50,
                "camera_swap_threshold": 0.35,
                "ghost_days_threshold": 5,
                "ghost_score_alert": 60.0,
            },
        )
        session.add(tp)
        await session.flush()

    # ── 10. Audit Log with Tamper-Evident Hash Chain ──────────────────────────
    existing_audit = (await session.execute(select(AuditLog).limit(1))).scalar_one_or_none()
    if not existing_audit:
        audit_repo = AuditRepository(session)
        await audit_repo.append(
            actor="system",
            action="SYSTEM_INITIALIZE",
            resource_type="system",
            resource_id="pramaan-cluster",
            detail={"version": "1.0.0", "environment": "development", "node": "master-01"},
        )
        await audit_repo.append(
            actor="dev-national-admin",
            action="THRESHOLD_PROFILE_ACTIVATE",
            resource_type="threshold_profile",
            resource_id="v1-national-default",
            detail={"t_green": 0.80, "t_amber": 0.50, "note": "National baseline calibration"},
        )
        await audit_repo.append(
            actor="system",
            action="DEVICE_HEARTBEAT_TIMEOUT",
            resource_type="device",
            resource_id="EDGE-UP-001",
            detail={"status": "OFFLINE", "centre_code": "TC-UP-004", "offline_duration_hours": 72},
        )
        await audit_repo.append(
            actor="system",
            action="CAMERA_INTEGRITY_ALERT",
            resource_type="camera",
            resource_id="CAM-MH-01",
            detail={"state": "SWAP_SUSPECTED", "similarity": 0.19, "centre_code": "TC-MH-002"},
        )

    # ── 11. Evidence Keyframe Records ─────────────────────────────────────────
    existing_ev = (await session.execute(select(Evidence).limit(1))).scalar_one_or_none()
    if not existing_ev and seeded_sessions:
        dev_dl = devices_by_serial["EDGE-DL-001"]
        ev1 = Evidence(
            id=uuid.uuid4(),
            device_id=dev_dl.id,
            zone_id=zones_by_code["Z-DL-CR-101"].id,
            session_id=seeded_sessions[0].id,
            s3_key="evidence/redacted/2026/10/04/TC-DL-001/frame_104200.jpg",
            content_type="image/jpeg",
            size_bytes=142050,
            phash_hex="a1f4c3b2e5d60987",
            is_near_duplicate=False,
            created_at=now - timedelta(hours=3),
        )
        session.add(ev1)

    await session.commit()
    logger.info("Database seeding successfully completed with full domain entities!")
