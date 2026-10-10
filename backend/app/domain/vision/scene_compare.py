"""app/domain/vision/scene_compare.py — Pure server-side scene comparison.

INPUTS:  image bytes (query) + image bytes (reference) + optional masks
OUTPUTS: SceneMetrics dataclass (all metrics) + SceneClassification enum

This module has NO I/O, NO side effects. It is a pure function of its inputs.
Re-running with the same inputs ALWAYS gives identical outputs (deterministic).

Algorithm version: v1
Working resolution: 480 x 360 px (stored in ALGORITHM_VERSION tag)

Dependencies: opencv-python-headless, numpy, scikit-image
Install: pip install opencv-python-headless numpy scikit-image

Privacy: this module never receives un-redacted frames. Redacted regions
(blurred faces/bodies from edge privacy model) are excluded from all metrics
via the valid_mask computation. The module cannot and does not attempt to
un-blur or identify any person.

Limits (documented honestly):
- A swap to a visually near-identical room may score high similarity.
- A high-quality looped/replayed stream scores identically to a live view.
- These are known residual risks; random server challenges reduce but do not
  eliminate them.
"""
from __future__ import annotations

import io
import struct
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

# OpenCV and scikit-image are optional at import time so the rest of the app
# does not fail if they are not installed. Functions raise ImportError with a
# helpful message when called without the deps.
try:
    import cv2  # type: ignore[import-untyped]
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False

try:
    from skimage.metrics import structural_similarity as _ssim  # type: ignore[import-untyped]
    _SKIMAGE_AVAILABLE = True
except ImportError:
    _SKIMAGE_AVAILABLE = False


# ── Constants ─────────────────────────────────────────────────────────────────

ALGORITHM_VERSION = "v1"
WORKING_WIDTH = 480
WORKING_HEIGHT = 360
WORKING_SHAPE = (WORKING_HEIGHT, WORKING_WIDTH)

# ORB parameters
_ORB_N_FEATURES = 1000
_ORB_RATIO_TEST = 0.75        # Lowe's ratio test threshold
_ORB_MIN_MATCHES = 8          # minimum matches for RANSAC to be meaningful
_ORB_RANSAC_REPROJ = 5.0      # reprojection error threshold (pixels)

# Histogram parameters
_HIST_BINS = 32               # bins per HSV channel

# Minimum valid-pixel area (fraction of working resolution)
_MIN_VALID_PIXEL_FRACTION = 0.05


# ── Data structures ───────────────────────────────────────────────────────────

class SceneClassification(str, Enum):
    STABLE          = "STABLE"
    LIGHTING_CHANGE = "LIGHTING_CHANGE"
    OCCLUDED        = "OCCLUDED"
    MOVED           = "MOVED"
    SWAPPED         = "SWAPPED"
    UNKNOWN         = "UNKNOWN"


@dataclass(frozen=True)
class SceneMetrics:
    """All similarity metrics from one pairwise comparison.

    All values are server-computed; edge-reported values are stored separately
    and are NEVER used as inputs to this function.

    phash_dist:       pHash Hamming distance [0, 64]; lower = more similar.
    orb_inliers:      RANSAC geometric inlier count; higher = same geometry.
    inlier_ratio:     orb_inliers / total_matched_kps; [0, 1].
    ssim_masked:      SSIM on valid-pixel region; [−1, 1]; −1 if mask too small.
    hist_distance:    HSV histogram Bhattacharyya distance; [0, 1]; lower = similar.
    fused_similarity: weighted combination; [0, 1]; 1.0 = identical.
    transform_params: homography decomposition (tx, ty, rotation_deg, scale).
    classification:   scene classification decision.
    valid_pixel_fraction: fraction of working-resolution pixels in the valid mask.
    algorithm_version: version string for cache invalidation.
    """
    phash_dist: int                             # [0, 64]
    orb_inliers: int
    inlier_ratio: float                         # [0, 1]
    ssim_masked: float                          # [−1, 1] or −1.0 for INSUFFICIENT_MASK
    hist_distance: float                        # [0, 1]
    fused_similarity: float                     # [0, 1]
    transform_params: dict[str, float]          # {tx_px, ty_px, rotation_deg, scale}
    classification: SceneClassification
    valid_pixel_fraction: float                 # fraction of frame that is valid
    algorithm_version: str = ALGORITHM_VERSION


