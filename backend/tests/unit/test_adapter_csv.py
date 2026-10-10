"""tests/unit/test_adapter_csv.py — CSV adapter unit tests with in-memory CSV data.

Tests the CsvAttendanceSource, CsvInventorySource, CsvTimetableSource,
and CsvTrainerAttendanceSource against real (in-process) CSV files written
to a temp directory.

Privacy enforcement: verifies prohibited PII fields are rejected.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio

from app.adapters.csv_file import (
    CsvAttendanceSource,
    CsvInventorySource,
    CsvTimetableSource,
    CsvTrainerAttendanceSource,
)


# ── Fixtures: write temp CSV files ────────────────────────────────────────────

@pytest.fixture
def tmp_attendance_csv(tmp_path: Path) -> Path:
    f = tmp_path / "attendance.csv"
    f.write_text(
        "batch_id,session_ref,claimed_count,source_ref\n"
        "BATCH-001,2024-06-15,30,SDMS\n"
        "BATCH-001,2024-06-16,25,SDMS\n"
        "BATCH-002,2024-06-15,40,SDMS\n"
    )
    return f


@pytest.fixture
def tmp_pii_csv(tmp_path: Path) -> Path:
    f = tmp_path / "pii.csv"
    f.write_text(
        "batch_id,name,claimed_count\n"
        "BATCH-001,Ram,30\n"
    )
    return f


@pytest.fixture
def tmp_inventory_csv(tmp_path: Path) -> Path:
    f = tmp_path / "inventory.csv"
    f.write_text(
        "centre_code,zone_code,item_class,sanctioned_count,critical\n"
        "CTR-01,ZONE-A,workbench,20,true\n"
        "CTR-01,ZONE-A,pc,15,false\n"
        "CTR-02,ZONE-B,lathe,5,true\n"
    )
    return f


@pytest.fixture
def tmp_timetable_csv(tmp_path: Path) -> Path:
    f = tmp_path / "timetable.csv"
    f.write_text(
        "centre_code,batch_id,zone_code,scheduled_start,scheduled_end,trade_code\n"
        "CTR-01,BATCH-001,ZONE-A,2024-06-15 09:00,2024-06-15 13:00,WELDER\n"
        "CTR-01,BATCH-001,ZONE-A,2024-06-16 09:00,2024-06-16 13:00,WELDER\n"
        "CTR-02,BATCH-002,ZONE-B,2024-06-15 10:00,2024-06-15 14:00,FITTER\n"
    )
    return f


@pytest.fixture
def tmp_trainer_csv(tmp_path: Path) -> Path:
    f = tmp_path / "trainers.csv"
    f.write_text(
        "batch_id,session_ref,trainer_count\n"
        "BATCH-001,2024-06-15,2\n"
        "BATCH-001,2024-06-16,1\n"
    )
    return f


# ── Attendance source ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_attendance_returns_correct_batch(tmp_attendance_csv: Path) -> None:
    src = CsvAttendanceSource(str(tmp_attendance_csv))
    results = await src.get_claimed_counts(
        "BATCH-001",
        datetime(2024, 6, 14, tzinfo=UTC),
        datetime(2024, 6, 17, tzinfo=UTC),
    )
    assert len(results) == 2
    assert all(r.batch_id == "BATCH-001" for r in results)
    counts = {r.session_ref: r.claimed_count for r in results}
    assert counts["2024-06-15"] == 30
    assert counts["2024-06-16"] == 25


@pytest.mark.asyncio
async def test_attendance_different_batch_excluded(tmp_attendance_csv: Path) -> None:
    src = CsvAttendanceSource(str(tmp_attendance_csv))
    results = await src.get_claimed_counts(
        "BATCH-002",
        datetime(2024, 6, 14, tzinfo=UTC),
        datetime(2024, 6, 17, tzinfo=UTC),
    )
    assert len(results) == 1
    assert results[0].claimed_count == 40


@pytest.mark.asyncio
async def test_attendance_health_check_ok(tmp_attendance_csv: Path) -> None:
    src = CsvAttendanceSource(str(tmp_attendance_csv))
    assert await src.health_check() is True


@pytest.mark.asyncio
async def test_attendance_health_check_missing_file() -> None:
    src = CsvAttendanceSource("/nonexistent/path.csv")
    assert await src.health_check() is False


@pytest.mark.asyncio
async def test_pii_rejection(tmp_pii_csv: Path) -> None:
    src = CsvAttendanceSource(str(tmp_pii_csv))
    with pytest.raises(ValueError, match="prohibited personal data"):
        await src.get_claimed_counts(
            "BATCH-001",
            datetime(2024, 6, 14, tzinfo=UTC),
            datetime(2024, 6, 17, tzinfo=UTC),
        )


# ── Inventory source ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_inventory_returns_correct_centre(tmp_inventory_csv: Path) -> None:
    src = CsvInventorySource(str(tmp_inventory_csv))
    items = await src.get_inventory("CTR-01")
    assert len(items) == 2
    item_classes = {i.item_class for i in items}
    assert "workbench" in item_classes
    assert "pc" in item_classes


@pytest.mark.asyncio
async def test_inventory_critical_flag(tmp_inventory_csv: Path) -> None:
    src = CsvInventorySource(str(tmp_inventory_csv))
    items = await src.get_inventory("CTR-01")
    workbench = next(i for i in items if i.item_class == "workbench")
    assert workbench.critical is True
    pc = next(i for i in items if i.item_class == "pc")
    assert pc.critical is False


@pytest.mark.asyncio
async def test_inventory_other_centre_excluded(tmp_inventory_csv: Path) -> None:
    src = CsvInventorySource(str(tmp_inventory_csv))
    items = await src.get_inventory("CTR-02")
    assert len(items) == 1
    assert items[0].item_class == "lathe"


# ── Timetable source ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_timetable_returns_correct_window(tmp_timetable_csv: Path) -> None:
    src = CsvTimetableSource(str(tmp_timetable_csv))
    entries = await src.get_sessions(
        "CTR-01",
        datetime(2024, 6, 15, tzinfo=UTC),
        datetime(2024, 6, 16, tzinfo=UTC),
    )
    assert len(entries) == 2
    assert all(e.batch_id == "BATCH-001" for e in entries)


@pytest.mark.asyncio
async def test_timetable_excludes_other_centre(tmp_timetable_csv: Path) -> None:
    src = CsvTimetableSource(str(tmp_timetable_csv))
    entries = await src.get_sessions(
        "CTR-02",
        datetime(2024, 6, 15, tzinfo=UTC),
        datetime(2024, 6, 16, tzinfo=UTC),
    )
    assert len(entries) == 1
    assert entries[0].zone_code == "ZONE-B"


# ── Trainer attendance source ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_trainer_counts_batch(tmp_trainer_csv: Path) -> None:
    src = CsvTrainerAttendanceSource(str(tmp_trainer_csv))
    results = await src.get_trainer_counts(
        "BATCH-001",
        datetime(2024, 6, 14, tzinfo=UTC),
        datetime(2024, 6, 17, tzinfo=UTC),
    )
    assert len(results) == 2
    total_trainers = sum(r.trainer_count for r in results)
    assert total_trainers == 3


@pytest.mark.asyncio
async def test_trainer_counts_nonexistent_batch(tmp_trainer_csv: Path) -> None:
    src = CsvTrainerAttendanceSource(str(tmp_trainer_csv))
    results = await src.get_trainer_counts(
        "BATCH-999",
        datetime(2024, 6, 14, tzinfo=UTC),
        datetime(2024, 6, 17, tzinfo=UTC),
    )
    assert results == []
