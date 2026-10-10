"""app/adapters/csv_file.py — CSV file implementations of all adapter interfaces.

Reads real CSV files from disk (or S3 path). Field mapping is configurable via YAML.
No personal data accepted — validation rejects rows containing name/aadhaar fields.

Example YAML config (attendance):
  path: /data/attendance.csv
  field_map:
    batch_id: batch_code
    session_ref: session_date
    claimed_count: total_present
    source_ref: source_system_ref
  date_format: "%Y-%m-%d %H:%M"

Privacy enforcement: rows containing 'name', 'aadhaar', 'pan', 'mobile' columns
are rejected with a validation error logged (no data stored).
"""
from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.adapters.interfaces import (
    AggregateCount, AttendanceSource, InventoryItem, InventorySource,
    TimetableEntry, TimetableSource, TrainerAttendanceSource, TrainerCount,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

# Fields that must never appear in source data
_PROHIBITED_FIELDS = frozenset({
    "name", "full_name", "first_name", "last_name", "aadhaar",
    "aadhar", "pan", "mobile", "phone", "email", "address",
    "dob", "date_of_birth", "trainee_id", "employee_id",
})


def _check_prohibited(headers: list[str], source: str) -> None:
    found = [h for h in headers if h.lower() in _PROHIBITED_FIELDS]
    if found:
        raise ValueError(
            f"CSV source '{source}' contains prohibited personal data fields: {found}. "
            "Per DATA_CONTRACT.md, no individual identifiers may be present."
        )


def _parse_dt(value: str, fmt: str) -> datetime:
    dt = datetime.strptime(value.strip(), fmt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class CsvAttendanceSource(AttendanceSource):
    """Reads aggregate attendance from a CSV file."""

    def __init__(
        self,
        path: str,
        *,
        field_map: dict[str, str] | None = None,
        date_format: str = "%Y-%m-%d %H:%M",
    ) -> None:
        self._path = Path(path)
        self._map = field_map or {
            "batch_id": "batch_id",
            "session_ref": "session_ref",
            "claimed_count": "claimed_count",
        }
        self._date_fmt = date_format

    async def get_claimed_counts(
        self, batch_id: str, window_start: datetime, window_end: datetime
    ) -> list[AggregateCount]:
        results: list[AggregateCount] = []
        with self._path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            headers = reader.fieldnames or []
            _check_prohibited(list(headers), str(self._path))
            for row in reader:
                if row.get(self._map["batch_id"]) != batch_id:
                    continue
                try:
                    count = int(row[self._map["claimed_count"]])
                except (KeyError, ValueError) as exc:
                    logger.warning("csv_attendance_bad_row", row=dict(row), error=str(exc))
                    continue
                results.append(AggregateCount(
                    batch_id=batch_id,
                    session_ref=row.get(self._map.get("session_ref", "session_ref"), ""),
                    claimed_count=count,
                    source_ref=row.get(self._map.get("source_ref", "source_ref"), ""),
                ))
        return results

    async def health_check(self) -> bool:
        return self._path.exists()


class CsvTimetableSource(TimetableSource):
    """Reads timetable (scheduled sessions) from a CSV file."""

    def __init__(
        self,
        path: str,
        *,
        field_map: dict[str, str] | None = None,
        date_format: str = "%Y-%m-%d %H:%M",
    ) -> None:
        self._path = Path(path)
        self._map = field_map or {
            "batch_id": "batch_id",
            "zone_code": "zone_code",
            "scheduled_start": "scheduled_start",
            "scheduled_end": "scheduled_end",
        }
        self._date_fmt = date_format

    async def get_sessions(
        self, centre_code: str, from_date: datetime, to_date: datetime
    ) -> list[TimetableEntry]:
        results: list[TimetableEntry] = []
        from_dt = _ensure_utc(from_date)
        to_dt = _ensure_utc(to_date)
        if to_dt.hour == 0 and to_dt.minute == 0 and to_dt.second == 0 and to_dt.microsecond == 0:
            to_dt = to_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        with self._path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            _check_prohibited(list(reader.fieldnames or []), str(self._path))
            for row in reader:
                if row.get("centre_code", "") != centre_code:
                    continue
                try:
                    start = _parse_dt(row[self._map["scheduled_start"]], self._date_fmt)
                    end = _parse_dt(row[self._map["scheduled_end"]], self._date_fmt)
                    if not (from_dt <= start <= to_dt):
                        continue
                    results.append(TimetableEntry(
                        batch_id=row[self._map["batch_id"]],
                        zone_code=row[self._map["zone_code"]],
                        scheduled_start=start,
                        scheduled_end=end,
                        trade_code=row.get("trade_code"),
                        source_ref=row.get("source_ref"),
                    ))
                except (KeyError, ValueError) as exc:
                    logger.warning("csv_timetable_bad_row", error=str(exc))
        return results

    async def health_check(self) -> bool:
        return self._path.exists()


class CsvInventorySource(InventorySource):
    """Reads sanctioned inventory from a CSV file."""

    def __init__(
        self,
        path: str,
        *,
        field_map: dict[str, str] | None = None,
    ) -> None:
        self._path = Path(path)
        self._map = field_map or {
            "centre_code": "centre_code",
            "zone_code": "zone_code",
            "item_class": "item_class",
            "sanctioned_count": "sanctioned_count",
        }

    async def get_inventory(self, centre_code: str) -> list[InventoryItem]:
        results: list[InventoryItem] = []
        with self._path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            _check_prohibited(list(reader.fieldnames or []), str(self._path))
            for row in reader:
                if row.get(self._map["centre_code"], "") != centre_code:
                    continue
                try:
                    results.append(InventoryItem(
                        centre_code=centre_code,
                        zone_code=row[self._map["zone_code"]],
                        item_class=row[self._map["item_class"]],
                        sanctioned_count=int(row[self._map["sanctioned_count"]]),
                        critical=row.get("critical", "false").lower() == "true",
                        source_ref=row.get("source_ref"),
                    ))
                except (KeyError, ValueError) as exc:
                    logger.warning("csv_inventory_bad_row", error=str(exc))
        return results

    async def health_check(self) -> bool:
        return self._path.exists()


class CsvTrainerAttendanceSource(TrainerAttendanceSource):
    """Reads aggregate trainer counts from a CSV file."""

    def __init__(
        self,
        path: str,
        *,
        field_map: dict[str, str] | None = None,
    ) -> None:
        self._path = Path(path)
        self._map = field_map or {
            "batch_id": "batch_id",
            "session_ref": "session_ref",
            "trainer_count": "trainer_count",
        }

    async def get_trainer_counts(
        self, batch_id: str, window_start: datetime, window_end: datetime
    ) -> list[TrainerCount]:
        results: list[TrainerCount] = []
        with self._path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            _check_prohibited(list(reader.fieldnames or []), str(self._path))
            for row in reader:
                if row.get(self._map["batch_id"]) != batch_id:
                    continue
                try:
                    results.append(TrainerCount(
                        batch_id=batch_id,
                        session_ref=row.get(self._map.get("session_ref", "session_ref"), ""),
                        trainer_count=int(row[self._map["trainer_count"]]),
                        source_ref=row.get("source_ref"),
                    ))
                except (KeyError, ValueError) as exc:
                    logger.warning("csv_trainer_bad_row", error=str(exc))
        return results

    async def health_check(self) -> bool:
        return self._path.exists()