@dataclass(frozen=True)
class VisionWeights:
    """Fusion weights for similarity metrics.

    All weights must sum to 1.0.
    Initial hypothesis values — calibrate in pilot.
    """
    phash: float = 0.25
    orb_inlier_ratio: float = 0.35
    ssim: float = 0.25
    hist: float = 0.15


@dataclass(frozen=True)
class CameraThresholds:
    """Decision thresholds for scene classification.

    All values are initial hypotheses — calibrate in pilot.
    These should be loaded from ThresholdProfile.extra; defaults here
    are only used when no profile is available.
    """
    # fused_similarity thresholds
    swap_threshold: float = 0.40       # below this → suspicious (SWAPPED candidate)
    moved_threshold: float = 0.65      # [swap, moved) → MOVED candidate
    # ORB geometry
    orb_inlier_ratio_swap: float = 0.10  # inlier_ratio < this → low geometric match
    orb_min_inliers_moved: int = 20    # need this many inliers to call MOVED (not SWAPPED)
    # pHash
    phash_swap_threshold: int = 20     # Hamming >= this → suspicious
    # SSIM
    ssim_swap_threshold: float = 0.40
    # Histogram
    hist_lighting_threshold: float = 0.35  # hist_distance > this with stable geometry → LIGHTING_CHANGE
    # Transform magnitude for MOVED classification
    moved_max_rotation_deg: float = 30.0   # rotation > this → suspicious (not a nudge)
    moved_max_scale_change: float = 0.30   # |scale - 1.0| > this → suspicious


# ── Helper: require OpenCV ────────────────────────────────────────────────────

def _require_cv2() -> None:
    if not _CV2_AVAILABLE:
        raise ImportError(
            "opencv-python-headless is required for scene comparison. "
            "Install with: pip install opencv-python-headless numpy scikit-image"
        )

def _require_skimage() -> None:
    if not _SKIMAGE_AVAILABLE:
        raise ImportError(
            "scikit-image is required for SSIM computation. "
            "Install with: pip install scikit-image"
        )


# ── Image loading ─────────────────────────────────────────────────────────────

def load_image(image_bytes: bytes) -> np.ndarray:
    """Decode image bytes to BGR numpy array at working resolution.

    Raises ValueError on corrupt, oversized, or unsupported images.
    """
    _require_cv2()
    if len(image_bytes) == 0:
        raise ValueError("Empty image bytes")
    if len(image_bytes) > 20 * 1024 * 1024:   # 20 MB hard limit
        raise ValueError(f"Image too large: {len(image_bytes)} bytes (max 20 MB)")

    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image (corrupt or unsupported format)")

    img = cv2.resize(img, (WORKING_WIDTH, WORKING_HEIGHT), interpolation=cv2.INTER_AREA)
    return img


def build_valid_mask(
    shape: tuple[int, int],
    include_polygons: list[list[tuple[int, int]]] | None = None,
    exclude_polygons: list[list[tuple[int, int]]] | None = None,
) -> np.ndarray:
    """Build a binary mask (uint8, 255=valid, 0=excluded).

    include_polygons: static regions to include (e.g. fixed furniture areas).
                      If None, the entire frame is included initially.
    exclude_polygons: blurred/redacted regions to exclude (faces, bodies).
                      These override includes.
    """
    _require_cv2()
    h, w = shape
    mask = np.ones((h, w), dtype=np.uint8) * 255

    if include_polygons:
        # Start with blank and fill only included regions
        include_mask = np.zeros((h, w), dtype=np.uint8)
        for poly in include_polygons:
            pts = np.array(poly, dtype=np.int32).reshape((-1, 1, 2))
            cv2.fillPoly(include_mask, [pts], 255)
        mask = cv2.bitwise_and(mask, include_mask)

    if exclude_polygons:
        exclude_mask = np.zeros((h, w), dtype=np.uint8)
        for poly in exclude_polygons:
            pts = np.array(poly, dtype=np.int32).reshape((-1, 1, 2))
            cv2.fillPoly(exclude_mask, [pts], 255)
        mask = cv2.bitwise_and(mask, cv2.bitwise_not(exclude_mask))

    return mask


