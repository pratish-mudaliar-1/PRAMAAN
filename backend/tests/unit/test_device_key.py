"""tests/unit/test_device_key.py — Ed25519 signing and verification unit tests."""
import json
import pytest

from app.core.security.device_key import (
    DeviceSigningKey,
    canonical_json,
    compute_record_hash,
    decode_public_key,
    encode_public_key,
    verify_record_signature,
)


def test_canonical_json_is_sorted_and_compact() -> None:
    payload = {"z": 1, "a": 2, "m": "hello world"}
    result = canonical_json(payload)
    assert result == b'{"a":2,"m":"hello world","z":1}'


def test_canonical_json_is_deterministic() -> None:
    p = {"x": [1, 2, 3], "y": {"b": True, "a": False}}
    assert canonical_json(p) == canonical_json(p)


def test_record_hash_is_sha256_hex() -> None:
    b = b"test"
    import hashlib
    expected = hashlib.sha256(b).hexdigest()
    assert compute_record_hash(b) == expected
    assert len(compute_record_hash(b)) == 64


def test_encode_decode_public_key_roundtrip() -> None:
    key = DeviceSigningKey()
    encoded = encode_public_key(key.public_key_bytes)
    decoded = decode_public_key(encoded)
    assert decoded == key.public_key_bytes


def test_sign_and_verify_success() -> None:
    key = DeviceSigningKey()
    payload = {"device_id": "dev-1", "minute_ts": "2024-06-15T09:00:00Z", "persons_p90": 25.0}
    record_hash, sig_b64 = key.sign(payload)

    # Verify should not raise
    cb = canonical_json(payload)
    verify_record_signature(
        public_key_bytes=key.public_key_bytes,
        canonical_bytes=cb,
        signature_b64url=sig_b64,
    )


def test_verify_fails_with_wrong_key() -> None:
    key1 = DeviceSigningKey()
    key2 = DeviceSigningKey()
    payload = {"x": 1}
    _, sig_b64 = key1.sign(payload)
    cb = canonical_json(payload)

    with pytest.raises(ValueError, match="signature verification failed"):
        verify_record_signature(
            public_key_bytes=key2.public_key_bytes,
            canonical_bytes=cb,
            signature_b64url=sig_b64,
        )


def test_verify_fails_with_tampered_payload() -> None:
    key = DeviceSigningKey()
    payload = {"count": 10}
    _, sig_b64 = key.sign(payload)

    tampered = canonical_json({"count": 999})
    with pytest.raises(ValueError):
        verify_record_signature(
            public_key_bytes=key.public_key_bytes,
            canonical_bytes=tampered,
            signature_b64url=sig_b64,
        )


def test_verify_fails_with_invalid_signature_encoding() -> None:
    key = DeviceSigningKey()
    with pytest.raises(ValueError):
        verify_record_signature(
            public_key_bytes=key.public_key_bytes,
            canonical_bytes=b"data",
            signature_b64url="!!!not-base64!!!",
        )


def test_signing_key_from_seed_is_deterministic() -> None:
    seed = b"\x01" * 32
    k1 = DeviceSigningKey.from_seed(seed)
    k2 = DeviceSigningKey.from_seed(seed)
    assert k1.public_key_bytes == k2.public_key_bytes
    payload = {"test": True}
    h1, s1 = k1.sign(payload)
    h2, s2 = k2.sign(payload)
    assert h1 == h2
    assert s1 == s2
