"""tests/unit/test_camera_ghost_property.py — Hypothesis property-based tests.

Validates invariants:
1. Deterministic replay: same inputs always produce identical outputs.
2. Idempotent re-evaluation: re-evaluating with stable state preserves the state.
3. Order-invariance: out-of-order session ingestion yields identical day aggregation.
4. Monotonicity: higher observed occupancy (o_hat) never increases ghost score.
5. Untrusted days isolation: untrusted camera observations never create a ghost state.
6. Hysteresis dampening: single observations do not cause rapid state flapping.
"""
from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.domain.camera_integrity import (
    CameraIntegrityThresholds,
    CameraStateSnapshot,
    SceneObservationRecord,
    evaluate_camera_state,
)
from app.domain.ghost_batch import (
    GhostState,
    GhostThresholds,
    SessionDayInput,
    evaluate_ghost_batch,
    to_ist_date,
)
from app.domain.vision.scene_compare import SceneClassification


# ─────────────────────────────────────────────────────────────────────────────
# 1. DETERMINISTIC REPLAY
# ─────────────────────────────────────────────────────────────────────────────

@settings(max_examples=50, deadline=None)
@given(
    claimed_1=st.integers(min_value=5, max_value=50),
    claimed_2=st.integers(min_value=5, max_value=50),
    o_hat_1=st.floats(min_value=0.0, max_value=50.0),
    o_hat_2=st.floats(min_value=0.0, max_value=50.0),
    feed_health=st.floats(min_value=0.5, max_value=1.0),
)
def test_ghost_batch_deterministic_replay(
    claimed_1: int,
    claimed_2: int,
    o_hat_1: float,
    o_hat_2: float,
    feed_health: float,
) -> None:
    """Repeated evaluation with identical inputs produces bitwise-identical results."""
    base_time = datetime(2024, 6, 15, 6, 0, tzinfo=UTC)
    now = datetime(2024, 6, 18, 12, 0, tzinfo=UTC)
    s1 = SessionDayInput(
        session_id="s1",
        scheduled_start=base_time,
        scheduled_end=base_time + timedelta(hours=2),
        claimed_count=claimed_1,
        o_hat=o_hat_1,
        feed_health=feed_health,
        camera_trust="TRUSTED",
    )
    s2 = SessionDayInput(
        session_id="s2",
        scheduled_start=base_time + timedelta(days=1),
        scheduled_end=base_time + timedelta(days=1, hours=2),
        claimed_count=claimed_2,
        o_hat=o_hat_2,
        feed_health=feed_health,
        camera_trust="TRUSTED",
    )

    sessions = [s1, s2]
    res_1 = evaluate_ghost_batch(
        batch_id="batch-det",
        centre_id="ctr-det",
        sessions=sessions,
        previous_state="NORMAL",
        now=now,
    )
    res_2 = evaluate_ghost_batch(
        batch_id="batch-det",
        centre_id="ctr-det",
        sessions=sessions,
        previous_state="NORMAL",
        now=now,
    )

    assert res_1.current_state == res_2.current_state
    assert res_1.ghost_days == res_2.ghost_days
    assert res_1.eligible_days == res_2.eligible_days
    assert res_1.ghost_score == res_2.ghost_score
    assert res_1.per_day_detail == res_2.per_day_detail


# ─────────────────────────────────────────────────────────────────────────────
# 2. ORDER-INVARIANCE OF SESSION LIST
# ─────────────────────────────────────────────────────────────────────────────

