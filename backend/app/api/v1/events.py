"""app/api/v1/events.py — Real-time WebSocket and SSE event streaming endpoints."""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse

from app.api.v1.deps import CurrentPrincipal
from app.core.errors import AuthenticationError
from app.core.security.jwt import get_token_verifier
from app.core.security.policy import Principal
from app.events.bus import EventMessage, can_principal_receive_event, get_event_bus

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/events", tags=["events"])


def _authenticate_ws_token(token: str | None) -> Principal:
    if not token:
        raise AuthenticationError("Missing token query parameter for WebSocket")
    verifier = get_token_verifier()
    claims = verifier.verify(token)
    return Principal.from_claims(claims)


@router.websocket("/ws")
async def websocket_events_endpoint(
    websocket: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    """WebSocket stream for real-time flags, cases, integrity alerts, and heartbeats.
    
    Scoped automatically based on the user's role and tenant attributes in JWT.
    """
    try:
        principal = _authenticate_ws_token(token)
    except Exception as exc:
        logger.warning("WebSocket authentication failed", error=str(exc))
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    bus = get_event_bus()

    async def _listen_and_forward() -> None:
        async for event in bus.subscribe():
            if can_principal_receive_event(principal, event):
                await websocket.send_text(event.to_json())

    async def _ping_loop() -> None:
        while True:
            await asyncio.sleep(30.0)
            await websocket.send_text(json.dumps({"event_type": "PING", "timestamp": "heartbeat"}))

    forward_task = asyncio.create_task(_listen_and_forward())
    ping_task = asyncio.create_task(_ping_loop())

    try:
        while True:
            # Keep receiving client heartbeats or messages
            msg = await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("WebSocket error", error=str(exc))
    finally:
        forward_task.cancel()
        ping_task.cancel()
        try:
            await websocket.close()
        except Exception:
            pass


@router.get("/stream")
async def sse_events_stream(
    principal: CurrentPrincipal,
) -> StreamingResponse:
    """Server-Sent Events (SSE) fallback endpoint for clients unable to use WebSockets."""
    bus = get_event_bus()

    async def event_generator() -> AsyncGenerator[str, None]:
        # Initial connect message
        yield f"event: connected\ndata: {json.dumps({'status': 'ok'})}\n\n"
        
        queue: asyncio.Queue[EventMessage] = asyncio.Queue(maxsize=100)
        async with bus._lock:
            bus._subscribers.add(queue)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    if can_principal_receive_event(principal, event):
                        yield f"event: {event.event_type}\ndata: {event.to_json()}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            async with bus._lock:
                bus._subscribers.discard(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
