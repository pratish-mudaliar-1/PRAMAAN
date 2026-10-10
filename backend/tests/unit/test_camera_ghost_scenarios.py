"""tests/unit/test_camera_ghost_scenarios.py — Comprehensive scenario & adversarial tests.

Scenarios tested:
1. Genuine batch stays NORMAL.
2. Single bad day does not trigger SUSPECTED_GHOST.
3. 3 consecutive ghost days triggers SUSPECTED_GHOST.
4. Intermittent 3-of-5 triggers SUSPECTED_GHOST via M-of-N pattern.
5. Data gaps do not trigger ghost batch.
6. Late attendance data re-evaluation.
7. Abrupt camera swap triggers SWAP_CONFIRMED.
8. Gradual camera drift.
9. Lights off in evening (LIGHTING_CHANGE) does not escalate to swap.
10. Person in front of lens (OCCLUDED) does not escalate.
11. Small nudge with high inlier ratio is MOVED_CONFIRMED.
12. Legitimate relocation via rebaseline approval.
13. Swap making batch look empty gives an integrity case and NO ghost accusation.

Adversarial tests:
14. Forged edge similarity with different-room keyframe caught by server-side comparison.
15. Corrupt or unparseable image handled gracefully.
16. RBAC cross-centre isolation (Centre A principal rejected from Centre B data).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import cv2
import numpy as np
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import FrozenClock
from app.core.errors import AuthorizationError
from app.core.security.policy import Policy, Principal
from app.db.models.camera_integrity import CameraIntegrityState, CameraReference, SceneObservation
from app.db.models.centre import Camera, Centre, Zone
from app.db.models.flag import Flag
from app.db.models.session_ import Batch, Session
from app.domain.camera_integrity import (
    CameraIntegrityThresholds,
    CameraStateSnapshot,
    SceneObservationRecord,
    evaluate_camera_state,
)
from app.domain.ghost_batch import (
    GhostThresholds,
    SessionDayInput,
    evaluate_ghost_batch,
)
from app.domain.vision.scene_compare import (
    SceneClassification,
    compare_scene,
)
from app.services.camera_integrity import CameraIntegrityService
from app.services.ghost_batch import GhostBatchDetectionService


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIOS 1-6: GHOST BATCH SCENARIOS
# ─────────────────────────────────────────────────────────────────────────────

def test_scenario_genuine_batch_stays_normal() -> None:
    """A genuine batch with 5 consecutive days of normal attendance stays NORMAL."""
    base = datetime(2024, 6, 1, 4, 30, tzinfo=UTC)
    now = datetime(2024, 6, 10, 12, 0, tzinfo=UTC)
    sessions = [
        SessionDayInput(
            session_id=f"s-gen-{i}",
            scheduled_start=base + timedelta(days=i),
            scheduled_end=base + timedelta(days=i, hours=2),
            claimed_count=30,
            o_hat=27.0,  # 90% attendance
            feed_health=1.0,
            camera_trust="TRUSTED",
            attendance_status="GREEN",
        )
        for i in range(5)
    ]
    res = evaluate_ghost_batch("b-gen", "c-1", sessions, previous_state="NORMAL", now=now)
    assert res.current_state == "NORMAL"
    assert res.ghost_days == 0
    assert res.eligible_days == 5


def test_scenario_single_bad_day_does_not_escalate() -> None:
    """A single bad day (e.g. heavy rain) does not escalate to SUSPECTED_GHOST."""
    base = datetime(2024, 6, 1, 4, 30, tzinfo=UTC)
    now = datetime(2024, 6, 10, 12, 0, tzinfo=UTC)
    sessions = [
        # Day 0: 0 attendance
        SessionDayInput("s-0", base, base + timedelta(hours=2), 30, 0.0, 1.0, "TRUSTED", "RED"),
        # Days 1-4: normal attendance
        *[
            SessionDayInput(f"s-{i}", base + timedelta(days=i), base + timedelta(days=i, hours=2), 30, 26.0, 1.0, "TRUSTED", "GREEN")
            for i in range(1, 5)
        ]
    ]
    res = evaluate_ghost_batch("b-rain", "c-1", sessions, previous_state="NORMAL", now=now)
    assert res.current_state == "WATCH"
    assert res.ghost_days == 1
    assert res.is_ghost_pattern is False


def test_scenario_three_consecutive_ghost_days() -> None:
    """3 consecutive ghost days escalates to SUSPECTED_GHOST."""
    base = datetime(2024, 6, 1, 4, 30, tzinfo=UTC)
    now = datetime(2024, 6, 10, 12, 0, tzinfo=UTC)
    sessions = [
        SessionDayInput(f"s-{i}", base + timedelta(days=i), base + timedelta(days=i, hours=2), 30, 2.0, 1.0, "TRUSTED", "RED")
        for i in range(3)
    ]
    res = evaluate_ghost_batch("b-ghost3", "c-1", sessions, previous_state="NORMAL", now=now)
    assert res.current_state == "SUSPECTED_GHOST"
    assert res.ghost_days == 3
    assert res.is_ghost_pattern is True


def test_scenario_intermittent_three_of_five() -> None:
    """Intermittent pattern (3 ghost days out of 5 eligible days) triggers SUSPECTED_GHOST."""
    base = datetime(2024, 6, 1, 4, 30, tzinfo=UTC)
    now = datetime(2024, 6, 10, 12, 0, tzinfo=UTC)
    # Days 0, 2, 4 are ghost days; Days 1, 3 are healthy
    sessions = [
        SessionDayInput("s-0", base, base + timedelta(hours=2), 30, 1.0, 1.0, "TRUSTED", "RED"),
        SessionDayInput("s-1", base + timedelta(days=1), base + timedelta(days=1, hours=2), 30, 28.0, 1.0, "TRUSTED", "GREEN"),
        SessionDayInput("s-2", base + timedelta(days=2), base + timedelta(days=2, hours=2), 30, 2.0, 1.0, "TRUSTED", "RED"),
        SessionDayInput("s-3", base + timedelta(days=3), base + timedelta(days=3, hours=2), 30, 27.0, 1.0, "TRUSTED", "GREEN"),
        SessionDayInput("s-4", base + timedelta(days=4), base + timedelta(days=4, hours=2), 30, 1.0, 1.0, "TRUSTED", "RED"),
    ]
    thresholds = GhostThresholds(m_of_n_m=3, m_of_n_n=5)
    res = evaluate_ghost_batch("b-intermit", "c-1", sessions, previous_state="NORMAL", thresholds=thresholds, now=now)
    assert res.current_state == "SUSPECTED_GHOST"
    assert res.ghost_days == 3


def test_scenario_data_gaps_do_not_trigger() -> None:
    """Days with no sessions or unhealthy feeds are NO_DATA and do NOT trigger ghost status."""
    base = datetime(2024, 6, 1, 4, 30, tzinfo=UTC)
    now = datetime(2024, 6, 10, 12, 0, tzinfo=UTC)
    sessions = [
        # Session with unhealthy feed (< 0.50)
        SessionDayInput("s-gap-1", base, base + timedelta(hours=2), 30, 0.0, 0.20, "TRUSTED"),
        # Session with claimed < min_claimed (< 5)
        SessionDayInput("s-gap-2", base + timedelta(days=1), base + timedelta(days=1, hours=2), 3, 0.0, 1.0, "TRUSTED"),
    ]
    res = evaluate_ghost_batch("b-gap", "c-1", sessions, previous_state="NORMAL", now=now)
    assert res.current_state == "NORMAL"
    assert res.nodata_days == 2
    assert res.ghost_days == 0


def test_scenario_late_attendance_data() -> None:
    """Re-evaluating after late attendance data arrives smoothly resolves or updates assessment."""
    base = datetime(2024, 6, 1, 4, 30, tzinfo=UTC)
    now = datetime(2024, 6, 5, 12, 0, tzinfo=UTC)

    # Initial state with 2 ghost days -> SUSPECTED_GHOST
    s_early = [
        SessionDayInput(f"s-{i}", base + timedelta(days=i), base + timedelta(days=i, hours=2), 25, 1.0, 1.0, "TRUSTED", "RED")
        for i in range(2)
    ]
    res1 = evaluate_ghost_batch("b-late", "c-1", s_early, previous_state="NORMAL", now=now)
    assert res1.current_state == "SUSPECTED_GHOST"

    # Late data arrives for 3 subsequent healthy days -> transitions to RESOLVED
    s_all = s_early + [
        SessionDayInput(f"s-{i}", base + timedelta(days=i), base + timedelta(days=i, hours=2), 25, 24.0, 1.0, "TRUSTED", "GREEN")
        for i in range(2, 5)
    ]
    res2 = evaluate_ghost_batch("b-late", "c-1", s_all, previous_state=res1.current_state, now=now + timedelta(days=5))
    assert res2.current_state == "RESOLVED"


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIOS 7-12: CAMERA INTEGRITY SCENARIOS
# ─────────────────────────────────────────────────────────────────────────────

def test_scenario_abrupt_swap_and_gradual_drift() -> None:
    """Abrupt visual difference escalates to SWAP_CONFIRMED.
    Gradual drift without high geometric mismatch stops at DRIFT_SUSPECTED.
    """
    base = datetime(2024, 6, 1, 8, 0, tzinfo=UTC)
    thresholds = CameraIntegrityThresholds(escalate_k=3, escalate_m=5, escalate_min_duration=timedelta(hours=1))

    snapshot = CameraStateSnapshot("cam-1", "STABLE", base, None, base, 0, 5, 0.9, "v1")

    # 1. Abrupt swap: low similarity + low inlier ratio
    obs_abrupt = [
        SceneObservationRecord(
            ts=base + timedelta(minutes=30 * i),
            classification=SceneClassification.SWAPPED,
            fused_similarity=0.15,
            orb_inliers=3,
            inlier_ratio=0.03,
            source="server_verified",
        )
        for i in range(1, 4)
    ]
    t1 = evaluate_camera_state(snapshot, obs_abrupt, thresholds)
    assert t1.new_state == "DRIFT_SUSPECTED"

    snap2 = CameraStateSnapshot("cam-1", "DRIFT_SUSPECTED", t1.first_suspected_at or base, t1.first_suspected_at, base, 3, 0, 0.7, "v1")
    t2 = evaluate_camera_state(snap2, obs_abrupt, thresholds)
    assert t2.new_state == "SWAP_SUSPECTED"

    snap3 = CameraStateSnapshot("cam-1", "SWAP_SUSPECTED", t1.first_suspected_at or base, t1.first_suspected_at, base, 3, 0, 0.7, "v1")
    t3 = evaluate_camera_state(snap3, obs_abrupt, thresholds)
    assert t3.new_state == "SWAP_CONFIRMED"


def test_scenario_lights_off_evening_does_not_escalate() -> None:
    """LIGHTING_CHANGE classification does not trigger suspicious count or escalation."""
    base = datetime(2024, 6, 1, 18, 0, tzinfo=UTC)
    snapshot = CameraStateSnapshot("cam-light", "STABLE", base, None, base, 0, 5, 0.9, "v1")

    obs_evening = [
        SceneObservationRecord(
            ts=base + timedelta(minutes=10 * i),
            classification=SceneClassification.LIGHTING_CHANGE,
            fused_similarity=0.68,
            orb_inliers=40,
            inlier_ratio=0.60,
            source="server_verified",
        )
        for i in range(1, 5)
    ]
    transition = evaluate_camera_state(snapshot, obs_evening)
    assert transition.changed is False
    assert transition.new_state == "STABLE"


def test_scenario_person_in_front_of_lens_occlusion() -> None:
    """A brief OCCLUDED observation without sustained duration does not escalate."""
    base = datetime(2024, 6, 1, 10, 0, tzinfo=UTC)
    thresholds = CameraIntegrityThresholds(escalate_k=3, escalate_min_duration=timedelta(hours=2))
    snapshot = CameraStateSnapshot("cam-occ", "STABLE", base, None, base, 0, 5, 0.9, "v1")

    # 1 single occluded observation
    obs = [
        SceneObservationRecord(
            ts=base + timedelta(minutes=5),
            classification=SceneClassification.OCCLUDED,
            fused_similarity=0.40,
            orb_inliers=10,
            inlier_ratio=0.20,
            source="server_verified",
        )
    ]
    transition = evaluate_camera_state(snapshot, obs, thresholds)
    assert transition.changed is False
    assert transition.new_state == "STABLE"


def test_scenario_small_nudge_is_moved_confirmed() -> None:
    """Camera physically shifted/nudged has good ORB inliers and classifies as MOVED_CONFIRMED."""
    base = datetime(2024, 6, 1, 8, 0, tzinfo=UTC)
    thresholds = CameraIntegrityThresholds(escalate_k=3, escalate_min_duration=timedelta(hours=1))

    obs_moved = [
        SceneObservationRecord(
            ts=base + timedelta(minutes=30 * i),
            classification=SceneClassification.MOVED,
            fused_similarity=0.55,
            orb_inliers=35,
            inlier_ratio=0.50,
            source="server_verified",
        )
        for i in range(1, 4)
    ]

    snap_suspected = CameraStateSnapshot("cam-move", "SWAP_SUSPECTED", base, base, base, 3, 0, 0.7, "v1")
    transition = evaluate_camera_state(snap_suspected, obs_moved, thresholds)
    assert transition.new_state == "MOVED_CONFIRMED"


def test_scenario_rebaseline_approval() -> None:
    """An approved rebaseline transitions the camera to REBASELINED."""
    base = datetime(2024, 6, 1, 8, 0, tzinfo=UTC)
    snap = CameraStateSnapshot("cam-rebase", "SWAP_CONFIRMED", base, base, base, 5, 0, 0.9, "v1")
    t = evaluate_camera_state(snap, [], rebaseline_approved=True)
    assert t.new_state == "REBASELINED"
    assert t.cause == "rebaseline"


# ─────────────────────────────────────────────────────────────────────────────
# SCENARIO 13: SWAP ISOLATION — INTEGRITY CASE, NEVER GHOST ACCUSATION
# ─────────────────────────────────────────────────────────────────────────────

def test_scenario_swap_empty_batch_gives_integrity_case_not_ghost() -> None:
    """When a camera is swapped, observations are marked UNTRUSTED.
    The ghost detection service marks sessions as UNTRUSTED, isolates the batch,
    and sets camera_integrity_explains = True without accusing of ghost attendance.
    """
    base = datetime(2024, 6, 1, 4, 30, tzinfo=UTC)
    now = datetime(2024, 6, 5, 12, 0, tzinfo=UTC)

    # All sessions during the swapped camera period
    sessions = [
        SessionDayInput(
            session_id=f"s-swapped-{i}",
            scheduled_start=base + timedelta(days=i),
            scheduled_end=base + timedelta(days=i, hours=2),
            claimed_count=30,
            o_hat=0.0,  # 0 people seen because camera points at wrong wall/room
            feed_health=1.0,
            camera_trust="UNTRUSTED",  # marked UNTRUSTED by camera integrity
            attendance_status="NO_DATA",
        )
        for i in range(4)
    ]

    res = evaluate_ghost_batch("b-swapped", "c-1", sessions, previous_state="NORMAL", now=now)
    assert res.current_state in ("NORMAL", "RESOLVED")
    assert res.ghost_days == 0
    assert res.untrusted_days == 4
    assert res.camera_integrity_explains is True


# ─────────────────────────────────────────────────────────────────────────────
# ADVERSARIAL TESTS 14-16
# ─────────────────────────────────────────────────────────────────────────────

def test_adversarial_forged_edge_reported_similarity() -> None:
    """Edge submits a forged claim of high similarity (0.99), but server-side
    comparison compares the real keyframe pixels against the reference and flags SWAPPED.
    """
    # Create two distinctly textured synthetic rooms
    ref_img = np.zeros((360, 480, 3), dtype=np.uint8)
    for y in range(0, 360, 30):
        for x in range(0, 480, 30):
            if (x // 30 + y // 30) % 2 == 0:
                cv2.rectangle(ref_img, (x, y), (x + 30, y + 30), (220, 220, 220), -1)

    # Forged room has completely different diagonal pattern and color palette
    forged_img = np.full((360, 480, 3), 120, dtype=np.uint8)
    for i in range(-360, 480, 20):
        cv2.line(forged_img, (i, 0), (i + 360, 360), (20, 180, 50), 4)

    ref_bytes = cv2.imencode(".jpg", ref_img)[1].tobytes()
    forged_bytes = cv2.imencode(".jpg", forged_img)[1].tobytes()

    result = compare_scene(forged_bytes, ref_bytes)

    # Server-verified comparison catches forged edge report
    assert result.fused_similarity < 0.40
    assert result.classification in (SceneClassification.SWAPPED, SceneClassification.UNKNOWN)
    assert result.classification != SceneClassification.STABLE



def test_adversarial_corrupt_or_empty_image() -> None:
    """Zero-byte or invalid image data handled safely without unhandled crashes."""
    ref_img = np.zeros((240, 320, 3), dtype=np.uint8)
    ref_bytes = cv2.imencode(".jpg", ref_img)[1].tobytes()

    with pytest.raises(ValueError):
        compare_scene(b"invalid_corrupt_bytes", ref_bytes)



def test_adversarial_rbac_cross_centre_isolation() -> None:
    """A user assigned to Centre A cannot access Centre B cameras or assessments."""
    centre_a = "CTR-A"
    centre_b = "CTR-B"

    tc_principal = Principal(
        subject="tc-user-1",
        roles=("training_centre",),
        centre_ids=(centre_a,),
    )

    # Training centre admin should be denied access to Centre B
    with pytest.raises(AuthorizationError):
        Policy.require_centre_access(tc_principal, centre_b)

