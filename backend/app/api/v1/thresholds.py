"""app/api/v1/thresholds.py — Threshold profile retrieval and update endpoints."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentPrincipal, DbSession
from app.api.v1.schemas import ThresholdProfileResponse, ThresholdUpdateRequest
from app.core.errors import AuthorizationError, ValidationError
from app.core.security.policy import Policy
from app.db.models.threshold import ThresholdProfile
from app.db.repositories.audit import AuditRepository

router = APIRouter(prefix="/thresholds", tags=["thresholds"])


@router.get("", response_model=ThresholdProfileResponse)
async def get_thresholds(
    principal: CurrentPrincipal,
    db: DbSession,
    scheme_code: str | None = Query(default=None),
    state_code: str | None = Query(default=None),
) -> ThresholdProfileResponse:
    """Retrieve active threshold profile using hierarchical scope fallback (state+scheme -> scheme -> national)."""
    Policy.require_read(principal)

    profile = None

    # 1. State + Scheme specific
    if scheme_code and state_code:
        q = (
            select(ThresholdProfile)
            .where(
                ThresholdProfile.scheme_code == scheme_code,
                ThresholdProfile.state_code == state_code,
                ThresholdProfile.is_active == True,
            )
            .order_by(desc(ThresholdProfile.version))
        )
        profile = (await db.execute(q)).scalar_one_or_none()

    # 2. Scheme-level fallback
    if not profile and scheme_code:
        q = (
            select(ThresholdProfile)
            .where(
                ThresholdProfile.scheme_code == scheme_code,
                ThresholdProfile.state_code == None,
                ThresholdProfile.is_active == True,
            )
            .order_by(desc(ThresholdProfile.version))
        )
        profile = (await db.execute(q)).scalar_one_or_none()

    # 3. National default fallback
    if not profile:
        q = (
            select(ThresholdProfile)
            .where(
                ThresholdProfile.scheme_code == None,
                ThresholdProfile.state_code == None,
                ThresholdProfile.is_active == True,
            )
            .order_by(desc(ThresholdProfile.version))
        )
        profile = (await db.execute(q)).scalar_one_or_none()

    # Fallback to defaults if no profile exists in db
    if not profile:
        profile = ThresholdProfile(
            id=uuid.uuid4(),
            scheme_code=None,
            state_code=None,
            version=1,
            is_active=True,
            t_green=0.80,
            t_amber=0.50,
            repeat_n=2,
            min_feed_health_fraction=0.50,
            item_absent_min_windows=3,
            item_absent_min_days=2,
            phash_hamming_threshold=10,
            approval_note="System default profile",
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)

    return ThresholdProfileResponse(
        id=profile.id,
        scheme_code=profile.scheme_code,
        state_code=profile.state_code,
        version=profile.version,
        is_active=profile.is_active,
        t_green=profile.t_green,
        t_amber=profile.t_amber,
        repeat_n=profile.repeat_n,
        min_feed_health_fraction=profile.min_feed_health_fraction,
        item_absent_min_windows=profile.item_absent_min_windows,
        item_absent_min_days=profile.item_absent_min_days,
        phash_hamming_threshold=profile.phash_hamming_threshold,
        extra=profile.extra,
        approved_by=profile.approved_by,
        approved_at=profile.approved_at,
        approval_note=profile.approval_note,
    )


@router.put("", response_model=ThresholdProfileResponse)
async def update_thresholds(
    req: ThresholdUpdateRequest,
    principal: CurrentPrincipal,
    db: DbSession,
    scheme_code: str | None = Query(default=None),
    state_code: str | None = Query(default=None),
) -> ThresholdProfileResponse:
    """Update active thresholds, enforce validation, record in audit trail, and persist."""
    # RBAC check: only officers or admin can modify thresholds
    allowed_roles = {"national_admin", "national_officer", "state_officer", "admin"}
    if not (set(principal.roles) & allowed_roles):
        raise AuthorizationError("Only national or state officers can update threshold profiles")


    # Range validation
    if req.t_amber >= req.t_green:
        raise ValidationError(
            f"t_amber ({req.t_amber}) must be strictly less than t_green ({req.t_green})"
        )

    # Find existing active profile for this scope
    q = (
        select(ThresholdProfile)
        .where(
            ThresholdProfile.scheme_code == scheme_code,
            ThresholdProfile.state_code == state_code,
            ThresholdProfile.is_active == True,
        )
        .order_by(desc(ThresholdProfile.version))
    )
    existing = (await db.execute(q)).scalar_one_or_none()

    now = datetime.now(UTC)
    version = (existing.version + 1) if existing else 1

    # Deactivate existing if present
    if existing:
        existing.is_active = False

    new_profile = ThresholdProfile(
        id=uuid.uuid4(),
        scheme_code=scheme_code,
        state_code=state_code,
        version=version,
        is_active=True,
        t_green=req.t_green,
        t_amber=req.t_amber,
        repeat_n=req.repeat_n,
        min_feed_health_fraction=req.min_feed_health_fraction,
        item_absent_min_windows=req.item_absent_min_windows,
        item_absent_min_days=req.item_absent_min_days,
        phash_hamming_threshold=req.phash_hamming_threshold,
        approved_by=principal.sub,
        approved_at=now,
        approval_note=req.approval_note or "Updated via settings console",
    )
    db.add(new_profile)

    # Append to tamper-evident audit log
    audit_repo = AuditRepository(db)
    await audit_repo.append(
        actor=principal.sub,
        action="THRESHOLD_UPDATE",
        resource_type="threshold_profile",
        resource_id=str(new_profile.id),
        detail={
            "version": version,
            "scheme_code": scheme_code,
            "state_code": state_code,
            "t_green": req.t_green,
            "t_amber": req.t_amber,
            "repeat_n": req.repeat_n,
            "note": req.approval_note,
        },
    )

    await db.commit()
    await db.refresh(new_profile)

    return ThresholdProfileResponse(
        id=new_profile.id,
        scheme_code=new_profile.scheme_code,
        state_code=new_profile.state_code,
        version=new_profile.version,
        is_active=new_profile.is_active,
        t_green=new_profile.t_green,
        t_amber=new_profile.t_amber,
        repeat_n=new_profile.repeat_n,
        min_feed_health_fraction=new_profile.min_feed_health_fraction,
        item_absent_min_windows=new_profile.item_absent_min_windows,
        item_absent_min_days=new_profile.item_absent_min_days,
        phash_hamming_threshold=new_profile.phash_hamming_threshold,
        extra=new_profile.extra,
        approved_by=new_profile.approved_by,
        approved_at=new_profile.approved_at,
        approval_note=new_profile.approval_note,
    )
