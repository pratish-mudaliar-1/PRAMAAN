"""app/jobs/__init__.py — Asynchronous job enqueuing utilities with graceful local fallback."""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

from arq import create_pool
from arq.connections import RedisSettings as ArqRedisSettings

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def enqueue_session_reconciliation(session_id: uuid.UUID) -> bool:
    """Enqueue a session reconciliation background job via Arq, or fallback to inline async execution."""
    s = get_settings()
    job_id = f"recon:{session_id}"

    # Try Arq Redis pool with fast failure if Redis is offline
    try:
        redis_settings = ArqRedisSettings(host=s.redis.host, port=s.redis.port)
        pool = await asyncio.wait_for(create_pool(redis_settings, retry=0), timeout=0.5)
        await pool.enqueue_job(
            "reconcile_active_sessions_job",
            str(session_id),
            _job_id=job_id,
        )
        await pool.close()
        logger.info("reconciliation_enqueued_arq", session_id=str(session_id), job_id=job_id)
        return True
    except Exception as exc:
        logger.info(
            "arq_redis_unavailable_fallback_inline",
            session_id=str(session_id),
            reason=str(exc),
        )
        # Direct execution fallback for local dev or tests where Redis is not active
        try:
            try:
                from app.main import get_session_factory
                factory = get_session_factory()
            except Exception:
                from app.db.base import create_engine, create_session_factory
                engine = create_engine(s.db.async_url)
                factory = create_session_factory(engine)


            from app.services.reconciliation import ReconciliationService

            async with factory() as db:
                svc = ReconciliationService(db)
                await svc.reconcile_session(session_id)
                await db.commit()
            logger.info("reconciliation_completed_inline", session_id=str(session_id))
            return True
        except Exception as inline_exc:
            logger.error("inline_reconciliation_failed", session_id=str(session_id), error=str(inline_exc))
            return False

