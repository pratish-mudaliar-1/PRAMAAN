"""app/api/v1/device.py — Edge device enrollment, heartbeat, and management endpoints."""
from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession


from app.api.v1.deps import DbSession
from app.api.v1.schemas import (
    DeviceEnrollRequest,
    DeviceEnrollResponse,
    HeartbeatRequest,
    HeartbeatResponse,
)
from app.core.clock import AbstractClock, system_clock
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.security.device_key import decode_public_key
from app.db.models.centre import Centre
from app.db.models.device import Device, DeviceStatusEnum
from app.db.repositories.device import DeviceRepository

logger = get_logger(__name__)

router = APIRouter(prefix="/device", tags=["device"])


@router.post(
    "/enroll",
    response_model=DeviceEnrollResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enroll a new edge video-analytics device",
)
async def enroll_device(
    payload: DeviceEnrollRequest,
    session: DbSession,
) -> DeviceEnrollResponse:
    """Enroll an edge device with its Ed25519 public key and one-time enrollment token."""
    device_repo = DeviceRepository(session)

    # 1. Check if device with this serial number already exists
    existing = await device_repo.get_by_serial(payload.serial_number)
    if existing:
        raise ConflictError(f"Device with serial number '{payload.serial_number}' is already registered")

    # 2. Check if Centre exists
    centre = await session.get(Centre, payload.centre_id)
    if not centre:
        raise NotFoundError(f"Training centre '{payload.centre_id}' not found")

    # 3. Decode Ed25519 public key
    try:
        pubkey_bytes = decode_public_key(payload.public_key_b64url)
        if len(pubkey_bytes) != 32:
            raise ValueError("Public key must decode to exactly 32 bytes")
    except Exception as exc:
        raise ValidationError(f"Invalid public key encoding: {exc}") from exc

    # 4. Hash enrollment token
    token_hash = hashlib.sha256(payload.enrollment_token.encode("utf-8")).hexdigest()

    # 5. Create device record
    now = datetime.now(UTC)
    device = Device(
        centre_id=payload.centre_id,
        zone_id=payload.zone_id,
        serial_number=payload.serial_number,
        public_key=pubkey_bytes,
        public_key_b64url=payload.public_key_b64url,
        enrollment_token_hash=token_hash,
        status=DeviceStatusEnum.ACTIVE,
        is_active=True,
        model_version=payload.model_version,
        firmware_version=payload.firmware_version,
        enrolled_at=now,
        last_seen_at=now,
    )
    session.add(device)
    await session.commit()
    await session.refresh(device)

    logger.info("device_enrolled", device_id=str(device.id), serial_number=device.serial_number)

    return DeviceEnrollResponse(
        device_id=device.id,
        serial_number=device.serial_number,
        status=device.status.value,
    )


@router.post(
    "/heartbeat",
    response_model=HeartbeatResponse,
    summary="Receive edge device health and telemetry heartbeat",
)
async def device_heartbeat(
    payload: HeartbeatRequest,
    session: DbSession,
) -> HeartbeatResponse:
    """Update device liveness and telemetry snapshot."""
    device_repo = DeviceRepository(session)
    device = await device_repo.get_by_id(payload.device_id)
    if not device:
        raise NotFoundError(f"Device '{payload.device_id}' not found")

    now = datetime.now(UTC)
    telemetry = payload.model_dump(exclude={"device_id"}, exclude_none=True, mode="json")
    await device_repo.record_heartbeat(device, telemetry)
    await session.commit()

    return HeartbeatResponse(
        acknowledged=True,
        server_ts=now,
        config_update_available=False,
    )


@router.get(
    "s",
    summary="List edge devices with health status and telemetry",
)
@router.get(
    "",
    summary="List edge devices with health status and telemetry (alias)",
)
async def list_devices(
    session: DbSession,
    principal: Annotated[Any, Depends(lambda: None)] = None,
    centre_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """List edge devices with health metrics and telemetry."""
    from sqlalchemy import select
    from app.db.repositories.audit import AuditRepository

    query = (
        select(Device, Centre.name.label("centre_name"))
        .join(Centre, Device.centre_id == Centre.id)
    )

    if centre_id:
        query = query.where(Device.centre_id == centre_id)
    if status:
        query = query.where(Device.status == status)

    query = query.order_by(Device.serial_number).limit(limit).offset(offset)
    res = await session.execute(query)
    rows = res.all()

    items = []
    for d, c_name in rows:
        telemetry = d.last_telemetry or {}
        # derive health
        health = "HEALTHY"
        if d.status == DeviceStatusEnum.OFFLINE:
            health = "OFFLINE"
        elif d.status in (DeviceStatusEnum.SUSPENDED, DeviceStatusEnum.REVOKED):
            health = "UNHEALTHY"
        elif telemetry.get("cpu_percent", 0) > 90 or (telemetry.get("queue_depth", 0) > 1000):
            health = "DEGRADED"

        items.append({
            "id": d.id,
            "serial_number": d.serial_number,
            "centre_id": d.centre_id,
            "centre_name": c_name,
            "zone_id": d.zone_id,
            "camera_id": d.camera_id,
            "status": d.status.value if hasattr(d.status, "value") else str(d.status),
            "is_active": d.is_active,
            "last_seen_at": d.last_seen_at,
            "last_heartbeat_at": d.last_heartbeat_at,
            "firmware_version": d.firmware_version,
            "model_version": d.model_version,
            "queue_depth": telemetry.get("queue_depth", 0),
            "cpu_percent": telemetry.get("cpu_percent"),
            "temperature_celsius": telemetry.get("temperature_celsius"),
            "free_disk_mb": telemetry.get("free_disk_mb"),
            "last_telemetry": telemetry,
            "health_status": health,
        })

    return {
        "items": items,
        "limit": limit,
        "offset": offset,
    }


@router.post(
    "s/{device_id}/status",
    summary="Update device operational status",
)
async def update_device_status(
    device_id: uuid.UUID,
    session: DbSession,
    payload: dict[str, Any] | None = Body(default=None),
    new_status: str | None = Query(default=None),
) -> dict[str, Any]:
    """Manually update edge device operational status and record audit log."""
    from app.db.repositories.audit import AuditRepository
    target_status = (payload.get("status") if payload else None) or new_status
    if not target_status or target_status not in ("ACTIVE", "OFFLINE", "SUSPENDED", "REVOKED"):
        raise ValidationError("Missing or invalid 'status' parameter")

    device = await session.get(Device, device_id)
    if not device:
        raise NotFoundError(f"Device '{device_id}' not found")

    old_status = device.status.value if hasattr(device.status, "value") else str(device.status)
    device.status = DeviceStatusEnum(target_status)
    if target_status == "REVOKED":
        device.is_active = False
        device.revoked_at = datetime.now(UTC)
        device.revocation_reason = (payload.get("reason") if payload else None) or "Manually revoked by administrator"
    elif target_status == "ACTIVE":
        device.is_active = True

    audit_repo = AuditRepository(session)
    await audit_repo.append(
        actor="system",
        action="DEVICE_STATUS_UPDATE",
        resource_type="device",
        resource_id=str(device_id),
        detail={"old_status": old_status, "new_status": new_status, "serial": device.serial_number},
    )

    await session.commit()
    return {
        "device_id": str(device.id),
        "status": device.status.value,
        "is_active": device.is_active,
    }

