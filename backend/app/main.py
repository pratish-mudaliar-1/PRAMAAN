"""app/main.py — FastAPI application factory and lifespan.

Singleton state (engine, redis, s3) is stored on the app instance
so it can be overridden in tests without monkey-patching globals.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)

# ── Singleton accessors — set during lifespan ──────────────────────────────────

def get_db_engine() -> Any:
    from app.main import _app
    return _app.state.db_engine


def get_session_factory() -> Any:
    from app.main import _app
    return _app.state.session_factory


def get_redis_client() -> Any:
    from app.main import _app
    return _app.state.redis


def get_s3_client() -> Any:
    from app.main import _app
    return _app.state.s3


_app: FastAPI  # module-level reference set by create_app()


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings: Settings = app.state.settings

    # Logging
    configure_logging(
        log_level=settings.otel.log_level,
        json_logs=settings.is_production,
    )

    # Database
    from app.db.base import create_engine, create_session_factory
    engine = create_engine(
        settings.db.async_url,
        pool_size=settings.db.pool_size,
        max_overflow=settings.db.max_overflow,
        pool_pre_ping=settings.db.pool_pre_ping,
    )
    app.state.db_engine = engine
    app.state.session_factory = create_session_factory(engine)
    logger.info("db_connected", url=settings.db.async_url)

    if settings.db.async_url.startswith("sqlite"):
        from app.db.base import Base
        from app.db import models as _models  # noqa: F401
        from app.db.seed import seed_dev_database
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with app.state.session_factory() as session:
            await seed_dev_database(session)

    # Redis
    redis_client = aioredis.from_url(
        settings.redis.url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=50,
    )
    app.state.redis = redis_client
    logger.info("redis_connected", host=settings.redis.host)

    # S3 / MinIO
    import aioboto3
    session = aioboto3.Session()
    s3_kwargs: dict[str, Any] = {
        "region_name": settings.s3.region,
        "aws_access_key_id": settings.s3.access_key_id.get_secret_value(),
        "aws_secret_access_key": settings.s3.secret_access_key.get_secret_value(),
    }
    if settings.s3.endpoint_url:
        s3_kwargs["endpoint_url"] = settings.s3.endpoint_url

    s3_resource = session.client("s3", **s3_kwargs)
    app.state.s3 = s3_resource
    logger.info("s3_configured", endpoint=settings.s3.endpoint_url)

    logger.info("pramaan_backend_started", environment=settings.environment)
    yield

    # Shutdown
    await engine.dispose()
    await redis_client.aclose()
    logger.info("pramaan_backend_stopped")


# ── App factory ────────────────────────────────────────────────────────────────

def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(
        title="PRAMAAN Backend API",
        description=(
            "Backend platform for Smart India Hackathon PS-26245 (MSDE). "
            "Receives signed observations from edge devices and reconciles "
            "attendance and infrastructure compliance."
        ),
        version="1.0.0",
        openapi_url="/v1/openapi.json",
        docs_url="/v1/docs" if not settings.is_production else None,
        redoc_url="/v1/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )
    app.state.settings = settings

    # Request ID middleware
    @app.middleware("http")
    async def _request_id(request: Request, call_next: Any) -> Any:
        request_id = request.headers.get(settings.request_id_header) or str(uuid.uuid4())
        request.state.request_id = request_id
        import structlog
        with structlog.contextvars.bound_contextvars(request_id=request_id):
            response = await call_next(request)
        response.headers[settings.request_id_header] = request_id
        return response

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Error handlers
    register_exception_handlers(app)

    # Routers
    from app.api.v1 import api_router
    app.include_router(api_router)

    # Store module-level reference for singleton accessors
    global _app
    _app = app

    return app


# ── Entry point ────────────────────────────────────────────────────────────────
app = create_app()
