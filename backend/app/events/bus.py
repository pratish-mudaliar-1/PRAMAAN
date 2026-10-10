"""app/events/bus.py — Real-time event broker with role/tenant-aware routing."""
from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, AsyncIterator

import structlog

from app.core.security.policy import Principal

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class EventMessage:
    """An event dispatched over the real-time event bus."""
    event_type: str
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    centre_id: str | None = None
    state_code: str | None = None
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "centre_id": self.centre_id,
            "state_code": self.state_code,
            "payload": self.payload,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


def can_principal_receive_event(principal: Principal, event: EventMessage) -> bool:
    """Check if the principal's role and tenant scoping permit receiving this event."""
    if "national_admin" in principal.roles or "auditor" in principal.roles:
        return True

    if "state_officer" in principal.roles:
        if event.state_code is None:
            return True
        return principal.state_code == event.state_code

    if "inspector" in principal.roles or "training_centre" in principal.roles:
        if event.centre_id is None:
            return False
        return event.centre_id in principal.centre_ids

    return False


class EventBus:
    """In-memory and Redis-backed publish/subscribe event bus."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[EventMessage]] = set()
        self._lock = asyncio.Lock()

    async def publish(self, event: EventMessage) -> None:
        """Broadcast an event to all connected active listener queues."""
        async with self._lock:
            subs = list(self._subscribers)

        for queue in subs:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Event bus queue full, dropping event", event_type=event.event_type)

    async def subscribe(self, maxsize: int = 100) -> AsyncIterator[EventMessage]:
        """Subscribe to events as an async generator."""
        queue: asyncio.Queue[EventMessage] = asyncio.Queue(maxsize=maxsize)
        async with self._lock:
            self._subscribers.add(queue)
        try:
            while True:
                msg = await queue.get()
                yield msg
        finally:
            async with self._lock:
                self._subscribers.discard(queue)


# Global singleton event bus
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
