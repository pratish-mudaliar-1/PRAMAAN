"""app/services/reconciliation.py — Reconciliation orchestration service.

Orchestrates database queries, feeds data into pure domain functions in
app.domain.reconciliation, writes flags and snapshots, and calculates risk scores.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import AbstractClock, system_clock
from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.db.models.centre import Centre, Zone
from app.db.models.flag import Flag, FlagInputSnapshot
from app.db.models.observation import Observation
from app.db.models.session_ import Batch, Session
from app.db.repositories.flag import FlagRepository
from app.db.repositories.session_ import SessionRepository
from app.domain.reconciliation import (
    ReconciliationResult,
    ThresholdConfig,
    WindowObservations,
    compute_risk_score,
    reconcile_attendance,
)

logger = get_logger(__name__)


class ReconciliationService:
    """Orchestrates session evaluation against observed edge observations."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
        clock: AbstractClock = system_clock,
    ) -> None:
        self._session = session
        self._cfg = settings or get_settings()
        self._clock = clock
        self._session_repo = SessionRepository(session)
        self._flag_repo = FlagRepository(session)

    async def reconcile_session(self, session_id: uuid.UUID) -> ReconciliationResult:
        """Reconcile a single training session against ingested observations."""
        sess = await self._session.get(Session, session_id)
        if not sess:
            raise NotFoundError(f"Session '{session_id}' not found")

        # 1. Query observations in scheduled session window
        obs_query = (
            select(Observation)
            .where(
                Observation.minute_ts >= sess.scheduled_start,
                Observation.minute_ts <= sess.scheduled_end,
            )
            .order_by(Observation.minute_ts.asc())
        )
        if sess.zone_id:
            obs_query = obs_query.where(Observation.zone_id == sess.zone_id)

        res = await self._session.execute(obs_query)
        observations = list(res.scalars().all())

        # 2. Extract values for domain computation
        start_ts = sess.scheduled_start if sess.scheduled_start.tzinfo else sess.scheduled_start.replace(tzinfo=UTC)
        end_ts = sess.scheduled_end if sess.scheduled_end.tzinfo else sess.scheduled_end.replace(tzinfo=UTC)

        scheduled_length = max(
            1,
            int((end_ts - start_ts).total_seconds() / 60),
        )
        now_ts = self._clock.utcnow()
        if start_ts <= now_ts < end_ts:
            # Session is currently in-progress: evaluate based on active observation stream
            total_minutes = max(len(observations), 1)
        else:
            total_minutes = scheduled_length


        # Filter untrusted observations — camera swap/tampering invalidates evidence
        trusted_observations = [
            o for o in observations
            if getattr(o, "trust", "TRUSTED") != "UNTRUSTED"
        ]

        persons_p90 = [
            o.persons_p90
            for o in trusted_observations
            if o.persons_p90 is not None and o.feed_health > 0.0
        ]
        # Treat feed health of untrusted observations as 0.0 so feed health fraction drops
        feed_health = [
            o.feed_health if getattr(o, "trust", "TRUSTED") != "UNTRUSTED" else 0.0
            for o in observations
        ]

        window = WindowObservations(
            persons_p90_values=persons_p90,
            feed_health_values=feed_health,
            total_minutes=total_minutes,
            trainer_count=sess.trainer_count or 0,
        )

        # 3. Load zone coverage factor and threshold profile
        coverage_factor = 1.0
        if sess.zone_id:
            zone = await self._session.get(Zone, sess.zone_id)
            if zone and zone.coverage_factor:
                coverage_factor = float(zone.coverage_factor)

        # Query active ThresholdProfile from DB if available
        from app.db.models.threshold import ThresholdProfile
        from app.events.bus import EventMessage, get_event_bus

        t_green = self._cfg.default_t_green
        t_amber = self._cfg.default_t_amber
        repeat_n = self._cfg.default_repeat_n
        min_feed_health = self._cfg.min_feed_health_fraction

        thresh_q = select(ThresholdProfile).where(ThresholdProfile.is_active == True).order_by(ThresholdProfile.version.desc())
        thresh_prof = (await self._session.execute(thresh_q)).scalars().first()
        if thresh_prof:
            t_green = thresh_prof.t_green
            t_amber = thresh_prof.t_amber
            repeat_n = thresh_prof.repeat_n
            min_feed_health = thresh_prof.min_feed_health_fraction

        cfg = ThresholdConfig(
            t_green=t_green,
            t_amber=t_amber,
            repeat_n=repeat_n,
            min_feed_health_fraction=min_feed_health,
            coverage_factor_k=coverage_factor,
        )

        # 4. Pure domain evaluation
        claimed = sess.claimed_count if sess.claimed_count is not None else 0
        result = reconcile_attendance(window, claimed_count=claimed, cfg=cfg)

        # 5. Update session entity
        now = self._clock.utcnow()
        sess.attendance_status = result.status
        sess.attendance_ratio = result.ratio
        sess.last_evaluated_at = now

        # 6. Raise / update flag if violation detected
        flag_key = f"FLAG:ATTENDANCE:{sess.id}"
        if result.status in ("RED", "AMBER"):
            batch = await self._session.get(Batch, sess.batch_id)
            centre_id = batch.centre_id if batch else uuid.uuid4()
            flag_type = "ATTENDANCE_RED" if result.status == "RED" else "ATTENDANCE_AMBER_REPEAT"

            flag = Flag(
                centre_id=centre_id,
                session_id=sess.id,
                zone_id=sess.zone_id,
                flag_key=flag_key,
                flag_type=flag_type,
                severity=result.status,
                status="OPEN",
                rule_name="attendance_p90_ratio",
                rule_version="v1",
                description=result.reason,
                risk_score=1.0 - (result.ratio or 0.0),
                window_start=sess.scheduled_start,
                window_end=sess.scheduled_end,
            )
            saved_flag, created = await self._flag_repo.upsert_by_key(flag)

            # Store immutable input snapshot for auditability
            if created:
                snapshot = FlagInputSnapshot(
                    flag_id=saved_flag.id,
                    inputs={
                        "claimed_count": claimed,
                        "trainer_count": sess.trainer_count,
                        "total_minutes": total_minutes,
                        "observations_count": len(observations),
                        "observed_hat": result.observed_hat,
                        "feed_health_fraction": result.feed_health_fraction,
                    },
                    thresholds={
                        "t_green": cfg.t_green,
                        "t_amber": cfg.t_amber,
                        "coverage_factor_k": cfg.coverage_factor_k,
                    },
                    model_version="recon-v1",
                )
                self._session.add(snapshot)

                # Publish event to bus
                try:
                    bus = get_event_bus()
                    await bus.publish(
                        EventMessage(
                            event_type="FLAG_CREATED",
                            centre_id=str(centre_id),
                            payload={
                                "flag_id": str(saved_flag.id),
                                "flag_type": flag_type,
                                "session_id": str(sess.id),
                                "severity": result.status,
                                "status": "OPEN",
                            },
                        )
                    )
                except Exception as bus_err:
                    logger.warning("event_publish_failed", error=str(bus_err))
        else:
            # If session is now NO_DATA / GREEN, resolve any previous open attendance flag
            existing_flag = await self._flag_repo.get_by_key(flag_key)
            if existing_flag and existing_flag.status == "OPEN":
                existing_flag.status = "RESOLVED"
                existing_flag.description = f"Resolved upon re-evaluation: {result.status} ({result.reason})"

        await self._session.flush()
        return result

    async def reevaluate_all(
        self,
        centre_id: uuid.UUID | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> dict[str, Any]:
        """Re-evaluate all sessions in scope and compute risk scores."""
        query = select(Session)
        if centre_id:
            query = query.join(Batch, Session.batch_id == Batch.id).where(Batch.centre_id == centre_id)
        if from_date:
            query = query.where(Session.scheduled_start >= from_date)
        if to_date:
            query = query.where(Session.scheduled_end <= to_date)

        res = await self._session.execute(query)
        sessions = list(res.scalars().all())

        evaluated = 0
        flags_raised = 0
        status_counts: dict[str, int] = {}

        for sess in sessions:
            r = await self.reconcile_session(sess.id)
            evaluated += 1
            status_counts[r.status] = status_counts.get(r.status, 0) + 1
            if r.status in ("RED", "AMBER"):
                flags_raised += 1

        return {
            "evaluated_sessions": evaluated,
            "flags_raised": flags_raised,
            "status_breakdown": status_counts,
        }
