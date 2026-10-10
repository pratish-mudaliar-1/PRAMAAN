"""app/api/v1/flags.py — Flag querying, explainability, and resolution endpoints."""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentPrincipal, DbSession
from app.core.errors import NotFoundError
from app.core.security.policy import Policy
from app.db.models.centre import Centre
from app.db.models.flag import Flag, FlagInputSnapshot

router = APIRouter(prefix="/flags", tags=["flags"])


class ResolveFlagRequest(BaseModel):
    resolution_reason: str | None = None
    note: str | None = None
    status: str = "CLOSED_DISMISSED"  # CLOSED_CONFIRMED or CLOSED_DISMISSED



@router.get("")
async def list_flags(
    principal: CurrentPrincipal,
    db: DbSession,
    centre_id: uuid.UUID | None = Query(default=None),
    severity: str | None = Query(default=None),
    flag_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """List flags with policy-aware scoping and filter parameters."""
    Policy.require_read(principal)

    query = select(Flag).join(Centre, Flag.centre_id == Centre.id)

    if "state_officer" in principal.roles and principal.state_code:
        query = query.where(Centre.state_code == principal.state_code)
    elif "inspector" in principal.roles or "training_centre" in principal.roles:
        c_uuids = [uuid.UUID(cid) for cid in principal.centre_ids if cid]
        query = query.where(Centre.id.in_(c_uuids))

    if centre_id:
        query = query.where(Flag.centre_id == centre_id)
    if severity:
        query = query.where(Flag.severity == severity)
    if flag_type:
        query = query.where(Flag.flag_type == flag_type)
    if status:
        query = query.where(Flag.status == status)

    query = query.order_by(Flag.created_at.desc()).limit(limit).offset(offset)
    res = await db.execute(query)
    flags = res.scalars().all()

    return {
        "items": [
            {
                "id": str(f.id),
                "centre_id": str(f.centre_id),
                "session_id": str(f.session_id) if f.session_id else None,
                "zone_id": str(f.zone_id) if f.zone_id else None,
                "flag_type": f.flag_type,
                "severity": f.severity,
                "status": f.status,
                "rule_name": f.rule_name,
                "description": f.description,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in flags
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/{flag_id}")
async def get_flag(
    flag_id: Annotated[uuid.UUID, Path()],
    principal: CurrentPrincipal,
    db: DbSession,
) -> dict[str, Any]:
    """Get single flag details including immutable input snapshot."""
    Policy.require_read(principal)

    flag = (await db.execute(select(Flag).where(Flag.id == flag_id))).scalar_one_or_none()
    if not flag:
        raise NotFoundError("Flag", str(flag_id))

    centre = (await db.execute(select(Centre).where(Centre.id == flag.centre_id))).scalar_one_or_none()
    if not centre:
        raise NotFoundError("Flag", str(flag_id))

    if "state_officer" in principal.roles and principal.state_code:
        if centre.state_code != principal.state_code:
            raise NotFoundError("Flag", str(flag_id))
    elif "inspector" in principal.roles or "training_centre" in principal.roles:
        if str(centre.id) not in principal.centre_ids:
            raise NotFoundError("Flag", str(flag_id))

    snapshot = (
        await db.execute(select(FlagInputSnapshot).where(FlagInputSnapshot.flag_id == flag_id))
    ).scalar_one_or_none()

    return {
        "id": str(flag.id),
        "centre_id": str(flag.centre_id),
        "session_id": str(flag.session_id) if flag.session_id else None,
        "zone_id": str(flag.zone_id) if flag.zone_id else None,
        "flag_type": flag.flag_type,
        "severity": flag.severity,
        "status": flag.status,
        "rule_name": flag.rule_name,
        "rule_version": flag.rule_version,
        "description": flag.description,
        "updated_at": flag.updated_at.isoformat() if flag.updated_at else None,
        "snapshot": {
            "inputs": snapshot.inputs if snapshot else {},
            "thresholds": snapshot.thresholds if snapshot else {},
            "model_version": snapshot.model_version if snapshot else None,
        } if snapshot else None,
        "created_at": flag.created_at.isoformat() if flag.created_at else None,
    }


@router.post("/{flag_id}/resolve")
async def resolve_flag(
    flag_id: Annotated[uuid.UUID, Path()],
    body: ResolveFlagRequest,
    principal: CurrentPrincipal,
    db: DbSession,
) -> dict[str, Any]:
    """Resolve/dismiss a flag (requires write permission)."""
    Policy.require_write(principal)

    flag = (await db.execute(select(Flag).where(Flag.id == flag_id))).scalar_one_or_none()
    if not flag:
        raise NotFoundError("Flag", str(flag_id))

    from datetime import UTC, datetime
    from app.db.repositories.audit import AuditRepository

    old_status = flag.status
    flag.status = body.status
    flag.updated_at = datetime.now(UTC)

    audit_repo = AuditRepository(db)
    await audit_repo.append(
        actor=principal.sub,
        action="FLAG_RESOLVE",
        resource_type="flag",
        resource_id=str(flag_id),
        detail={
            "flag_type": flag.flag_type,
            "centre_id": str(flag.centre_id),
            "old_status": old_status,
            "new_status": body.status,
            "note": body.note or body.resolution_reason or "",
        },
    )

    await db.commit()
    return {"status": "ok", "flag_id": str(flag.id), "new_status": flag.status}

