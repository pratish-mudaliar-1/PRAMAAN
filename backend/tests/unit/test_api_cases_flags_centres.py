"""tests/unit/test_api_cases_flags_centres.py — Tests for centres, sessions, flags, cases API."""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db_session
from app.core.security.jwt import create_dev_token
from app.db.models.case_ import Case, CaseEvent
from app.db.models.centre import Centre, Zone
from app.db.models.device import Device, DeviceStatusEnum
from app.db.models.flag import Flag
from app.db.models.session_ import Batch, Session
from app.main import create_app


@pytest_asyncio.fixture
async def sample_db_data(sqlite_session: AsyncSession) -> tuple[Centre, Zone, Batch, Session, Flag]:
    centre = Centre(
        name="Hubballi Tech Academy",
        code="CTR-HUB-01",
        state_code="KA",
        district="Dharwad",
        scheme_code="PMKVY",
    )
    sqlite_session.add(centre)
    await sqlite_session.flush()

    zone = Zone(centre_id=centre.id, zone_code="LAB-01", zone_type="practical_lab", coverage_factor=1.0)
    sqlite_session.add(zone)
    await sqlite_session.flush()

    batch = Batch(
        centre_id=centre.id,
        batch_code="BATCH-HUB-01",
        scheme_code="PMKVY",
        enrolled_count=25,
        batch_start_date=datetime(2024, 6, 1, tzinfo=UTC).date(),
        batch_end_date=datetime(2024, 8, 31, tzinfo=UTC).date(),
    )
    sqlite_session.add(batch)
    await sqlite_session.flush()

    start = datetime(2024, 6, 15, 9, 0, 0, tzinfo=UTC)
    end = datetime(2024, 6, 15, 11, 0, 0, tzinfo=UTC)
    session = Session(
        batch_id=batch.id,
        zone_id=zone.id,
        scheduled_start=start,
        scheduled_end=end,
        claimed_count=25,
        trainer_count=1,
        attendance_status="AMBER",
        attendance_ratio=0.45,
    )
    sqlite_session.add(session)
    await sqlite_session.flush()

    flag = Flag(
        centre_id=centre.id,
        session_id=session.id,
        zone_id=zone.id,
        flag_key=f"flag-test-{uuid.uuid4().hex[:8]}",
        flag_type="ATTENDANCE_MISMATCH",
        severity="AMBER",
        status="OPEN",
        rule_name="attendance_p90_mismatch",
        rule_version="1.0",
        description="Observed attendance below amber threshold",
    )
    sqlite_session.add(flag)
    await sqlite_session.flush()

    return centre, zone, batch, session, flag


@pytest_asyncio.fixture
async def client_and_session(sqlite_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _override_get_db() -> Any:
        yield sqlite_session

    app.dependency_overrides[get_db_session] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_centres_api_list_and_get(
    client_and_session: AsyncClient,
    sample_db_data: tuple[Centre, Zone, Batch, Session, Flag],
) -> None:
    centre, _, _, _, _ = sample_db_data
    token = create_dev_token(subject="admin-1", roles=["national_admin"], secret="test-secret-key")

    # List centres
    res = await client_and_session.get("/v1/centres", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) >= 1
    assert data["items"][0]["code"] == "CTR-HUB-01"

    # Get single centre
    res2 = await client_and_session.get(f"/v1/centres/{centre.id}", headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 200
    assert res2.json()["name"] == "Hubballi Tech Academy"


@pytest.mark.asyncio
async def test_sessions_and_flags_api(
    client_and_session: AsyncClient,
    sample_db_data: tuple[Centre, Zone, Batch, Session, Flag],
) -> None:
    centre, _, _, session, flag = sample_db_data
    token = create_dev_token(subject="admin-1", roles=["national_admin"], secret="test-secret-key")

    # List sessions
    res = await client_and_session.get("/v1/sessions", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert len(res.json()["items"]) >= 1

    # Get single session
    res_s = await client_and_session.get(f"/v1/sessions/{session.id}", headers={"Authorization": f"Bearer {token}"})
    assert res_s.status_code == 200
    assert res_s.json()["claimed_count"] == 25

    # List flags
    res_f = await client_and_session.get("/v1/flags", headers={"Authorization": f"Bearer {token}"})
    assert res_f.status_code == 200
    assert len(res_f.json()["items"]) >= 1

    # Resolve flag
    res_res = await client_and_session.post(
        f"/v1/flags/{flag.id}/resolve",
        json={"resolution_reason": "Verified biometric offline log with state officer", "status": "CLOSED_DISMISSED"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_res.status_code == 200
    assert res_res.json()["new_status"] == "CLOSED_DISMISSED"


@pytest.mark.asyncio
async def test_case_management_workflow(
    client_and_session: AsyncClient,
    sample_db_data: tuple[Centre, Zone, Batch, Session, Flag],
) -> None:
    centre, _, _, _, flag = sample_db_data
    token = create_dev_token(subject="admin-1", roles=["national_admin"], secret="test-secret-key")

    # 1. Create a case
    create_res = await client_and_session.post(
        "/v1/cases",
        json={
            "centre_id": str(centre.id),
            "title": "Severe attendance deviation in Hubballi",
            "description": "Observed multiple consecutive mismatch sessions",
            "priority": "HIGH",
            "flag_ids": [str(flag.id)],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_res.status_code == 200
    case_data = create_res.json()
    case_id = case_data["id"]
    assert case_data["status"] == "OPEN"

    # 2. Get case
    get_res = await client_and_session.get(f"/v1/cases/{case_id}", headers={"Authorization": f"Bearer {token}"})
    assert get_res.status_code == 200
    assert len(get_res.json()["events"]) >= 1

    # 3. Add case event (transition to EXPLANATION_REQUESTED)
    event_res = await client_and_session.post(
        f"/v1/cases/{case_id}/events",
        json={"to_status": "EXPLANATION_REQUESTED", "note": "Requested clarification from TC"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert event_res.status_code == 200
    assert event_res.json()["to_status"] == "EXPLANATION_REQUESTED"

    # 4. Submit TC response
    tc_token = create_dev_token(subject="tc-manager", roles=["training_centre"], centre_ids=[str(centre.id)], secret="test-secret-key")
    resp_res = await client_and_session.post(
        f"/v1/cases/{case_id}/respond",
        json={
            "response_text": "Students were attending outdoor field workshop during this practical hour.",
            "attachment_s3_keys": ["evidence/field_activity_log.pdf"],
        },
        headers={"Authorization": f"Bearer {tc_token}"},
    )
    assert resp_res.status_code == 200
    assert "response_id" in resp_res.json()

    # 5. Check case status transitioned to TC_RESPONDED
    updated_res = await client_and_session.get(f"/v1/cases/{case_id}", headers={"Authorization": f"Bearer {token}"})
    assert updated_res.status_code == 200
    assert updated_res.json()["status"] == "TC_RESPONDED"
    assert len(updated_res.json()["tc_responses"]) == 1
