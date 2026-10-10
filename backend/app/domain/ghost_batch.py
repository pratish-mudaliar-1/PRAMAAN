"""app/domain/ghost_batch.py — Pure domain functions for multi-day ghost batch detection.

All functions in this module are deterministic and pure (no DB, no network, no I/O).
Inputs are dataclasses; outputs are domain evaluation results.

Key principles:
- These are leads for human review, NEVER automatic penalties.
- Local-day boundaries are evaluated in Indian Standard Time (IST, UTC+05:30).
- NO_DATA, PENDING, and UNTRUSTED days are NEVER counted as violations or in the
  denominator for ghost score calculations; they are tracked and displayed.
- If an UNTRUSTED camera explains low physical occupancy, it generates a camera
  integrity case, NEVER a ghost batch accusation.
- Thresholds are initial hypotheses, calibrated in pilot.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

IST_OFFSET = timedelta(hours=5, minutes=30)

GhostState = Literal[
    "NORMAL",
    "WATCH",
    "SUSPECTED_GHOST",
    "ESCALATED",
    "RESOLVED",
]

DayStatus = Literal[
    "GHOST",
    "HEALTHY",
    "NO_DATA",
    "UNTRUSTED",
    "PENDING",
]


@dataclass(frozen=True)
class SessionDayInput:
    """Input representation of a scheduled session for daily aggregation."""
    session_id: str
    scheduled_start: datetime           # UTC timestamp
    scheduled_end: datetime             # UTC timestamp
    claimed_count: int | None
    o_hat: float | None                 # Observed occupancy P90 hat
    feed_health: float                  # Usable feed fraction [0, 1]
    camera_trust: str = "TRUSTED"       # "TRUSTED" | "UNTRUSTED" | "DEGRADED"
    attendance_status: str = "PENDING"  # GREEN, AMBER, RED, NO_DATA, PENDING
    coverage_factor_k: float = 1.0


@dataclass(frozen=True)
class DayEvaluation:
    """Aggregated assessment for a single IST calendar day."""
    date_str: str                       # YYYY-MM-DD in IST
    status: DayStatus
    claimed_count: int
    o_hat: float
    ratio: float
    evidence_quality: float
    session_ids: list[str]
    reason: str


@dataclass(frozen=True)
class GhostThresholds:
    """Configurable thresholds for ghost batch detection.

    All values labelled: "initial hypothesis, calibrate in pilot".
    """
    min_claimed_attendance: int = 5          # Below this, session not eligible for ghost check
    ghost_ratio_threshold: float = 0.20      # Ratio o_hat / (k * claimed) < 0.20 = GHOST day
    min_feed_health: float = 0.50            # Minimum feed health to consider evidence usable
    min_eligible_days: int = 2               # Minimum eligible days before SUSPECTED_GHOST
    min_distinct_evidence_days: int = 2      # Minimum distinct days with observations
    m_of_n_m: int = 2                        # M ghost days in last N eligible days
    m_of_n_n: int = 3                        # N window size
    l_consecutive: int = 2                   # L consecutive ghost days to trigger
    recovery_r_consecutive: int = 3          # R consecutive healthy days to transition to RESOLVED
    escalation_ghost_days: int = 5           # Ghost days needed for ESCALATED
    escalation_score_threshold: float = 0.85 # Score threshold for ESCALATED
    cusum_threshold: float = 2.0             # Cumulative sum threshold for supporting signal
    weights: tuple[float, float, float, float] = (0.35, 0.30, 0.20, 0.15)
    # (persistence, magnitude, consistency, evidence_quality)


@dataclass(frozen=True)
class GhostScoreBreakdown:
    """Transparent components of the ghost score."""
    persistence: float                       # Fraction of eligible days that are ghost days [0, 1]
    magnitude: float                         # Depth of shortfall on ghost days [0, 1]
    consistency: float                       # Artificial claim uniformity [0, 1]
    evidence_quality: float                  # Fraction of window with trusted valid data [0, 1]
    cusum_score: float                       # Supporting CUSUM metric
    ghost_score: float                       # Weighted composite [0, 1]
    weights: list[float]
    algorithm_version: str = "v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "persistence": round(self.persistence, 4),
            "magnitude": round(self.magnitude, 4),
            "consistency": round(self.consistency, 4),
            "evidence_quality": round(self.evidence_quality, 4),
            "cusum_score": round(self.cusum_score, 4),
            "ghost_score": round(self.ghost_score, 4),
            "weights": list(self.weights),
            "algorithm_version": self.algorithm_version,
        }


@dataclass(frozen=True)
class GhostBatchEvaluationResult:
    """Full result of evaluating a batch across multiple days."""
    batch_id: str
    centre_id: str
    current_state: GhostState
    previous_state: GhostState
    transitioned: bool
    window_start: str                        # IST date YYYY-MM-DD
    window_end: str                          # IST date YYYY-MM-DD
    eligible_days: int
    ghost_days: int
    nodata_days: int
    untrusted_days: int
    pending_days: int
    hysteresis_ok_streak: int
    per_day_detail: list[dict[str, Any]]
    score_breakdown: GhostScoreBreakdown | None
    ghost_score: float | None
    camera_integrity_explains: bool          # True if untrusted camera explains low occupancy
    explanation: dict[str, Any]
    cause: str = "evaluation"

    @property
    def state(self) -> str:
        return self.current_state

    @property
    def is_ghost_pattern(self) -> bool:
        return self.current_state in ("SUSPECTED_GHOST", "ESCALATED")

    @property
    def ghost_sessions_count(self) -> int:
        return self.ghost_days

    @property
    def total_sessions_count(self) -> int:
        return self.eligible_days + self.nodata_days + self.untrusted_days + self.pending_days


# ── Timezone Helper ────────────────────────────────────────────────────────────

def to_ist_date(dt: datetime) -> str:
    """Convert UTC or naive datetime to IST calendar date string (YYYY-MM-DD)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    ist_time = dt.astimezone(UTC) + IST_OFFSET
    return ist_time.strftime("%Y-%m-%d")


def ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is offset-aware in UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


# ── Per-Day Evaluation ─────────────────────────────────────────────────────────

def evaluate_session_day(
    date_str: str,
    sessions: list[SessionDayInput],
    thresholds: GhostThresholds,
    now: datetime,
) -> DayEvaluation:
    """Aggregate all sessions for a single IST calendar day and determine DayStatus.

    Rules:
    - If any session has camera_trust == 'UNTRUSTED', or if all sessions have UNTRUSTED camera,
      we treat the day as UNTRUSTED (not a ghost accusation).
    - If claimed < min_claimed_attendance, it's not eligible (treated as NO_DATA / ignored).
    - If feed_health < min_feed_health, treated as NO_DATA.
    - If session is in the future, treated as PENDING.
    - Otherwise, compute day ratio: sum(o_hat) / sum(k * claimed).
      If ratio < ghost_ratio_threshold, status is GHOST, else HEALTHY.
    """
    if not sessions:
        return DayEvaluation(
            date_str=date_str,
            status="NO_DATA",
            claimed_count=0,
            o_hat=0.0,
            ratio=0.0,
            evidence_quality=0.0,
            session_ids=[],
            reason="No scheduled sessions",
        )

    # Sort sessions deterministically
    sorted_sessions = sorted(sessions, key=lambda s: s.scheduled_start)
    session_ids = [s.session_id for s in sorted_sessions]

    # Check future / pending sessions
    all_future = all(ensure_utc(s.scheduled_start) > ensure_utc(now) for s in sorted_sessions)
    if all_future:
        return DayEvaluation(
            date_str=date_str,
            status="PENDING",
            claimed_count=sum(s.claimed_count or 0 for s in sorted_sessions),
            o_hat=0.0,
            ratio=0.0,
            evidence_quality=0.0,
            session_ids=session_ids,
            reason="Sessions scheduled in future",
        )

    # Check camera trust: if any camera was UNTRUSTED during this day's sessions,
    # the day is untrusted. Low physical occupancy is explained by camera tampering.
    untrusted_sessions = [s for s in sorted_sessions if s.camera_trust == "UNTRUSTED"]
    if len(untrusted_sessions) == len(sorted_sessions):
        return DayEvaluation(
            date_str=date_str,
            status="UNTRUSTED",
            claimed_count=sum(s.claimed_count or 0 for s in sorted_sessions),
            o_hat=0.0,
            ratio=0.0,
            evidence_quality=0.0,
            session_ids=session_ids,
            reason="Camera view marked UNTRUSTED for all sessions on this day",
        )

    # Filter to usable sessions (past and non-untrusted)
    usable_sessions = [
        s for s in sorted_sessions
        if ensure_utc(s.scheduled_start) <= ensure_utc(now) and s.camera_trust != "UNTRUSTED"
    ]

    if not usable_sessions:
        return DayEvaluation(
            date_str=date_str,
            status="UNTRUSTED" if untrusted_sessions else "NO_DATA",
            claimed_count=sum(s.claimed_count or 0 for s in sorted_sessions),
            o_hat=0.0,
            ratio=0.0,
            evidence_quality=0.0,
            session_ids=session_ids,
            reason="No usable trusted session telemetry",
        )

    # Check feed health
    mean_feed_health = statistics.mean(s.feed_health for s in usable_sessions)
    if mean_feed_health < thresholds.min_feed_health:
        return DayEvaluation(
            date_str=date_str,
            status="NO_DATA",
            claimed_count=sum(s.claimed_count or 0 for s in usable_sessions),
            o_hat=0.0,
            ratio=0.0,
            evidence_quality=mean_feed_health,
            session_ids=session_ids,
            reason=f"Insufficient feed health ({mean_feed_health:.2f} < {thresholds.min_feed_health:.2f})",
        )

    # Check claimed attendance
    total_claimed = sum(s.claimed_count or 0 for s in usable_sessions)
    if total_claimed < thresholds.min_claimed_attendance:
        return DayEvaluation(
            date_str=date_str,
            status="NO_DATA",
            claimed_count=total_claimed,
            o_hat=0.0,
            ratio=0.0,
            evidence_quality=mean_feed_health,
            session_ids=session_ids,
            reason=f"Claimed attendance ({total_claimed}) below minimum ({thresholds.min_claimed_attendance})",
        )

    # Compute observed occupancy and ratio
    total_effective_claimed = sum(
        max(1.0, (s.claimed_count or 0) * max(0.1, s.coverage_factor_k))
        for s in usable_sessions
    )
    total_observed = sum(s.o_hat or 0.0 for s in usable_sessions)
    day_ratio = total_observed / max(1.0, total_effective_claimed)

    if day_ratio < thresholds.ghost_ratio_threshold:
        status: DayStatus = "GHOST"
        reason = f"Observed occupancy ratio {day_ratio:.2f} below ghost threshold {thresholds.ghost_ratio_threshold:.2f}"
    else:
        status = "HEALTHY"
        reason = f"Normal attendance ratio {day_ratio:.2f}"

    return DayEvaluation(
        date_str=date_str,
        status=status,
        claimed_count=total_claimed,
        o_hat=round(total_observed, 2),
        ratio=round(day_ratio, 4),
        evidence_quality=round(mean_feed_health, 3),
        session_ids=session_ids,
        reason=reason,
    )


