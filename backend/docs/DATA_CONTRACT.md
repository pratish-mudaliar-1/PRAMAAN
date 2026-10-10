# PRAMAAN Data Contracts & API Schema Specification

## 1. Edge-to-Backend Observation Contract

### 1.1 Ingestion Payload Schema (`POST /v1/ingest/observations`)
```json
{
  "device_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "zone_id": "e4d2629b-7da7-4e3a-86c2-04e38c35201a",
  "session_id": "8c6b738e-97c2-4a0b-93e1-925763b01a8f",
  "minute_ts": "2024-06-15T09:30:00Z",
  "persons_p90": 28.5,
  "feed_health": 1.0,
  "frames_used": 60,
  "prev_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "record_hash": "a4f8b2...64-char-hex-sha256...",
  "signature": "base64url-encoded-ed25519-signature"
}
```

### 1.2 Canonical Hashing Algorithm
```python
import hashlib
import json

canonical_data = {
    "device_id": str(device_id),
    "feed_health": float(feed_health),
    "frames_used": int(frames_used),
    "minute_ts": minute_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "persons_p90": float(persons_p90),
    "prev_hash": prev_hash or "",
    "session_id": str(session_id) if session_id else None,
    "zone_id": str(zone_id) if zone_id else None,
}
canonical_bytes = json.dumps(canonical_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
computed_hash = hashlib.sha256(canonical_bytes).hexdigest()
```

---

## 2. External System Integration Interfaces

### 2.1 Attendance System (`AttendanceAdapter`)
- Input: `get_session_attendance(session_id: UUID) -> AttendanceRecord`
- Record: `session_id`, `claimed_count` (int), `timestamp` (UTC). **No trainee names or individual logs.**

### 2.2 Timetable System (`TimetableAdapter`)
- Input: `get_active_sessions(centre_id: UUID, window_start: datetime, window_end: datetime) -> list[TimetableSession]`
- Record: `session_id`, `batch_id`, `zone_id`, `scheduled_start`, `scheduled_end`, `trainer_count`.

### 2.3 Inventory System (`InventoryAdapter`)
- Input: `get_zone_equipment(zone_id: UUID) -> list[SanctionedEquipment]`
- Record: `item_class`, `required_count`.

---

## 3. RFC 9457 Problem Details Error Contract

```json
{
  "type": "https://pramaan.gov.in/errors/ATTENDANCE_MISMATCH",
  "title": "Attendance Mismatch",
  "status": 422,
  "detail": "Observed headcount ratio 0.35 is below required threshold 0.80",
  "instance": "/v1/sessions/8c6b738e-97c2-4a0b-93e1-925763b01a8f",
  "error_id": "550e8400-e29b-41d4-a716-446655440000"
}
```
