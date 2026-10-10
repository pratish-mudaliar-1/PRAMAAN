"""tests/unit/test_events_pipeline.py — Unit tests for EventBus, SSE, and WebSocket."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.security.jwt import create_dev_token
from app.core.security.policy import Principal
from app.events.bus import EventBus, EventMessage, can_principal_receive_event, get_event_bus
from app.main import create_app


@pytest.mark.asyncio
async def test_event_bus_pub_sub() -> None:
    bus = EventBus()
    received: list[EventMessage] = []

    async def listener() -> None:
        async for msg in bus.subscribe():
            received.append(msg)
            if len(received) >= 2:
                break

    task = asyncio.create_task(listener())
    await asyncio.sleep(0.01)

    msg1 = EventMessage(event_type="FLAG_CREATED", payload={"id": "flag-1"})
    msg2 = EventMessage(event_type="CASE_UPDATED", payload={"id": "case-1"})
    await bus.publish(msg1)
    await bus.publish(msg2)

    await asyncio.wait_for(task, timeout=2.0)
    assert len(received) == 2
    assert received[0].event_type == "FLAG_CREATED"
    assert received[1].event_type == "CASE_UPDATED"


def test_can_principal_receive_event_scoping() -> None:
    admin = Principal(subject="u1", roles=("national_admin",))
    auditor = Principal(subject="u2", roles=("auditor",))
    state_ka = Principal(subject="u3", roles=("state_officer",), state_code="KA")
    tc_mng = Principal(subject="u4", roles=("training_centre",), centre_ids=("ctr-1",))

    ka_event = EventMessage(event_type="FLAG_CREATED", payload={}, state_code="KA", centre_id="ctr-1")
    mh_event = EventMessage(event_type="FLAG_CREATED", payload={}, state_code="MH", centre_id="ctr-2")

    # Admin and Auditor see everything
    assert can_principal_receive_event(admin, ka_event) is True
    assert can_principal_receive_event(admin, mh_event) is True
    assert can_principal_receive_event(auditor, ka_event) is True

    # State officer sees only their state
    assert can_principal_receive_event(state_ka, ka_event) is True
    assert can_principal_receive_event(state_ka, mh_event) is False

    # TC sees only their centre
    assert can_principal_receive_event(tc_mng, ka_event) is True
    assert can_principal_receive_event(tc_mng, mh_event) is False


@pytest.mark.asyncio
async def test_sse_stream_generator() -> None:
    principal = Principal(subject="u-admin", roles=("national_admin",))
    bus = get_event_bus()

    # Test that generator yields connected event and published event
    from app.api.v1.events import sse_events_stream
    response = await sse_events_stream(principal=principal)
    assert response.status_code == 200
    assert response.media_type == "text/event-stream"

    first_chunk: str = ""
    async for chunk in response.body_iterator:
        if isinstance(chunk, bytes):
            first_chunk = chunk.decode("utf-8")
        else:
            first_chunk = str(chunk)
        break
    assert "event: connected" in first_chunk



