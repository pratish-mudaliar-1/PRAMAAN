"""tests/unit/test_schemas.py — Pydantic schema validation tests.

Verifies that all ingestion schemas reject bad inputs, accept good inputs,
and enforce privacy (no PII fields accepted).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from typing import Any

from app.api.v1.schemas import (
    DeviceEnrollRequest,
    EvidencePresignRequest,
    HeartbeatRequest,
    ObservationBatchRequest,
    ObservationRecord,
)


def make_record(**kwargs: Any) -> dict[str, Any]:
    defaults = {
        "minute_ts": "2024-06-15T09:00:00Z",
        "zone_id": str(uuid.uuid4()),
        "persons_p90": 25.0,
        "feed_health": 0.95,
        "frames_used": 58,
        "record_hash": "a" * 64,
        "signature": "B" * 86,
    }
    defaults.update(kwargs)
    return defaults


# ── ObservationRecord ──────────────────────────────────────────────────────────

def test_record_accepts_valid_minimal() -> None:
    rec = ObservationRecord(**make_record())
    assert rec.persons_p90 == 25.0


def test_record_minute_ts_is_truncated() -> None:
    rec = ObservationRecord(**make_record(minute_ts="2024-06-15T09:02:47Z"))
    assert rec.minute_ts.second == 0
    assert rec.minute_ts.microsecond == 0


def test_record_rejects_negative_persons() -> None:
    with pytest.raises(ValidationError):
        ObservationRecord(**make_record(persons_p90=-1.0))


def test_record_rejects_feed_health_above_one() -> None:
    with pytest.raises(ValidationError):
        ObservationRecord(**make_record(feed_health=1.1))


def test_record_rejects_feed_health_negative() -> None:
    with pytest.raises(ValidationError):
        ObservationRecord(**make_record(feed_health=-0.1))


def test_record_rejects_short_record_hash() -> None:
    with pytest.raises(ValidationError):
        ObservationRecord(**make_record(record_hash="abc"))


def test_record_rejects_extra_fields() -> None:
    """extra='forbid' must reject unknown fields — prevents PII injection."""
    with pytest.raises(ValidationError):
        ObservationRecord(**make_record(aadhaar="1234-5678-9012"))


def test_record_rejects_name_field() -> None:
    with pytest.raises(ValidationError):
        ObservationRecord(**make_record(trainee_name="Someone"))


def test_record_item_counts_accepts_dict() -> None:
    rec = ObservationRecord(**make_record(item_counts={"workbench": 10, "pc": 5}))
    assert rec.item_counts == {"workbench": 10, "pc": 5}


# ── ObservationBatchRequest ────────────────────────────────────────────────────

def test_batch_rejects_empty_records() -> None:
    with pytest.raises(ValidationError):
        ObservationBatchRequest(device_id=str(uuid.uuid4()), records=[])


def test_batch_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ObservationBatchRequest.model_validate({
            "device_id": str(uuid.uuid4()),
            "records": [make_record()],
            "extra_field": "not_allowed",
        })


def test_batch_accepts_valid() -> None:
    batch = ObservationBatchRequest(
        device_id=str(uuid.uuid4()),
        records=[make_record()],
    )
    assert len(batch.records) >= 1  # just ensure it parses


# ── DeviceEnrollRequest ────────────────────────────────────────────────────────

def test_enroll_rejects_short_public_key() -> None:
    with pytest.raises(ValidationError):
        DeviceEnrollRequest(
            serial_number="DEV-001",
            centre_id=str(uuid.uuid4()),
            public_key_b64url="short",
            enrollment_token="tok-123",
        )


def test_enroll_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        DeviceEnrollRequest.model_validate({
            "serial_number": "DEV-001",
            "centre_id": str(uuid.uuid4()),
            "public_key_b64url": "A" * 43,
            "enrollment_token": "tok",
            "employee_id": "EMP001",    # PII — must be rejected
        })


def test_enroll_accepts_valid() -> None:
    req = DeviceEnrollRequest(
        serial_number="CAM-A-001",
        centre_id=str(uuid.uuid4()),
        public_key_b64url="A" * 43,
        enrollment_token="one-time-tok",
    )
    assert req.serial_number == "CAM-A-001"


# ── EvidencePresignRequest ────────────────────────────────────────────────────

def test_presign_rejects_oversized() -> None:
    with pytest.raises(ValidationError):
        EvidencePresignRequest(
            device_id=str(uuid.uuid4()),
            content_type="image/jpeg",
            size_bytes=10 * 1024 * 1024,  # 10MB — over limit
        )


def test_presign_rejects_wrong_mime() -> None:
    with pytest.raises(ValidationError):
        EvidencePresignRequest(
            device_id=str(uuid.uuid4()),
            content_type="video/mp4",
            size_bytes=1024,
        )


def test_presign_accepts_valid() -> None:
    req = EvidencePresignRequest(
        device_id=str(uuid.uuid4()),
        content_type="image/jpeg",
        size_bytes=512 * 1024,
    )
    assert req.size_bytes == 512 * 1024


# ── HeartbeatRequest ──────────────────────────────────────────────────────────

def test_heartbeat_rejects_negative_queue_depth() -> None:
    with pytest.raises(ValidationError):
        HeartbeatRequest(**{"device_id": str(uuid.uuid4()), "queue_depth": -1})


def test_heartbeat_rejects_cpu_over_100() -> None:
    with pytest.raises(ValidationError):
        HeartbeatRequest(device_id=str(uuid.uuid4()), cpu_percent=101.0)


def test_heartbeat_accepts_valid_minimal() -> None:
    hb = HeartbeatRequest(device_id=str(uuid.uuid4()))
    assert hb.model_version is None


def test_heartbeat_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        HeartbeatRequest.model_validate({"device_id": str(uuid.uuid4()), "secret_api_key": "hack"})