# ── Score & Indicator Computation ──────────────────────────────────────────────

def compute_ghost_score(
    eligible_days: list[DayEvaluation],
    all_claimed_counts: list[int],
    thresholds: GhostThresholds,
) -> GhostScoreBreakdown:
    """Compute transparent multi-component ghost score over eligible days.

    Components:
    1. persistence: fraction of eligible days with ghost deficit
    2. magnitude: depth of shortfall below 0.50 threshold on ghost days
    3. consistency: uniformity of claimed attendance (low CV = high score)
    4. evidence_quality: mean feed health across eligible days
    5. cusum_score: cumulative shortfall accumulation
    """
    if not eligible_days:
        return GhostScoreBreakdown(
            persistence=0.0,
            magnitude=0.0,
            consistency=0.0,
            evidence_quality=0.0,
            cusum_score=0.0,
            ghost_score=0.0,
            weights=list(thresholds.weights),
        )

    n_eligible = len(eligible_days)
    ghost_days = [d for d in eligible_days if d.status == "GHOST"]
    n_ghost = len(ghost_days)

    # 1. Persistence
    persistence = n_ghost / max(1, n_eligible)

    # 2. Magnitude: average shortfall relative to half-occupancy (0.50)
    if ghost_days:
        shortfalls = [max(0.0, 1.0 - (d.ratio / 0.50)) for d in ghost_days]
        magnitude = statistics.mean(shortfalls)
    else:
        magnitude = 0.0
    magnitude = max(0.0, min(1.0, magnitude))

    # 3. Consistency: coefficient of variation of claimed counts
    # Highly suspicious batches report identical or near-identical claimed counts daily
    if len(all_claimed_counts) >= 2:
        mean_claimed = statistics.mean(all_claimed_counts)
        stdev_claimed = statistics.stdev(all_claimed_counts)
        cv = stdev_claimed / max(1.0, mean_claimed)
        # Low CV (flat claims) -> higher suspicion score in [0, 1]
        consistency = max(0.0, min(1.0, 1.0 - cv))
    else:
        consistency = 0.5

    # 4. Evidence quality: mean feed health on eligible days
    evidence_quality = statistics.mean(d.evidence_quality for d in eligible_days)
    evidence_quality = max(0.0, min(1.0, evidence_quality))

    # 5. CUSUM supporting signal
    # Accumulate shortfall below expected 0.80 ratio
    cusum = 0.0
    target_ratio = 0.80
    for d in eligible_days:
        shortfall = max(0.0, target_ratio - d.ratio)
        cusum = max(0.0, cusum + shortfall - 0.20)

    # Composite weighted score
    w_p, w_m, w_c, w_e = thresholds.weights
    composite = (
        w_p * persistence
        + w_m * magnitude
        + w_c * consistency
        + w_e * evidence_quality
    )
    composite = max(0.0, min(1.0, composite))

    return GhostScoreBreakdown(
        persistence=persistence,
        magnitude=magnitude,
        consistency=consistency,
        evidence_quality=evidence_quality,
        cusum_score=round(cusum, 3),
        ghost_score=round(composite, 4),
        weights=list(thresholds.weights),
    )


