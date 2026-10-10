"""app/api/v1/ingest.py — Observation ingestion router endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import DbSession
from app.api.v1.schemas import ObservationBatchRequest, ObservationBatchResponse
from app.core.clock import system_clock
from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.ingestion import ObservationIngestionService

logger = get_logger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post(
    "/observations",
    response_model=ObservationBatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest a batch of signed observation records from an edge device",
)
async def ingest_observations(
    batch: ObservationBatchRequest,
    session: DbSession,
    x_device_signature: str | None = Header(default=None, alias="X-Device-Signature"),
) -> ObservationBatchResponse:
    """Receive, verify, hash-chain, and store minute-level observation records."""
    settings = get_settings()
    service = ObservationIngestionService(
        session=session,
        settings=settings,
        clock=system_clock,
    )

    result = await service.process_batch(batch)

    return ObservationBatchResponse(
        device_id=batch.device_id,
        accepted=result.accepted,
        rejected=result.rejected,
        results=result.results,
    )