# ── pHash ─────────────────────────────────────────────────────────────────────

def compute_phash(img: np.ndarray) -> int:
    """Compute 64-bit perceptual hash (dHash) of an image.

    dHash: compare brightness of adjacent pixels in an 8×8 downscaled image.
    Returns an integer with bits set where left pixel is brighter than right.
    """
    _require_cv2()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    diff = small[:, 1:] > small[:, :-1]
    bits = diff.flatten()
    # Pack 64 bits into an integer
    result = 0
    for b in bits:
        result = (result << 1) | int(b)
    return result


def phash_distance(h1: int, h2: int) -> int:
    """Hamming distance between two 64-bit pHashes."""
    xor = h1 ^ h2
    return bin(xor).count("1")


def phash_hex(h: int) -> str:
    """Encode pHash integer as 16-char hex string."""
    return f"{h:016x}"


def phash_from_hex(s: str) -> int:
    """Decode 16-char hex string to pHash integer."""
    return int(s, 16)


# ── ORB feature matching ──────────────────────────────────────────────────────

def extract_orb_features(
    img: np.ndarray,
    mask: np.ndarray | None = None,
) -> tuple[list[Any], np.ndarray | None]:
    """Extract ORB keypoints and descriptors from an image.

    Returns (keypoints, descriptors). descriptors is None if no keypoints found.
    """
    _require_cv2()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB.create(nfeatures=_ORB_N_FEATURES)
    kps, desc = orb.detectAndCompute(gray, mask if mask is not None else None)
    return list(kps), desc


def match_orb_features(
    desc_query: np.ndarray,
    desc_reference: np.ndarray,
    kps_query: list[Any],
    kps_reference: list[Any],
) -> tuple[int, float, dict[str, float]]:
    """Match ORB descriptors and estimate homography with RANSAC.

    Returns:
        inlier_count: number of RANSAC geometric inliers
        inlier_ratio: inlier_count / len(good_matches)
        transform_params: {tx_px, ty_px, rotation_deg, scale}
    """
    _require_cv2()
    empty_transform: dict[str, float] = {
        "tx_px": 0.0, "ty_px": 0.0, "rotation_deg": 0.0, "scale": 1.0
    }

    if desc_query is None or desc_reference is None:
        return 0, 0.0, empty_transform

    # BFMatcher with Hamming (ORB uses binary descriptors)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    raw_matches = bf.knnMatch(desc_query, desc_reference, k=2)

    # Lowe's ratio test
    good: list[Any] = []
    for pair in raw_matches:
        if len(pair) == 2:
            m, n = pair
            if m.distance < _ORB_RATIO_TEST * n.distance:
                good.append(m)

    if len(good) < _ORB_MIN_MATCHES:
        return 0, 0.0, empty_transform

    src_pts = np.array([kps_query[m.queryIdx].pt for m in good], dtype=np.float32).reshape(-1, 1, 2)
    dst_pts = np.array([kps_reference[m.trainIdx].pt for m in good], dtype=np.float32).reshape(-1, 1, 2)

    H, inlier_mask = cv2.findHomography(
        src_pts, dst_pts, cv2.RANSAC, _ORB_RANSAC_REPROJ
    )

    if H is None or inlier_mask is None:
        return 0, 0.0, empty_transform

    inlier_count = int(inlier_mask.sum())
    inlier_ratio = inlier_count / len(good) if good else 0.0

    # Decompose homography to get rough tx, ty, rotation, scale
    transform_params = _decompose_homography(H)
    return inlier_count, inlier_ratio, transform_params


