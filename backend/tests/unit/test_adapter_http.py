"""tests/unit/test_adapter_http.py — HTTP REST adapter tests with respx mocking."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
import respx
import httpx

from app.adapters.http_rest import (
    HttpAttendanceSource,
    HttpInventorySource,
    HttpTimetableSource,
    HttpTrainerAttendanceSource,
    validate_url_ssrf_safe,
)


# ── SSRF Security Tests ───────────────────────────────────────────────────────

def test_ssrf_blocks_loopback() -> None:
    with pytest.raises(ValueError, match="Loopback IP"):
        validate_url_ssrf_safe("http://127.0.0.1:8080/api")


def test_ssrf_blocks_cloud_metadata() -> None:
    with pytest.raises(ValueError, match="Restricted IP|Private IP"):
        validate_url_ssrf_safe("http://169.254.169.254/latest/meta-data")


def test_ssrf_blocks_private_networks() -> None:
    with pytest.raises(ValueError, match="Private IP"):
        validate_url_ssrf_safe("http://10.1.2.3/api")
    with pytest.raises(ValueError, match="Private IP"):
        validate_url_ssrf_safe("http://192.168.1.10/api")


def test_ssrf_blocks_invalid_scheme() -> None:
    with pytest.raises(ValueError, match="Invalid URL scheme"):
        validate_url_ssrf_safe("ftp://example.com/data.csv")


def test_ssrf_allows_when_explicitly_permitted_for_tests() -> None:
    # Should not raise
    validate_url_ssrf_safe("http://127.0.0.1:8080/api", allow_private=True)


# ── HTTP Adapter Functionality Tests (with respx) ────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_http_attendance_source() -> None:
    base = "http://127.0.0.1:9999"
    respx.get(f"{base}/attendance").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {"batch_id": "BATCH-01", "session_ref": "2024-06-15", "claimed_count": 28, "source_ref": "SDMS"},
                    {"batch_id": "BATCH-01", "session_ref": "2024-06-16", "claimed_count": 25, "source_ref": "SDMS"},
                ]
            },
        )
    )

    src = HttpAttendanceSource(base, allow_private=True)
    counts = await src.get_claimed_counts("BATCH-01", datetime.now(UTC), datetime.now(UTC))
    assert len(counts) == 2
    assert counts[0].claimed_count == 28
    assert counts[1].claimed_count == 25


@pytest.mark.asyncio
@respx.mock
async def test_http_timetable_source() -> None:
    base = "http://127.0.0.1:9999"
    respx.get(f"{base}/timetable").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "batch_id": "BATCH-01",
                        "zone_code": "ZONE-A",
                        "scheduled_start": "2024-06-15T09:00:00Z",
                        "scheduled_end": "2024-06-15T13:00:00Z",
                        "trade_code": "ELECTRICIAN",
                    }
                ]
            },
        )
    )

    src = HttpTimetableSource(base, allow_private=True)
    sessions = await src.get_sessions("CTR-01", datetime.now(UTC), datetime.now(UTC))
    assert len(sessions) == 1
    assert sessions[0].zone_code == "ZONE-A"
    assert sessions[0].trade_code == "ELECTRICIAN"


@pytest.mark.asyncio
@respx.mock
async def test_http_inventory_source() -> None:
    base = "http://127.0.0.1:9999"
    respx.get(f"{base}/inventory/CTR-01").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "zone_code": "LAB-1",
                        "item_class": "multimeter",
                        "sanctioned_count": 10,
                        "critical": True,
                    }
                ]
            },
        )
    )

    src = HttpInventorySource(base, allow_private=True)
    inv = await src.get_inventory("CTR-01")
    assert len(inv) == 1
    assert inv[0].item_class == "multimeter"
    assert inv[0].sanctioned_count == 10
    assert inv[0].critical is True


@pytest.mark.asyncio
@respx.mock
async def test_http_trainer_attendance_source() -> None:
    base = "http://127.0.0.1:9999"
    respx.get(f"{base}/trainer-attendance").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {"batch_id": "BATCH-01", "session_ref": "2024-06-15", "trainer_count": 2}
                ]
            },
        )
    )

    src = HttpTrainerAttendanceSource(base, allow_private=True)
    trainers = await src.get_trainer_counts("BATCH-01", datetime.now(UTC), datetime.now(UTC))
    assert len(trainers) == 1
    assert trainers[0].trainer_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_http_adapter_rejects_pii() -> None:
    base = "http://127.0.0.1:9999"
    respx.get(f"{base}/attendance").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {"batch_id": "BATCH-01", "name": "Aadhaar Cardholder", "claimed_count": 30}
                ]
            },
        )
    )

    src = HttpAttendanceSource(base, allow_private=True)
    with pytest.raises(ValueError, match="prohibited field 'name'"):
        await src.get_claimed_counts("BATCH-01", datetime.now(UTC), datetime.now(UTC))
