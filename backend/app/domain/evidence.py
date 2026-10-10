"""app/domain/evidence.py — Pure perceptual hash computation and Hamming distance functions.

Privacy: All perceptual hashing is done on redacted/scene-level frames.
No biometric face templates or personal identifiers are extracted or stored.
"""
from __future__ import annotations

import io
from typing import Final

import imagehash
from PIL import Image

DEFAULT_HAMMING_THRESHOLD: Final[int] = 5  # Initial hypothesis: Hamming distance <= 5 implies near-duplicate


def compute_phash_from_image(image: Image.Image) -> tuple[str, int]:
    """Compute 64-bit difference hash (dHash) from PIL Image.

    Returns:
        phash_hex: 16-character hexadecimal representation.
        phash_int: 64-bit integer representation for fast bitwise Hamming distance computation.
    """
    dh = imagehash.dhash(image, hash_size=8)
    phash_hex = str(dh)
    phash_int = int(phash_hex, 16)
    return phash_hex, phash_int


def compute_phash_from_bytes(image_bytes: bytes) -> tuple[str, int]:
    """Compute 64-bit difference hash (dHash) from raw image bytes."""
    with Image.open(io.BytesIO(image_bytes)) as img:
        return compute_phash_from_image(img)


def hamming_distance(hash1: int, hash2: int) -> int:
    """Compute the Hamming distance (number of differing bits) between two 64-bit hashes."""
    return (hash1 ^ hash2).bit_count()


def is_near_duplicate(
    hash1: int, hash2: int, threshold: int = DEFAULT_HAMMING_THRESHOLD
) -> bool:
    """Return True if two hashes are within the near-duplicate Hamming distance threshold."""
    return hamming_distance(hash1, hash2) <= threshold
