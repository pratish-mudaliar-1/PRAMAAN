"""app/services/ghost_batch.py — Multi-day ghost batch detection service.

Orchestrates:
- Gathering sessions, timetable, and minute-level observations
- Evaluating camera trust for each session (isolating untrusted cameras from ghost accusations)
- Pure domain evaluation (IST local-day bucketing, eligibility gating, pattern rules, transparent indicators)
- Upserting GhostAssessment and recording GhostStateEvent transitions
- Automatic Case creation upon entering SUSPECTED_GHOST
- Flag creation with flag_type GHOST_BATCH_PATTERN
- Event bus publication (ghost.*) scoped by RBAC for WebSocket push
- Centre rollup risk score calculation
- Idempotent re-evaluation upon late-arriving data
"""
from __future__ import annotations

import statistics
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import AbstractClock, SystemClock
from app.db.models.case_ import Case, CaseEvent
from app.db.models.camera_integrity import CameraIntegrityState
from app.db.models.centre import Camera, Centre, Zone
from app.db.models.flag import Flag, FlagInputSnapshot
from app.db.models.ghost import GhostAssessment, GhostStateEvent
from app.db.models.observation import Observation
from app.db.models.session_ import Batch, Session
from app.domain.ghost_batch import (
    GhostBatchEvaluationResult,
    GhostState,
    GhostThresholds,
    SessionDayInput,
    evaluate_ghost_batch,
)
from app.events.bus import EventMessage, get_event_bus

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class CentreGhostRollupResult:
    centre_id: uuid.UUID
    centre_name: str
    total_batches: int
    normal_batches: int
    watch_batches: int
    suspected_ghost_batches: int
    escalated_batches: int
    resolved_batches: int
    centre_ghost_risk_score: float         # Aggregated risk score [0, 1]
    batch_assessments: list[dict[str, Any]]


