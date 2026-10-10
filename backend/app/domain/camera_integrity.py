"""app/domain/camera_integrity.py — Pure camera integrity state machine.

ALL functions here are pure (no I/O, no side effects).
Inputs come from DB queries; outputs are transition decisions.

State machine:
  STABLE
    → DRIFT_SUSPECTED   (K-of-M suspicious observations, minimum duration)
  DRIFT_SUSPECTED
    → SWAP_SUSPECTED    (continued suspicious + corroborating signal)
    → STABLE            (recovery: K consecutive stable observations)
  SWAP_SUSPECTED
    → SWAP_CONFIRMED    (sustained evidence, mandatory corroboration)
    → MOVED_CONFIRMED   (geometry evidence shows physical move, not full swap)
    → STABLE            (recovery with hysteresis)
  SWAP_CONFIRMED | MOVED_CONFIRMED
    → RESOLVED          (after R stable observations AND rebaseline or manual override)
  Any state
    → REBASELINED       (after approved rebaseline request)

Honesty:
  Insufficient or untrusted data → NO transition (state unchanged).
  All thresholds are initial hypotheses; calibrate in pilot.
  These are leads for human review, never automatic penalties.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from app.domain.vision.scene_compare import SceneClassification


# ── Type aliases ──────────────────────────────────────────────────────────────

CameraState = Literal[
    "STABLE",
    "DRIFT_SUSPECTED",
    "SWAP_SUSPECTED",
    "SWAP_CONFIRMED",
    "MOVED_CONFIRMED",
    "RESOLVED",
    "REBASELINED",
]

TransitionCause = Literal[
    "evaluation",
    "retroactive",
    "maintenance_window",
    "rebaseline",
    "manual",
]


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SceneObservationRecord:
    """Input record for the state machine — loaded from scene_observation table.

    All fields are server-computed values; edge-reported values are stored
    separately and are NOT used as inputs to the state machine.
    """
    ts: datetime
    classification: SceneClassification
    fused_similarity: float | None         # server-computed [0, 1]
    orb_inliers: int | None                # server-computed
    inlier_ratio: float | None             # server-computed
    source: str                            # "edge_reported" | "server_verified"
    # Was this observation taken during a declared maintenance window?
    in_maintenance_window: bool = False


@dataclass(frozen=True)
class CameraIntegrityThresholds:
    """Thresholds for the camera integrity state machine.

    All values are initial hypotheses — calibrate in pilot.
    Load from ThresholdProfile.extra; these defaults apply only when no
    profile is available.
    """
    # K-of-M: K suspicious in M consecutive server_verified observations → escalate
    escalate_k: int = 3                    # [initial hypothesis]
    escalate_m: int = 5                    # [initial hypothesis]
    # Minimum wall-time across K suspicious observations
    escalate_min_duration: timedelta = field(
        default_factory=lambda: timedelta(hours=2)
    )                                      # [initial hypothesis]
    # Recovery: K consecutive STABLE observations → recover
    recovery_k_stable: int = 3            # [initial hypothesis]
    # Corroboration: require 2+ independent signals for SWAP_SUSPECTED → SWAP_CONFIRMED
    require_two_signals: bool = True       # [initial hypothesis]
    # Fused similarity below this = suspicious observation
    fused_suspicious_threshold: float = 0.50  # [initial hypothesis]
    # Minimum server_verified observations before any escalation
    min_server_verified: int = 2           # [initial hypothesis]


@dataclass(frozen=True)
class CameraStateSnapshot:
    """Current state machine snapshot (loaded from camera_integrity_state)."""
    camera_id: str
    state: CameraState
    since: datetime
    first_suspected_at: datetime | None
    last_transition_at: datetime
    consecutive_suspicious: int
    consecutive_stable: int
    confidence: float | None
    algorithm_version: str


@dataclass(frozen=True)
class StateTransition:
    """Result of evaluating the state machine against recent observations.

    If `new_state` equals `current_state` → no transition (state unchanged).
    """
    current_state: CameraState
    new_state: CameraState
    changed: bool
    confidence: float
    explanation: dict[str, object]
    new_consecutive_suspicious: int
    new_consecutive_stable: int
    # Change-point: earliest plausible swap time (set on first escalation)
    first_suspected_at: datetime | None
    cause: TransitionCause = "evaluation"


# ── Helper functions ──────────────────────────────────────────────────────────

def _is_suspicious(obs: SceneObservationRecord, t: CameraIntegrityThresholds) -> bool:
    """True if this observation is suspicious (not STABLE or LIGHTING_CHANGE)."""
    if obs.in_maintenance_window:
        return False
    if obs.classification in (
        SceneClassification.SWAPPED,
        SceneClassification.MOVED,
        SceneClassification.OCCLUDED,
    ):
        return True
    if obs.fused_similarity is not None and obs.fused_similarity < t.fused_suspicious_threshold:
        return True
    return False


def _count_independent_signals(
    suspicious_obs: list[SceneObservationRecord],
) -> int:
    """Count distinct independent signal types in a set of suspicious observations.

    Two signals are considered independent if:
    - They come from different sources (edge_reported vs server_verified), OR
    - They are server_verified but from different keyframes (always different).
    Returns the count of distinct source types observed.
    """
    sources = {obs.source for obs in suspicious_obs}
    # server_verified observations each represent an independent keyframe comparison
    server_verified_count = sum(
        1 for o in suspicious_obs if o.source == "server_verified"
    )
    if server_verified_count >= 2:
        return 2  # two independent server-side verifications
    if len(sources) >= 2:
        return 2  # both edge-reported and server-verified
    if server_verified_count == 1 and "edge_reported" in sources:
        return 2
    return len(sources)


def _estimate_change_point(
    observations: list[SceneObservationRecord],
    current_first_suspected: datetime | None,
) -> datetime | None:
    """Estimate the earliest plausible time a swap/move occurred.

    Strategy: find the timestamp of the LAST STABLE observation before the
    first suspicious one in the current window. If no stable observation
    exists before the first suspicious one, use the first suspicious timestamp.

    This is a conservative estimate — the real swap could have happened
    before the first suspicious observation but after the last stable one.
    """
    if not observations:
        return current_first_suspected

    sorted_obs = sorted(observations, key=lambda o: o.ts)

    # Find the last stable observation
    last_stable_ts: datetime | None = None
    first_suspicious_ts: datetime | None = None

    for obs in sorted_obs:
        if obs.classification in (SceneClassification.STABLE, SceneClassification.LIGHTING_CHANGE):
            last_stable_ts = obs.ts
        elif _is_suspicious_classification(obs.classification):
            if first_suspicious_ts is None:
                first_suspicious_ts = obs.ts

    if first_suspicious_ts is None:
        return current_first_suspected  # No change-point detected

    # Change-point is between last_stable and first_suspicious
    estimated = first_suspicious_ts
    if last_stable_ts is not None and last_stable_ts < first_suspicious_ts:
        # Midpoint as a conservative estimate
        mid_seconds = (first_suspicious_ts - last_stable_ts).total_seconds() / 2
        estimated = last_stable_ts + timedelta(seconds=mid_seconds)

    # Never move first_suspected_at forward (only earlier)
    if current_first_suspected is not None:
        return min(current_first_suspected, estimated)
    return estimated


def _is_suspicious_classification(cls: SceneClassification) -> bool:
    return cls in (
        SceneClassification.SWAPPED,
        SceneClassification.MOVED,
        SceneClassification.OCCLUDED,
    )


# ── Main state machine function ───────────────────────────────────────────────

def evaluate_camera_state(
    snapshot: CameraStateSnapshot,
    recent_observations: list[SceneObservationRecord],
    thresholds: CameraIntegrityThresholds | None = None,
    *,
    rebaseline_approved: bool = False,
    now: datetime | None = None,
) -> StateTransition:
    """Evaluate the camera integrity state machine against recent observations.

    Pure function — same inputs always produce the same output.

    Args:
        snapshot: current persisted state (from camera_integrity_state table).
        recent_observations: list of scene_observation rows to evaluate
            (typically the last M server_verified observations, newest first
            or oldest first — the function sorts by ts internally).
        thresholds: loaded from ThresholdProfile.extra; None = defaults.
        rebaseline_approved: if True, transition to REBASELINED regardless.
        now: evaluation timestamp (injectable for testing; defaults to newest obs ts).

    Returns:
        StateTransition — if changed=False, no DB update is needed.
    """
    t = thresholds or CameraIntegrityThresholds()

    if rebaseline_approved:
        return StateTransition(
            current_state=snapshot.state,
            new_state="REBASELINED",
            changed=snapshot.state != "REBASELINED",
            confidence=1.0,
            explanation={"reason": "rebaseline_approved"},
            new_consecutive_suspicious=0,
            new_consecutive_stable=0,
            first_suspected_at=None,
            cause="rebaseline",
        )

    # Sort observations oldest → newest
    obs = sorted(recent_observations, key=lambda o: o.ts)

    if not obs:
        # Nothing to evaluate
        return _no_transition(snapshot)

    # Filter to server_verified only for primary state machine decisions
    sv_obs = [o for o in obs if o.source == "server_verified" and not o.in_maintenance_window]

    if len(sv_obs) < t.min_server_verified:
        return _no_transition(snapshot, explanation={
            "reason": "INSUFFICIENT_EVIDENCE",
            "server_verified_count": len(sv_obs),
            "min_required": t.min_server_verified,
        })

    # Compute running counters from the tail of the observation list
    # (state machine uses the most recent M observations)
    window = sv_obs[-t.escalate_m:]
    suspicious_in_window = [o for o in window if _is_suspicious(o, t)]
    stable_in_window = [
        o for o in window
        if o.classification in (SceneClassification.STABLE, SceneClassification.LIGHTING_CHANGE)
    ]

    n_suspicious = len(suspicious_in_window)
    n_stable = len(stable_in_window)

    # Compute wall-time span of suspicious observations
    sus_duration = timedelta(0)
    if len(suspicious_in_window) >= 2:
        sus_duration = suspicious_in_window[-1].ts - suspicious_in_window[0].ts

    # Recovery streak (most recent consecutive stable)
    recovery_streak = 0
    for o in reversed(sv_obs):
        if o.classification in (SceneClassification.STABLE, SceneClassification.LIGHTING_CHANGE):
            recovery_streak += 1
        else:
            break

    # Independent signal count
    n_signals = _count_independent_signals(suspicious_in_window)

    # ── State machine transitions ──────────────────────────────────────────────

    current = snapshot.state

    # ── Recovery path (highest priority after rebaseline) ─────────────────────
    if current in ("SWAP_CONFIRMED", "MOVED_CONFIRMED", "SWAP_SUSPECTED", "DRIFT_SUSPECTED"):
        if recovery_streak >= t.recovery_k_stable:
            return StateTransition(
                current_state=current,
                new_state="RESOLVED" if current in ("SWAP_CONFIRMED", "MOVED_CONFIRMED") else "STABLE",
                changed=True,
                confidence=min(1.0, recovery_streak / t.recovery_k_stable),
                explanation={
                    "reason": "recovery",
                    "recovery_streak": recovery_streak,
                    "required": t.recovery_k_stable,
                },
                new_consecutive_suspicious=0,
                new_consecutive_stable=recovery_streak,
                first_suspected_at=snapshot.first_suspected_at,
                cause="evaluation",
            )

    # ── Escalation path ────────────────────────────────────────────────────────

    escalation_met = (
        n_suspicious >= t.escalate_k
        and sus_duration >= t.escalate_min_duration
    )
    corroboration_met = (
        (not t.require_two_signals) or n_signals >= 2
    )

    if current == "STABLE":
        if n_suspicious >= t.escalate_k:
            new_first_suspected = _estimate_change_point(obs, snapshot.first_suspected_at)
            return StateTransition(
                current_state="STABLE",
                new_state="DRIFT_SUSPECTED",
                changed=True,
                confidence=n_suspicious / t.escalate_m,
                explanation={
                    "reason": "suspicious_observations",
                    "n_suspicious": n_suspicious,
                    "window_size": len(window),
                    "threshold_k": t.escalate_k,
                    "classifications": [o.classification.value for o in suspicious_in_window],
                },
                new_consecutive_suspicious=n_suspicious,
                new_consecutive_stable=n_stable,
                first_suspected_at=new_first_suspected,
                cause="evaluation",
            )
        return _no_transition(snapshot)

    if current == "DRIFT_SUSPECTED":
        if escalation_met and corroboration_met:
            # Determine SWAP vs MOVED based on ORB inlier count
            moved_obs = [
                o for o in suspicious_in_window
                if o.classification == SceneClassification.MOVED
            ]
            swapped_obs = [
                o for o in suspicious_in_window
                if o.classification == SceneClassification.SWAPPED
            ]
            new_state: CameraState
            if len(moved_obs) > len(swapped_obs) and len(swapped_obs) == 0:
                new_state = "SWAP_SUSPECTED"  # will resolve to MOVED_CONFIRMED
            else:
                new_state = "SWAP_SUSPECTED"

            new_first = _estimate_change_point(obs, snapshot.first_suspected_at)
            return StateTransition(
                current_state="DRIFT_SUSPECTED",
                new_state=new_state,
                changed=True,
                confidence=min(1.0, n_suspicious / t.escalate_k),
                explanation={
                    "reason": "sustained_suspicious",
                    "n_suspicious": n_suspicious,
                    "n_signals": n_signals,
                    "duration_hours": sus_duration.total_seconds() / 3600,
                },
                new_consecutive_suspicious=n_suspicious,
                new_consecutive_stable=n_stable,
                first_suspected_at=new_first,
                cause="evaluation",
            )

        if n_suspicious < t.escalate_k // 2:
            # Dropping back — not enough sustained evidence
            return StateTransition(
                current_state="DRIFT_SUSPECTED",
                new_state="STABLE",
                changed=True,
                confidence=0.3,
                explanation={"reason": "insufficient_sustained_evidence"},
                new_consecutive_suspicious=n_suspicious,
                new_consecutive_stable=n_stable,
                first_suspected_at=None,
                cause="evaluation",
            )
        return _no_transition(snapshot)

    if current == "SWAP_SUSPECTED":
        if escalation_met and corroboration_met:
            # Confirm as SWAP or MOVED based on dominant classification
            moved_count = sum(
                1 for o in suspicious_in_window if o.classification == SceneClassification.MOVED
            )
            swapped_count = sum(
                1 for o in suspicious_in_window if o.classification == SceneClassification.SWAPPED
            )
            confirmed_state: CameraState = (
                "MOVED_CONFIRMED" if moved_count > swapped_count else "SWAP_CONFIRMED"
            )
            new_first = _estimate_change_point(obs, snapshot.first_suspected_at)
            return StateTransition(
                current_state="SWAP_SUSPECTED",
                new_state=confirmed_state,
                changed=True,
                confidence=min(1.0, n_suspicious / t.escalate_k + 0.1 * n_signals),
                explanation={
                    "reason": "confirmed",
                    "moved_observations": moved_count,
                    "swapped_observations": swapped_count,
                    "n_signals": n_signals,
                    "duration_hours": sus_duration.total_seconds() / 3600,
                },
                new_consecutive_suspicious=n_suspicious,
                new_consecutive_stable=n_stable,
                first_suspected_at=new_first,
                cause="evaluation",
            )
        return _no_transition(snapshot)

    # STABLE, RESOLVED, REBASELINED — check for fresh drift
    if current in ("RESOLVED", "REBASELINED"):
        if n_suspicious >= t.escalate_k:
            new_first = _estimate_change_point(obs, None)  # fresh event
            return StateTransition(
                current_state=current,
                new_state="DRIFT_SUSPECTED",
                changed=True,
                confidence=n_suspicious / t.escalate_m,
                explanation={
                    "reason": "fresh_drift_after_resolution",
                    "n_suspicious": n_suspicious,
                },
                new_consecutive_suspicious=n_suspicious,
                new_consecutive_stable=n_stable,
                first_suspected_at=new_first,
                cause="evaluation",
            )

    return _no_transition(snapshot)


def _no_transition(
    snapshot: CameraStateSnapshot,
    explanation: dict[str, object] | None = None,
) -> StateTransition:
    return StateTransition(
        current_state=snapshot.state,
        new_state=snapshot.state,
        changed=False,
        confidence=snapshot.confidence or 0.0,
        explanation=explanation or {"reason": "no_change"},
        new_consecutive_suspicious=snapshot.consecutive_suspicious,
        new_consecutive_stable=snapshot.consecutive_stable,
        first_suspected_at=snapshot.first_suspected_at,
        cause="evaluation",
    )


# ── Trust propagation helper ──────────────────────────────────────────────────

def compute_observation_trust(
    camera_state: CameraState,
    observation_ts: datetime,
    first_suspected_at: datetime | None,
) -> str:
    """Compute the trust level for one observation given camera state.

    Returns: "TRUSTED" | "UNTRUSTED" | "DEGRADED"

    Rules:
    - SWAP_CONFIRMED / MOVED_CONFIRMED AND obs_ts >= first_suspected_at → UNTRUSTED
    - SWAP_SUSPECTED / DRIFT_SUSPECTED AND obs_ts >= first_suspected_at → DEGRADED
    - All other cases → TRUSTED

    This function is called during retroactive trust updates AND during
    live reconciliation to determine whether to use an observation.
    """
    if camera_state in ("SWAP_CONFIRMED", "MOVED_CONFIRMED"):
        if first_suspected_at is not None and observation_ts >= first_suspected_at:
            return "UNTRUSTED"
    if camera_state in ("SWAP_SUSPECTED", "DRIFT_SUSPECTED"):
        if first_suspected_at is not None and observation_ts >= first_suspected_at:
            return "DEGRADED"
    return "TRUSTED"
