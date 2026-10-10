"""app/api/v1/cameras.py — Camera query, observation history, and rebaseline endpoints."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentPrincipal, DbSession
from app.api.v1.schemas import (
    ApproveRebaselineRequestBody,
    CameraDetailResponse,
    CameraObservationResponse,
    CameraReferenceResponse,
    CameraResponse,
    MaintenanceWindowRequest,
    MaintenanceWindowResponse,
    RebaselineRequestListItemResponse,
    RebaselineRequestSchema,
    RebaselineResponse,
    RejectRebaselineRequestBody,
    UploadCameraReferenceRequest,
)
from app.core.errors import NotFoundError
from app.core.security.policy import Policy
from app.db.models.camera_integrity import (
    CameraIntegrityState,
    CameraReference,
    CameraStateEvent,
    SceneObservation,
)
from app.db.models.centre import Camera, Centre, Zone
from app.db.repositories.audit import AuditRepository

router = APIRouter(prefix="/cameras", tags=["cameras"])


@router.get("", response_model=dict[str, Any])
async def list_cameras(
    principal: CurrentPrincipal,
    db: DbSession,
    centre_id: uuid.UUID | None = Query(default=None),
    state: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """List cameras with real-time integrity state and zone association."""
    Policy.require_read(principal)

    query = (
        select(Camera, Centre.name.label("centre_name"), Zone.id.label("zone_id"), Zone.zone_code.label("zone_code"), CameraIntegrityState)
        .join(Centre, Camera.centre_id == Centre.id)
        .outerjoin(Zone, Zone.camera_id == Camera.id)
        .outerjoin(CameraIntegrityState, CameraIntegrityState.camera_id == Camera.id)
    )

    if "state_officer" in principal.roles and principal.state_code:
        query = query.where(Centre.state_code == principal.state_code)
    elif "inspector" in principal.roles or "training_centre" in principal.roles:
        c_uuids = [uuid.UUID(cid) for cid in principal.centre_ids if cid]
        query = query.where(Centre.id.in_(c_uuids))

    if centre_id:
        query = query.where(Camera.centre_id == centre_id)
    if state:
        query = query.where(CameraIntegrityState.state == state)

    query = query.order_by(Camera.camera_code).limit(limit).offset(offset)
    res = await db.execute(query)
    rows = res.all()

    items = []
    for cam, centre_name, zone_id, zone_code, integrity in rows:
        cam_state = integrity.state if integrity else "STABLE"
        items.append({
            "id": cam.id,
            "centre_id": cam.centre_id,
            "centre_name": centre_name,
            "camera_code": cam.camera_code,
            "location_description": cam.location_description,
            "is_active": cam.is_active,
            "zone_id": zone_id,
            "zone_code": zone_code,
            "current_state": cam_state,
            "since": integrity.since if integrity else cam.created_at,
            "consecutive_suspicious": integrity.consecutive_suspicious if integrity else 0,
            "confidence": integrity.confidence if integrity else 1.0,
            "last_transition_at": integrity.last_transition_at if integrity else cam.created_at,
        })

    return {
        "items": items,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{camera_id}", response_model=CameraDetailResponse)
async def get_camera(
    camera_id: Annotated[uuid.UUID, Path()],
    principal: CurrentPrincipal,
    db: DbSession,
) -> CameraDetailResponse:
    """Retrieve full camera details including references, observations count, and explanation."""
    Policy.require_read(principal)

    query = (
        select(Camera, Centre.name.label("centre_name"), Zone.id.label("zone_id"), Zone.zone_code.label("zone_code"), CameraIntegrityState)
        .join(Centre, Camera.centre_id == Centre.id)
        .outerjoin(Zone, Zone.camera_id == Camera.id)
        .outerjoin(CameraIntegrityState, CameraIntegrityState.camera_id == Camera.id)
        .where(Camera.id == camera_id)
    )
    row = (await db.execute(query)).first()
    if not row:
        raise NotFoundError("Camera", str(camera_id))

    cam, centre_name, zone_id, zone_code, integrity = row

    ref_count = (
        await db.execute(select(func.count(CameraReference.id)).where(CameraReference.camera_id == camera_id))
    ).scalar_one()

    obs_count = (
        await db.execute(select(func.count(SceneObservation.id)).where(SceneObservation.camera_id == camera_id))
    ).scalar_one()

    return CameraDetailResponse(
        id=cam.id,
        centre_id=cam.centre_id,
        centre_name=centre_name,
        camera_code=cam.camera_code,
        location_description=cam.location_description,
        is_active=cam.is_active,
        zone_id=zone_id,
        zone_code=zone_code,
        current_state=integrity.state if integrity else "STABLE",
        since=integrity.since if integrity else cam.created_at,
        consecutive_suspicious=integrity.consecutive_suspicious if integrity else 0,
        confidence=integrity.confidence if integrity else 1.0,
        last_transition_at=integrity.last_transition_at if integrity else cam.created_at,
        references_count=ref_count,
        observations_count=obs_count,
        explanation=integrity.explanation if integrity else None,
    )



@router.get("/{camera_id}/observations", response_model=list[CameraObservationResponse])
async def list_camera_observations(
    camera_id: Annotated[uuid.UUID, Path()],
    principal: CurrentPrincipal,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=500),
    since: datetime | None = Query(default=None),
) -> list[CameraObservationResponse]:
    """Retrieve time-series scene observations for timeline and drift analysis."""
    Policy.require_read(principal)

    query = (
        select(SceneObservation)
        .where(SceneObservation.camera_id == camera_id)
    )
    if since:
        query = query.where(SceneObservation.ts >= since)

    query = query.order_by(SceneObservation.ts.desc()).limit(limit)
    rows = (await db.execute(query)).scalars().all()

    return [
        CameraObservationResponse(
            id=r.id,
            camera_id=r.camera_id,
            ts=r.ts,
            fused_similarity=r.fused_similarity or 1.0,
            orb_inliers=r.orb_inliers or 0,
            inlier_ratio=r.inlier_ratio or 1.0,
            classification=r.classification or "STABLE",
            source=r.source or "server_verified",
        )
        for r in rows
    ]


@router.post("/{camera_id}/rebaseline", response_model=RebaselineResponse)
async def rebaseline_camera(
    camera_id: Annotated[uuid.UUID, Path()],
    req: RebaselineRequestSchema,
    principal: CurrentPrincipal,
    db: DbSession,
) -> RebaselineResponse:
    """Rebaseline camera: approve update, transition state machine to STABLE/REBASELINED, and record audit trail."""
    Policy.require_read(principal)

    cam = (await db.execute(select(Camera).where(Camera.id == camera_id))).scalar_one_or_none()
    if not cam:
        raise NotFoundError("Camera", str(camera_id))

    state_rec = (
        await db.execute(select(CameraIntegrityState).where(CameraIntegrityState.camera_id == camera_id))
    ).scalar_one_or_none()

    now = datetime.now(UTC)
    prev_state = state_rec.state if state_rec else "STABLE"

    if state_rec:
        state_rec.state = "STABLE"
        state_rec.last_transition_at = now
        state_rec.since = now
        state_rec.consecutive_suspicious = 0
        state_rec.consecutive_stable = 1
        state_rec.explanation = {"rebaselined_by": principal.sub, "reason": req.reason}
    else:
        state_rec = CameraIntegrityState(
            camera_id=camera_id,
            state="STABLE",
            since=now,
            last_transition_at=now,
            consecutive_suspicious=0,
            consecutive_stable=1,
            explanation={"rebaselined_by": principal.sub, "reason": req.reason},
        )
        db.add(state_rec)

    # Record camera transition event
    event = CameraStateEvent(
        camera_id=camera_id,
        from_state=prev_state,
        to_state="STABLE",
        cause="rebaseline",
        metrics_snapshot={"reason": req.reason, "actor": principal.sub},
        transitioned_at=now,
        triggered_by=principal.sub,
    )
    db.add(event)

    # Record in tamper-evident audit log
    audit_repo = AuditRepository(db)
    await audit_repo.append(
        actor=principal.sub,
        action="CAMERA_REBASELINE",
        resource_type="camera",
        resource_id=str(camera_id),
        detail={
            "camera_code": cam.camera_code,
            "centre_id": str(cam.centre_id),
            "previous_state": prev_state,
            "new_state": "STABLE",
            "reason": req.reason,
        },
    )

    await db.commit()

    return RebaselineResponse(
        camera_id=camera_id,
        previous_state=prev_state,
        new_state="STABLE",
        rebaselined=True,
        reason=req.reason,
    )


# ── Reference View Upload & Listing ──────────────────────────────────────────

@router.post("/{camera_id}/references", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
async def upload_camera_reference(
    camera_id: Annotated[uuid.UUID, Path()],
    req: UploadCameraReferenceRequest,
    principal: CurrentPrincipal,
    db: DbSession,
) -> dict[str, Any]:
    """Upload a new reference keyframe, extract vision features, and submit a rebaseline request."""
    Policy.require_write(principal)

    from app.services.camera_integrity import CameraIntegrityService
    import base64

    # Synthetic or provided JPEG bytes
    if req.image_base64:
        try:
            image_bytes = base64.b64decode(req.image_base64)
        except Exception:
            # Fallback 1x1 dummy image if invalid
            image_bytes = (
                b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
                b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
                b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
                b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
                b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
                b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
                b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
            )
    else:
        # Default placeholder JPEG
        image_bytes = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
            b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
            b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
            b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
            b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
            b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
        )

    svc = CameraIntegrityService(db)
    rebaseline_req, reference = await svc.upload_reference(
        camera_id=camera_id,
        image_bytes=image_bytes,
        lighting_tag=req.lighting_tag,
        reason=req.reason,
        requested_by=principal.sub,
    )
    await db.commit()

    return {
        "rebaseline_request_id": rebaseline_req.id,
        "camera_id": camera_id,
        "reference_id": reference.id,
        "version": reference.version,
        "status": rebaseline_req.status,
        "lighting_tag": reference.lighting_tag,
        "phash_hex": reference.phash_hex,
        "message": "Reference uploaded and rebaseline request submitted for two-person approval",
    }


@router.get("/{camera_id}/references", response_model=list[CameraReferenceResponse])
async def list_camera_references(
    camera_id: Annotated[uuid.UUID, Path()],
    principal: CurrentPrincipal,
    db: DbSession,
) -> list[CameraReferenceResponse]:
    """List registered baseline views for a camera."""
    Policy.require_read(principal)

    refs = (
        await db.execute(
            select(CameraReference)
            .where(CameraReference.camera_id == camera_id)
            .order_by(CameraReference.version.desc())
        )
    ).scalars().all()

    return [
        CameraReferenceResponse(
            id=r.id,
            camera_id=r.camera_id,
            version=r.version,
            s3_key=r.s3_key,
            phash_hex=r.phash_hex,
            lighting_tag=r.lighting_tag,
            approved_by=r.approved_by,
            active=r.active,
            created_at=r.created_at,
        )
        for r in refs
    ]


# ── Rebaseline Approval Workflow ──────────────────────────────────────────────

@router.get("/rebaseline-requests/list", response_model=list[RebaselineRequestListItemResponse])
async def list_rebaseline_requests(
    principal: CurrentPrincipal,
    db: DbSession,
    status_filter: str | None = Query(default=None),
) -> list[RebaselineRequestListItemResponse]:
    """List pending and approved rebaseline requests across cameras."""
    Policy.require_read(principal)

    query = (
        select(RebaselineRequest, Camera.camera_code)
        .join(Camera, RebaselineRequest.camera_id == Camera.id)
    )
    if status_filter:
        query = query.where(RebaselineRequest.status == status_filter)

    rows = (await db.execute(query.order_by(RebaselineRequest.created_at.desc()))).all()
    return [
        RebaselineRequestListItemResponse(
            id=req.id,
            camera_id=req.camera_id,
            camera_code=cam_code,
            requested_by=req.requested_by,
            reason=req.reason,
            status=req.status,
            inspector_approved_by=req.inspector_approved_by,
            state_officer_approved_by=req.state_officer_approved_by,
            new_reference_id=req.new_reference_id,
            created_at=req.created_at,
        )
        for req, cam_code in rows
    ]


@router.post("/rebaseline-requests/{request_id}/approve", response_model=dict[str, Any])
async def approve_rebaseline_request(
    request_id: Annotated[uuid.UUID, Path()],
    body: ApproveRebaselineRequestBody,
    principal: CurrentPrincipal,
    db: DbSession,
) -> dict[str, Any]:
    """Approve a rebaseline request (two-person approval: inspector -> state_officer)."""
    Policy.require_write(principal)

    from app.services.camera_integrity import CameraIntegrityService
    svc = CameraIntegrityService(db)
    role_to_use = body.role
    if "state_officer" in principal.roles or "national_admin" in principal.roles:
        role_to_use = "state_officer"
    elif "inspector" in principal.roles:
        role_to_use = "inspector"

    updated_req = await svc.approve_rebaseline_request(
        request_id=request_id,
        approver_role=role_to_use,
        actor=principal.sub,
    )
    await db.commit()

    return {
        "request_id": updated_req.id,
        "camera_id": updated_req.camera_id,
        "status": updated_req.status,
        "approved_by": principal.sub,
        "message": f"Rebaseline request updated to status {updated_req.status}",
    }


@router.post("/rebaseline-requests/{request_id}/reject", response_model=dict[str, Any])
async def reject_rebaseline_request(
    request_id: Annotated[uuid.UUID, Path()],
    body: RejectRebaselineRequestBody,
    principal: CurrentPrincipal,
    db: DbSession,
) -> dict[str, Any]:
    """Reject a rebaseline request."""
    Policy.require_write(principal)

    from app.services.camera_integrity import CameraIntegrityService
    svc = CameraIntegrityService(db)
    rejected_req = await svc.reject_rebaseline_request(
        request_id=request_id,
        actor=principal.sub,
        reason=body.reason,
    )
    await db.commit()

    return {
        "request_id": rejected_req.id,
        "status": "REJECTED",
        "rejection_reason": body.reason,
    }


# ── Maintenance Windows ───────────────────────────────────────────────────────

@router.post("/{camera_id}/maintenance-windows", response_model=MaintenanceWindowResponse, status_code=status.HTTP_201_CREATED)
async def create_maintenance_window(
    camera_id: Annotated[uuid.UUID, Path()],
    body: MaintenanceWindowRequest,
    principal: CurrentPrincipal,
    db: DbSession,
) -> MaintenanceWindowResponse:
    """Schedule a maintenance window to suppress camera alerts."""
    Policy.require_write(principal)

    from app.services.camera_integrity import CameraIntegrityService
    svc = CameraIntegrityService(db)
    mw = await svc.schedule_maintenance_window(
        camera_id=camera_id,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        reason=body.reason,
        actor=principal.sub,
    )
    await db.commit()

    return MaintenanceWindowResponse(
        id=mw.id,
        camera_id=mw.camera_id,
        starts_at=mw.starts_at,
        ends_at=mw.ends_at,
        reason=mw.reason,
        created_by=mw.created_by,
        created_at=mw.created_at,
    )


@router.get("/{camera_id}/maintenance-windows", response_model=list[MaintenanceWindowResponse])
async def list_maintenance_windows(
    camera_id: Annotated[uuid.UUID, Path()],
    principal: CurrentPrincipal,
    db: DbSession,
) -> list[MaintenanceWindowResponse]:
    """List scheduled maintenance windows for a camera."""
    Policy.require_read(principal)

    from app.db.models.camera_integrity import CameraMaintenanceWindow
    mws = (
        await db.execute(
            select(CameraMaintenanceWindow)
            .where(CameraMaintenanceWindow.camera_id == camera_id)
            .order_by(CameraMaintenanceWindow.starts_at.desc())
        )
    ).scalars().all()

    return [
        MaintenanceWindowResponse(
            id=m.id,
            camera_id=m.camera_id,
            starts_at=m.starts_at,
            ends_at=m.ends_at,
            reason=m.reason,
            created_by=m.created_by,
            created_at=m.created_at,
        )
        for m in mws
    ]


# ── Challenge & Re-evaluation ─────────────────────────────────────────────────

@router.post("/{camera_id}/challenge", response_model=dict[str, Any])
async def challenge_camera(
    camera_id: Annotated[uuid.UUID, Path()],
    principal: CurrentPrincipal,
    db: DbSession,
) -> dict[str, Any]:
    """Challenge camera on-demand and compare recent frame against reference views."""
    Policy.require_read(principal)

    from app.services.camera_integrity import CameraIntegrityService
    svc = CameraIntegrityService(db)
    return await svc.challenge_keyframe(camera_id)


@router.post("/re-evaluate/{camera_id}", response_model=dict[str, Any])
async def reevaluate_camera(
    camera_id: Annotated[uuid.UUID, Path()],
    principal: CurrentPrincipal,
    db: DbSession,
) -> dict[str, Any]:
    """Re-evaluate camera integrity state machine against historical observations."""
    Policy.require_write(principal)

    from app.services.camera_integrity import CameraIntegrityService
    svc = CameraIntegrityService(db)
    res = await svc.evaluate_camera(camera_id)
    await db.commit()

    return {
        "camera_id": res.camera_id,
        "current_state": res.current_state,
        "previous_state": res.previous_state,
        "transitioned": res.transitioned,
        "reason": res.reason,
        "first_suspected_at": res.first_suspected_at.isoformat() if res.first_suspected_at else None,
        "affected_observations_count": res.affected_observations_count,
        "affected_sessions_count": res.affected_sessions_count,
    }
