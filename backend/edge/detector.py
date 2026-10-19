"""backend/edge/detector.py — Shared PRAMAAN person detection module.

This is the SINGLE source of truth for person detection used by:
  - backend/scripts/webcam_edge_agent.py  (production agent)
  - scripts/eval_person_counting.py        (evaluation harness)
  - scripts/debug_detection.py             (diagnostic tool)
  - backend/tests/unit/test_detector.py    (unit tests)

Any accuracy improvement goes here; the agent and harness automatically inherit it.

Licence note
------------
Ultralytics YOLOv8 is licenced under AGPL-3.0.  For any deployment beyond a
prototype / evaluation, replace with a permissively-licenced detector such as
RT-DETR (Apache-2.0 code; verify weights licence) or YOLOX (Apache-2.0).
"""
from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Public data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Detection:
    """One person detection on a single frame."""

    xyxy: tuple[float, float, float, float]   # x1, y1, x2, y2 in pixel coords
    confidence: float                          # 0.0 – 1.0
    class_id: int = 0                         # always 0 (COCO person)


@dataclass
class FrameResult:
    """Detection output for one frame."""

    detections: list[Detection] = field(default_factory=list)
    inference_ms: float = 0.0               # wall-clock time for model.predict()
    frame_index: int = 0

    @property
    def person_count(self) -> int:
        """Number of persons detected in this frame."""
        return len(self.detections)

    @property
    def confidences(self) -> list[float]:
        return [d.confidence for d in self.detections]


# ---------------------------------------------------------------------------
# PersonDetector
# ---------------------------------------------------------------------------

class PersonDetector:
    """
    Wraps Ultralytics YOLOv8 for PRAMAAN person counting.

    Parameters (all configurable; sensible defaults chosen from Phase-3 data)
    ----------
    model_path : str
        Path to .pt weights.  Searched automatically if not found.
    conf : float
        Confidence threshold.  Default 0.25 (Phase-3 finding: 0.35 was too
        conservative for partially-occluded people at close range).
    iou : float
        NMS IoU threshold.  Default 0.45 (Phase-1 root cause: 0.70 default
        merges overlapping boxes of side-by-side people).
    imgsz : int
        Inference image size (pixels).  Default 640.
    max_det : int
        Maximum detections per frame.  Default 100 (well above any realistic
        classroom scene; original default was 300 — equally fine).
    device : str
        'cpu', '0', 'cuda', etc.
    """

    # Recommended defaults (chosen from diagnostic data; see docs/DETECTION_EVAL.md)
    DEFAULT_CONF: float = 0.25
    DEFAULT_IOU: float = 0.45
    DEFAULT_IMGSZ: int = 640
    DEFAULT_MAX_DET: int = 100
    DEFAULT_DEVICE: str = "cpu"

    def __init__(
        self,
        model_path: str = "",
        conf: float = DEFAULT_CONF,
        iou: float = DEFAULT_IOU,
        imgsz: int = DEFAULT_IMGSZ,
        max_det: int = DEFAULT_MAX_DET,
        device: str = DEFAULT_DEVICE,
    ) -> None:
        self.conf = conf
        self.iou = iou
        self.imgsz = imgsz
        self.max_det = max_det
        self.device = device

        resolved_path = self._resolve_model_path(model_path)
        self.model_path = resolved_path
        self.weights_sha256 = self._hash_weights(resolved_path)

        # Import here so the module is importable without ultralytics (e.g. in
        # pure-unit-test environments that mock detect_persons).
        from ultralytics import YOLO  # type: ignore[import-untyped]
        self._model = YOLO(resolved_path)

        # Warm-up run to exclude JIT / load overhead from timing measurements.
        self._warmup()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def detect(self, frame: Any) -> FrameResult:
        """
        Run person detection on a single BGR frame (numpy ndarray).

        Returns a FrameResult with all detected persons.
        Raises nothing — errors are surfaced as FrameResult with empty detections.
        """
        t0 = time.perf_counter()
        try:
            results = self._model(
                frame,
                classes=[0],           # COCO class 0 = person
                conf=self.conf,
                iou=self.iou,
                imgsz=self.imgsz,
                max_det=self.max_det,
                device=self.device,
                verbose=False,
            )
        except Exception:  # noqa: BLE001
            return FrameResult(detections=[], inference_ms=0.0)
        t1 = time.perf_counter()
        inference_ms = (t1 - t0) * 1000.0

        detections: list[Detection] = []
        if results and len(results) > 0:
            boxes = results[0].boxes
            if boxes is not None:
                for box in boxes:
                    xyxy = tuple(float(v) for v in box.xyxy[0].tolist())
                    conf_val = float(box.conf[0])
                    detections.append(
                        Detection(
                            xyxy=xyxy,  # type: ignore[arg-type]
                            confidence=conf_val,
                        )
                    )

        return FrameResult(detections=detections, inference_ms=inference_ms)

    def describe(self) -> dict[str, Any]:
        """Return a loggable dict of model identity and settings."""
        return {
            "model_path": self.model_path,
            "weights_sha256_prefix": self.weights_sha256[:16],
            "conf": self.conf,
            "iou": self.iou,
            "imgsz": self.imgsz,
            "max_det": self.max_det,
            "device": self.device,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _warmup(self) -> None:
        """Run one silent inference on a black frame to trigger JIT compilation."""
        dummy = np.zeros((self.imgsz, self.imgsz, 3), dtype=np.uint8)
        self._model(
            dummy,
            classes=[0],
            conf=self.conf,
            iou=self.iou,
            imgsz=self.imgsz,
            max_det=self.max_det,
            device=self.device,
            verbose=False,
        )

    @staticmethod
    def _resolve_model_path(model_path: str) -> str:
        """Search common locations for weights if the given path does not exist."""
        if model_path and os.path.exists(model_path):
            return model_path
        # Locate workspace root heuristically
        cur = os.path.abspath(os.path.dirname(__file__))
        for _ in range(6):
            candidate = os.path.join(cur, "yolov8n.pt")
            if os.path.exists(candidate):
                return candidate
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
        # Fall back to Ultralytics auto-download
        return "yolov8n.pt"

    @staticmethod
    def _hash_weights(path: str) -> str:
        """SHA-256 of the weights file for logging / reproducibility."""
        if not os.path.exists(path):
            return "unknown"
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()


# ---------------------------------------------------------------------------
# Minute-level aggregation — shared with agent and tests
# ---------------------------------------------------------------------------

def aggregate_counts(frame_counts: list[int]) -> dict[str, float]:
    """
    Compute minute-level statistics from a list of per-frame person counts.

    Returns dict with keys: persons_min, persons_median, persons_p90, persons_max.
    Raises ValueError if frame_counts is empty.
    """
    if not frame_counts:
        raise ValueError("frame_counts must not be empty")
    arr = np.array(frame_counts, dtype=float)
    return {
        "persons_min": float(int(arr.min())),
        "persons_median": float(np.median(arr)),
        "persons_p90": float(np.percentile(arr, 90)),
        "persons_max": float(int(arr.max())),
    }
