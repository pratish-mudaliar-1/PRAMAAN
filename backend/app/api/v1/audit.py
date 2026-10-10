"""app/api/v1/audit.py — Tamper-evident hash-chained audit log querying endpoints."""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentPrincipal, DbSession
from app.api.v1.schemas import AuditLogResponse
from app.core.security.policy import Policy
from app.db.models.audit import AuditLog

router = APIRouter(prefix="/audit-log", tags=["audit"])


@router.get("", response_model=dict[str, Any])
async def list_audit_logs(
    principal: CurrentPrincipal,
    db: DbSession,
    actor: str | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    resource_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """Retrieve immutable audit log records with cryptographic hash-chain provenance."""
    Policy.require_read(principal)

    query = select(AuditLog)
    if actor:
        query = query.where(AuditLog.actor == actor)
    if action:
        query = query.where(AuditLog.action == action)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if resource_id:
        query = query.where(AuditLog.resource_id == resource_id)

    query = query.order_by(desc(AuditLog.occurred_at)).limit(limit).offset(offset)
    res = await db.execute(query)
    rows = res.scalars().all()

    items = [
        {
            "id": r.id,
            "actor": r.actor,
            "action": r.action,
            "resource_type": r.resource_type,
            "resource_id": r.resource_id,
            "request_id": r.request_id,
            "detail": r.detail,
            "row_hash": r.row_hash,
            "prev_hash": r.prev_hash,
            "occurred_at": r.occurred_at,
        }
        for r in rows
    ]

    return {
        "items": items,
        "limit": limit,
        "offset": offset,
    }
