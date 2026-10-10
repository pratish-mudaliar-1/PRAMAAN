"""tests/unit/test_audit_hash_chain.py — Audit log hash chain unit tests."""
import asyncio
import hashlib
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def audit_repo(sqlite_session: AsyncSession):  # type: ignore[no-untyped-def]
    from app.db.repositories.audit import AuditRepository
    return AuditRepository(sqlite_session)


@pytest.mark.asyncio
async def test_first_row_has_zero_prev_hash(audit_repo) -> None:  # type: ignore[no-untyped-def]
    row = await audit_repo.append(
        actor="system",
        action="test.action",
        resource_type="test",
    )
    assert row.prev_hash == "0" * 64
    assert len(row.row_hash) == 64


@pytest.mark.asyncio
async def test_second_row_links_to_first(audit_repo) -> None:  # type: ignore[no-untyped-def]
    r1 = await audit_repo.append(actor="system", action="a1", resource_type="t")
    r2 = await audit_repo.append(actor="user-1", action="a2", resource_type="t")
    assert r2.prev_hash == r1.row_hash


@pytest.mark.asyncio
async def test_multiple_rows_form_chain(audit_repo) -> None:  # type: ignore[no-untyped-def]
    rows = []
    for i in range(5):
        r = await audit_repo.append(
            actor=f"actor-{i}",
            action=f"action.{i}",
            resource_type="resource",
            resource_id=str(i),
        )
        rows.append(r)

    # Verify chain continuity
    for i in range(1, len(rows)):
        assert rows[i].prev_hash == rows[i - 1].row_hash


@pytest.mark.asyncio
async def test_list_for_resource(audit_repo) -> None:  # type: ignore[no-untyped-def]
    await audit_repo.append(actor="u", action="create", resource_type="centre", resource_id="c-1")
    await audit_repo.append(actor="u", action="update", resource_type="centre", resource_id="c-1")
    await audit_repo.append(actor="u", action="create", resource_type="device", resource_id="d-1")

    centre_logs = await audit_repo.list_for_resource("centre", "c-1")
    assert len(centre_logs) == 2
    device_logs = await audit_repo.list_for_resource("device", "d-1")
    assert len(device_logs) == 1
