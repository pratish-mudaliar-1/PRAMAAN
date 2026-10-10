"""tests/unit/test_clock.py — Tests for clock abstractions."""
import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.core.clock import FrozenClock, SteppingClock, SystemClock


def test_system_clock_is_utc() -> None:
    clock = SystemClock()
    now = clock.utcnow()
    assert now.tzinfo is not None
    assert now.tzinfo == UTC


def test_frozen_clock_returns_fixed_time() -> None:
    fixed = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    clock = FrozenClock(fixed)
    assert clock.utcnow() == fixed
    # Calling multiple times returns the same value
    assert clock.utcnow() == fixed


def test_stepping_clock_advances() -> None:
    start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
    clock = SteppingClock(start, step_seconds=30)
    t1 = clock.utcnow()
    t2 = clock.utcnow()
    t3 = clock.utcnow()
    assert t1 == start
    assert t2 == start + timedelta(seconds=30)
    assert t3 == start + timedelta(seconds=60)
