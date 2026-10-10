"""app/core/security/device_key.py — Ed25519 device request signing verification.

Edge devices sign each observation record using their Ed25519 private key.
The server verifies against the stored public key.

Signing protocol:
  signature = Ed25519Sign(privkey, canonical_json_bytes(payload))

Canonical JSON = json.dumps(payload, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=True).encode('utf-8')

The signature is base64url-encoded (no padding) in the HTTP header:
  X-Device-Signature: <base64url>

And also embedded per-record in the observation payload signature field.
"""
from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

import nacl.exceptions
import nacl.signing


def canonical_json(payload: dict[str, Any]) -> bytes:
    """Produce canonical JSON bytes (sorted keys, no whitespace, ASCII-safe)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def compute_record_hash(canonical_bytes: bytes) -> str:
    """SHA-256 of the canonical payload bytes, hex-encoded."""
    return hashlib.sha256(canonical_bytes).hexdigest()


def verify_record_signature(
    *,
    public_key_bytes: bytes,
    canonical_bytes: bytes,
    signature_b64url: str,
) -> None:
    """Verify an Ed25519 signature over canonical_bytes.

    Raises ValueError if the signature is invalid.
    public_key_bytes: 32-byte raw Ed25519 public key (as stored in DB).
    signature_b64url: base64url-encoded (no padding) 64-byte signature.
    """
    # Restore padding for standard base64 decode
    padded = signature_b64url + "=" * (4 - len(signature_b64url) % 4)
    try:
        sig_bytes = base64.urlsafe_b64decode(padded)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Invalid signature encoding: {exc}") from exc

    try:
        verify_key = nacl.signing.VerifyKey(public_key_bytes)
        verify_key.verify(canonical_bytes, sig_bytes)
    except nacl.exceptions.BadSignatureError as exc:
        raise ValueError("Ed25519 signature verification failed") from exc


def encode_public_key(public_key_bytes: bytes) -> str:
    """Base64url-encode a 32-byte public key for storage / display."""
    return base64.urlsafe_b64encode(public_key_bytes).rstrip(b"=").decode("ascii")


def decode_public_key(encoded: str) -> bytes:
    """Decode a base64url public key back to 32 raw bytes."""
    padded = encoded + "=" * (4 - len(encoded) % 4)
    return base64.urlsafe_b64decode(padded)


# ── Test helper (used only by contract_client, not production code) ──────────

class DeviceSigningKey:
    """Wraps an Ed25519 signing key pair. Used exclusively in the contract test client."""

    def __init__(self) -> None:
        self._sk = nacl.signing.SigningKey.generate()

    @classmethod
    def from_seed(cls, seed: bytes) -> "DeviceSigningKey":
        obj = cls.__new__(cls)
        obj._sk = nacl.signing.SigningKey(seed)
        return obj

    @property
    def public_key_bytes(self) -> bytes:
        return bytes(self._sk.verify_key)

    @property
    def public_key_b64url(self) -> str:
        return encode_public_key(self.public_key_bytes)

    def sign(self, payload: dict[str, Any]) -> tuple[str, str]:
        """Return (record_hash_hex, signature_b64url) for the given payload dict."""
        cb = canonical_json(payload)
        rec_hash = compute_record_hash(cb)
        signed = self._sk.sign(cb)
        sig_bytes = signed.signature
        sig_b64 = base64.urlsafe_b64encode(sig_bytes).rstrip(b"=").decode("ascii")
        return rec_hash, sig_b64
