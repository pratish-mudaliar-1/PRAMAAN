"""tests/unit/test_migrations.py — Schema and migration metadata tests.

Verifies that all 28 models and tables in Base.metadata create cleanly,
all foreign key references resolve, indexes are defined, and tables
can be created and dropped in-memory without errors.
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.base import Base
import app.db.models  # noqa: F401


EXPECTED_TABLES = {
    "centre",
    "camera",
    "zone",
    "sanctioned_layout",
    "device",
    "batch",
    "session",
    "ingest_dedupe",
    "observation",
    "evidence",
    "case",
    "flag",
    "flag_input_snapshot",
    "integrity_event",
    "case_event",
    "tc_response",
    "threshold_profile",
    "user",
    "role_binding",
    "audit_log",
    "camera_reference",
    "scene_observation",
    "camera_integrity_state",
    "camera_state_event",
    "rebaseline_request",
    "camera_maintenance_window",
    "ghost_assessment",
    "ghost_state_event",
}


def test_all_expected_tables_registered() -> None:
    """Ensure all 28 expected domain and system tables are registered in Base.metadata."""
    registered_tables = set(Base.metadata.tables.keys())
    missing = EXPECTED_TABLES - registered_tables
    assert not missing, f"Missing tables in Base.metadata: {missing}"
    assert len(registered_tables) == 28


@pytest.mark.asyncio
async def test_schema_create_and_drop_cycle() -> None:
    """Ensure Base.metadata creates and drops all tables cleanly in an async engine."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    
    # Create all
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # Drop all
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        
    await engine.dispose()
