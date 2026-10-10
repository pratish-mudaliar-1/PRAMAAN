"""tests/unit/test_camera_swap_and_ghost_unit.py — Unit tests for camera swap and ghost batch domain logic.

Tests all threshold boundaries, state transitions, K-of-M, eligibility gating,
IST day boundaries, and change-point estimation.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.camera_integrity import (
    CameraIntegrityThresholds,
    CameraStateSnapshot,
    SceneObservationRecord,
    _count_independent_signals,
    _estimate_change_point,
    _is_suspicious,
    evaluate_camera_state,
)
from app.domain.ghost_batch import (
    DayEvaluation,
    GhostState,
    GhostThresholds,
    SessionDayInput,
    compute_ghost_score,
    evaluate_ghost_batch,
    evaluate_session_day,
    to_ist_date,
)
from app.domain.vision.scene_compare import SceneClassification


# ─────────────────────────────────────────────────────────────────────────────
# 1. THRESHOLD BOUNDARIES & ELIGIBILITY GATING
# ─────────────────────────────────────────────────────────────────────────────

def test_ghost_ratio_threshold_boundary() -> None:
    """Boundary at ghost_ratio_threshold (default 0.20):
    ratio < 0.20 is GHOST, ratio >= 0.20 is HEALTHY.
    """
    thresholds = GhostThresholds(ghost_ratio_threshold=0.20, min_claimed_attendance=10)
    start_utc = datetime(2024, 6, 15, 4, 30, tzinfo=UTC)  # 10:00 IST
    end_utc = datetime(2024, 6, 15, 6, 30, tzinfo=UTC)
    now = datetime(2024, 6, 15, 7, 0, tzinfo=UTC)

    # 1. Below threshold: 1.9 / 10 = 0.19 (< 0.20) -> GHOST
    session_ghost = SessionDayInput(
        session_id="s-ghost",
        scheduled_start=start_utc,
        scheduled_end=end_utc,
        claimed_count=10,
        o_hat=1.9,
        feed_health=1.0,
        camera_trust="TRUSTED",
        attendance_status="RED",
    )
    eval_ghost = evaluate_session_day("2024-06-15", [session_ghost], thresholds, now)
    assert eval_ghost.status == "GHOST"
    assert eval_ghost.ratio == pytest.approx(0.19)

    # 2. Exactly at threshold: 2.0 / 10 = 0.20 (>= 0.20) -> HEALTHY
    session_healthy = SessionDayInput(
        session_id="s-healthy",
        scheduled_start=start_utc,
        scheduled_end=end_utc,
        claimed_count=10,
        o_hat=2.0,
        feed_health=1.0,
        camera_trust="TRUSTED",
        attendance_status="AMBER",
    )
    eval_healthy = evaluate_session_day("2024-06-15", [session_healthy], thresholds, now)
    assert eval_healthy.status == "HEALTHY"
    assert eval_healthy.ratio == pytest.approx(0.20)


def test_ghost_min_claimed_attendance_boundary() -> None:
    """Boundary at min_claimed_attendance (default 5):
    claimed < 5 is ineligible (NO_DATA), claimed >= 5 is eligible.
    """
    thresholds = GhostThresholds(min_claimed_attendance=5)
    start_utc = datetime(2024, 6, 15, 4, 30, tzinfo=UTC)
    end_utc = datetime(2024, 6, 15, 6, 30, tzinfo=UTC)
    now = datetime(2024, 6, 15, 7, 0, tzinfo=UTC)

    # claimed = 4 (< 5) -> Ineligible -> NO_DATA
    s_low = SessionDayInput(
        session_id="s-low",
        scheduled_start=start_utc,
        scheduled_end=end_utc,
        claimed_count=4,
        o_hat=0.0,
        feed_health=1.0,
        camera_trust="TRUSTED",
    )
    eval_low = evaluate_session_day("2024-06-15", [s_low], thresholds, now)
    assert eval_low.status == "NO_DATA"
    assert "below minimum" in eval_low.reason

    # claimed = 5 (>= 5) -> Eligible -> GHOST
    s_min = SessionDayInput(
        session_id="s-min",
        scheduled_start=start_utc,
        scheduled_end=end_utc,
        claimed_count=5,
        o_hat=0.0,
        feed_health=1.0,
        camera_trust="TRUSTED",
    )
    eval_min = evaluate_session_day("2024-06-15", [s_min], thresholds, now)
    assert eval_min.status == "GHOST"


def test_ghost_feed_health_boundary() -> None:
    """Feed health below min_feed_health (default 0.50) is excluded from denominator."""
    thresholds = GhostThresholds(min_feed_health=0.50)
    start_utc = datetime(2024, 6, 15, 4, 30, tzinfo=UTC)
    end_utc = datetime(2024, 6, 15, 6, 30, tzinfo=UTC)
    now = datetime(2024, 6, 15, 7, 0, tzinfo=UTC)

    # feed_health = 0.49 (< 0.50) -> NO_DATA
    s_unhealthy = SessionDayInput(
        session_id="s-unhealthy",
        scheduled_start=start_utc,
        scheduled_end=end_utc,
        claimed_count=20,
        o_hat=0.0,
        feed_health=0.49,
        camera_trust="TRUSTED",
    )
    eval_unhealthy = evaluate_session_day("2024-06-15", [s_unhealthy], thresholds, now)
    assert eval_unhealthy.status == "NO_DATA"
    assert "Insufficient feed health" in eval_unhealthy.reason


def test_ghost_untrusted_camera_isolation() -> None:
    """An UNTRUSTED camera day is marked as UNTRUSTED, never GHOST."""
    thresholds = GhostThresholds()
    start_utc = datetime(2024, 6, 15, 4, 30, tzinfo=UTC)
    end_utc = datetime(2024, 6, 15, 6, 30, tzinfo=UTC)
    now = datetime(2024, 6, 15, 7, 0, tzinfo=UTC)

    s_untrusted = SessionDayInput(
        session_id="s-untrusted",
        scheduled_start=start_utc,
        scheduled_end=end_utc,
        claimed_count=30,
        o_hat=0.0,  # 0 observed
        feed_health=1.0,
        camera_trust="UNTRUSTED",
    )
    eval_untrusted = evaluate_session_day("2024-06-15", [s_untrusted], thresholds, now)
    assert eval_untrusted.status == "UNTRUSTED"
    assert "UNTRUSTED" in eval_untrusted.reason


# ─────────────────────────────────────────────────────────────────────────────
# 2. IST DAY BOUNDARY CALCULATION
# ─────────────────────────────────────────────────────────────────────────────

def test_to_ist_date_boundaries() -> None:
    """IST is UTC+05:30.
    2024-06-15 18:29:59 UTC -> 2024-06-15 23:59:59 IST (Same day)
    2024-06-15 18:30:00 UTC -> 2024-06-16 00:00:00 IST (Next day)
    """
    dt_before_midnight = datetime(2024, 6, 15, 18, 29, 59, tzinfo=UTC)
    dt_at_midnight = datetime(2024, 6, 15, 18, 30, 0, tzinfo=UTC)
    dt_morning = datetime(2024, 6, 16, 4, 0, 0, tzinfo=UTC)

    assert to_ist_date(dt_before_midnight) == "2024-06-15"
    assert to_ist_date(dt_at_midnight) == "2024-06-16"
    assert to_ist_date(dt_morning) == "2024-06-16"

    # Naive timestamp treated as UTC
    dt_naive = datetime(2024, 6, 15, 18, 30, 0)
    assert to_ist_date(dt_naive) == "2024-06-16"


# ─────────────────────────────────────────────────────────────────────────────
# 3. CAMERA INTEGRITY: STATE MACHINE & THRESHOLDS
# ─────────────────────────────────────────────────────────────────────────────

def test_camera_state_transition_stable_to_drift_to_swap() -> None:
    """STABLE -> DRIFT_SUSPECTED -> SWAP_SUSPECTED -> SWAP_CONFIRMED.
    Requires sustained low similarity and two independent signals for SWAP_CONFIRMED.
    """
    base_time = datetime(2024, 6, 15, 8, 0, 0, tzinfo=UTC)
    t = CameraIntegrityThresholds(
        escalate_k=3,
        escalate_m=5,
        escalate_min_duration=timedelta(hours=1),
        require_two_signals=True,
    )

    snapshot = CameraStateSnapshot(
        camera_id="cam-1",
        state="STABLE",
        since=base_time,
        first_suspected_at=None,
        last_transition_at=base_time,
        consecutive_suspicious=0,
        consecutive_stable=5,
        confidence=0.9,
        algorithm_version="v1",
    )

    # 1. Add 3 suspicious observations spanning > 1 hour
    obs_list = [
        SceneObservationRecord(
            ts=base_time + timedelta(minutes=10),
            classification=SceneClassification.SWAPPED,
            fused_similarity=0.20,
            orb_inliers=5,
            inlier_ratio=0.05,
            source="server_verified",
        ),
        SceneObservationRecord(
            ts=base_time + timedelta(minutes=40),
            classification=SceneClassification.SWAPPED,
            fused_similarity=0.18,
            orb_inliers=4,
            inlier_ratio=0.04,
            source="server_verified",
        ),
        SceneObservationRecord(
            ts=base_time + timedelta(minutes=70),
            classification=SceneClassification.SWAPPED,
            fused_similarity=0.15,
            orb_inliers=3,
            inlier_ratio=0.03,
            source="server_verified",
        ),
    ]

    transition = evaluate_camera_state(snapshot, obs_list, thresholds=t)
    assert transition.changed is True
    assert transition.new_state == "DRIFT_SUSPECTED"
    assert transition.first_suspected_at is not None

    # 2. DRIFT_SUSPECTED -> SWAP_SUSPECTED
    snapshot_drift = CameraStateSnapshot(
        camera_id="cam-1",
        state="DRIFT_SUSPECTED",
        since=base_time + timedelta(minutes=70),
        first_suspected_at=transition.first_suspected_at,
        last_transition_at=base_time + timedelta(minutes=70),
        consecutive_suspicious=3,
        consecutive_stable=0,
        confidence=0.7,
        algorithm_version="v1",
    )

    transition2 = evaluate_camera_state(snapshot_drift, obs_list, thresholds=t)
    assert transition2.changed is True
    assert transition2.new_state == "SWAP_SUSPECTED"

    # 3. SWAP_SUSPECTED -> SWAP_CONFIRMED (with 2 independent server_verified signals)
    snapshot_swap_susp = CameraStateSnapshot(
        camera_id="cam-1",
        state="SWAP_SUSPECTED",
        since=base_time + timedelta(minutes=70),
        first_suspected_at=transition.first_suspected_at,
        last_transition_at=base_time + timedelta(minutes=70),
        consecutive_suspicious=3,
        consecutive_stable=0,
        confidence=0.7,
        algorithm_version="v1",
    )

    transition3 = evaluate_camera_state(snapshot_swap_susp, obs_list, thresholds=t)
    assert transition3.changed is True
    assert transition3.new_state == "SWAP_CONFIRMED"


def test_camera_state_recovery_with_hysteresis() -> None:
    """DRIFT_SUSPECTED recovers to STABLE after recovery_k_stable consecutive stable frames."""
    base_time = datetime(2024, 6, 15, 8, 0, 0, tzinfo=UTC)
    t = CameraIntegrityThresholds(recovery_k_stable=3)

    snapshot = CameraStateSnapshot(
        camera_id="cam-1",
        state="DRIFT_SUSPECTED",
        since=base_time,
        first_suspected_at=base_time,
        last_transition_at=base_time,
        consecutive_suspicious=3,
        consecutive_stable=0,
        confidence=0.6,
        algorithm_version="v1",
    )

    # 3 consecutive stable observations
    stable_obs = [
        SceneObservationRecord(
            ts=base_time + timedelta(minutes=10 * i),
            classification=SceneClassification.STABLE,
            fused_similarity=0.92,
            orb_inliers=70,
            inlier_ratio=0.85,
            source="server_verified",
        )
        for i in range(1, 4)
    ]

    transition = evaluate_camera_state(snapshot, stable_obs, thresholds=t)
    assert transition.changed is True
    assert transition.new_state == "STABLE"
    assert transition.new_consecutive_stable == 3


def test_camera_rebaseline_transition() -> None:
    """When rebaseline_approved is True, state transitions to REBASELINED."""
    base_time = datetime(2024, 6, 15, 8, 0, 0, tzinfo=UTC)
    snapshot = CameraStateSnapshot(
        camera_id="cam-1",
        state="SWAP_CONFIRMED",
        since=base_time,
        first_suspected_at=base_time,
        last_transition_at=base_time,
        consecutive_suspicious=5,
        consecutive_stable=0,
        confidence=0.9,
        algorithm_version="v1",
    )

    transition = evaluate_camera_state(snapshot, [], rebaseline_approved=True)
    assert transition.changed is True
    assert transition.new_state == "REBASELINED"
    assert transition.cause == "rebaseline"


# ─────────────────────────────────────────────────────────────────────────────
# 4. CHANGE-POINT ESTIMATION & CORROBORATION
# ─────────────────────────────────────────────────────────────────────────────

def test_change_point_midpoint_estimation() -> None:
    """Change-point is estimated at the midpoint between last stable observation
    and first suspicious observation.
    """
    t0 = datetime(2024, 6, 15, 10, 0, 0, tzinfo=UTC)
    t_stable = datetime(2024, 6, 15, 10, 30, 0, tzinfo=UTC)   # Last stable
    t_suspicious = datetime(2024, 6, 15, 11, 30, 0, tzinfo=UTC) # First suspicious (+60m)

    obs = [
        SceneObservationRecord(
            ts=t0,
            classification=SceneClassification.STABLE,
            fused_similarity=0.95,
            orb_inliers=80,
            inlier_ratio=0.9,
            source="server_verified",
        ),
        SceneObservationRecord(
            ts=t_stable,
            classification=SceneClassification.STABLE,
            fused_similarity=0.92,
            orb_inliers=75,
            inlier_ratio=0.85,
            source="server_verified",
        ),
        SceneObservationRecord(
            ts=t_suspicious,
            classification=SceneClassification.SWAPPED,
            fused_similarity=0.10,
            orb_inliers=2,
            inlier_ratio=0.02,
            source="server_verified",
        ),
    ]

    cp = _estimate_change_point(obs, None)
    assert cp is not None
    # Midpoint between 10:30 and 11:30 is 11:00
    expected_midpoint = datetime(2024, 6, 15, 11, 0, 0, tzinfo=UTC)
    assert cp == expected_midpoint


def test_corroboration_two_independent_signals() -> None:
    """_count_independent_signals identifies 2 signals when either:
    1) >= 2 server_verified keyframes are present, or
    2) edge_reported and server_verified sources are both present.
    """
    t0 = datetime(2024, 6, 15, 10, 0, 0, tzinfo=UTC)
    obs_server_1 = SceneObservationRecord(
        ts=t0,
        classification=SceneClassification.SWAPPED,
        fused_similarity=0.1,
        orb_inliers=1,
        inlier_ratio=0.01,
        source="server_verified",
    )
    obs_server_2 = SceneObservationRecord(
        ts=t0 + timedelta(minutes=5),
        classification=SceneClassification.SWAPPED,
        fused_similarity=0.1,
        orb_inliers=1,
        inlier_ratio=0.01,
        source="server_verified",
    )
    obs_edge = SceneObservationRecord(
        ts=t0 + timedelta(minutes=10),
        classification=SceneClassification.SWAPPED,
        fused_similarity=0.1,
        orb_inliers=1,
        inlier_ratio=0.01,
        source="edge_reported",
    )

    # 1 server + 1 edge -> 2 independent signals
    assert _count_independent_signals([obs_server_1, obs_edge]) == 2
    # 2 server verifications -> 2 independent signals
    assert _count_independent_signals([obs_server_1, obs_server_2]) == 2
    # 1 edge only -> 1 signal
    assert _count_independent_signals([obs_edge]) == 1


# ─────────────────────────────────────────────────────────────────────────────
# 5. GHOST BATCH: STATE MACHINE & PATTERN RULES
# ─────────────────────────────────────────────────────────────────────────────

def test_ghost_batch_state_machine_escalation_and_recovery() -> None:
    """NORMAL -> SUSPECTED_GHOST (2 consecutive ghost days) -> RESOLVED (3 healthy days)."""
    thresholds = GhostThresholds(l_consecutive=2, recovery_r_consecutive=3, min_eligible_days=2)
    start_utc = datetime(2024, 6, 15, 4, 30, tzinfo=UTC)
    eval_now = datetime(2024, 6, 20, 12, 0, tzinfo=UTC)

    # Day 1 & Day 2: 2 ghost sessions (1 per day)
    s1 = SessionDayInput(
        session_id="s1",
        scheduled_start=start_utc,
        scheduled_end=start_utc + timedelta(hours=2),
        claimed_count=25,
        o_hat=1.0,  # 1/25 = 0.04 (< 0.20)
        feed_health=1.0,
        camera_trust="TRUSTED",
        attendance_status="RED",
    )
    s2 = SessionDayInput(
        session_id="s2",
        scheduled_start=start_utc + timedelta(days=1),
        scheduled_end=start_utc + timedelta(days=1, hours=2),
        claimed_count=25,
        o_hat=2.0,  # 2/25 = 0.08 (< 0.20)
        feed_health=1.0,
        camera_trust="TRUSTED",
        attendance_status="RED",
    )

    res = evaluate_ghost_batch(
        batch_id="b-1",
        centre_id="c-1",
        sessions=[s1, s2],
        previous_state="NORMAL",
        thresholds=thresholds,
        now=eval_now,
    )
    assert res.current_state == "SUSPECTED_GHOST"
    assert res.transitioned is True
    assert res.ghost_days == 2

    # Days 3, 4, 5: 3 consecutive healthy days
    s3 = SessionDayInput(
        session_id="s3",
        scheduled_start=start_utc + timedelta(days=2),
        scheduled_end=start_utc + timedelta(days=2, hours=2),
        claimed_count=25,
        o_hat=22.0,
        feed_health=1.0,
        camera_trust="TRUSTED",
        attendance_status="GREEN",
    )
    s4 = SessionDayInput(
        session_id="s4",
        scheduled_start=start_utc + timedelta(days=3),
        scheduled_end=start_utc + timedelta(days=3, hours=2),
        claimed_count=25,
        o_hat=23.0,
        feed_health=1.0,
        camera_trust="TRUSTED",
        attendance_status="GREEN",
    )
    s5 = SessionDayInput(
        session_id="s5",
        scheduled_start=start_utc + timedelta(days=4),
        scheduled_end=start_utc + timedelta(days=4, hours=2),
        claimed_count=25,
        o_hat=24.0,
        feed_health=1.0,
        camera_trust="TRUSTED",
        attendance_status="GREEN",
    )

    res_recovery = evaluate_ghost_batch(
        batch_id="b-1",
        centre_id="c-1",
        sessions=[s1, s2, s3, s4, s5],
        previous_state="SUSPECTED_GHOST",
        thresholds=thresholds,
        now=eval_now,
    )
    assert res_recovery.current_state == "RESOLVED"
    assert res_recovery.transitioned is True
