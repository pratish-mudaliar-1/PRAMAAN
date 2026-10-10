"""app/api/v1/sessions.py — Session querying endpoints."""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentPrincipal, DbSession
from app.core.errors import NotFoundError
from app.core.security.policy import Policy
from app.db.models.centre import Centre
from app.db.models.session_ import Batch, Session

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("")
async def list_sessions(
    principal: CurrentPrincipal,
    db: DbSession,
    centre_id: uuid.UUID | None = Query(default=None),
    batch_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """List sessions with optional filtering and row-level policy enforcement."""
    Policy.require_read(principal)

    query = select(Session).join(Batch, Session.batch_id == Batch.id).join(Centre, Batch.centre_id == Centre.id)

    if "state_officer" in principal.roles and principal.state_code:
        query = query.where(Centre.state_code == principal.state_code)
    elif "inspector" in principal.roles or "training_centre" in principal.roles:
        c_uuids = [uuid.UUID(cid) for cid in principal.centre_ids if cid]
        query = query.where(Centre.id.in_(c_uuids))

    if centre_id:
        query = query.where(Centre.id == centre_id)
    if batch_id:
        query = query.where(Session.batch_id == batch_id)
    if status:
        query = query.where(Session.attendance_status == status)

    query = query.order_by(Session.scheduled_start.desc()).limit(limit).offset(offset)
    res = await db.execute(query)
    sessions = res.scalars().all()

    return {
        "items": [
            {
                "id": str(s.id),
                "batch_id": str(s.batch_id),
                "zone_id": str(s.zone_id),
                "scheduled_start": s.scheduled_start.isoformat() if s.scheduled_start else None,
                "scheduled_end": s.scheduled_end.isoformat() if s.scheduled_end else None,
                "claimed_count": s.claimed_count,
                "trainer_count": s.trainer_count,
                "attendance_status": s.attendance_status,
                "attendance_ratio": s.attendance_ratio,
                "source_ref": s.source_ref,
            }
            for s in sessions

        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/{session_id}")
async def get_session(
    session_id: Annotated[uuid.UUID, Path()],
    principal: CurrentPrincipal,
    db: DbSession,
) -> dict[str, Any]:
    """Get single session details."""
    Policy.require_read(principal)

    query = (
        select(Session, Centre)
        .join(Batch, Session.batch_id == Batch.id)
        .join(Centre, Batch.centre_id == Centre.id)
        .where(Session.id == session_id)
    )
    row = (await db.execute(query)).first()
    if not row:
        raise NotFoundError("Session", str(session_id))

    sess, centre = row

    if "state_officer" in principal.roles and principal.state_code:
        if centre.state_code != principal.state_code:
            raise NotFoundError("Session", str(session_id))
    elif "inspector" in principal.roles or "training_centre" in principal.roles:
        if str(centre.id) not in principal.centre_ids:
            raise NotFoundError("Session", str(session_id))

    return {
        "id": str(sess.id),
        "batch_id": str(sess.batch_id),
        "zone_id": str(sess.zone_id),
        "scheduled_start": sess.scheduled_start.isoformat() if sess.scheduled_start else None,
        "scheduled_end": sess.scheduled_end.isoformat() if sess.scheduled_end else None,
        "claimed_count": sess.claimed_count,
        "trainer_count": sess.trainer_count,
        "attendance_status": sess.attendance_status,
        "attendance_ratio": sess.attendance_ratio,
        "last_evaluated_at": sess.last_evaluated_at.isoformat() if sess.last_evaluated_at else None,
    }