class GhostBatchDetectionService:
    """Service to detect sustained ghost batches across sessions and multi-day windows."""

    def __init__(self, db_session: AsyncSession, clock: AbstractClock | None = None) -> None:
        self._session = db_session
        self._clock = clock or SystemClock()

    async def assess_batch(
        self,
        batch_id: uuid.UUID,
        thresholds: GhostThresholds | None = None,
    ) -> GhostBatchEvaluationResult:
        """Evaluate multi-day ghost batch pattern for a specific batch."""
        now = self._clock.utcnow()
        t = thresholds or GhostThresholds()

        # 1. Load batch and centre
        batch = (await self._session.execute(select(Batch).where(Batch.id == batch_id))).scalar_one_or_none()
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")

        centre = (await self._session.execute(select(Centre).where(Centre.id == batch.centre_id))).scalar_one_or_none()

        # 2. Fetch all scheduled sessions for this batch
        sessions = (
            await self._session.execute(
                select(Session)
                .where(Session.batch_id == batch_id)
                .order_by(Session.scheduled_start.asc())
            )
        ).scalars().all()

        # 3. For each session, determine observed occupancy, feed health, and camera trust
        session_inputs: list[SessionDayInput] = []

        for s in sessions:
            # Query observations for this session
            obs_stmt = select(Observation).where(
                Observation.minute_ts >= s.scheduled_start,
                Observation.minute_ts <= s.scheduled_end,
            )
            if s.zone_id:
                obs_stmt = obs_stmt.where(Observation.zone_id == s.zone_id)

            obs_rows = (await self._session.execute(obs_stmt)).scalars().all()

            # Determine camera trust
            cam_trust = "TRUSTED"
            if s.zone_id:
                zone = (await self._session.execute(select(Zone).where(Zone.id == s.zone_id))).scalar_one_or_none()
                if zone and zone.camera_id:
                    cam_state = (
                        await self._session.execute(
                            select(CameraIntegrityState).where(CameraIntegrityState.camera_id == zone.camera_id)
                        )
                    ).scalar_one_or_none()
                    if cam_state and cam_state.state in ("SWAP_CONFIRMED", "MOVED_CONFIRMED"):
                        # If session overlaps with swap change-point
                        if cam_state.first_suspected_at and s.scheduled_end >= cam_state.first_suspected_at:
                            cam_trust = "UNTRUSTED"

            # Check individual observations for untrusted markers
            if obs_rows:
                untrusted_count = sum(1 for o in obs_rows if getattr(o, "trust", "TRUSTED") == "UNTRUSTED")
                if untrusted_count > len(obs_rows) * 0.5:
                    cam_trust = "UNTRUSTED"

            # Compute effective observed occupancy (P90 of trusted observations)
            trusted_obs = [o for o in obs_rows if getattr(o, "trust", "TRUSTED") != "UNTRUSTED"]
            if trusted_obs:
                feed_health = statistics.mean(o.feed_health for o in trusted_obs)
                valid_counts = [o.persons_p90 for o in trusted_obs if o.persons_p90 is not None and o.feed_health > 0.0]
                o_hat = float(max(valid_counts)) if valid_counts else 0.0
            else:
                feed_health = 0.0 if obs_rows else 1.0  # Fallback
                o_hat = 0.0

            # Coverage factor k from zone
            k_factor = 1.0
            if s.zone_id:
                zone = (await self._session.execute(select(Zone).where(Zone.id == s.zone_id))).scalar_one_or_none()
                if zone and zone.coverage_factor:
                    k_factor = float(zone.coverage_factor)

            # If session was already reconciled, we can also read attendance_status
            att_status = s.attendance_status or "PENDING"

            session_inputs.append(
                SessionDayInput(
                    session_id=str(s.id),
                    scheduled_start=s.scheduled_start,
                    scheduled_end=s.scheduled_end,
                    claimed_count=s.claimed_count,
                    o_hat=o_hat,
                    feed_health=feed_health,
                    camera_trust=cam_trust,
                    attendance_status=att_status,
                    coverage_factor_k=k_factor,
                )
            )

        # 4. Fetch previous assessment record if exists
        assessment = (
            await self._session.execute(select(GhostAssessment).where(GhostAssessment.batch_id == batch_id))
        ).scalar_one_or_none()

        prev_state: GhostState = assessment.state if assessment else "NORMAL"  # type: ignore[assignment]
        prev_streak = assessment.hysteresis_ok_streak if assessment else 0

        # 5. Run pure domain evaluation
        result: GhostBatchEvaluationResult = evaluate_ghost_batch(
            batch_id=str(batch_id),
            centre_id=str(batch.centre_id),
            sessions=session_inputs,
            previous_state=prev_state,
            current_hysteresis_streak=prev_streak,
            thresholds=t,
            now=now,
        )

        # 6. Upsert GhostAssessment record
        if not assessment:
            assessment = GhostAssessment(
                batch_id=batch_id,
                centre_id=batch.centre_id,
                window_start=result.window_start,
                window_end=result.window_end,
                eligible_days=result.eligible_days,
                ghost_days=result.ghost_days,
                nodata_days=result.nodata_days,
                untrusted_days=result.untrusted_days,
                pending_days=result.pending_days,
                per_day_detail=result.per_day_detail,
                ghost_score=result.ghost_score,
                state=result.current_state,
                hysteresis_ok_streak=result.hysteresis_ok_streak,
                explanation=result.explanation,
                algorithm_version="v1",
                computed_at=now,
            )
            self._session.add(assessment)
            await self._session.flush()
        else:
            assessment.window_start = result.window_start
            assessment.window_end = result.window_end
            assessment.eligible_days = result.eligible_days
            assessment.ghost_days = result.ghost_days
            assessment.nodata_days = result.nodata_days
            assessment.untrusted_days = result.untrusted_days
            assessment.pending_days = result.pending_days
            assessment.per_day_detail = result.per_day_detail
            assessment.ghost_score = result.ghost_score
            assessment.state = result.current_state
            assessment.hysteresis_ok_streak = result.hysteresis_ok_streak
            assessment.explanation = result.explanation
            assessment.computed_at = now

        # 7. Record append-only GhostStateEvent on state change
        if result.transitioned:
            event = GhostStateEvent(
                batch_id=batch_id,
                assessment_id=assessment.id,
                from_state=prev_state,
                to_state=result.current_state,
                cause="evaluation",
                metrics_snapshot=result.explanation,
                transitioned_at=now,
            )
            self._session.add(event)

            centre_state = centre.state_code if centre else None

            # Handle entry into SUSPECTED_GHOST or ESCALATED
            if result.current_state in ("SUSPECTED_GHOST", "ESCALATED"):
                # Raise Flag with flag_type GHOST_BATCH_PATTERN
                flag_key = f"ghost-batch-pattern-{batch_id}-{now.strftime('%Y%m%d')}"
                flag = Flag(
                    centre_id=batch.centre_id,
                    flag_key=flag_key,
                    flag_type="GHOST_BATCH_PATTERN",
                    severity="RED",
                    status="OPEN",
                    rule_name="multi_day_ghost_batch_pattern",
                    rule_version="1.0",
                    description=(
                        f"Batch {batch.batch_code} ({batch.trade_code or 'General'}) met ghost pattern criteria: "
                        f"{result.ghost_days} ghost days of {result.eligible_days} eligible days. "
                        f"Score: {(result.ghost_score or 0.0) * 100:.1f}/100. Lead for human review."
                    ),
                    risk_score=result.ghost_score or 0.0,
                )
                self._session.add(flag)
                await self._session.flush()

                # Store snapshot
                snapshot = FlagInputSnapshot(
                    flag_id=flag.id,
                    inputs={
                        "batch_id": str(batch_id),
                        "batch_code": batch.batch_code,
                        "eligible_days": result.eligible_days,
                        "ghost_days": result.ghost_days,
                        "untrusted_days": result.untrusted_days,
                        "score_breakdown": result.score_breakdown.to_dict() if result.score_breakdown else {},
                    },
                    thresholds={
                        "min_eligible_days": t.min_eligible_days,
                        "m_of_n": f"{t.m_of_n_m}_of_{t.m_of_n_n}",
                        "l_consecutive": t.l_consecutive,
                        "ghost_ratio_threshold": t.ghost_ratio_threshold,
                    },
                    model_version="ghost-v1",
                )
                self._session.add(snapshot)

                # Automatically open investigation Case
                case_num = f"CASE-GHOST-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
                new_case = Case(
                    centre_id=batch.centre_id,
                    case_number=case_num,
                    title=f"Ghost Batch Pattern: {batch.batch_code} ({batch.trade_code or 'General'})",
                    description=(
                        f"Formal review case opened for batch {batch.batch_code}. "
                        f"Multi-day evaluation detected persistent attendance deficit across {result.ghost_days} "
                        f"of {result.eligible_days} eligible days. Ghost Score: {(result.ghost_score or 0.0) * 100:.1f}/100. "
                        f"Note: This is an analytical lead for reviewer verification, not an automated penalty."
                    ),
                    priority="HIGH" if result.current_state == "ESCALATED" else "MEDIUM",
                    status="OPEN",
                    assigned_to="system:ghost_detector",
                    assigned_at=now,
                )
                self._session.add(new_case)
                await self._session.flush()

                case_event = CaseEvent(
                    case_id=new_case.id,
                    from_status=None,
                    to_status="OPEN",
                    actor="system:ghost_detector",
                    note=f"Automatic investigation case generated for {result.current_state}",
                )
                self._session.add(case_event)
                assessment.case_id = new_case.id

                # Broadcast scoped ghost.* events
                bus = get_event_bus()
                ev_name = "ghost.suspected" if result.current_state == "SUSPECTED_GHOST" else "ghost.escalated"
                await bus.publish(
                    EventMessage(
                        event_type=ev_name,
                        centre_id=str(batch.centre_id),
                        state_code=centre_state,
                        payload={
                            "batch_id": str(batch_id),
                            "batch_code": batch.batch_code,
                            "state": result.current_state,
                            "ghost_score": result.ghost_score,
                            "case_id": str(new_case.id),
                            "case_number": case_num,
                            "reason": result.explanation,
                        },
                    )
                )

            elif result.current_state == "RESOLVED":
                # Resolve open ghost flags
                open_flags = (
                    await self._session.execute(
                        select(Flag).where(
                            Flag.centre_id == batch.centre_id,
                            Flag.flag_type == "GHOST_BATCH_PATTERN",
                            Flag.status == "OPEN",
                        )
                    )
                ).scalars().all()
                for fl in open_flags:
                    fl.status = "RESOLVED"
                    fl.description += f" [Resolved on {now.strftime('%Y-%m-%d')}: recovery streak achieved]"

                bus = get_event_bus()
                await bus.publish(
                    EventMessage(
                        event_type="ghost.resolved",
                        centre_id=str(batch.centre_id),
                        state_code=centre_state,
                        payload={
                            "batch_id": str(batch_id),
                            "batch_code": batch.batch_code,
                            "state": "RESOLVED",
                            "reason": result.explanation,
                        },
                    )
                )

            elif result.current_state in ("WATCH", "NORMAL"):
                bus = get_event_bus()
                await bus.publish(
                    EventMessage(
                        event_type="ghost.state_changed",
                        centre_id=str(batch.centre_id),
                        state_code=centre_state,
                        payload={
                            "batch_id": str(batch_id),
                            "batch_code": batch.batch_code,
                            "state": result.current_state,
                            "reason": result.explanation,
                        },
                    )
                )

        await self._session.flush()
        return result

    async def assess_centre_ghost_batches(
        self,
        centre_id: uuid.UUID,
    ) -> CentreGhostRollupResult:
        """Roll up ghost batch risk across all batches in a training centre."""
        centre = (await self._session.execute(select(Centre).where(Centre.id == centre_id))).scalar_one_or_none()
        if not centre:
            raise ValueError(f"Centre {centre_id} not found")

        batches = (
            await self._session.execute(select(Batch).where(Batch.centre_id == centre_id))
        ).scalars().all()

        total = len(batches)
        normal_count = 0
        watch_count = 0
        suspected_count = 0
        escalated_count = 0
        resolved_count = 0
        scores: list[float] = []
        batch_assessments: list[dict[str, Any]] = []

        for b in batches:
            ass = (
                await self._session.execute(select(GhostAssessment).where(GhostAssessment.batch_id == b.id))
            ).scalar_one_or_none()

            st = ass.state if ass else "NORMAL"
            score = float(ass.ghost_score or 0.0) if ass and ass.ghost_score is not None else 0.0

            if st == "NORMAL":
                normal_count += 1
            elif st == "WATCH":
                watch_count += 1
            elif st == "SUSPECTED_GHOST":
                suspected_count += 1
                scores.append(score)
            elif st == "ESCALATED":
                escalated_count += 1
                scores.append(score)
            elif st == "RESOLVED":
                resolved_count += 1

            batch_assessments.append({
                "batch_id": str(b.id),
                "batch_code": b.batch_code,
                "trade_code": b.trade_code,
                "state": st,
                "ghost_score": score,
                "eligible_days": ass.eligible_days if ass else 0,
                "ghost_days": ass.ghost_days if ass else 0,
            })

        # Calculate rolled up centre risk factor
        # Weight suspected/escalated batches heavily
        if total > 0:
            suspected_fraction = (suspected_count + 1.5 * escalated_count + 0.3 * watch_count) / total
            mean_score = statistics.mean(scores) if scores else 0.0
            rollup_risk = min(1.0, 0.6 * suspected_fraction + 0.4 * mean_score)
        else:
            rollup_risk = 0.0

        return CentreGhostRollupResult(
            centre_id=centre_id,
            centre_name=centre.name,
            total_batches=total,
            normal_batches=normal_count,
            watch_batches=watch_count,
            suspected_ghost_batches=suspected_count,
            escalated_batches=escalated_count,
            resolved_batches=resolved_count,
            centre_ghost_risk_score=round(rollup_risk, 3),
            batch_assessments=batch_assessments,
        )

    async def admin_reevaluate_batch(
        self,
        batch_id: uuid.UUID,
    ) -> GhostBatchEvaluationResult:
        """Idempotently re-evaluate a batch (used upon late attendance data ingestion)."""
        return await self.assess_batch(batch_id)