# ── Pattern Rules ──────────────────────────────────────────────────────────────

def check_ghost_pattern(
    eligible_days: list[DayEvaluation],
    thresholds: GhostThresholds,
) -> tuple[bool, str]:
    """Check if multi-day ghost pattern rules are met.

    Rule 1: M of last N eligible days are GHOST.
    Rule 2: L consecutive eligible days are GHOST.
    """
    if len(eligible_days) < thresholds.min_eligible_days:
        return False, f"Insufficient eligible days ({len(eligible_days)} < {thresholds.min_eligible_days})"

    # Rule 1: M of last N
    recent_window = eligible_days[-thresholds.m_of_n_n:]
    ghosts_in_window = sum(1 for d in recent_window if d.status == "GHOST")
    if ghosts_in_window >= thresholds.m_of_n_m:
        return True, f"Met {thresholds.m_of_n_m}-of-{thresholds.m_of_n_n} rule: {ghosts_in_window} ghost days in last {len(recent_window)} eligible days"

    # Rule 2: L consecutive
    consecutive = 0
    for d in reversed(eligible_days):
        if d.status == "GHOST":
            consecutive += 1
            if consecutive >= thresholds.l_consecutive:
                return True, f"Met {thresholds.l_consecutive} consecutive ghost days rule"
        else:
            break

    return False, "Pattern rules not met"


# ── Main Pure Evaluation Function ──────────────────────────────────────────────

