"""app/api/v1/evidence.py — Evidence presigning and upload completion endpoints."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentPrincipal, DbSession

from app.api.v1.schemas import (
    EvidenceCompleteRequest,
    EvidenceCompleteResponse,
    EvidencePresignRequest,
    EvidencePresignResponse,
    EvidenceViewResponse,
)

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security.policy import Policy
from app.services.evidence import EvidenceService


logger = get_logger(__name__)

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.post(
    "/presign",
    response_model=EvidencePresignResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate presigned S3 upload URL for redacted keyframe evidence",
)
async def presign_evidence_upload(
    req: EvidencePresignRequest,
    session: DbSession,
) -> EvidencePresignResponse:
    """Generate a presigned S3 upload URL and create a reserved evidence record."""
    service = EvidenceService(session=session, settings=get_settings())
    res = await service.presign_upload(req)
    await session.commit()
    return res


@router.post(
    "/complete",
    response_model=EvidenceCompleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Finalize evidence upload and perform near-duplicate pHash detection",
)
async def complete_evidence_upload(
    req: EvidenceCompleteRequest,
    session: DbSession,
    phash_hex: str | None = Query(
        default=None,
        description="16-character hexadecimal 64-bit dHash computed by edge device or server",
    ),
) -> EvidenceCompleteResponse:
    """Complete an evidence upload and verify near-duplicates with Hamming distance check."""
    service = EvidenceService(session=session, settings=get_settings())
    res = await service.complete_upload(req, phash_hex=phash_hex)
    await session.commit()
    return res


@router.get("", response_model=dict[str, Any])
async def list_evidence(
    principal: CurrentPrincipal,
    db: DbSession,
    centre_id: uuid.UUID | None = Query(default=None),
    session_id: uuid.UUID | None = Query(default=None),
    flag_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """List evidence items scoped by centre, session, or flag."""
    Policy.require_read(principal)
    from sqlalchemy import select
    from app.db.models.device import Device
    from app.db.models.evidence import Evidence

    query = select(Evidence)
    if centre_id:
        query = query.join(Device, Evidence.device_id == Device.id).where(Device.centre_id == centre_id)
    if session_id:
        query = query.where(Evidence.session_id == session_id)
    if flag_id:
        query = query.where(Evidence.flag_id == flag_id)

    query = query.order_by(Evidence.captured_at.desc()).limit(limit).offset(offset)
    res = await db.execute(query)
    rows = res.scalars().all()

    items = [
        {
            "id": e.id,
            "device_id": e.device_id,
            "zone_id": e.zone_id,
            "session_id": e.session_id,
            "flag_id": e.flag_id,
            "s3_key": e.s3_key,
            "content_type": e.content_type,
            "size_bytes": e.size_bytes,
            "captured_at": e.captured_at,
            "is_near_duplicate": e.is_near_duplicate,
            "duplicate_of_id": e.duplicate_of_id,
            "legal_hold": e.legal_hold,
        }
        for e in rows
    ]

    return {
        "items": items,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{evidence_id}/view", response_model=EvidenceViewResponse)
async def get_evidence_view(
    evidence_id: uuid.UUID,
    principal: CurrentPrincipal,
    db: DbSession,
) -> EvidenceViewResponse:
    """Generate secure expiring view URL for reviewer."""
    Policy.require_read(principal)
    from app.core.errors import NotFoundError
    from app.db.models.evidence import Evidence

    evidence = await db.get(Evidence, evidence_id)
    if not evidence:
        raise NotFoundError("Evidence", str(evidence_id))

    cfg = get_settings()
    expires_in = 300
    base_endpoint = cfg.s3.endpoint_url.rstrip("/") if cfg.s3.endpoint_url else "http://localhost:9000"
    view_url = f"{base_endpoint}/{cfg.s3.bucket_evidence}/{evidence.s3_key}"

    return EvidenceViewResponse(
        evidence_id=evidence.id,
        view_url=view_url,
        expires_in_seconds=expires_in,
        content_type=evidence.content_type,
        captured_at=evidence.captured_at,
    )

