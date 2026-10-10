"""app/db/base.py — Async SQLAlchemy engine, session factory and Unit-of-Work."""
from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import MetaData, event, text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

# ── Naming convention for all constraints / indexes ────────────────────────────
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    metadata = metadata


# ── Engine factory ─────────────────────────────────────────────────────────────

def create_engine(database_url: str, **kwargs: Any) -> AsyncEngine:
    if database_url.startswith("sqlite"):
        kwargs.pop("pool_size", None)
        kwargs.pop("max_overflow", None)
        kwargs.pop("pool_pre_ping", None)
    return create_async_engine(
        database_url,
        echo=False,
        future=True,
        **kwargs,
    )


# ── Session factory ────────────────────────────────────────────────────────────

def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


# ── Unit-of-Work context manager ───────────────────────────────────────────────

class UnitOfWork:
    """Provides a single AsyncSession for a logical transaction.

    Usage::
        async with UnitOfWork(session_factory) as uow:
            uow.session.add(entity)
            await uow.commit()
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = session_factory
        self.session: AsyncSession

    async def __aenter__(self) -> "UnitOfWork":
        self.session = self._factory()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type:
            await self.session.rollback()
        await self.session.close()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()


# ── Connection-level helpers ───────────────────────────────────────────────────

@contextlib.asynccontextmanager
async def get_connection(engine: AsyncEngine) -> AsyncGenerator[AsyncConnection, None]:
    """Low-level DDL/migration connection context manager."""
    async with engine.begin() as conn:
        yield conn


def get_session_factory() -> Any:
    """Access the application session factory singleton."""
    from app.main import get_session_factory as _gsf
    return _gsf()

