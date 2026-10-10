"""app/api/v1/cases.py — Case management and human review workflow endpoints."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentPrincipal, DbSession
from app.core.errors import NotFoundError
from app.core.security.policy import Policy
from app.db.models.case_ import Case, CaseEvent, TCResponse
from app.db.models.centre import Centre
from app.db.models.flag import Flag

router = APIRouter(prefix="/cases", tags=["cases"])


class CreateCaseRequest(BaseModel):
    centre_id: uuid.UUID
    title: str = Field(..., max_length=256)
    description: str | None = None
    priority: str = "MEDIUM"
    flag_ids: list[uuid.UUID] = Field(default_factory=list)


class AddCaseEventRequest(BaseModel):
    to_status: str
    note: str | None = None


class TCResponseRequest(BaseModel):
    response_text: str
    attachment_s3_keys: list[str] = Field(default_factory=list)


@router.get("")
async def list_cases(
    principal: CurrentPrincipal,
    db: DbSession,
    centre_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """List cases scoped by caller's role and tenant."""
    Policy.require_read(principal)

    query = select(Case).join(Centre, Case.centre_id == Centre.id)

    if "state_officer" in principal.roles and principal.state_code:
        query = query.where(Centre.state_code == principal.state_code)
    elif "inspector" in principal.roles or "training_centre" in principal.roles:
        c_uuids = [uuid.UUID(cid) for cid in principal.centre_ids if cid]
        query = query.where(Centre.id.in_(c_uuids))

    if centre_id:
        query = query.where(Case.centre_id == centre_id)
    if status:
        query = query.where(Case.status == status)
    if priority:
        query = query.where(Case.priority == priority)

    query = query.order_by(Case.created_at.desc()).limit(limit).offset(offset)
    res = await db.execute(query)
    cases = res.scalars().all()

    return {
        "items": [
            {
                "id": str(c.id),
                "case_number": c.case_number,
                "centre_id": str(c.centre_id),
                "title": c.title,
                "status": c.status,
                "priority": c.priority,
                "assigned_to": c.assigned_to,
                "sla_breached": c.sla_breached,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in cases
        ],
        "limit": limit,
        "offset": offset,
    }


@router.post("")
async def create_case(
    body: CreateCaseRequest,
    principal: CurrentPrincipal,
    db: DbSession,
) -> dict[str, Any]:
    """Open a new investigation case grouping leads/flags."""
    Policy.require_write(principal)

    centre = (await db.execute(select(Centre).where(Centre.id == body.centre_id))).scalar_one_or_none()
    if not centre:
        raise NotFoundError("Centre", str(body.centre_id))

    case_num = f"CASE-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    new_case = Case(
        centre_id=body.centre_id,
        case_number=case_num,
        title=body.title,
        description=body.description,
        priority=body.priority,
        status="OPEN",
        assigned_to=principal.subject,
        assigned_at=datetime.now(UTC),
    )
    db.add(new_case)
    await db.flush()

    # Log initial creation event
    event = CaseEvent(
        case_id=new_case.id,
        from_status=None,
        to_status="OPEN",
        actor=principal.subject,
        note="Case created",
    )
    db.add(event)
    await db.flush()

    return {
        "id": str(new_case.id),
        "case_number": new_case.case_number,
        "status": new_case.status,
    }


@router.get("/{case_id}")
async def get_case(
    case_id: Annotated[uuid.UUID, Path()],
    principal: CurrentPrincipal,
    db: DbSession,
) -> dict[str, Any]:
    """Get full case details, history timeline events, and responses."""
    Policy.require_read(principal)

    case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if not case:
        raise NotFoundError("Case", str(case_id))

    centre = (await db.execute(select(Centre).where(Centre.id == case.centre_id))).scalar_one_or_none()
    if not centre:
        raise NotFoundError("Case", str(case_id))

    if "state_officer" in principal.roles and principal.state_code:
        if centre.state_code != principal.state_code:
            raise NotFoundError("Case", str(case_id))
    elif "inspector" in principal.roles or "training_centre" in principal.roles:
        if str(centre.id) not in principal.centre_ids:
            raise NotFoundError("Case", str(case_id))

    events = (
        await db.execute(select(CaseEvent).where(CaseEvent.case_id == case_id).order_by(CaseEvent.occurred_at.asc()))
    ).scalars().all()

    tc_resps = (
        await db.execute(select(TCResponse).where(TCResponse.case_id == case_id).order_by(TCResponse.submitted_at.asc()))
    ).scalars().all()

    return {
        "id": str(case.id),
        "case_number": case.case_number,
        "centre_id": str(case.centre_id),
        "title": case.title,
        "description": case.description,
        "status": case.status,
        "priority": case.priority,
        "assigned_to": case.assigned_to,
        "assigned_at": case.assigned_at.isoformat() if case.assigned_at else None,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "events": [
            {
                "id": str(e.id),
                "from_status": e.from_status,
                "to_status": e.to_status,
                "actor": e.actor,
                "note": e.note,
                "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
            }
            for e in events
        ],
        "tc_responses": [
            {
                "id": str(r.id),
                "responder": r.responder,
                "response_text": r.response_text,
                "attachment_s3_keys": r.attachment_s3_keys,
                "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
            }
            for r in tc_resps
        ],
    }


@router.post("/{case_id}/events")
async def add_case_event(
    case_id: Annotated[uuid.UUID, Path()],
    body: AddCaseEventRequest,
    principal: CurrentPrincipal,
    db: DbSession,
) -> dict[str, Any]:
    """Transition case status and record audit event."""
    Policy.require_write(principal)

    case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if not case:
        raise NotFoundError("Case", str(case_id))

    old_status = case.status
    case.status = body.to_status
    if body.to_status == "CLOSED":
        case.closed_at = datetime.now(UTC)
        case.closure_reason = body.note

    event = CaseEvent(
        case_id=case.id,
        from_status=old_status,
        to_status=body.to_status,
        actor=principal.subject,
        note=body.note,
    )
    db.add(event)
    await db.flush()

    return {"status": "ok", "from_status": old_status, "to_status": case.status}


@router.post("/{case_id}/respond")
async def submit_tc_response(
    case_id: Annotated[uuid.UUID, Path()],
    body: TCResponseRequest,
    principal: CurrentPrincipal,
    db: DbSession,
) -> dict[str, Any]:
    """Training centre submits explanation / evidence for a case."""
    case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if not case:
        raise NotFoundError("Case", str(case_id))

    response = TCResponse(
        case_id=case.id,
        responder=principal.subject,
        response_text=body.response_text,
        attachment_s3_keys=body.attachment_s3_keys,
    )
    db.add(response)

    # Transition case status to TC_RESPONDED
    old_status = case.status
    case.status = "TC_RESPONDED"

    event = CaseEvent(
        case_id=case.id,
        from_status=old_status,
        to_status="TC_RESPONDED",
        actor=principal.subject,
        note="TC explanation submitted",
    )
    db.add(event)
    await db.flush()

    return {"status": "ok", "response_id": str(response.id)}