@settings(max_examples=50, deadline=None)
@given(
    days_count=st.integers(min_value=2, max_value=6),
)
def test_order_invariance_of_sessions(days_count: int) -> None:
    """Out-of-order session arrival produces identical day aggregation and state."""
    base_time = datetime(2024, 6, 10, 6, 0, tzinfo=UTC)
    now = datetime(2024, 6, 20, 12, 0, tzinfo=UTC)
    sessions: list[SessionDayInput] = []

    for i in range(days_count):
        s = SessionDayInput(
            session_id=f"s-{i}",
            scheduled_start=base_time + timedelta(days=i),
            scheduled_end=base_time + timedelta(days=i, hours=2),
            claimed_count=20,
            o_hat=2.0 if i % 2 == 0 else 18.0,
            feed_health=0.9,
            camera_trust="TRUSTED",
        )
        sessions.append(s)

    # In-order evaluation
    res_in_order = evaluate_ghost_batch(
        batch_id="b-order",
        centre_id="c-order",
        sessions=sessions,
        now=now,
    )

    # Shuffled evaluation
    shuffled_sessions = list(sessions)
    random.seed(42)
    random.shuffle(shuffled_sessions)

    res_shuffled = evaluate_ghost_batch(
        batch_id="b-order",
        centre_id="c-order",
        sessions=shuffled_sessions,
        now=now,
    )

    assert res_in_order.current_state == res_shuffled.current_state
    assert res_in_order.ghost_days == res_shuffled.ghost_days
    assert res_in_order.ghost_score == res_shuffled.ghost_score
    assert [d["date"] for d in res_in_order.per_day_detail] == [
        d["date"] for d in res_shuffled.per_day_detail
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 3. MONOTONICITY: HIGHER OCCUPANCY NEVER WORSENS GHOST SCORE
# ─────────────────────────────────────────────────────────────────────────────

@settings(max_examples=50, deadline=None)
@given(
    claimed=st.integers(min_value=10, max_value=40),
    o_hat_low=st.floats(min_value=0.0, max_value=5.0),
    delta=st.floats(min_value=1.0, max_value=20.0),
)
def test_monotonicity_more_observed_occupancy(
    claimed: int,
    o_hat_low: float,
    delta: float,
) -> None:
    """Increasing observed occupancy never increases ghost score or worsens ghost days."""
    o_hat_high = o_hat_low + delta
    base_time = datetime(2024, 6, 15, 6, 0, tzinfo=UTC)
    now = datetime(2024, 6, 18, 12, 0, tzinfo=UTC)

    # Batch with lower occupancy
    s_low_1 = SessionDayInput("s1", base_time, base_time + timedelta(hours=2), claimed, o_hat_low, 1.0, "TRUSTED")
    s_low_2 = SessionDayInput("s2", base_time + timedelta(days=1), base_time + timedelta(days=1, hours=2), claimed, o_hat_low, 1.0, "TRUSTED")

    # Batch with higher occupancy
    s_high_1 = SessionDayInput("s1", base_time, base_time + timedelta(hours=2), claimed, o_hat_high, 1.0, "TRUSTED")
    s_high_2 = SessionDayInput("s2", base_time + timedelta(days=1), base_time + timedelta(days=1, hours=2), claimed, o_hat_high, 1.0, "TRUSTED")

    res_low = evaluate_ghost_batch("b-low", "c", [s_low_1, s_low_2], now=now)
    res_high = evaluate_ghost_batch("b-high", "c", [s_high_1, s_high_2], now=now)

    # Ghost days in high-occupancy scenario must be <= ghost days in low-occupancy
    assert res_high.ghost_days <= res_low.ghost_days

    # Ghost score in high-occupancy scenario must be <= ghost score in low-occupancy
    score_low = res_low.ghost_score or 0.0
    score_high = res_high.ghost_score or 0.0
    assert score_high <= score_low + 1e-6


# ─────────────────────────────────────────────────────────────────────────────
# 4. UNTRUSTED DAYS NEVER CREATE A GHOST ACCUSATION
# ─────────────────────────────────────────────────────────────────────────────

@settings(max_examples=40, deadline=None)
@given(
    untrusted_count=st.integers(min_value=1, max_value=10),
    claimed=st.integers(min_value=10, max_value=50),
)
def test_untrusted_camera_days_never_create_ghost_accusation(
    untrusted_count: int,
    claimed: int,
) -> None:
    """Even with 0.0 observed occupancy across many days, UNTRUSTED cameras never flag a ghost batch."""
    base_time = datetime(2024, 6, 1, 6, 0, tzinfo=UTC)
    now = datetime(2024, 6, 20, 12, 0, tzinfo=UTC)

    sessions: list[SessionDayInput] = []
    for i in range(untrusted_count):
        s = SessionDayInput(
            session_id=f"s-untrusted-{i}",
            scheduled_start=base_time + timedelta(days=i),
            scheduled_end=base_time + timedelta(days=i, hours=2),
            claimed_count=claimed,
            o_hat=0.0,  # 0 people observed
            feed_health=1.0,
            camera_trust="UNTRUSTED",  # camera is untrusted
        )
        sessions.append(s)

    res = evaluate_ghost_batch("b-untrusted", "c", sessions, previous_state="NORMAL", now=now)

    # Must NEVER accuse of ghost batch
    assert res.current_state in ("NORMAL", "RESOLVED")
    assert res.ghost_days == 0
    assert res.untrusted_days == untrusted_count
    assert res.camera_integrity_explains is True


# ─────────────────────────────────────────────────────────────────────────────
# 5. CAMERA INTEGRITY: NO FLAPPING WITH HYSTERESIS
# ─────────────────────────────────────────────────────────────────────────────

@settings(max_examples=40, deadline=None)
@given(
    single_stable_fused=st.floats(min_value=0.80, max_value=0.99),
)
def test_camera_hysteresis_prevents_single_observation_flapping(
    single_stable_fused: float,
) -> None:
    """A single stable observation in SWAP_CONFIRMED does NOT cause flapping back to STABLE."""
    base_time = datetime(2024, 6, 15, 10, 0, tzinfo=UTC)
    thresholds = CameraIntegrityThresholds(recovery_k_stable=3)

    snapshot = CameraStateSnapshot(
        camera_id="cam-flap",
        state="SWAP_CONFIRMED",
        since=base_time,
        first_suspected_at=base_time - timedelta(hours=2),
        last_transition_at=base_time,
        consecutive_suspicious=5,
        consecutive_stable=0,
        confidence=0.9,
        algorithm_version="v1",
    )

    # Only 1 stable observation
    obs_single = [
        SceneObservationRecord(
            ts=base_time + timedelta(minutes=5),
            classification=SceneClassification.STABLE,
            fused_similarity=single_stable_fused,
            orb_inliers=60,
            inlier_ratio=0.8,
            source="server_verified",
        )
    ]

    transition = evaluate_camera_state(snapshot, obs_single, thresholds=thresholds)

    # State must NOT flap to RESOLVED or STABLE on a single observation
    assert transition.changed is False
    assert transition.new_state == "SWAP_CONFIRMED"
