"""app/jobs/worker.py — Arq worker entry point and scheduled tasks."""
from __future__ import annotations

import uuid
from typing import Any

import structlog
from arq import create_pool
from arq.connections import RedisSettings as ArqRedisSettings

logger = structlog.get_logger(__name__)


async def startup(ctx: dict[str, Any]) -> None:
    from app.core.config import get_settings
    from app.core.logging import configure_logging
    s = get_settings()
    configure_logging(log_level=s.otel.log_level, json_logs=s.is_production)
    logger.info("Arq worker started successfully")


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("Arq worker shutting down")


async def reconcile_active_sessions_job(ctx: dict[str, Any], session_id: str) -> dict[str, Any]:
    """Background task to run deterministic attendance reconciliation for a session."""
    from app.db.base import get_session_factory
    from app.services.reconciliation import ReconciliationService

    factory = get_session_factory()
    async with factory() as db:
        svc = ReconciliationService(db)
        result = await svc.reconcile_session(uuid.UUID(session_id))
        await db.commit()
        return {"session_id": session_id, "status": result.status, "ratio": result.ratio}


async def camera_drift_evaluation_job(ctx: dict[str, Any], camera_id: str) -> dict[str, Any]:
    """Background task to evaluate camera scene drift & tampering state machine."""
    from app.db.base import get_session_factory
    from app.services.camera_integrity import CameraIntegrityService

    factory = get_session_factory()
    async with factory() as db:
        svc = CameraIntegrityService(db)
        result = await svc.evaluate_camera(uuid.UUID(camera_id))
        await db.commit()
        return {
            "camera_id": camera_id,
            "current_state": result.current_state,
            "transitioned": result.transitioned,
        }


async def ghost_batch_scan_job(ctx: dict[str, Any], batch_id: str) -> dict[str, Any]:
    """Background task to evaluate multi-day ghost batch patterns."""
    from app.db.base import get_session_factory
    from app.services.ghost_batch import GhostBatchDetectionService

    factory = get_session_factory()
    async with factory() as db:
        svc = GhostBatchDetectionService(db)
        result = await svc.assess_batch(uuid.UUID(batch_id))
        await db.commit()
        return {
            "batch_id": batch_id,
            "state": result.state,
            "is_ghost": result.is_ghost_pattern,
            "ghost_sessions_count": result.ghost_sessions_count,
        }


class WorkerSettings:
    functions: list[object] = [
        reconcile_active_sessions_job,
        camera_drift_evaluation_job,
        ghost_batch_scan_job,
    ]
    on_startup = startup
    on_shutdown = shutdown

    @classmethod
    def redis_settings(cls) -> ArqRedisSettings:
        from app.core.config import get_settings
        s = get_settings()
        return ArqRedisSettings(host=s.redis.host, port=s.redis.port)


if __name__ == "__main__":
    from arq import run_worker
    run_worker(WorkerSettings)  # type: ignore[arg-type]
