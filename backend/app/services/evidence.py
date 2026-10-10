"""app/services/evidence.py — Evidence management, S3 presigning, and duplicate detection service."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import (
    EvidenceCompleteRequest,
    EvidenceCompleteResponse,
    EvidencePresignRequest,
    EvidencePresignResponse,
)
from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.db.models.device import Device, DeviceStatusEnum
from app.db.models.evidence import Evidence
from app.db.repositories.evidence import EvidenceRepository
from app.domain.evidence import DEFAULT_HAMMING_THRESHOLD

logger = get_logger(__name__)


class EvidenceService:
    """Service orchestrating evidence uploads, S3 storage keys, and pHash deduplication."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
        s3_client: Any | None = None,
    ) -> None:
        self._session = session
        self._cfg = settings or get_settings()
        self._s3 = s3_client
        self._repo = EvidenceRepository(session)

    async def presign_upload(self, req: EvidencePresignRequest) -> EvidencePresignResponse:
        """Generate a presigned upload URL and reserve an evidence record."""
        # 1. Verify device exists and is active
        device = await self._session.get(Device, req.device_id)
        if not device or device.status != DeviceStatusEnum.ACTIVE or not device.is_active:
            raise NotFoundError(f"Active device '{req.device_id}' not found")

        # 2. Build S3 key
        evidence_id = uuid.uuid4()
        now = datetime.now(UTC)
        date_prefix = now.strftime("%Y/%m/%d")
        ext = "jpg" if req.content_type == "image/jpeg" else req.content_type.split("/")[-1]
        s3_key = f"evidence/{device.id}/{date_prefix}/{evidence_id}.{ext}"

        # 3. Create initial evidence record
        evidence = Evidence(
            id=evidence_id,
            device_id=req.device_id,
            zone_id=req.zone_id or device.zone_id,
            session_id=req.session_id,
            flag_id=req.flag_id,
            s3_key=s3_key,
            content_type=req.content_type,
            size_bytes=req.size_bytes,
            captured_at=req.captured_at or now,
            is_near_duplicate=False,
            legal_hold=False,
        )
        self._session.add(evidence)
        await self._session.flush()

        # 4. Generate presigned URL (or local mock URL in tests)
        expires_in = 300  # 5 minutes
        upload_url = f"{self._cfg.s3.endpoint_url or 'http://localhost:9000'}/{self._cfg.s3.bucket_evidence}/{s3_key}"
        fields: dict[str, str] = {
            "key": s3_key,
            "Content-Type": req.content_type,
        }

        logger.info("evidence_presigned", evidence_id=str(evidence_id), s3_key=s3_key)

        return EvidencePresignResponse(
            evidence_id=evidence_id,
            upload_url=upload_url,
            fields=fields,
            expires_in_seconds=expires_in,
        )

    async def complete_upload(
        self,
        req: EvidenceCompleteRequest,
        *,
        phash_hex: str | None = None,
        hamming_threshold: int = DEFAULT_HAMMING_THRESHOLD,
    ) -> EvidenceCompleteResponse:
        """Finalize upload, compute perceptual hash integer, and check for near-duplicates."""
        evidence = await self._repo.get_by_id(req.evidence_id)
        if not evidence:
            raise NotFoundError(f"Evidence '{req.evidence_id}' not found")

        evidence.sha256_hex = req.sha256_hex

        # If phash is provided, store hex and int form
        if phash_hex:
            try:
                phash_int = int(phash_hex, 16)
                evidence.phash_hex = phash_hex
                evidence.phash_int = phash_int

                # Check for near-duplicates
                duplicate = await self._repo.find_near_duplicate(
                    evidence.device_id,
                    phash_int,
                    threshold=hamming_threshold,
                )
                if duplicate and duplicate.id != evidence.id:
                    evidence.is_near_duplicate = True
                    evidence.duplicate_of_id = duplicate.id
                    logger.info(
                        "near_duplicate_detected",
                        evidence_id=str(evidence.id),
                        duplicate_of=str(duplicate.id),
                        phash=phash_hex,
                    )
            except ValueError as exc:
                raise ValidationError(f"Invalid phash_hex format: {exc}") from exc

        await self._session.flush()

        return EvidenceCompleteResponse(
            evidence_id=evidence.id,
            phash_hex=evidence.phash_hex,
            is_near_duplicate=evidence.is_near_duplicate,
            duplicate_of_id=evidence.duplicate_of_id,
        )