def _decompose_homography(H: np.ndarray) -> dict[str, float]:
    """Extract approximate translation, rotation and scale from a homography.

    Uses SVD decomposition. Results are approximate (homography is not a
    rigid transform) but sufficient for distinguishing MOVED from SWAPPED.
    """
    tx = float(H[0, 2])
    ty = float(H[1, 2])

    # Scale = geometric mean of singular values of the 2×2 sub-matrix
    sub = H[:2, :2]
    _, s, _ = np.linalg.svd(sub)
    scale = float(np.sqrt(s[0] * s[1]))

    # Rotation from the normalised sub-matrix
    if scale > 1e-6:
        norm_sub = sub / scale
        rotation_rad = float(np.arctan2(norm_sub[1, 0], norm_sub[0, 0]))
    else:
        rotation_rad = 0.0

    rotation_deg = float(np.degrees(rotation_rad))

    return {
        "tx_px": tx,
        "ty_px": ty,
        "rotation_deg": rotation_deg,
        "scale": scale,
    }


# ── Serialise / deserialise ORB features (for DB storage) ────────────────────

def serialise_orb_features(
    kps: list[Any],
    desc: np.ndarray | None,
) -> bytes:
    """Pack ORB keypoints + descriptors into a compressed numpy .npz blob."""
    _require_cv2()
    import io as _io
    # Keypoints: x, y, size, angle, response, octave, class_id
    if not kps:
        kp_arr = np.zeros((0, 7), dtype=np.float32)
    else:
        kp_arr = np.array(
            [[k.pt[0], k.pt[1], k.size, k.angle, k.response, k.octave, k.class_id]
             for k in kps],
            dtype=np.float32,
        )
    buf = _io.BytesIO()
    if desc is not None:
        np.savez_compressed(buf, keypoints=kp_arr, descriptors=desc.astype(np.uint8))
    else:
        np.savez_compressed(buf, keypoints=kp_arr)
    return buf.getvalue()


def deserialise_orb_features(
    blob: bytes,
) -> tuple[list[Any], np.ndarray | None]:
    """Restore ORB keypoints + descriptors from a compressed numpy .npz blob."""
    _require_cv2()
    import io as _io
    data = np.load(_io.BytesIO(blob))
    kp_arr = data["keypoints"]
    kps = [
        cv2.KeyPoint(
            x=float(row[0]), y=float(row[1]),
            size=float(row[2]), angle=float(row[3]),
            response=float(row[4]), octave=int(row[5]), class_id=int(row[6]),
        )
        for row in kp_arr
    ]
    desc = data["descriptors"] if "descriptors" in data else None
    return kps, desc


# ── HSV histogram ─────────────────────────────────────────────────────────────

def compute_hsv_histogram(
    img: np.ndarray,
    mask: np.ndarray | None = None,
) -> np.ndarray:
    """Compute a 3×32-bin HSV histogram over the valid-pixel region.

    Returns a float32 array of shape (3, HIST_BINS), normalised to [0, 1].
    """
    _require_cv2()
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    ranges = [(0, 180), (0, 256), (0, 256)]  # H, S, V ranges
    hists = []
    for ch in range(3):
        h = cv2.calcHist([hsv], [ch], mask, [_HIST_BINS], [ranges[ch][0], ranges[ch][1]])
        h = cv2.normalize(h, h).flatten()
        hists.append(h.astype(np.float32))
    return np.stack(hists, axis=0)  # shape (3, HIST_BINS)


