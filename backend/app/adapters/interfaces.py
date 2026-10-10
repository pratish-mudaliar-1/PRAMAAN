"""app/adapters/interfaces.py — Abstract interfaces for all external data sources.

Each source has exactly two implementations: csv_file and http_rest.
Switch between them by config (YAML) only — no code changes needed.

Privacy: all methods return only aggregate counts, never individual names or IDs.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AggregateCount:
    """Aggregate attendance count for a batch-session. No individual identifiers."""
    batch_id: str
    session_ref: str
    claimed_count: int
    source_ref: str | None = None
    as_of: datetime | None = None


@dataclass(frozen=True)
class TimetableEntry:
    batch_id: str
    zone_code: str
    scheduled_start: datetime
    scheduled_end: datetime
    trade_code: str | None = None
    source_ref: str | None = None


@dataclass(frozen=True)
class InventoryItem:
    centre_code: str
    zone_code: str
    item_class: str
    sanctioned_count: int
    critical: bool = False
    source_ref: str | None = None


@dataclass(frozen=True)
class TrainerCount:
    """Aggregate trainer count for a session. No individual names."""
    batch_id: str
    session_ref: str
    trainer_count: int
    source_ref: str | None = None


class AttendanceSource(abc.ABC):
    """Returns aggregate claimed attendance counts per batch-session."""

    @abc.abstractmethod
    async def get_claimed_counts(
        self, batch_id: str, window_start: datetime, window_end: datetime
    ) -> list[AggregateCount]: ...

    @abc.abstractmethod
    async def health_check(self) -> bool: ...


class TimetableSource(abc.ABC):
    """Returns the timetable (scheduled sessions) for a centre or batch."""

    @abc.abstractmethod
    async def get_sessions(
        self, centre_code: str, from_date: datetime, to_date: datetime
    ) -> list[TimetableEntry]: ...

    @abc.abstractmethod
    async def health_check(self) -> bool: ...


class InventorySource(abc.ABC):
    """Returns sanctioned infrastructure inventory per centre."""

    @abc.abstractmethod
    async def get_inventory(self, centre_code: str) -> list[InventoryItem]: ...

    @abc.abstractmethod
    async def health_check(self) -> bool: ...


class TrainerAttendanceSource(abc.ABC):
    """Returns aggregate trainer attendance counts. No individual names."""

    @abc.abstractmethod
    async def get_trainer_counts(
        self, batch_id: str, window_start: datetime, window_end: datetime
    ) -> list[TrainerCount]: ...

    @abc.abstractmethod
    async def health_check(self) -> bool: ...


class Notifier(abc.ABC):
    """Send notifications for cases and flags."""

    @abc.abstractmethod
    async def send(self, subject: str, body: str, recipient_refs: list[str]) -> bool: ...