def evaluate_ghost_batch(
    batch_id: str,
    centre_id: str,
    sessions: list[SessionDayInput],
    previous_state: GhostState = "NORMAL",
    current_hysteresis_streak: int = 0,
    thresholds: GhostThresholds | None = None,
    now: datetime | None = None,
) -> GhostBatchEvaluationResult:
    """Pure domain function to evaluate ghost batch patterns across multi-day window.

    Deterministic: same inputs -> exact same output.
    """
    t = thresholds or GhostThresholds()
    eval_now = now or datetime.now(UTC)

    # 1. Bucket sessions by IST date
    day_buckets: dict[str, list[SessionDayInput]] = {}
    for s in sessions:
        d_str = to_ist_date(s.scheduled_start)
        day_buckets.setdefault(d_str, []).append(s)

    # Sort dates chronologically
    sorted_dates = sorted(day_buckets.keys())

    # 2. Evaluate each calendar day
    daily_evals: list[DayEvaluation] = [
        evaluate_session_day(d_str, day_buckets[d_str], t, eval_now)
        for d_str in sorted_dates
    ]

    # Partition days
    eligible_days = [d for d in daily_evals if d.status in ("GHOST", "HEALTHY")]
    ghost_days = [d for d in daily_evals if d.status == "GHOST"]
    nodata_days = [d for d in daily_evals if d.status == "NO_DATA"]
    untrusted_days = [d for d in daily_evals if d.status == "UNTRUSTED"]
    pending_days = [d for d in daily_evals if d.status == "PENDING"]

    window_start = sorted_dates[0] if sorted_dates else eval_now.strftime("%Y-%m-%d")
    window_end = sorted_dates[-1] if sorted_dates else eval_now.strftime("%Y-%m-%d")

    # 3. Check if untrusted camera explains low physical occupancy
    # If the majority of absent/low-occupancy days occurred when the camera was untrusted,
    # we NEVER accuse of ghost batch — this is an integrity concern.
    camera_integrity_explains = False
    if len(untrusted_days) > 0 and len(ghost_days) == 0:
        camera_integrity_explains = True
    elif len(untrusted_days) >= 2 and len(untrusted_days) >= len(ghost_days):
        camera_integrity_explains = True

    # 4. Compute streak of healthy eligible days from the tail
    healthy_streak = 0
    for d in reversed(eligible_days):
        if d.status == "HEALTHY":
            healthy_streak += 1
        else:
            break

    # 5. Check pattern rule
    pattern_met, pattern_reason = check_ghost_pattern(eligible_days, t)

    # 6. Compute transparent score breakdown
    claimed_counts = [d.claimed_count for d in eligible_days if d.claimed_count > 0]
    score_breakdown = compute_ghost_score(eligible_days, claimed_counts, t) if eligible_days else None
    ghost_score = score_breakdown.ghost_score if score_breakdown else None

    # 7. State Machine with Hysteresis
    new_state: GhostState = previous_state
    explanation: dict[str, Any] = {
        "pattern_met": pattern_met,
        "pattern_reason": pattern_reason,
        "eligible_days": len(eligible_days),
        "ghost_days": len(ghost_days),
        "untrusted_days": len(untrusted_days),
        "camera_integrity_explains": camera_integrity_explains,
    }

    if score_breakdown:
        explanation.update(score_breakdown.to_dict())

    if camera_integrity_explains:
        # Untrusted camera explains low occupancy -> Never escalate to SUSPECTED_GHOST!
        # Revert or hold in NORMAL / WATCH with integrity explanation note
        new_state = "NORMAL" if previous_state in ("NORMAL", "RESOLVED") else "WATCH"
        explanation["reason"] = "Low occupancy explained by UNTRUSTED camera; integrity alert raised instead of ghost batch"
    else:
        # Standard ghost state machine
        if previous_state in ("SUSPECTED_GHOST", "ESCALATED"):
            # Check for recovery
            if healthy_streak >= t.recovery_r_consecutive:
                new_state = "RESOLVED"
                explanation["reason"] = f"Recovery: {healthy_streak} consecutive healthy eligible days (required {t.recovery_r_consecutive})"
            elif previous_state == "SUSPECTED_GHOST":
                # Check for escalation
                if (len(ghost_days) >= t.escalation_ghost_days or
                        (ghost_score is not None and ghost_score >= t.escalation_score_threshold)):
                    new_state = "ESCALATED"
                    explanation["reason"] = f"Escalated: sustained ghost pattern ({len(ghost_days)} ghost days, score {ghost_score})"
                else:
                    new_state = "SUSPECTED_GHOST"
            else:
                new_state = "ESCALATED"

        elif previous_state in ("NORMAL", "WATCH", "RESOLVED"):
            if pattern_met:
                new_state = "SUSPECTED_GHOST"
                explanation["reason"] = pattern_reason
            elif len(ghost_days) >= 1 or (score_breakdown and score_breakdown.cusum_score >= t.cusum_threshold):
                new_state = "WATCH"
                explanation["reason"] = f"Elevated watch: {len(ghost_days)} ghost day(s) detected"
            else:
                new_state = "NORMAL"
                explanation["reason"] = "Normal attendance patterns"

    # Per day detail for structured display
    per_day_detail = [
        {
            "date": d.date_str,
            "status": d.status,
            "claimed": d.claimed_count,
            "o_hat": d.o_hat,
            "ratio": d.ratio,
            "evidence_quality": d.evidence_quality,
            "session_ids": d.session_ids,
            "reason": d.reason,
        }
        for d in daily_evals
    ]

    return GhostBatchEvaluationResult(
        batch_id=batch_id,
        centre_id=centre_id,
        current_state=new_state,
        previous_state=previous_state,
        transitioned=(new_state != previous_state),
        window_start=window_start,
        window_end=window_end,
        eligible_days=len(eligible_days),
        ghost_days=len(ghost_days),
        nodata_days=len(nodata_days),
        untrusted_days=len(untrusted_days),
        pending_days=len(pending_days),
        hysteresis_ok_streak=healthy_streak,
        per_day_detail=per_day_detail,
        score_breakdown=score_breakdown,
        ghost_score=ghost_score,
        camera_integrity_explains=camera_integrity_explains,
        explanation=explanation,
        cause="evaluation",
    )
