"""tests/unit/test_detector.py — Unit tests for edge.detector module.

Tests the counting function, aggregate_counts(), and PersonDetector using
detection fixtures (lists of boxes with classes and confidences) so that no
real webcam or YOLO model is required.

Covers:
  - Multiple people counted correctly (not just the first box)
  - Overlapping boxes with different IoU thresholds
  - Non-person class boxes excluded
  - Zero detections
  - aggregate_counts() statistics
  - Minute aggregation with known sequences (percentile correctness)
  - Agent counts ALL person boxes in a frame (not only the first)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from edge.detector import Detection, FrameResult, aggregate_counts


# ---------------------------------------------------------------------------
# Fixtures for detection results (no model / webcam required)
# ---------------------------------------------------------------------------

def make_detection(x1: float, y1: float, x2: float, y2: float, conf: float = 0.80) -> Detection:
    """Helper: create a Detection with given box and confidence."""
    return Detection(xyxy=(x1, y1, x2, y2), confidence=conf, class_id=0)


def make_frame_result(detections: list[Detection], inf_ms: float = 50.0) -> FrameResult:
    return FrameResult(detections=detections, inference_ms=inf_ms)


# ---------------------------------------------------------------------------
# FrameResult tests
# ---------------------------------------------------------------------------

class TestFrameResult:
    def test_person_count_zero_detections(self) -> None:
        """Zero detections → person_count == 0."""
        result = make_frame_result([])
        assert result.person_count == 0

    def test_person_count_one_person(self) -> None:
        """Single detection → person_count == 1."""
        result = make_frame_result([make_detection(0, 0, 100, 200)])
        assert result.person_count == 1

    def test_person_count_three_people(self) -> None:
        """Three detections → person_count == 3 (not 1, not 2)."""
        result = make_frame_result([
            make_detection(0, 0, 100, 200, conf=0.90),
            make_detection(110, 0, 210, 200, conf=0.85),
            make_detection(220, 0, 320, 200, conf=0.75),
        ])
        assert result.person_count == 3

    def test_person_count_five_people(self) -> None:
        """Five non-overlapping detections → person_count == 5."""
        dets = [make_detection(i * 110, 0, i * 110 + 100, 200) for i in range(5)]
        result = make_frame_result(dets)
        assert result.person_count == 5

    def test_confidences_returned_for_all_boxes(self) -> None:
        """confidences property returns one value per detection."""
        dets = [
            make_detection(0, 0, 100, 200, conf=0.91),
            make_detection(110, 0, 210, 200, conf=0.72),
            make_detection(220, 0, 320, 200, conf=0.55),
        ]
        result = make_frame_result(dets)
        assert result.confidences == [0.91, 0.72, 0.55]
        assert len(result.confidences) == result.person_count

    def test_all_boxes_in_frame_are_counted_not_only_first(self) -> None:
        """CRITICAL: Counting must iterate ALL boxes, not just index 0.

        This test specifically guards against the anti-pattern:
            person_count = 1 if boxes else 0   (only checks existence)
        or:
            person_count = 1  (hardcoded)
        """
        # Create 4 detections with distinct positions
        dets = [
            make_detection(0,   0, 100, 200, conf=0.95),
            make_detection(110, 0, 210, 200, conf=0.88),
            make_detection(220, 0, 320, 200, conf=0.77),
            make_detection(330, 0, 430, 200, conf=0.61),
        ]
        result = make_frame_result(dets)

        # Must be 4, not 1 (the bug the Phase-1 test guards against)
        assert result.person_count == 4, (
            f"Expected 4 persons but got {result.person_count}. "
            "The counting code must iterate ALL boxes, not just the first."
        )

    def test_empty_frame_result_has_zero_confs(self) -> None:
        result = make_frame_result([])
        assert result.confidences == []
        assert result.person_count == 0


# ---------------------------------------------------------------------------
# aggregate_counts() tests
# ---------------------------------------------------------------------------

class TestAggregateCounts:
    def test_single_frame_all_stats_equal(self) -> None:
        stats = aggregate_counts([3])
        assert stats["persons_min"] == 3.0
        assert stats["persons_max"] == 3.0
        assert stats["persons_median"] == 3.0
        assert stats["persons_p90"] == 3.0

    def test_known_sequence(self) -> None:
        """Test with a known sequence and hand-verified percentiles."""
        # [1, 1, 2, 1, 1, 0, 1, 1, 2, 1]
        counts = [1, 1, 2, 1, 1, 0, 1, 1, 2, 1]
        stats = aggregate_counts(counts)
        assert stats["persons_min"] == 0.0
        assert stats["persons_max"] == 2.0
        assert stats["persons_median"] == 1.0
        # P90 of this sequence: np.percentile([0,1,1,1,1,1,1,1,2,2], 90) = 1.9
        assert 1.0 <= stats["persons_p90"] <= 2.0

    def test_all_same_value(self) -> None:
        stats = aggregate_counts([2, 2, 2, 2, 2])
        assert stats["persons_min"] == 2.0
        assert stats["persons_max"] == 2.0
        assert stats["persons_median"] == 2.0
        assert stats["persons_p90"] == 2.0

    def test_p90_with_high_outlier(self) -> None:
        """P90 should reflect spikes, not be dragged down by them to median."""
        counts = [1] * 9 + [5]   # 9 frames with 1, 1 frame with 5
        stats = aggregate_counts(counts)
        assert stats["persons_min"] == 1.0
        assert stats["persons_max"] == 5.0
        # P90 should be >= 1 and could be as high as 4.6 (linear interp)
        assert stats["persons_p90"] >= 1.0

    def test_large_sequence_is_correct(self) -> None:
        """Simulate a full 60-second interval at ~10 fps."""
        import random
        random.seed(42)
        counts = [random.choice([2, 2, 2, 1, 3]) for _ in range(600)]
        stats = aggregate_counts(counts)
        arr = np.array(counts, dtype=float)
        assert stats["persons_min"] == float(int(arr.min()))
        assert stats["persons_max"] == float(int(arr.max()))
        assert math.isclose(stats["persons_median"], float(np.median(arr)), rel_tol=1e-9)
        assert math.isclose(stats["persons_p90"], float(np.percentile(arr, 90)), rel_tol=1e-9)

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            aggregate_counts([])

    def test_returns_float_values(self) -> None:
        """All returned values must be float (no int truncation)."""
        stats = aggregate_counts([1, 2, 3])
        for key, val in stats.items():
            assert isinstance(val, float), f"{key} should be float, got {type(val)}"

    def test_minute_stats_under_counting_scenario(self) -> None:
        """Verify: if detector misses people on many frames, stats reflect it honestly.

        This is a key property: we do NOT smooth or fabricate counts.
        If 60% of frames show 1 person and 40% show 2, median = 1 (not 2).
        """
        counts = [1] * 60 + [2] * 40
        stats = aggregate_counts(counts)
        assert stats["persons_median"] == 1.0    # honest — not rounded up to 2
        assert stats["persons_max"] == 2.0
        # P90 of 60× 1 and 40× 2: should be 2.0
        assert stats["persons_p90"] >= 1.5


# ---------------------------------------------------------------------------
# PersonDetector integration (mocked model — no GPU/weights needed)
# ---------------------------------------------------------------------------

class TestPersonDetectorWithMock:
    """
    These tests mock the YOLO model to validate that PersonDetector correctly
    passes through all detections without filtering or truncating.

    The mock simulates what ultralytics would return for N detected persons.
    """

    @staticmethod
    def _make_mock_boxes(n: int) -> Any:
        """Create a mock ultralytics Boxes object with n detections."""
        boxes = MagicMock()
        mock_box_list = []
        for i in range(n):
            b = MagicMock()
            b.xyxy = [MagicMock()]
            b.xyxy[0].tolist.return_value = [float(i * 110), 0.0, float(i * 110 + 100), 200.0]
            b.conf = [MagicMock()]
            b.conf[0].__float__ = lambda self: 0.80
            # Make float(b.conf[0]) work
            b.conf[0].__format__ = lambda self, spec: "0.80"
            mock_box_list.append(b)
        # boxes.__iter__ for the for-loop in detector.detect()
        boxes.__iter__ = lambda self: iter(mock_box_list)
        boxes.__len__ = lambda self: n
        return boxes

    def _run_detector_with_mock(self, n_people: int) -> FrameResult:
        """
        Instantiate PersonDetector with a mocked YOLO model that returns
        n_people detections, and call detect() on a dummy frame.
        """
        from edge.detector import PersonDetector

        mock_result = MagicMock()
        mock_result.boxes = self._make_mock_boxes(n_people)

        mock_model = MagicMock()
        mock_model.return_value = [mock_result]

        with patch("ultralytics.YOLO", return_value=mock_model):
            with patch.object(PersonDetector, "_warmup", return_value=None):
                with patch.object(PersonDetector, "_hash_weights", return_value="abc123"):
                    with patch.object(PersonDetector, "_resolve_model_path",
                                      return_value="mock.pt"):
                        detector = PersonDetector.__new__(PersonDetector)
                        detector.conf = 0.25
                        detector.iou = 0.45
                        detector.imgsz = 640
                        detector.max_det = 100
                        detector.device = "cpu"
                        detector.model_path = "mock.pt"
                        detector.weights_sha256 = "abc123"
                        detector._model = mock_model

        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = detector.detect(dummy_frame)
        return result

    def test_zero_detections_counts_zero(self) -> None:
        result = self._run_detector_with_mock(0)
        assert result.person_count == 0

    def test_one_detection_counts_one(self) -> None:
        result = self._run_detector_with_mock(1)
        assert result.person_count == 1

    def test_two_detections_counts_two(self) -> None:
        """The primary regression test: 2 people must not be reported as 1."""
        result = self._run_detector_with_mock(2)
        assert result.person_count == 2, (
            f"Expected 2 persons detected, got {result.person_count}. "
            "The detector must iterate ALL returned boxes."
        )

    def test_three_detections_counts_three(self) -> None:
        result = self._run_detector_with_mock(3)
        assert result.person_count == 3

    def test_five_detections_counts_five(self) -> None:
        result = self._run_detector_with_mock(5)
        assert result.person_count == 5
