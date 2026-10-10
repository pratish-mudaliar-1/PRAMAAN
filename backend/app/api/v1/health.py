"""app/api/v1/health.py — /healthz and /readyz endpoints."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.logging import get_logger

router = APIRouter(tags=["health"])
logger = get_logger(__name__)

BUILD_START = datetime.now(UTC)


@router.get("/healthz", summary="Liveness probe")
async def liveness() -> dict[str, str]:
    """Returns 200 immediately. Used by Kubernetes liveness probe.

    Does NOT check dependencies — only confirms the process is alive.
    """
    return {"status": "ok", "service": "pramaan-backend"}


@router.get("/readyz", summary="Readiness probe")
async def readiness(response: Response) -> dict[str, Any]:
    """Check all hard dependencies and return their status.

    Returns 200 if all dependencies are healthy, 503 otherwise.
    Used by Kubernetes readiness probe and the dashboard health indicator.
    """
    from app.main import get_db_engine, get_redis_client

    checks: dict[str, str] = {}
    overall_ok = True

    # PostgreSQL
    try:
        engine = get_db_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["postgres"] = f"error: {exc}"
        overall_ok = False
        logger.error("readyz_postgres_fail", error=str(exc))

    # Redis
    try:
        redis = get_redis_client()
        await redis.ping()  # type: ignore[attr-defined]
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc}"
        overall_ok = False
        logger.error("readyz_redis_fail", error=str(exc))

    # S3 / MinIO — check bucket exists
    try:
        from app.main import get_s3_client
        s3 = get_s3_client()
        from app.core.config import get_settings
        await s3.head_bucket(Bucket=get_settings().s3.bucket_evidence)  # type: ignore[attr-defined]
        checks["s3"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["s3"] = f"error: {exc}"
        # S3 is non-critical for readiness; log warning only
        logger.warning("readyz_s3_warn", error=str(exc))

    if not overall_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if overall_ok else "degraded",
        "checks": checks,
        "uptime_seconds": (datetime.now(UTC) - BUILD_START).total_seconds(),
    }
