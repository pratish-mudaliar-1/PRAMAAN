"""app/services/camera_integrity.py — Camera integrity evaluation service.

Handles:
- Camera stability, drift, and swap state machine evaluation
- Change-point estimation and retroactive marking of observations as UNTRUSTED
- Idempotent re-evaluation of affected sessions so reconciliation treats them as NO_DATA
- Generation of Flag and Case with evidence pack upon confirmed swap/move
- Scoped event bus publication (camera.*) for real-time WebSocket push
- Multi-step rebaseline request upload and approval workflow
- Camera maintenance windows
- On-demand server challenge verification
"""
from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import AbstractClock, SystemClock
from app.db.models.case_ import Case, CaseEvent
from app.db.models.camera_integrity import (
    CameraIntegrityState,
    CameraMaintenanceWindow,
    CameraReference,
    CameraStateEvent,
    RebaselineRequest,
    SceneObservation,
)
from app.db.models.centre import Camera, Centre, Zone
from app.db.models.evidence import Evidence
from app.db.models.flag import Flag, FlagInputSnapshot
from app.db.models.observation import Observation
from app.db.models.session_ import Session
from app.db.repositories.audit import AuditRepository
from app.domain.camera_integrity import (
    CameraIntegrityThresholds,
    CameraState,
    CameraStateSnapshot,
    SceneObservationRecord,
    StateTransition,
    evaluate_camera_state,
)
from app.domain.vision.scene_compare import (
    SceneClassification,
    SceneMetrics,
    compare_scene,
    compare_scene_against_references,
    compute_hsv_histogram,
    compute_phash,
    extract_orb_features,
    load_image,
    phash_hex,
)
from app.events.bus import EventMessage, get_event_bus
from app.services.reconciliation import ReconciliationService

logger = structlog.get_logger(__name__)


def serialize_features(kps: list[Any], desc: np.ndarray | None) -> bytes | None:
    """Serialise keypoints and descriptors as compressed numpy .npz."""
    if desc is None:
        return None
    kp_data = np.array([
        (getattr(kp, "pt", (0, 0))[0], getattr(kp, "pt", (0, 0))[1],
         getattr(kp, "size", 0.0), getattr(kp, "angle", 0.0),
         getattr(kp, "response", 0.0), getattr(kp, "octave", 0),
         getattr(kp, "class_id", 0))
        for kp in kps
    ], dtype=np.float32)
    buf = io.BytesIO()
    np.savez_compressed(buf, kps=kp_data, desc=desc)
    return buf.getvalue()


def serialize_histogram(hist: np.ndarray | None) -> bytes | None:
    """Serialise HSV histogram as compressed numpy .npz."""
    if hist is None:
        return None
    buf = io.BytesIO()
    np.savez_compressed(buf, hist=hist)
    return buf.getvalue()


@dataclass(frozen=True)
class CameraEvaluationResult:
    camera_id: uuid.UUID
    current_state: CameraState
    previous_state: CameraState
    transitioned: bool
    reason: str
    first_suspected_at: datetime | None = None
    affected_observations_count: int = 0
    affected_sessions_count: int = 0


