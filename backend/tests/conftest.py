"""tests/conftest.py — Shared fixtures for unit and integration tests."""
from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ── Settings override for tests ───────────────────────────────────────────────

os.environ.setdefault("PRAMAAN_ENVIRONMENT", "development")
os.environ.setdefault("AUTH_DEV_JWT_SECRET", "test-secret-key")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PASSWORD", "pramaan")


@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.DefaultEventLoopPolicy:
    return asyncio.DefaultEventLoopPolicy()


# ── Dev JWT helper ─────────────────────────────────────────────────────────────

@pytest.fixture
def make_token() -> Any:
    """Factory: returns JWT strings for test principals."""
    from app.core.security.jwt import create_dev_token

    def _make(
        subject: str = "test-user",
        roles: list[str] | None = None,
        centre_ids: list[str] | None = None,
        state_code: str | None = None,
    ) -> str:
        return create_dev_token(
            subject=subject,
            roles=roles or ["national_admin"],
            centre_ids=centre_ids,
            state_code=state_code,
            secret="test-secret-key",
        )

    return _make


# ── Clock fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def frozen_clock() -> Any:
    from app.core.clock import FrozenClock
    return FrozenClock(datetime(2024, 6, 15, 9, 0, 0, tzinfo=UTC))


# ── In-memory SQLite engine for ultra-fast unit tests ────────────────────────
# Note: integration tests use real Postgres via testcontainers.

@pytest_asyncio.fixture
async def sqlite_session() -> AsyncGenerator[AsyncSession, None]:
    """SQLite-backed async session for fast unit tests that need DB interactions.

    TimescaleDB-specific features (hypertable, continuous aggregates) are not
    available; this fixture is for pure SQL correctness tests only.
    """
    from app.db.base import Base
    import app.db.models  # noqa: F401

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with factory() as session:
        yield session

    await engine.dispose()