def histogram_distance(h1: np.ndarray, h2: np.ndarray) -> float:
    """Bhattacharyya distance between two HSV histograms [0, 1].

    0 = identical distributions, 1 = completely different.
    """
    _require_cv2()
    dist = 0.0
    for ch in range(3):
        # cv2.HISTCMP_BHATTACHARYYA returns [0, 1]
        d = float(cv2.compareHist(
            h1[ch].reshape(-1, 1),
            h2[ch].reshape(-1, 1),
            cv2.HISTCMP_BHATTACHARYYA,
        ))
        dist += d
    return dist / 3.0


def serialise_histogram(hist: np.ndarray) -> bytes:
    """Compress HSV histogram to bytes for DB storage."""
    buf = io.BytesIO()
    np.savez_compressed(buf, histogram=hist)
    return buf.getvalue()


def deserialise_histogram(blob: bytes) -> np.ndarray:
    """Restore HSV histogram from DB blob."""
    data = np.load(io.BytesIO(blob))
    return np.asarray(data["histogram"])


# ── SSIM ──────────────────────────────────────────────────────────────────────

def compute_ssim_masked(
    img_query: np.ndarray,
    img_reference: np.ndarray,
    mask: np.ndarray,
) -> float:
    """Structural similarity on valid-pixel region only.

    Returns SSIM in [-1, 1]. Returns -1.0 if the valid mask covers less than
    MIN_VALID_PIXEL_FRACTION of the working-resolution frame (mask too small
    to be meaningful; logged as INSUFFICIENT_MASK).
    """
    _require_cv2()
    _require_skimage()

    total_pixels = mask.shape[0] * mask.shape[1]
    valid_pixels = int(np.sum(mask > 0))
    if valid_pixels < _MIN_VALID_PIXEL_FRACTION * total_pixels:
        return -1.0   # INSUFFICIENT_MASK

    gray_q = cv2.cvtColor(img_query, cv2.COLOR_BGR2GRAY)
    gray_r = cv2.cvtColor(img_reference, cv2.COLOR_BGR2GRAY)

    # Apply mask: set excluded pixels to the mean of valid pixels to avoid
    # border-effect bias without introducing fabricated content.
    mean_q = float(gray_q[mask > 0].mean()) if valid_pixels > 0 else 128.0
    mean_r = float(gray_r[mask > 0].mean()) if valid_pixels > 0 else 128.0

    masked_q = gray_q.copy().astype(np.float32)
    masked_r = gray_r.copy().astype(np.float32)
    masked_q[mask == 0] = mean_q
    masked_r[mask == 0] = mean_r

    score, _ = _ssim(masked_q, masked_r, full=True, data_range=255.0)
    return float(score)


# ── Fused similarity ──────────────────────────────────────────────────────────

def fuse_similarity(
    phash_dist: int,
    inlier_ratio: float,
    ssim: float,
    hist_distance: float,
    weights: VisionWeights | None = None,
) -> float:
    """Combine metrics into a single similarity score in [0, 1].

    Higher = more similar to reference.
    ssim == -1.0 (INSUFFICIENT_MASK) → ssim component is excluded,
    remaining weights are renormalised.
    """
    w = weights or VisionWeights()

    # Convert each metric to [0, 1] similarity
    phash_sim = 1.0 - (phash_dist / 64.0)
    orb_sim = min(inlier_ratio, 1.0)
    hist_sim = 1.0 - min(hist_distance, 1.0)

    if ssim < -0.5:  # INSUFFICIENT_MASK sentinel
        # Renormalise without SSIM component
        total_w = w.phash + w.orb_inlier_ratio + w.hist
        if total_w < 1e-6:
            return 0.0
        return (
            w.phash * phash_sim
            + w.orb_inlier_ratio * orb_sim
            + w.hist * hist_sim
        ) / total_w

    ssim_sim = (ssim + 1.0) / 2.0  # [-1,1] → [0,1]
    return (
        w.phash * phash_sim
        + w.orb_inlier_ratio * orb_sim
        + w.ssim * ssim_sim
        + w.hist * hist_sim
    )


# ── Classification decision ───────────────────────────────────────────────────

