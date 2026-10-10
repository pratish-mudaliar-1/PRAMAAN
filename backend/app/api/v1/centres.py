"""app/api/v1/centres.py — Centre querying and risk score endpoints."""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentPrincipal, DbSession
from app.api.v1.schemas import CentreDetailResponse, CentreResponse, ZoneResponse
from app.core.errors import NotFoundError
from app.core.security.policy import Policy
from app.db.models.centre import Centre, Zone
from app.db.models.device import Device
from app.db.models.flag import Flag
from app.db.models.session_ import Batch, Session
from app.domain.reconciliation import compute_risk_score

router = APIRouter(prefix="/centres", tags=["centres"])


async def _enrich_centre_metrics(
    c: Centre,
    db: AsyncSession,
) -> dict[str, Any]:
    """Compute real database-backed rollup metrics for a single centre."""
    cid = c.id

    # 1. Flags rollup
    flag_rows = (
        await db.execute(
            select(Flag.flag_type, Flag.status).where(Flag.centre_id == cid)
        )
    ).all()

    open_flags = sum(1 for f in flag_rows if f.status == "OPEN")
    suspected_swaps = sum(
        1 for f in flag_rows
        if f.status == "OPEN" and ("SWAP" in f.flag_type or "CAMERA" in f.flag_type)
    )
    suspected_ghosts = sum(
        1 for f in flag_rows
        if f.status == "OPEN" and "GHOST" in f.flag_type
    )

    # 2. Devices / Heartbeat
    dev_rows = (
        await db.execute(
            select(Device.last_heartbeat_at, Device.status).where(Device.centre_id == cid)
        )
    ).all()

    latest_hb = None
    all_offline = len(dev_rows) > 0
    for d in dev_rows:
        if d.last_heartbeat_at:
            if latest_hb is None or d.last_heartbeat_at > latest_hb:
                latest_hb = d.last_heartbeat_at
        if d.status == "ACTIVE":
            all_offline = False

    # 3. Sessions status
    session_rows = (
        await db.execute(
            select(Session.attendance_status)
            .join(Batch, Session.batch_id == Batch.id)
            .where(Batch.centre_id == cid)
        )
    ).all()

    red_sessions = sum(1 for s in session_rows if s.attendance_status == "RED")
    amber_sessions = sum(1 for s in session_rows if s.attendance_status == "AMBER")

    # Status derivation: RED > AMBER > NO_DATA > GREEN
    if red_sessions > 0:
        overall_status = "RED"
    elif amber_sessions > 0:
        overall_status = "AMBER"
    elif all_offline or (len(dev_rows) > 0 and latest_hb is None):
        overall_status = "NO_DATA"
    else:
        overall_status = "GREEN"

    # Risk score calculation
    risk_result = compute_risk_score(
        red_flag_count=red_sessions,
        amber_flag_count=amber_sessions,
        integrity_event_count=suspected_swaps,
        device_offline_count=1 if all_offline else 0,
    )
    risk_tier = "HIGH" if risk_result.score >= 0.7 else ("MEDIUM" if risk_result.score >= 0.4 else "LOW")

    return {
        "id": c.id,
        "name": c.name,
        "code": c.code,
        "state_code": c.state_code,
        "district": c.district,
        "scheme_code": c.scheme_code,
        "registration_no": c.registration_no,
        "is_active": c.is_active,
        "lat": c.latitude,
        "lng": c.longitude,
        "status": overall_status,
        "open_flags": open_flags,
        "suspected_swaps": suspected_swaps,
        "suspected_ghosts": suspected_ghosts,
        "last_heartbeat": latest_hb,
        "risk_score": risk_result.score,
        "risk_tier": risk_tier,
    }


@router.get("")
async def list_centres(
    principal: CurrentPrincipal,
    db: DbSession,
    state_code: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """List training centres with live derived operational metrics."""
    Policy.require_read(principal)

    query = select(Centre)
    if "state_officer" in principal.roles and principal.state_code:
        query = query.where(Centre.state_code == principal.state_code)
    elif "inspector" in principal.roles or "training_centre" in principal.roles:
        c_uuids = [uuid.UUID(cid) for cid in principal.centre_ids if cid]
        query = query.where(Centre.id.in_(c_uuids))
    elif state_code:
        query = query.where(Centre.state_code == state_code)

    query = query.order_by(Centre.name).limit(limit).offset(offset)
    res = await db.execute(query)
    centres = res.scalars().all()

    items = []
    for c in centres:
        enriched = await _enrich_centre_metrics(c, db)
        items.append(enriched)

    return {
        "items": items,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{centre_id}")
async def get_centre(
    centre_id: Annotated[uuid.UUID, Path()],
    principal: CurrentPrincipal,
    db: DbSession,
) -> dict[str, Any]:
    """Retrieve details for a specific centre with live rollup metrics and zones."""
    Policy.require_read(principal)
    query = select(Centre).where(Centre.id == centre_id)
    centre = (await db.execute(query)).scalar_one_or_none()
    if not centre:
        raise NotFoundError(f"Centre {centre_id} not found")

    # Verify tenant access
    if "state_officer" in principal.roles and principal.state_code:
        if centre.state_code != principal.state_code:
            raise NotFoundError(f"Centre {centre_id} not found")
    elif "inspector" in principal.roles or "training_centre" in principal.roles:
        if str(centre.id) not in principal.centre_ids:
            raise NotFoundError(f"Centre {centre_id} not found")

    zones = (await db.execute(select(Zone).where(Zone.centre_id == centre_id))).scalars().all()
    enriched = await _enrich_centre_metrics(centre, db)
    enriched["zones"] = [
        {
            "id": z.id,
            "zone_code": z.zone_code,
            "zone_type": z.zone_type,
            "coverage_factor": float(z.coverage_factor or 1.0),
        }
        for z in zones
    ]

    return enriched


@router.get("/{centre_id}/risk")
async def get_centre_risk(
    centre_id: Annotated[uuid.UUID, Path()],
    principal: CurrentPrincipal,
    db: DbSession,
) -> dict[str, Any]:
    """Calculate and return real-time risk breakdown for a centre."""
    Policy.require_read(principal)
    centre = (await db.execute(select(Centre).where(Centre.id == centre_id))).scalar_one_or_none()
    if not centre:
        raise NotFoundError("Centre", str(centre_id))

    from app.db.models.flag import Flag
    from app.db.models.session_ import Session

    flags = (await db.execute(select(Flag).where(Flag.centre_id == centre_id))).scalars().all()
    sessions = (
        await db.execute(
            select(Session).join(Batch, Session.batch_id == Batch.id).where(Batch.centre_id == centre_id)
        )
    ).scalars().all()

    red_count = sum(1 for s in sessions if s.attendance_status == "RED")
    amber_count = sum(1 for s in sessions if s.attendance_status == "AMBER")
    ghost_count = sum(1 for f in flags if f.flag_type == "GHOST_BATCH")

    result = compute_risk_score(
        red_flag_count=red_count,
        amber_flag_count=amber_count,
        integrity_event_count=0,
        device_offline_count=0,
    )

    tier = "HIGH" if result.score >= 0.7 else ("MEDIUM" if result.score >= 0.4 else "LOW")

    return {
        "centre_id": str(centre_id),
        "risk_score": result.score,
        "risk_tier": tier,
        "explanation": result.explanation,
        "red_sessions": red_count,
        "amber_sessions": amber_count,
        "ghost_batch_flags": ghost_count,
        "total_sessions": len(sessions),
    }