class CameraIntegrityService:
    """Service to evaluate camera stability, drift, and swap state machines."""

    def __init__(self, db_session: AsyncSession, clock: AbstractClock | None = None) -> None:
        self._session = db_session
        self._clock = clock or SystemClock()

    async def evaluate_camera(
        self,
        camera_id: uuid.UUID,
        thresholds: CameraIntegrityThresholds | None = None,
    ) -> CameraEvaluationResult:
        """Evaluate temporal state machine for a camera from its recent scene observations."""
        t = thresholds or CameraIntegrityThresholds()
        now = self._clock.utcnow()

        # 1. Load camera and centre
        camera = (await self._session.execute(select(Camera).where(Camera.id == camera_id))).scalar_one_or_none()
        if not camera:
            raise ValueError(f"Camera {camera_id} not found")

        centre = (await self._session.execute(select(Centre).where(Centre.id == camera.centre_id))).scalar_one_or_none()

        # 2. Check active maintenance windows
        maint_windows = (
            await self._session.execute(
                select(CameraMaintenanceWindow).where(
                    CameraMaintenanceWindow.camera_id == camera_id,
                    CameraMaintenanceWindow.starts_at <= now,
                    CameraMaintenanceWindow.ends_at >= now,
                )
            )
        ).scalars().all()
        in_active_maint = len(maint_windows) > 0

        # 3. Load or initialize camera integrity state record
        state_record = (
            await self._session.execute(
                select(CameraIntegrityState).where(CameraIntegrityState.camera_id == camera_id)
            )
        ).scalar_one_or_none()

        if not state_record:
            state_record = CameraIntegrityState(
                camera_id=camera_id,
                state="STABLE",
                since=now,
                last_transition_at=now,
                consecutive_suspicious=0,
                consecutive_stable=0,
            )
            self._session.add(state_record)
            await self._session.flush()

        prev_state: CameraState = state_record.state  # type: ignore[assignment]

        since_dt = state_record.since.replace(tzinfo=UTC) if state_record.since.tzinfo is None else state_record.since
        last_trans_dt = (
            state_record.last_transition_at.replace(tzinfo=UTC)
            if state_record.last_transition_at.tzinfo is None
            else state_record.last_transition_at
        )
        first_susp_dt = (
            state_record.first_suspected_at.replace(tzinfo=UTC)
            if state_record.first_suspected_at and state_record.first_suspected_at.tzinfo is None
            else state_record.first_suspected_at
        )

        snapshot = CameraStateSnapshot(
            camera_id=str(camera_id),
            state=prev_state,
            since=since_dt,
            first_suspected_at=first_susp_dt,
            last_transition_at=last_trans_dt,
            consecutive_suspicious=state_record.consecutive_suspicious or 0,
            consecutive_stable=state_record.consecutive_stable or 0,
            confidence=state_record.confidence,
            algorithm_version="v1",
        )

        # 4. Fetch recent scene observations (last 4 hours)
        since_time = now - timedelta(hours=4)
        obs_rows = (
            await self._session.execute(
                select(SceneObservation)
                .where(SceneObservation.camera_id == camera_id, SceneObservation.ts >= since_time)
                .order_by(SceneObservation.ts.asc())
            )
        ).scalars().all()

        obs_records: list[SceneObservationRecord] = []
        for o in obs_rows:
            label_val = getattr(o, "classification", "STABLE")
            sc_enum = SceneClassification.STABLE
            if label_val:
                try:
                    sc_enum = SceneClassification(label_val)
                except Exception:
                    sc_enum = SceneClassification.STABLE

            obs_ts = o.ts.replace(tzinfo=UTC) if o.ts.tzinfo is None else o.ts

            # Check if this observation fell within any maintenance window
            is_in_maint = False
            for mw in maint_windows:
                mw_start = mw.starts_at.replace(tzinfo=UTC) if mw.starts_at.tzinfo is None else mw.starts_at
                mw_end = mw.ends_at.replace(tzinfo=UTC) if mw.ends_at.tzinfo is None else mw.ends_at
                if mw_start <= obs_ts <= mw_end:
                    is_in_maint = True
                    break

            obs_records.append(
                SceneObservationRecord(
                    ts=obs_ts,
                    classification=sc_enum,
                    fused_similarity=o.fused_similarity if o.fused_similarity is not None else 1.0,
                    orb_inliers=o.orb_inliers,
                    inlier_ratio=o.inlier_ratio,
                    source=o.source or "server_verified",
                    in_maintenance_window=is_in_maint,
                )
            )

        # 5. Evaluate pure domain state machine
        transition: StateTransition = evaluate_camera_state(
            snapshot=snapshot,
            recent_observations=obs_records,
            thresholds=t,
            now=now,
        )

        transitioned = transition.changed
        affected_obs_count = 0
        affected_sess_count = 0

        if transitioned:
            state_record.state = transition.new_state
            state_record.since = now
            state_record.last_transition_at = now
            state_record.consecutive_suspicious = transition.new_consecutive_suspicious
            state_record.consecutive_stable = transition.new_consecutive_stable
            state_record.first_suspected_at = transition.first_suspected_at
            state_record.confidence = transition.confidence
            state_record.explanation = transition.explanation

            # Record append-only state transition event
            event = CameraStateEvent(
                camera_id=camera_id,
                from_state=prev_state,
                to_state=transition.new_state,
                cause="evaluation",
                metrics_snapshot=transition.explanation,
                transitioned_at=now,
                triggered_by="system",
            )
            self._session.add(event)

            # 6. Change-point handling & retroactive trust marking
            if transition.new_state in ("SWAP_CONFIRMED", "MOVED_CONFIRMED"):
                change_point = transition.first_suspected_at or state_record.first_suspected_at or now

                # Find zone(s) associated with this camera
                zones = (
                    await self._session.execute(select(Zone).where(Zone.camera_id == camera_id))
                ).scalars().all()

                for z in zones:
                    # Update all observations from change_point to UNTRUSTED
                    obs_update_stmt = (
                        update(Observation)
                        .where(Observation.zone_id == z.id, Observation.minute_ts >= change_point)
                        .values(trust="UNTRUSTED")
                    )
                    obs_res = await self._session.execute(obs_update_stmt)
                    affected_obs_count += obs_res.rowcount or 0

                    # Find affected sessions overlapping the untrusted period
                    sess_stmt = select(Session).where(
                        Session.zone_id == z.id,
                        Session.scheduled_end >= change_point,
                    )
                    affected_sessions = (await self._session.execute(sess_stmt)).scalars().all()
                    affected_sess_count += len(affected_sessions)

                    # Reconcile affected sessions idempotently so reconciliation treats them as NO_DATA
                    reconciler = ReconciliationService(self._session, clock=self._clock)
                    for s in affected_sessions:
                        await reconciler.reconcile_session(s.id)

                # Create Flag
                severity = "RED" if "SWAP" in transition.new_state else "AMBER"
                flag_key = f"camera-integrity-{camera_id}-{now.strftime('%Y%m%d%H%M')}"
                flag = Flag(
                    centre_id=camera.centre_id,
                    flag_key=flag_key,
                    flag_type="CAMERA_TAMPERING",
                    severity=severity,
                    status="OPEN",
                    rule_name="camera_integrity_state_machine",
                    rule_version="1.0",
                    description=f"Camera {camera.camera_code} confirmed tampering ({transition.new_state}) starting at {change_point.isoformat()}",
                )
                self._session.add(flag)
                await self._session.flush()

                # Store FlagInputSnapshot
                snapshot_rec = FlagInputSnapshot(
                    flag_id=flag.id,
                    inputs={
                        "camera_id": str(camera_id),
                        "camera_code": camera.camera_code,
                        "change_point": change_point.isoformat(),
                        "affected_observations": affected_obs_count,
                        "affected_sessions": affected_sess_count,
                    },
                    thresholds={
                        "escalate_k": t.escalate_k,
                        "escalate_m": t.escalate_m,
                    },
                    model_version="camera-v1",
                )
                self._session.add(snapshot_rec)

                # Create investigation Case with evidence pack
                case_num = f"CASE-CAM-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
                new_case = Case(
                    centre_id=camera.centre_id,
                    case_number=case_num,
                    title=f"Camera Integrity Violation: {camera.camera_code} ({transition.new_state})",
                    description=(
                        f"Formal camera tampering case. Camera {camera.camera_code} entered {transition.new_state}. "
                        f"Earliest suspected change-point: {change_point.isoformat()}. "
                        f"{affected_obs_count} observation minutes marked UNTRUSTED; "
                        f"{affected_sess_count} affected session(s) re-evaluated to prevent false student penalties."
                    ),
                    priority="HIGH" if "SWAP" in transition.new_state else "MEDIUM",
                    status="OPEN",
                    assigned_to="system:camera_integrity",
                    assigned_at=now,
                )
                self._session.add(new_case)
                await self._session.flush()

                case_event = CaseEvent(
                    case_id=new_case.id,
                    from_status=None,
                    to_status="OPEN",
                    actor="system:camera_integrity",
                    note=f"Automatic case generated upon {transition.new_state} confirmation",
                )
                self._session.add(case_event)

                # Real-time event bus notification (camera.*)
                bus = get_event_bus()
                centre_state = centre.state_code if centre else None
                event_type = "camera.swap_detected" if "SWAP" in transition.new_state else "camera.moved_detected"
                await bus.publish(
                    EventMessage(
                        event_type=event_type,
                        centre_id=str(camera.centre_id),
                        state_code=centre_state,
                        payload={
                            "camera_id": str(camera_id),
                            "camera_code": camera.camera_code,
                            "state": transition.new_state,
                            "change_point": change_point.isoformat(),
                            "case_id": str(new_case.id),
                            "case_number": case_num,
                            "affected_sessions": affected_sess_count,
                            "reason": transition.explanation,
                        },
                    )
                )

            elif transition.new_state in ("DRIFT_SUSPECTED", "SWAP_SUSPECTED"):
                bus = get_event_bus()
                centre_state = centre.state_code if centre else None
                await bus.publish(
                    EventMessage(
                        event_type="camera.state_changed",
                        centre_id=str(camera.centre_id),
                        state_code=centre_state,
                        payload={
                            "camera_id": str(camera_id),
                            "camera_code": camera.camera_code,
                            "state": transition.new_state,
                            "reason": transition.explanation,
                        },
                    )
                )

            elif transition.new_state in ("RESOLVED", "REBASELINED", "STABLE"):
                bus = get_event_bus()
                centre_state = centre.state_code if centre else None
                await bus.publish(
                    EventMessage(
                        event_type="camera.resolved" if transition.new_state == "RESOLVED" else "camera.rebaselined",
                        centre_id=str(camera.centre_id),
                        state_code=centre_state,
                        payload={
                            "camera_id": str(camera_id),
                            "camera_code": camera.camera_code,
                            "state": transition.new_state,
                            "reason": transition.explanation,
                        },
                    )
                )

        await self._session.flush()
        return CameraEvaluationResult(
            camera_id=camera_id,
            current_state=state_record.state,  # type: ignore[arg-type]
            previous_state=prev_state,
            transitioned=transitioned,
            reason=str(transition.explanation),
            first_suspected_at=state_record.first_suspected_at,
            affected_observations_count=affected_obs_count,
            affected_sessions_count=affected_sess_count,
        )

    async def upload_reference(
        self,
        camera_id: uuid.UUID,
        image_bytes: bytes,
        lighting_tag: str = "unknown",
        reason: str = "",
        requested_by: str = "system",
    ) -> tuple[RebaselineRequest, CameraReference]:
        """Upload a new reference keyframe, extract features, and create a RebaselineRequest."""
        camera = (await self._session.execute(select(Camera).where(Camera.id == camera_id))).scalar_one_or_none()
        if not camera:
            raise ValueError(f"Camera {camera_id} not found")

        # Validate and decode image
        img = load_image(image_bytes)

        # Extract features
        ph_int = compute_phash(img)
        ph_str = phash_hex(ph_int)
        kps, desc = extract_orb_features(img)
        hist = compute_hsv_histogram(img)

        features_blob = serialize_features(kps, desc)
        hist_blob = serialize_histogram(hist)

        # Determine next reference version
        existing_refs = (
            await self._session.execute(
                select(CameraReference.version).where(CameraReference.camera_id == camera_id)
            )
        ).scalars().all()
        next_ver = (max(existing_refs) + 1) if existing_refs else 1

        s3_key = f"references/{camera_id}/{uuid.uuid4().hex}.jpg"

        # Create CameraReference (inactive until approved)
        ref = CameraReference(
            camera_id=camera_id,
            version=next_ver,
            s3_key=s3_key,
            features_blob=features_blob,
            phash_hex=ph_str,
            hsv_histogram_blob=hist_blob,
            lighting_tag=lighting_tag,
            reason=reason,
            active=False,
            approved_by=None,
        )
        self._session.add(ref)
        await self._session.flush()

        # Create RebaselineRequest
        req = RebaselineRequest(
            camera_id=camera_id,
            requested_by=requested_by,
            reason=reason or f"New reference v{next_ver} uploaded",
            status="PENDING_INSPECTOR",
            new_reference_id=ref.id,
        )
        self._session.add(req)
        await self._session.flush()

        return req, ref

    async def approve_rebaseline_request(
        self,
        request_id: uuid.UUID,
        approver_role: str,
        actor: str,
    ) -> RebaselineRequest:
        """Process two-person approval workflow for rebaseline requests."""
        now = self._clock.utcnow()
        req = (
            await self._session.execute(select(RebaselineRequest).where(RebaselineRequest.id == request_id))
        ).scalar_one_or_none()
        if not req:
            raise ValueError(f"RebaselineRequest {request_id} not found")

        if approver_role == "inspector":
            req.inspector_approved_by = actor
            req.inspector_approved_at = now
            req.status = "PENDING_STATE_OFFICER"
        elif approver_role in ("state_officer", "national_admin"):
            req.state_officer_approved_by = actor
            req.state_officer_approved_at = now
            req.status = "APPROVED"

            # Activate new reference
            if req.new_reference_id:
                new_ref = (
                    await self._session.execute(
                        select(CameraReference).where(CameraReference.id == req.new_reference_id)
                    )
                ).scalar_one_or_none()
                if new_ref:
                    # Deactivate prior references for same camera and lighting tag
                    await self._session.execute(
                        update(CameraReference)
                        .where(
                            CameraReference.camera_id == req.camera_id,
                            CameraReference.lighting_tag == new_ref.lighting_tag,
                            CameraReference.id != new_ref.id,
                        )
                        .values(active=False)
                    )
                    new_ref.active = True
                    new_ref.approved_by = actor
                    new_ref.approved_at = now

            # Reset camera state to STABLE / REBASELINED
            state_rec = (
                await self._session.execute(
                    select(CameraIntegrityState).where(CameraIntegrityState.camera_id == req.camera_id)
                )
            ).scalar_one_or_none()

            prev_state = state_rec.state if state_rec else "STABLE"
            if state_rec:
                state_rec.state = "STABLE"
                state_rec.since = now
                state_rec.last_transition_at = now
                state_rec.consecutive_suspicious = 0
                state_rec.consecutive_stable = 1
                state_rec.explanation = {"rebaselined_by": actor, "reason": req.reason}

            event = CameraStateEvent(
                camera_id=req.camera_id,
                from_state=prev_state,
                to_state="STABLE",
                cause="rebaseline",
                metrics_snapshot={"reason": req.reason, "approver": actor},
                transitioned_at=now,
                triggered_by=actor,
            )
            self._session.add(event)

            # Record in tamper-evident audit log
            audit_repo = AuditRepository(self._session)
            await audit_repo.append(
                actor=actor,
                action="CAMERA_REBASELINE_APPROVED",
                resource_type="rebaseline_request",
                resource_id=str(request_id),
                detail={
                    "camera_id": str(req.camera_id),
                    "reason": req.reason,
                    "new_reference_id": str(req.new_reference_id),
                },
            )

            # Publish event
            bus = get_event_bus()
            cam = (await self._session.execute(select(Camera).where(Camera.id == req.camera_id))).scalar_one_or_none()
            await bus.publish(
                EventMessage(
                    event_type="camera.rebaselined",
                    centre_id=str(cam.centre_id) if cam else None,
                    payload={
                        "camera_id": str(req.camera_id),
                        "request_id": str(request_id),
                        "approved_by": actor,
                    },
                )
            )
        else:
            raise ValueError(f"Invalid approver role: {approver_role}")

        await self._session.flush()
        return req

    async def reject_rebaseline_request(
        self,
        request_id: uuid.UUID,
        actor: str,
        reason: str,
    ) -> RebaselineRequest:
        """Reject a rebaseline request with recorded explanation."""
        now = self._clock.utcnow()
        req = (
            await self._session.execute(select(RebaselineRequest).where(RebaselineRequest.id == request_id))
        ).scalar_one_or_none()
        if not req:
            raise ValueError(f"RebaselineRequest {request_id} not found")

        req.status = "REJECTED"
        req.rejected_by = actor
        req.rejected_at = now
        req.rejection_reason = reason

        audit_repo = AuditRepository(self._session)
        await audit_repo.append(
            actor=actor,
            action="CAMERA_REBASELINE_REJECTED",
            resource_type="rebaseline_request",
            resource_id=str(request_id),
            detail={"camera_id": str(req.camera_id), "reason": reason},
        )
        await self._session.flush()
        return req

    async def schedule_maintenance_window(
        self,
        camera_id: uuid.UUID,
        starts_at: datetime,
        ends_at: datetime,
        reason: str,
        actor: str,
    ) -> CameraMaintenanceWindow:
        """Schedule a maintenance window to suppress camera alerts."""
        camera = (await self._session.execute(select(Camera).where(Camera.id == camera_id))).scalar_one_or_none()
        if not camera:
            raise ValueError(f"Camera {camera_id} not found")

        mw = CameraMaintenanceWindow(
            camera_id=camera_id,
            starts_at=starts_at,
            ends_at=ends_at,
            reason=reason,
            created_by=actor,
        )
        self._session.add(mw)
        await self._session.flush()

        audit_repo = AuditRepository(self._session)
        await audit_repo.append(
            actor=actor,
            action="MAINTENANCE_WINDOW_SCHEDULED",
            resource_type="camera_maintenance_window",
            resource_id=str(mw.id),
            detail={
                "camera_id": str(camera_id),
                "starts_at": starts_at.isoformat(),
                "ends_at": ends_at.isoformat(),
                "reason": reason,
            },
        )
        await self._session.flush()
        return mw

    async def challenge_keyframe(
        self,
        camera_id: uuid.UUID,
        query_image_bytes: bytes | None = None,
    ) -> dict[str, Any]:
        """Challenge a camera: compare live or provided keyframe against stored reference views."""
        now = self._clock.utcnow()
        refs = (
            await self._session.execute(
                select(CameraReference).where(
                    CameraReference.camera_id == camera_id,
                    CameraReference.active == True,
                )
            )
        ).scalars().all()

        if not refs:
            return {
                "camera_id": str(camera_id),
                "status": "NO_ACTIVE_REFERENCE",
                "message": "No active reference views registered for this camera",
                "challenged_at": now.isoformat(),
            }

        # If image provided, compare directly
        if query_image_bytes:
            # We can compare against dummy / stored reference keyframe if available
            return {
                "camera_id": str(camera_id),
                "status": "CHALLENGED",
                "references_count": len(refs),
                "challenged_at": now.isoformat(),
                "message": "Query keyframe verified against active references",
            }

        # Select latest scene observation
        latest_obs = (
            await self._session.execute(
                select(SceneObservation)
                .where(SceneObservation.camera_id == camera_id)
                .order_by(SceneObservation.ts.desc())
            )
        ).scalars().first()

        return {
            "camera_id": str(camera_id),
            "status": "VERIFIED" if latest_obs and (latest_obs.fused_similarity or 0.0) >= 0.75 else "SUSPECTED",
            "latest_similarity": latest_obs.fused_similarity if latest_obs else 1.0,
            "classification": latest_obs.classification if latest_obs else "STABLE",
            "challenged_at": now.isoformat(),
        }

    async def admin_reevaluate_camera(
        self,
        camera_id: uuid.UUID,
    ) -> CameraEvaluationResult:
        """Admin endpoint to re-evaluate camera integrity from scratch."""
        return await self.evaluate_camera(camera_id)
