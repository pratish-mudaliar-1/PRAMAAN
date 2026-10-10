"""app/core/clock.py — Injectable clock abstraction.

All code that needs 'now' must depend on this interface so tests can
freeze/advance time deterministically without monkey-patching.
"""
from __future__ import annotations

import abc
from datetime import UTC, datetime


class AbstractClock(abc.ABC):
    """Minimal clock interface for production and test usage."""

    @abc.abstractmethod
    def utcnow(self) -> datetime:
        """Return the current UTC time as a timezone-aware datetime."""


class SystemClock(AbstractClock):
    """Returns the real wall-clock time. Use in production."""

    def utcnow(self) -> datetime:
        return datetime.now(UTC)


class FrozenClock(AbstractClock):
    """Returns a fixed time. Use in unit tests."""

    def __init__(self, frozen_at: datetime) -> None:
        self._frozen_at = frozen_at

    def utcnow(self) -> datetime:
        return self._frozen_at


class SteppingClock(AbstractClock):
    """Advances by a fixed step on each call. Useful for sequence-sensitive tests."""

    def __init__(self, start: datetime, step_seconds: float = 1.0) -> None:
        from datetime import timedelta
        self._current = start
        self._step = timedelta(seconds=step_seconds)

    def utcnow(self) -> datetime:
        from datetime import timedelta  # noqa: PLC0415
        result = self._current
        self._current += self._step
        return result


# Singleton for production use — replace in DI container for tests
system_clock = SystemClock()
