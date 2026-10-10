"""app/api/v1/ghost.py — Ghost batch assessment and batch querying endpoints."""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentPrincipal, DbSession
from app.api.v1.schemas import BatchResponse, CentreGhostRollupResponse, GhostAssessmentResponse
from app.core.errors import NotFoundError
from app.core.security.policy import Policy
from app.db.models.centre import Centre
from app.db.models.ghost import GhostAssessment
from app.db.models.session_ import Batch, Session

router = APIRouter(tags=["ghost"])


@router.get("/ghost-assessments", response_model=dict[str, Any])
async def list_ghost_assessments(
    principal: CurrentPrincipal,
    db: DbSession,
    centre_id: uuid.UUID | None = Query(default=None),
    batch_id: uuid.UUID | None = Query(default=None),
    state: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """List ghost batch assessments with multi-day statistical indicators."""
    Policy.require_read(principal)

    query = (
        select(GhostAssessment, Batch.trade_code, Batch.scheme_code, Centre.name.label("centre_name"))
        .join(Batch, GhostAssessment.batch_id == Batch.id)
        .join(Centre, GhostAssessment.centre_id == Centre.id)
    )

    if "state_officer" in principal.roles and principal.state_code:
        query = query.where(Centre.state_code == principal.state_code)
    elif "inspector" in principal.roles or "training_centre" in principal.roles:
        c_uuids = [uuid.UUID(cid) for cid in principal.centre_ids if cid]
        query = query.where(Centre.id.in_(c_uuids))

    if centre_id:
        query = query.where(GhostAssessment.centre_id == centre_id)
    if batch_id:
        query = query.where(GhostAssessment.batch_id == batch_id)
    if state:
        query = query.where(GhostAssessment.state == state)

    query = query.order_by(GhostAssessment.ghost_score.desc()).limit(limit).offset(offset)
    res = await db.execute(query)
    rows = res.all()

    items = []
    for ga, trade, scheme, centre_name in rows:
        items.append({
            "id": ga.id,
            "batch_id": ga.batch_id,
            "batch_trade": trade or "General",
            "batch_scheme": scheme or "PMKVY",
            "centre_id": ga.centre_id,
            "centre_name": centre_name,
            "window_start": ga.window_start,
            "window_end": ga.window_end,
            "state": ga.state,
            "eligible_days": ga.eligible_days,
            "ghost_days": ga.ghost_days,
            "nodata_days": ga.nodata_days,
            "untrusted_days": ga.untrusted_days,
            "ghost_score": float(ga.ghost_score or 0.0),
            "explanation": ga.explanation or {},
            "algorithm_version": ga.algorithm_version or "v1",
            "computed_at": ga.computed_at,
        })

    return {
        "items": items,
        "limit": limit,
        "offset": offset,
    }


@router.get("/ghost-assessments/{assessment_id}", response_model=GhostAssessmentResponse)
async def get_ghost_assessment(
    assessment_id: Annotated[uuid.UUID, Path()],
    principal: CurrentPrincipal,
    db: DbSession,
) -> GhostAssessmentResponse:
    """Retrieve detailed ghost assessment breakdown."""
    Policy.require_read(principal)

    query = (
        select(GhostAssessment, Batch.trade_code, Batch.scheme_code, Centre.name.label("centre_name"))
        .join(Batch, GhostAssessment.batch_id == Batch.id)
        .join(Centre, GhostAssessment.centre_id == Centre.id)
        .where(GhostAssessment.id == assessment_id)
    )
    row = (await db.execute(query)).first()
    if not row:
        raise NotFoundError("GhostAssessment", str(assessment_id))

    ga, trade, scheme, centre_name = row
    return GhostAssessmentResponse(
        id=ga.id,
        batch_id=ga.batch_id,
        batch_trade=trade or "General",
        batch_scheme=scheme or "PMKVY",
        centre_id=ga.centre_id,
        centre_name=centre_name,
        window_start=ga.window_start,
        window_end=ga.window_end,
        state=ga.state,
        eligible_days=ga.eligible_days,
        ghost_days=ga.ghost_days,
        nodata_days=ga.nodata_days,
        untrusted_days=ga.untrusted_days,
        pending_days=ga.pending_days,
        ghost_score=float(ga.ghost_score or 0.0),
        per_day_detail=ga.per_day_detail or [],
        explanation=ga.explanation or {},
        case_id=ga.case_id,
        algorithm_version=ga.algorithm_version or "v1",
        computed_at=ga.computed_at,
    )


@router.get("/batches/{batch_id}/ghost-assessment", response_model=GhostAssessmentResponse)
async def get_batch_ghost_assessment(
    batch_id: Annotated[uuid.UUID, Path()],
    principal: CurrentPrincipal,
    db: DbSession,
) -> GhostAssessmentResponse:
    """Retrieve or compute live multi-day ghost assessment for a specific batch."""
    Policy.require_read(principal)

    from app.services.ghost_batch import GhostBatchDetectionService
    svc = GhostBatchDetectionService(db)

    # Check if assessment exists; if not, evaluate
    ga = (
        await db.execute(select(GhostAssessment).where(GhostAssessment.batch_id == batch_id))
    ).scalar_one_or_none()

    if not ga:
        await svc.assess_batch(batch_id)
        await db.commit()
        ga = (
            await db.execute(select(GhostAssessment).where(GhostAssessment.batch_id == batch_id))
        ).scalar_one_or_none()

    if not ga:
        raise NotFoundError("Batch", str(batch_id))

    batch = (await db.execute(select(Batch).where(Batch.id == batch_id))).scalar_one()
    centre = (await db.execute(select(Centre).where(Centre.id == batch.centre_id))).scalar_one()

    return GhostAssessmentResponse(
        id=ga.id,
        batch_id=ga.batch_id,
        batch_trade=batch.trade_code or "General",
        batch_scheme=batch.scheme_code or "PMKVY",
        centre_id=ga.centre_id,
        centre_name=centre.name,
        window_start=ga.window_start,
        window_end=ga.window_end,
        state=ga.state,
        eligible_days=ga.eligible_days,
        ghost_days=ga.ghost_days,
        nodata_days=ga.nodata_days,
        untrusted_days=ga.untrusted_days,
        pending_days=ga.pending_days,
        ghost_score=float(ga.ghost_score or 0.0),
        per_day_detail=ga.per_day_detail or [],
        explanation=ga.explanation or {},
        case_id=ga.case_id,
        algorithm_version=ga.algorithm_version or "v1",
        computed_at=ga.computed_at,
    )


@router.get("/centres/{centre_id}/ghost-batches", response_model=CentreGhostRollupResponse)
async def get_centre_ghost_rollup(
    centre_id: Annotated[uuid.UUID, Path()],
    principal: CurrentPrincipal,
    db: DbSession,
) -> CentreGhostRollupResponse:
    """Roll up ghost batch detection risk across all batches in a training centre."""
    Policy.require_read(principal)

    from app.services.ghost_batch import GhostBatchDetectionService
    svc = GhostBatchDetectionService(db)
    rollup = await svc.assess_centre_ghost_batches(centre_id)

    return CentreGhostRollupResponse(
        centre_id=rollup.centre_id,
        centre_name=rollup.centre_name,
        total_batches=rollup.total_batches,
        normal_batches=rollup.normal_batches,
        watch_batches=rollup.watch_batches,
        suspected_ghost_batches=rollup.suspected_ghost_batches,
        escalated_batches=rollup.escalated_batches,
        resolved_batches=rollup.resolved_batches,
        centre_ghost_risk_score=rollup.centre_ghost_risk_score,
        batch_assessments=rollup.batch_assessments,
    )


@router.post("/ghost/re-evaluate/{batch_id}", response_model=dict[str, Any])
async def reevaluate_ghost_batch(
    batch_id: Annotated[uuid.UUID, Path()],
    principal: CurrentPrincipal,
    db: DbSession,
) -> dict[str, Any]:
    """Idempotently re-evaluate a batch (e.g. after late data arrival)."""
    Policy.require_write(principal)

    from app.services.ghost_batch import GhostBatchDetectionService
    svc = GhostBatchDetectionService(db)
    res = await svc.assess_batch(batch_id)
    await db.commit()

    return {
        "batch_id": res.batch_id,
        "current_state": res.current_state,
        "previous_state": res.previous_state,
        "transitioned": res.transitioned,
        "eligible_days": res.eligible_days,
        "ghost_days": res.ghost_days,
        "untrusted_days": res.untrusted_days,
        "ghost_score": res.ghost_score,
        "camera_integrity_explains": res.camera_integrity_explains,
        "explanation": res.explanation,
    }


@router.get("/batches", response_model=dict[str, Any])
async def list_batches(
    principal: CurrentPrincipal,
    db: DbSession,
    centre_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """List batches with ghost status and total sessions count."""
    Policy.require_read(principal)

    query = (
        select(Batch, Centre.state_code)
        .join(Centre, Batch.centre_id == Centre.id)
    )

    if "state_officer" in principal.roles and principal.state_code:
        query = query.where(Centre.state_code == principal.state_code)
    elif "inspector" in principal.roles or "training_centre" in principal.roles:
        c_uuids = [uuid.UUID(cid) for cid in principal.centre_ids if cid]
        query = query.where(Centre.id.in_(c_uuids))

    if centre_id:
        query = query.where(Batch.centre_id == centre_id)

    query = query.order_by(Batch.batch_start_date.desc()).limit(limit).offset(offset)
    res = await db.execute(query)
    rows = res.all()

    items = []
    for b, _sc in rows:
        ga = (
            await db.execute(select(GhostAssessment).where(GhostAssessment.batch_id == b.id))
        ).scalar_one_or_none()

        sess_count = (
            await db.execute(select(func.count(Session.id)).where(Session.batch_id == b.id))
        ).scalar_one()

        s_date = b.batch_start_date.strftime("%Y-%m-%d") if b.batch_start_date else "2026-09-01"
        e_date = b.batch_end_date.strftime("%Y-%m-%d") if b.batch_end_date else "2026-11-30"

        items.append({
            "id": b.id,
            "centre_id": b.centre_id,
            "trade": b.trade_code or b.batch_code,
            "scheme": b.scheme_code,
            "start_date": s_date,
            "end_date": e_date,
            "ghost_state": ga.state if ga else "NORMAL",
            "ghost_score": float(ga.ghost_score) if ga and ga.ghost_score is not None else None,
            "total_sessions": sess_count,
        })

    return {
        "items": items,
        "limit": limit,
        "offset": offset,
    }
