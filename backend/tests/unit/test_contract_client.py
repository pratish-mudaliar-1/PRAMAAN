"""tests/unit/test_contract_client.py — Contract client self-consistency tests.

Verifies that the contract client produces valid, verifiable records — i.e.
the same verification logic that the server will use passes on its own output.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.core.security.device_key import (
    canonical_json,
    compute_record_hash,
    verify_record_signature,
)
from tests.contract_client.client import ContractClient


DEVICE_ID = uuid.uuid4()
ZONE_ID = uuid.uuid4()
TS = datetime(2024, 6, 15, 9, 0, 0, tzinfo=UTC)


@pytest.fixture
def client() -> ContractClient:
    return ContractClient(DEVICE_ID, seed=b"\x42" * 32)


def test_client_builds_verifiable_record(client: ContractClient) -> None:
    record = client.build_record(zone_id=ZONE_ID, minute_ts=TS)
    # Extract the payload that was hashed
    payload = {k: v for k, v in record.items() if k not in ("record_hash", "signature")}
    cb = canonical_json(payload)
    expected_hash = compute_record_hash(cb)
    assert record["record_hash"] == expected_hash
    # Verify the signature
    verify_record_signature(
        public_key_bytes=client.public_key_bytes,
        canonical_bytes=cb,
        signature_b64url=record["signature"],
    )


def test_client_chain_links_records(client: ContractClient) -> None:
    r1 = client.build_record(zone_id=ZONE_ID, minute_ts=TS)
    r2 = client.build_record(zone_id=ZONE_ID, minute_ts=TS)
    assert r2["prev_hash"] == r1["record_hash"]


def test_client_first_record_has_no_prev_hash(client: ContractClient) -> None:
    r = client.build_record(zone_id=ZONE_ID, minute_ts=TS)
    assert r["prev_hash"] is None


def test_client_chain_reset(client: ContractClient) -> None:
    r1 = client.build_record(zone_id=ZONE_ID, minute_ts=TS)
    client.reset_chain()
    r2 = client.build_record(zone_id=ZONE_ID, minute_ts=TS)
    assert r2["prev_hash"] is None


def test_client_tampered_hash_does_not_verify(client: ContractClient) -> None:
    record = client.build_record(zone_id=ZONE_ID, minute_ts=TS, tamper_hash=True)
    payload = {k: v for k, v in record.items() if k not in ("record_hash", "signature")}
    cb = canonical_json(payload)
    expected = compute_record_hash(cb)
    assert record["record_hash"] != expected


def test_batch_has_correct_record_count(client: ContractClient) -> None:
    batch = client.build_batch(ZONE_ID, start_ts=TS, num_records=5)
    assert len(batch["records"]) == 5
    assert batch["device_id"] == str(DEVICE_ID)


def test_batch_records_form_chain(client: ContractClient) -> None:
    batch = client.build_batch(ZONE_ID, start_ts=TS, num_records=5)
    records = batch["records"]
    for i in range(1, len(records)):
        assert records[i]["prev_hash"] == records[i - 1]["record_hash"]


def test_deterministic_seed_produces_same_keys() -> None:
    c1 = ContractClient(DEVICE_ID, seed=b"\x01" * 32)
    c2 = ContractClient(DEVICE_ID, seed=b"\x01" * 32)
    assert c1.public_key_bytes == c2.public_key_bytes


def test_different_seeds_produce_different_keys() -> None:
    c1 = ContractClient(DEVICE_ID, seed=b"\x01" * 32)
    c2 = ContractClient(DEVICE_ID, seed=b"\x02" * 32)
    assert c1.public_key_bytes != c2.public_key_bytes
