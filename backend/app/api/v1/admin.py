"""app/api/v1/admin.py — Administrative maintenance and re-evaluation endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentPrincipal, DbSession
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security.policy import Policy
from app.services.reconciliation import ReconciliationService

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


class ReevaluateRequest(BaseModel):
    centre_id: uuid.UUID | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None


class ReevaluateResponse(BaseModel):
    evaluated_sessions: int
    flags_raised: int
    status_breakdown: dict[str, int]


@router.post(
    "/reevaluate",
    response_model=ReevaluateResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger batch re-evaluation of training sessions and recalculate compliance flags",
)
async def reevaluate_sessions(
    payload: ReevaluateRequest,
    principal: CurrentPrincipal,
    session: DbSession,
) -> ReevaluateResponse:
    """Run retroactive or batch reconciliation across training sessions (national_admin / state_officer only)."""
    # 1. Enforce RBAC permission (national_admin or state_officer)
    Policy.require_threshold_management(principal)

    # 2. Run reconciliation service
    service = ReconciliationService(session=session, settings=get_settings())
    result = await service.reevaluate_all(
        centre_id=payload.centre_id,
        from_date=payload.from_date,
        to_date=payload.to_date,
    )
    await session.commit()

    logger.info(
        "admin_reevaluation_completed",
        actor=principal.subject,
        evaluated=result["evaluated_sessions"],
        flags=result["flags_raised"],
    )

    return ReevaluateResponse(
        evaluated_sessions=result["evaluated_sessions"],
        flags_raised=result["flags_raised"],
        status_breakdown=result["status_breakdown"],
    )