def classify_scene(
    metrics_partial: dict[str, float | int],
    thresholds: CameraThresholds | None = None,
) -> SceneClassification:
    """Classify a scene observation from computed metrics.

    Decision rules (applied in order; first match wins):

    1. UNKNOWN — not enough evidence (mask too small, no ORB features)
    2. STABLE — fused_similarity >= moved_threshold AND inlier_ratio high
    3. LIGHTING_CHANGE — fused_similarity >= swap_threshold BUT histogram
       distance is high while ORB geometry is intact (same room, lights changed)
    4. OCCLUDED — ssim is very low but fused is moderate (partial blockage)
    5. MOVED — fused >= swap_threshold, good ORB inliers, non-trivial transform
    6. SWAPPED — fused < swap_threshold, very low ORB inlier ratio
    7. UNKNOWN — fallback
    """
    t = thresholds or CameraThresholds()

    phash_dist: int = int(metrics_partial.get("phash_dist", 64))
    inlier_ratio: float = float(metrics_partial.get("inlier_ratio", 0.0))
    orb_inliers: int = int(metrics_partial.get("orb_inliers", 0))
    ssim: float = float(metrics_partial.get("ssim_masked", -1.0))
    hist_dist: float = float(metrics_partial.get("hist_distance", 1.0))
    fused: float = float(metrics_partial.get("fused_similarity", 0.0))
    rotation_deg: float = float(metrics_partial.get("rotation_deg", 0.0))
    scale: float = float(metrics_partial.get("scale", 1.0))

    # Validity check
    if ssim < -0.5 and orb_inliers == 0:
        return SceneClassification.UNKNOWN

    # STABLE — high similarity, solid geometry
    if fused >= t.moved_threshold and inlier_ratio >= t.orb_inlier_ratio_swap:
        return SceneClassification.STABLE

    # LIGHTING_CHANGE — same geometry (good inliers), but histogram diverges
    if (inlier_ratio >= t.orb_inlier_ratio_swap
            and hist_dist > t.hist_lighting_threshold
            and fused >= t.swap_threshold):
        return SceneClassification.LIGHTING_CHANGE

    # OCCLUDED — structural similarity drops sharply but geometry partly intact
    if ssim < t.ssim_swap_threshold and inlier_ratio >= t.orb_inlier_ratio_swap:
        return SceneClassification.OCCLUDED

    # MOVED — sufficient geometry but non-trivial transform
    if (orb_inliers >= t.orb_min_inliers_moved
            and inlier_ratio >= t.orb_inlier_ratio_swap
            and (abs(rotation_deg) > 2.0 or abs(scale - 1.0) > 0.05)):
        if (abs(rotation_deg) <= t.moved_max_rotation_deg
                and abs(scale - 1.0) <= t.moved_max_scale_change):
            return SceneClassification.MOVED

    # SWAPPED — low overall similarity, very poor ORB match
    if fused < t.swap_threshold and inlier_ratio < t.orb_inlier_ratio_swap:
        return SceneClassification.SWAPPED

    return SceneClassification.UNKNOWN


# ── Main entry point ──────────────────────────────────────────────────────────

