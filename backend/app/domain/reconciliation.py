"""app/domain/reconciliation.py — Pure reconciliation functions.

ALL functions here are pure (no I/O, no side effects).
Inputs come from DB queries performed in the service layer.
This makes every function trivially unit-testable and property-testable.

Attendance status vocabulary:
  GREEN   — observed ≥ t_green fraction of claimed
  AMBER   — observed between t_amber and t_green
  RED     — observed < t_amber (and repeated ≥ N times, or ghost batch)
  NO_DATA — feed health below minimum fraction; not a violation
  PENDING — claimed count not yet available

Item status vocabulary:
  PRESENT   — seen in sufficient windows
  ABSENT    — not seen across ≥ N unoccluded windows on ≥ 2 distinct days
  UNCERTAIN — occluded / low visibility / feed outage

Flags are LEADS for human review. They are never automatic penalties.
All defaults are labelled "initial hypothesis; calibrate in pilot."
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
import numpy as np

from datetime import datetime
from typing import Literal

AttendanceStatus = Literal["GREEN", "AMBER", "RED", "NO_DATA", "PENDING"]
ItemStatus = Literal["PRESENT", "ABSENT", "UNCERTAIN"]


# ── Data structures (pure, no ORM) ────────────────────────────────────────────

@dataclass(frozen=True)
class WindowObservations:
    """Aggregate observations for a session window."""
    persons_p90_values: list[float]      # one per minute with healthy feed
    feed_health_values: list[float]      # one per minute in window
    total_minutes: int                   # scheduled session length in minutes
    trainer_count: int                   # aggregate trainer count (from trainer-attendance)


@dataclass(frozen=True)
class ThresholdConfig:
    """Thresholds for reconciliation — loaded from ThresholdProfile, never hardcoded."""
    t_green: float = 0.80      # [initial hypothesis; calibrate in pilot]
    t_amber: float = 0.50      # [initial hypothesis; calibrate in pilot]
    repeat_n: int = 2          # [initial hypothesis; calibrate in pilot]
    min_feed_health_fraction: float = 0.50  # [initial hypothesis]
    coverage_factor_k: float = 1.0     # zone-specific (from Zone.coverage_factor)


@dataclass(frozen=True)
class ReconciliationResult:
    status: AttendanceStatus
    ratio: float | None
    observed_hat: float | None
    feed_health_fraction: float
    reason: str


@dataclass(frozen=True)
class ItemWindowObservation:
    """One observation window for an item class in a zone."""
    date: datetime
    count_seen: int
    is_occluded: bool
    feed_ok: bool


@dataclass(frozen=True)
class ItemStatusResult:
    status: ItemStatus
    reason: str
    windows_checked: int


# ── Feed health ───────────────────────────────────────────────────────────────

def compute_feed_health_fraction(
    feed_health_values: list[float], total_minutes: int
) -> float:
    """Fraction of the session window with healthy feed (feed_health > 0)."""
    if total_minutes <= 0:
        return 0.0
    healthy = sum(1 for v in feed_health_values if v > 0.0)
    return healthy / total_minutes


# ── P90 computation (core 60% of window) ─────────────────────────────────────

def compute_p90_core_window(
    persons_p90_values: list[float], total_minutes: int
) -> float | None:
    """Compute P90 of persons_p90 over the central 60% of the session window.

    The core window excludes the first and last 20% of minutes to reduce
    entry/exit transient effects.
    Returns None if fewer than 3 usable values.
    """
    if not persons_p90_values or total_minutes < 3:
        return None

    # Sort by position and take the middle 60%
    trim_each_side = max(1, int(total_minutes * 0.20))
    core = persons_p90_values[trim_each_side: max(trim_each_side + 1, total_minutes - trim_each_side)]

    if len(core) < 2:
        core = persons_p90_values  # fallback: use all if window is tiny

    if not core:
        return None

    if len(core) == 1:
        return float(core[0])

    return float(statistics.quantiles(core, n=10)[8])  # P90




# ── Ghost batch detection ─────────────────────────────────────────────────────

def is_ghost_batch(
    o_hat: float,
    claimed_count: int,
    *,
    ghost_min_claimed: int = 5,
    ghost_max_observed: float = 1.0,
) -> bool:
    """Ghost batch: claimed attendance is above minimum, but observed ≈ 0.

    [initial hypothesis; calibrate in pilot]
    ghost_min_claimed: minimum claimed count to trigger ghost-batch check.
    ghost_max_observed: O_hat must be at or below this to flag ghost batch.
    """
    return claimed_count >= ghost_min_claimed and o_hat <= ghost_max_observed


# ── Main attendance reconciliation ────────────────────────────────────────────

def reconcile_attendance(
    window: WindowObservations,
    claimed_count: int | None,
    cfg: ThresholdConfig,
    *,
    previous_below_amber_count: int = 0,
) -> ReconciliationResult:
    """Compute attendance status for one session window.

    Args:
        window: Observations for the session window.
        claimed_count: Aggregate claimed attendance from attendance system.
                       None means the data hasn't arrived yet (→ PENDING).
        cfg: Threshold configuration (from ThresholdProfile).
        previous_below_amber_count: How many consecutive prior sessions were RED/below t_amber.

    Returns:
        ReconciliationResult with status and all inputs for explainability.
    """
    # Step 1: Feed health check
    feed_fraction = compute_feed_health_fraction(window.feed_health_values, window.total_minutes)

    if feed_fraction < cfg.min_feed_health_fraction:
        return ReconciliationResult(
            status="NO_DATA",
            ratio=None,
            observed_hat=None,
            feed_health_fraction=feed_fraction,
            reason=(
                f"Feed health {feed_fraction:.1%} below minimum "
                f"{cfg.min_feed_health_fraction:.1%}; not a violation"
            ),
        )

    # Step 2: Claimed count availability
    if claimed_count is None:
        return ReconciliationResult(
            status="PENDING",
            ratio=None,
            observed_hat=None,
            feed_health_fraction=feed_fraction,
            reason="Attendance claim not yet received; will re-evaluate on arrival",
        )

    # Step 3: Compute O_hat
    p90 = compute_p90_core_window(window.persons_p90_values, window.total_minutes)
    if p90 is None:
        return ReconciliationResult(
            status="NO_DATA",
            ratio=None,
            observed_hat=None,
            feed_health_fraction=feed_fraction,
            reason="Insufficient valid observation samples in window",
        )

    o_hat = max(0.0, p90 - float(window.trainer_count))

    # Step 4: Ghost batch check
    if is_ghost_batch(o_hat, claimed_count):
        return ReconciliationResult(
            status="RED",
            ratio=0.0,
            observed_hat=o_hat,
            feed_health_fraction=feed_fraction,
            reason=(
                f"Ghost batch: O_hat={o_hat:.1f} ≈ 0 while claimed={claimed_count} "
                f"≥ {5} [initial hypothesis]"
            ),
        )

    # Step 5: Ratio computation
    denominator = cfg.coverage_factor_k * claimed_count
    if denominator <= 0:
        return ReconciliationResult(
            status="NO_DATA",
            ratio=None,
            observed_hat=o_hat,
            feed_health_fraction=feed_fraction,
            reason="Claimed count is zero or coverage factor is zero",
        )

    ratio = o_hat / denominator

    # Step 6: Status classification
    if ratio >= cfg.t_green:
        status: AttendanceStatus = "GREEN"
        reason = f"Ratio {ratio:.2f} ≥ t_green={cfg.t_green} [initial hypothesis]"
    elif ratio >= cfg.t_amber:
        status = "AMBER"
        reason = f"Ratio {ratio:.2f} between t_amber={cfg.t_amber} and t_green={cfg.t_green}"
    else:
        # Below t_amber: RED if repeated ≥ N times, else AMBER
        if previous_below_amber_count >= cfg.repeat_n - 1:
            status = "RED"
            reason = (
                f"Ratio {ratio:.2f} < t_amber={cfg.t_amber} for "
                f"{previous_below_amber_count + 1} consecutive sessions "
                f"(repeat_n={cfg.repeat_n}) [initial hypothesis]"
            )
        else:
            status = "AMBER"
            reason = (
                f"Ratio {ratio:.2f} < t_amber={cfg.t_amber} but only "
                f"{previous_below_amber_count + 1} session(s) "
                f"(need {cfg.repeat_n} for RED) [initial hypothesis]"
            )

    return ReconciliationResult(
        status=status,
        ratio=ratio,
        observed_hat=o_hat,
        feed_health_fraction=feed_fraction,
        reason=reason,
    )


# ── Infrastructure item status ─────────────────────────────────────────────────

def compute_item_status(
    observations: list[ItemWindowObservation],
    *,
    min_absent_windows: int = 3,    # [initial hypothesis; calibrate in pilot]
    min_absent_days: int = 2,       # [initial hypothesis; calibrate in pilot]
) -> ItemStatusResult:
    """Determine PRESENT/ABSENT/UNCERTAIN for one item class in one zone.

    ABSENT only if not seen across ≥ min_absent_windows unoccluded windows
    on ≥ min_absent_days distinct days.

    Occlusion, low visibility, or feed outage → UNCERTAIN (not ABSENT).

    Args:
        observations: List of observation windows for this item.
        min_absent_windows: Minimum clear windows with zero count before ABSENT.
        min_absent_days: Minimum distinct dates spanning those windows.

    Wording: "no evidence of use in N sessions" — never "non-functional".
    """
    if not observations:
        return ItemStatusResult(
            status="UNCERTAIN",
            reason="No observation data available",
            windows_checked=0,
        )

    unoccluded = [o for o in observations if not o.is_occluded and o.feed_ok]
    total_windows = len(observations)

    if not unoccluded:
        return ItemStatusResult(
            status="UNCERTAIN",
            reason=(
                f"All {total_windows} observation windows are occluded or "
                "have feed issues; cannot determine status"
            ),
            windows_checked=total_windows,
        )

    # Any window with count > 0 → PRESENT
    seen_windows = [o for o in unoccluded if o.count_seen > 0]
    if seen_windows:
        return ItemStatusResult(
            status="PRESENT",
            reason=f"Detected in {len(seen_windows)} of {len(unoccluded)} clear windows",
            windows_checked=total_windows,
        )

    # Count clear-zero windows
    zero_unoccluded = [o for o in unoccluded if o.count_seen == 0]
    distinct_days = len({o.date.date() for o in zero_unoccluded})

    if len(zero_unoccluded) >= min_absent_windows and distinct_days >= min_absent_days:
        return ItemStatusResult(
            status="ABSENT",
            reason=(
                f"No evidence of use in {len(zero_unoccluded)} clear sessions "
                f"across {distinct_days} distinct days "
                f"(thresholds: windows≥{min_absent_windows}, days≥{min_absent_days}) "
                "[initial hypothesis]"
            ),
            windows_checked=total_windows,
        )

    return ItemStatusResult(
        status="UNCERTAIN",
        reason=(
            f"Not detected in {len(zero_unoccluded)} clear windows across "
            f"{distinct_days} days — insufficient for ABSENT determination "
            f"(need ≥{min_absent_windows} windows, ≥{min_absent_days} days)"
        ),
        windows_checked=total_windows,
    )


# ── Risk score ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RiskComponent:
    name: str
    weight: float
    value: float    # 0.0–1.0 (normalised)
    contribution: float


@dataclass(frozen=True)
class RiskScoreResult:
    score: float           # 0.0–1.0 weighted sum
    components: list[RiskComponent]
    explanation: str


def compute_risk_score(
    red_flag_count: int,
    amber_flag_count: int,
    integrity_event_count: int,
    device_offline_count: int,
    *,
    weights: dict[str, float] | None = None,
) -> RiskScoreResult:
    """Transparent, weighted risk score. No black-box ML in v1.

    All component weights are stored alongside the score so the ranking
    is fully explainable. [initial hypothesis; calibrate in pilot]
    """
    default_weights = {
        "red_flags": 0.40,        # [initial hypothesis]
        "amber_flags": 0.20,      # [initial hypothesis]
        "integrity_events": 0.25, # [initial hypothesis]
        "device_offline": 0.15,   # [initial hypothesis]
    }
    w = weights or default_weights

    def norm(v: float, scale: float = 10.0) -> float:
        return min(1.0, v / scale)

    components = [
        RiskComponent("red_flags", w["red_flags"], norm(red_flag_count, 5), w["red_flags"] * norm(red_flag_count, 5)),
        RiskComponent("amber_flags", w["amber_flags"], norm(amber_flag_count, 10), w["amber_flags"] * norm(amber_flag_count, 10)),
        RiskComponent("integrity_events", w["integrity_events"], norm(integrity_event_count, 5), w["integrity_events"] * norm(integrity_event_count, 5)),
        RiskComponent("device_offline", w["device_offline"], norm(device_offline_count, 3), w["device_offline"] * norm(device_offline_count, 3)),
    ]
    score = sum(c.contribution for c in components)

    parts = ", ".join(f"{c.name}={c.contribution:.3f}" for c in components)
    return RiskScoreResult(
        score=min(1.0, score),
        components=components,
        explanation=f"score={score:.3f} [{parts}] [initial hypothesis weights]",
    )
