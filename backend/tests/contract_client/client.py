"""tests/contract_client/client.py — Contract-conformance test client.

This module is a TEST TOOL ONLY. It builds correctly signed, hash-chained
observation records from fixtures to exercise the ingestion pipeline.

It is NOT application code and must NOT be imported from application modules.
It mirrors the contract that real edge devices must implement, as documented
in docs/EDGE_CONTRACT.md.

Usage:
    python -m tests.contract_client.client  (or imported in integration tests)
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.security.device_key import (
    DeviceSigningKey,
    canonical_json,
    compute_record_hash,
)


class ContractClient:
    """Builds signed, hash-chained observation batches for testing.

    Each instance represents one edge device with a stable signing key.
    Records form a hash chain: each record's prev_hash is the previous
    record's record_hash, starting with None for the first record.
    """

    def __init__(
        self,
        device_id: uuid.UUID,
        *,
        seed: bytes | None = None,
        model_version: str = "test-model-v1.0",
    ) -> None:
        self.device_id = device_id
        self.model_version = model_version
        self._key = DeviceSigningKey.from_seed(seed) if seed else DeviceSigningKey()
        self._last_hash: str | None = None

    @property
    def public_key_b64url(self) -> str:
        return self._key.public_key_b64url

    @property
    def public_key_bytes(self) -> bytes:
        return self._key.public_key_bytes

    def build_record(
        self,
        *,
        zone_id: uuid.UUID,
        minute_ts: datetime,
        persons_p90: float = 25.0,
        persons_min: int = 20,
        persons_max: int = 30,
        feed_health: float = 1.0,
        frames_used: int = 60,
        item_counts: dict[str, int] | None = None,
        session_id: uuid.UUID | None = None,
        tamper_hash: bool = False,       # inject a bad hash (for negative tests)
        tamper_signature: bool = False,  # inject a bad signature (for negative tests)
        override_prev_hash: str | None = None,  # force a specific prev_hash
    ) -> dict[str, Any]:
        """Build one signed observation record following the edge contract."""
        ts = minute_ts.replace(second=0, microsecond=0, tzinfo=UTC if not minute_ts.tzinfo else minute_ts.tzinfo)
        ts_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ") if ts.tzinfo == UTC else ts.isoformat()

        payload_for_hash: dict[str, Any] = {
            "minute_ts": ts_str,
            "zone_id": str(zone_id),
            "session_id": str(session_id) if session_id else None,
            "persons_min": persons_min,
            "persons_median": float((persons_min + persons_max) / 2),
            "persons_p90": persons_p90,
            "persons_max": persons_max,
            "item_counts": item_counts or {},
            "feed_health": feed_health,
            "frames_used": frames_used,
            "model_version": self.model_version,
            "prev_hash": override_prev_hash if override_prev_hash is not None else self._last_hash,
        }

        record_hash, signature = self._key.sign(payload_for_hash)

        if tamper_hash:
            record_hash = "a" * 64   # corrupt hash

        if tamper_signature:
            signature = "A" * 86 + "=="   # corrupt signature (wrong length handled gracefully)
            signature = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"

        # Build the full record that will be sent to the API
        record: dict[str, Any] = {
            **payload_for_hash,
            "record_hash": record_hash,
            "signature": signature,
        }

        # Advance chain (even on tampered records — real device would)
        if not tamper_hash:
            self._last_hash = record_hash

        return record

    def build_batch(
        self,
        zone_id: uuid.UUID,
        *,
        start_ts: datetime,
        num_records: int = 5,
        persons_p90: float = 25.0,
        feed_health: float = 1.0,
    ) -> dict[str, Any]:
        """Build a complete batch request payload."""
        records = []
        for i in range(num_records):
            minute_ts = start_ts + timedelta(minutes=i)
            rec = self.build_record(
                zone_id=zone_id,
                minute_ts=minute_ts,
                persons_p90=persons_p90,
                feed_health=feed_health,
            )
            records.append(rec)

        return {
            "device_id": str(self.device_id),
            "records": records,
        }

    def reset_chain(self) -> None:
        """Reset the hash chain — simulates device restart."""
        self._last_hash = None