def compare_scene(
    query_bytes: bytes,
    reference_bytes: bytes,
    *,
    include_polygons: list[list[tuple[int, int]]] | None = None,
    exclude_polygons: list[list[tuple[int, int]]] | None = None,
    weights: VisionWeights | None = None,
    thresholds: CameraThresholds | None = None,
) -> SceneMetrics:
    """Compare a query keyframe against a reference keyframe.

    This is the main server-side verification function.
    Pure: same inputs → same output always.

    Args:
        query_bytes:      JPEG/PNG bytes of the query (current) keyframe.
        reference_bytes:  JPEG/PNG bytes of the reference keyframe.
        include_polygons: static regions to include in comparison.
        exclude_polygons: redacted regions to exclude (faces/bodies).
        weights:          fusion weights (None = defaults).
        thresholds:       classification thresholds (None = defaults).

    Returns:
        SceneMetrics with all computed values and classification.

    Raises:
        ValueError: if either image is corrupt, empty, or oversized.
        ImportError: if opencv-python-headless or scikit-image is not installed.
    """
    _require_cv2()

    # 1. Load and decode both images
    img_q = load_image(query_bytes)
    img_r = load_image(reference_bytes)

    # 2. Build valid-pixel mask (same mask applied to both)
    mask = build_valid_mask(
        WORKING_SHAPE,
        include_polygons=include_polygons,
        exclude_polygons=exclude_polygons,
    )
    valid_pixel_fraction = float(np.sum(mask > 0)) / (WORKING_HEIGHT * WORKING_WIDTH)

    # 3. pHash distance (on full masked image)
    ph_q = compute_phash(img_q)
    ph_r = compute_phash(img_r)
    pd = phash_distance(ph_q, ph_r)

    # 4. ORB features + geometric matching
    kps_q, desc_q = extract_orb_features(img_q, mask if valid_pixel_fraction < 0.95 else None)
    kps_r, desc_r = extract_orb_features(img_r, mask if valid_pixel_fraction < 0.95 else None)

    if desc_q is not None and desc_r is not None:
        orb_inliers, inlier_ratio, transform_params = match_orb_features(
            desc_q, desc_r, kps_q, kps_r
        )
    else:
        orb_inliers, inlier_ratio = 0, 0.0
        transform_params = {"tx_px": 0.0, "ty_px": 0.0, "rotation_deg": 0.0, "scale": 1.0}

    # 5. SSIM on masked region
    ssim_val = compute_ssim_masked(img_q, img_r, mask)

    # 6. HSV histogram distance
    hist_q = compute_hsv_histogram(img_q, mask)
    hist_r = compute_hsv_histogram(img_r, mask)
    hist_dist = histogram_distance(hist_q, hist_r)

    # 7. Fused similarity
    fused = fuse_similarity(pd, inlier_ratio, ssim_val, hist_dist, weights)

    # 8. Classification
    metrics_dict: dict[str, float | int] = {
        "phash_dist": pd,
        "inlier_ratio": inlier_ratio,
        "orb_inliers": orb_inliers,
        "ssim_masked": ssim_val,
        "hist_distance": hist_dist,
        "fused_similarity": fused,
        "rotation_deg": transform_params.get("rotation_deg", 0.0),
        "scale": transform_params.get("scale", 1.0),
    }
    classification = classify_scene(metrics_dict, thresholds)

    return SceneMetrics(
        phash_dist=pd,
        orb_inliers=orb_inliers,
        inlier_ratio=inlier_ratio,
        ssim_masked=ssim_val,
        hist_distance=hist_dist,
        fused_similarity=fused,
        transform_params=transform_params,
        classification=classification,
        valid_pixel_fraction=valid_pixel_fraction,
        algorithm_version=ALGORITHM_VERSION,
    )


def compare_scene_against_references(
    query_bytes: bytes,
    references: list[tuple[bytes, list[list[tuple[int, int]]] | None, list[list[tuple[int, int]]] | None]],
    *,
    weights: VisionWeights | None = None,
    thresholds: CameraThresholds | None = None,
) -> SceneMetrics:
    """Compare query against multiple reference images; return best match.

    Used when multiple active references exist (e.g. day + night lighting).
    Best match = highest fused_similarity.

    references: list of (reference_bytes, include_polygons, exclude_polygons)
    """
    if not references:
        raise ValueError("At least one reference is required")

    best: SceneMetrics | None = None
    for ref_bytes, inc_polys, exc_polys in references:
        m = compare_scene(
            query_bytes, ref_bytes,
            include_polygons=inc_polys,
            exclude_polygons=exc_polys,
            weights=weights,
            thresholds=thresholds,
        )
        if best is None or m.fused_similarity > best.fused_similarity:
            best = m

    assert best is not None
    return best
