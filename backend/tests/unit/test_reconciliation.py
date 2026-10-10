"""tests/unit/test_reconciliation.py — Reconciliation domain unit and property tests.

These test the pure functions in app/domain/reconciliation.py.
No DB, no HTTP, no I/O — just math.

Property tests use only stdlib random to avoid hypothesis dependency for now.
A full Hypothesis suite is added in tests/property/ when hypothesis is installed.
"""
from __future__ import annotations

import math
import random
import statistics
from datetime import UTC, datetime, timedelta

import pytest
from typing import Any

from app.domain.reconciliation import (
    ThresholdConfig,
    WindowObservations,
    ItemWindowObservation,
    compute_feed_health_fraction,
    compute_item_status,
    compute_p90_core_window,
    compute_risk_score,
    is_ghost_batch,
    reconcile_attendance,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def default_cfg(**kwargs: Any) -> ThresholdConfig:
    cfg_dict: dict[str, Any] = {
        "t_green": 0.80,
        "t_amber": 0.50,
        "repeat_n": 2,
        "min_feed_health_fraction": 0.50,
        "coverage_factor_k": 1.0,
    }
    cfg_dict.update(kwargs)
    return ThresholdConfig(**cfg_dict)


def healthy_window(count: int = 30, persons: float = 25.0, total: int = 60) -> WindowObservations:
    return WindowObservations(
        persons_p90_values=[persons] * count,
        feed_health_values=[1.0] * count,
        total_minutes=total,
        trainer_count=2,
    )


# ── Feed health ────────────────────────────────────────────────────────────────

def test_feed_health_all_healthy() -> None:
    assert compute_feed_health_fraction([1.0, 0.9, 0.8], 3) == pytest.approx(1.0)


def test_feed_health_half_healthy() -> None:
    assert compute_feed_health_fraction([1.0, 0.0, 1.0, 0.0], 4) == pytest.approx(0.5)


def test_feed_health_all_zero() -> None:
    assert compute_feed_health_fraction([0.0, 0.0, 0.0], 3) == pytest.approx(0.0)


def test_feed_health_empty_returns_zero() -> None:
    assert compute_feed_health_fraction([], 5) == pytest.approx(0.0)


def test_feed_health_zero_total_returns_zero() -> None:
    assert compute_feed_health_fraction([1.0], 0) == pytest.approx(0.0)


# ── P90 core window ────────────────────────────────────────────────────────────

def test_p90_homogeneous_values() -> None:
    values = [25.0] * 60
    result = compute_p90_core_window(values, 60)
    assert result is not None
    assert result == pytest.approx(25.0, rel=1e-2)


def test_p90_empty_returns_none() -> None:
    assert compute_p90_core_window([], 60) is None


def test_p90_too_few_minutes_returns_none() -> None:
    assert compute_p90_core_window([25.0], 2) is None


def test_p90_trims_extremes() -> None:
    # Spike at beginning and end; core should be ~25
    values = [100.0] * 6 + [25.0] * 48 + [100.0] * 6   # 60 total
    result = compute_p90_core_window(values, 60)
    # Core window (middle 60%) = indices 12..48 which are all 25.0
    assert result is not None
    assert result == pytest.approx(25.0, rel=0.1)


# ── Ghost batch ────────────────────────────────────────────────────────────────

def test_ghost_batch_zero_observed_high_claimed() -> None:
    assert is_ghost_batch(0.0, 30) is True


def test_ghost_batch_not_triggered_low_claimed() -> None:
    assert is_ghost_batch(0.0, 4) is False   # below min_claimed=5


def test_ghost_batch_not_triggered_when_observed() -> None:
    assert is_ghost_batch(5.0, 30) is False


# ── Main reconciliation ────────────────────────────────────────────────────────

def test_green_status() -> None:
    w = healthy_window(count=60, persons=28.0, total=60)
    result = reconcile_attendance(w, claimed_count=30, cfg=default_cfg())
    assert result.status == "GREEN"
    assert result.ratio is not None
    assert result.ratio >= 0.80


def test_amber_status() -> None:
    # O_hat will be ~20 (persons - trainers = 18), claimed 40
    # ratio = 18/40 = 0.45 → below t_green(0.80) but first session → AMBER not RED
    w = healthy_window(count=60, persons=20.0, total=60)
    result = reconcile_attendance(w, claimed_count=40, cfg=default_cfg(), previous_below_amber_count=0)
    assert result.status == "AMBER"


def test_red_status_repeated() -> None:
    # Low ratio AND previous_below_amber_count >= repeat_n - 1
    w = healthy_window(count=60, persons=5.0, total=60)
    result = reconcile_attendance(w, claimed_count=50, cfg=default_cfg(), previous_below_amber_count=2)
    assert result.status == "RED"


def test_red_ghost_batch() -> None:
    w = healthy_window(count=60, persons=2.0, total=60)
    result = reconcile_attendance(w, claimed_count=30, cfg=default_cfg())
    assert result.status == "RED"
    assert "Ghost" in result.reason or "ghost" in result.reason.lower()


def test_no_data_low_feed_health() -> None:
    w = WindowObservations(
        persons_p90_values=[25.0] * 25,
        feed_health_values=[0.0] * 25 + [1.0] * 10,  # 10/60 healthy
        total_minutes=60,
        trainer_count=0,
    )
    result = reconcile_attendance(w, claimed_count=30, cfg=default_cfg())
    assert result.status == "NO_DATA"
    assert "not a violation" in result.reason.lower()


def test_pending_status_when_no_claimed_count() -> None:
    result = reconcile_attendance(healthy_window(), claimed_count=None, cfg=default_cfg())
    assert result.status == "PENDING"


def test_no_data_zero_claimed_denominator() -> None:
    result = reconcile_attendance(healthy_window(), claimed_count=0, cfg=default_cfg())
    assert result.status == "NO_DATA"


def test_coverage_factor_scales_denominator() -> None:
    """k=0.5 means 50% of zone is visible — denominator is halved."""
    cfg = default_cfg(coverage_factor_k=0.5)
    # O_hat = 25 - 2 = 23; claimed = 50; denominator = 0.5 * 50 = 25
    # ratio = 23/25 = 0.92 → GREEN
    w = healthy_window(count=60, persons=25.0, total=60)
    result = reconcile_attendance(w, claimed_count=50, cfg=cfg)
    assert result.status == "GREEN"


def test_result_is_fully_explainable() -> None:
    """Every result must have reason, ratio or explanation of why ratio is absent."""
    cases = [
        (healthy_window(), 30, "GREEN or AMBER"),
        (healthy_window(), None, "PENDING"),
        (WindowObservations([], [0.0] * 60, 60, 0), 30, "NO_DATA"),
    ]
    for w, claimed, _ in cases:
        result = reconcile_attendance(w, claimed_count=claimed, cfg=default_cfg())
        assert result.reason, "Every result must have a non-empty reason"
        if result.ratio is not None:
            assert 0.0 <= result.ratio, "Ratio must be non-negative"


# ── Item status ────────────────────────────────────────────────────────────────

def _obs(count: int, days_ago: int = 0, occluded: bool = False, feed_ok: bool = True) -> ItemWindowObservation:
    return ItemWindowObservation(
        date=datetime(2024, 6, 15, tzinfo=UTC) - timedelta(days=days_ago),
        count_seen=count,
        is_occluded=occluded,
        feed_ok=feed_ok,
    )


def test_item_present_when_any_window_has_count() -> None:
    obs = [_obs(0), _obs(5), _obs(0)]
    result = compute_item_status(obs)
    assert result.status == "PRESENT"


def test_item_absent_multi_day() -> None:
    obs = [_obs(0, days_ago=0), _obs(0, days_ago=1), _obs(0, days_ago=2)]
    result = compute_item_status(obs, min_absent_windows=3, min_absent_days=2)
    assert result.status == "ABSENT"
    assert "initial hypothesis" in result.reason


def test_item_uncertain_all_occluded() -> None:
    obs = [_obs(0, occluded=True), _obs(0, occluded=True)]
    result = compute_item_status(obs)
    assert result.status == "UNCERTAIN"


def test_item_uncertain_insufficient_clear_windows() -> None:
    # Only 2 clear-zero windows when we need 3
    obs = [_obs(0, days_ago=0), _obs(0, days_ago=1)]
    result = compute_item_status(obs, min_absent_windows=3, min_absent_days=2)
    assert result.status == "UNCERTAIN"


def test_item_uncertain_insufficient_days() -> None:
    # 5 clear-zero windows but all same day
    obs = [_obs(0, days_ago=0)] * 5
    result = compute_item_status(obs, min_absent_windows=3, min_absent_days=2)
    assert result.status == "UNCERTAIN"


def test_item_uncertain_no_data() -> None:
    result = compute_item_status([])
    assert result.status == "UNCERTAIN"
    assert result.windows_checked == 0


def test_item_feed_issues_are_uncertain_not_absent() -> None:
    obs = [_obs(0, feed_ok=False)] * 10
    result = compute_item_status(obs)
    assert result.status == "UNCERTAIN"


# ── Risk score ─────────────────────────────────────────────────────────────────

def test_risk_score_zero_events_is_zero() -> None:
    result = compute_risk_score(0, 0, 0, 0)
    assert result.score == pytest.approx(0.0)


def test_risk_score_max_all_components() -> None:
    result = compute_risk_score(100, 100, 100, 100)
    assert result.score == pytest.approx(1.0)


def test_risk_score_partial_is_between_0_and_1() -> None:
    result = compute_risk_score(2, 3, 1, 0)
    assert 0.0 <= result.score <= 1.0


def test_risk_score_components_sum_to_score() -> None:
    result = compute_risk_score(3, 5, 2, 1)
    computed = sum(c.contribution for c in result.components)
    assert result.score == pytest.approx(min(1.0, computed), rel=1e-6)


def test_risk_score_has_explanation() -> None:
    result = compute_risk_score(1, 0, 0, 0)
    assert "initial hypothesis" in result.explanation


def test_risk_score_custom_weights() -> None:
    w = {"red_flags": 1.0, "amber_flags": 0.0, "integrity_events": 0.0, "device_offline": 0.0}
    result = compute_risk_score(10, 10, 10, 10, weights=w)
    # Only red_flags contribute (capped at 1.0)
    assert result.score == pytest.approx(1.0)


# ── Invariant properties (lightweight, no hypothesis dependency) ───────────────

def test_reconcile_always_has_non_empty_reason() -> None:
    rng = random.Random(42)
    cfg = default_cfg()
    for _ in range(100):
        n = rng.randint(0, 60)
        persons = rng.uniform(0, 50)
        claimed = rng.choice([None, 0, rng.randint(1, 60)])
        feed = [rng.uniform(0, 1) for _ in range(n)]
        w = WindowObservations(
            persons_p90_values=[persons] * n,
            feed_health_values=feed,
            total_minutes=60,
            trainer_count=rng.randint(0, 3),
        )
        result = reconcile_attendance(w, claimed_count=claimed, cfg=cfg)
        assert result.reason, "reason must never be empty"
        assert result.status in ("GREEN", "AMBER", "RED", "NO_DATA", "PENDING")


def test_item_status_always_has_reason() -> None:
    rng = random.Random(99)
    for _ in range(100):
        obs = [
            ItemWindowObservation(
                date=datetime(2024, 6, rng.randint(1, 28), tzinfo=UTC),
                count_seen=rng.randint(0, 10),
                is_occluded=rng.random() < 0.3,
                feed_ok=rng.random() < 0.8,
            )
            for _ in range(rng.randint(0, 10))
        ]
        result = compute_item_status(obs)
        assert result.reason
        assert result.status in ("PRESENT", "ABSENT", "UNCERTAIN")


def test_high_feed_healthy_never_no_data() -> None:
    """If feed_health_fraction is high, result should not be NO_DATA (unless zero claimed)."""
    cfg = default_cfg(min_feed_health_fraction=0.50)
    w = WindowObservations(
        persons_p90_values=[25.0] * 60,
        feed_health_values=[1.0] * 60,
        total_minutes=60,
        trainer_count=2,
    )
    result = reconcile_attendance(w, claimed_count=30, cfg=cfg)
    assert result.status != "NO_DATA"
