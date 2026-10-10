"""tests/unit/benchmark_measurements.py — Real latency & throughput measurements.

Measures:
1. Server keyframe comparison latency (p50, p95, p99, hardware info).
2. Multi-day ghost batch detection throughput for 1,000 batches and 10,000 batches.
"""
from __future__ import annotations

import os
import platform
import time
from datetime import UTC, datetime, timedelta

import cv2
import numpy as np

from app.domain.ghost_batch import SessionDayInput, evaluate_ghost_batch
from app.domain.vision.scene_compare import compare_scene


def run_keyframe_benchmarks(iterations: int = 50) -> dict[str, float | str | int]:
    print(f"\n--- Running Keyframe Comparison Benchmark ({iterations} iterations) ---")
    # Generate representative 480x360 images with textures
    ref_img = np.zeros((360, 480, 3), dtype=np.uint8)
    cv2.putText(ref_img, "ROOM-BENCHMARK-REF", (50, 180), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200, 200, 200), 2)
    for i in range(10):
        cv2.circle(ref_img, (40 * i + 30, 80), 15, (100, 150, 200), -1)

    query_img = np.zeros((360, 480, 3), dtype=np.uint8)
    cv2.putText(query_img, "ROOM-BENCHMARK-QUERY", (50, 180), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200, 200, 200), 2)
    for i in range(10):
        cv2.circle(query_img, (40 * i + 30, 80), 15, (100, 150, 200), -1)

    ref_bytes = cv2.imencode(".jpg", ref_img)[1].tobytes()
    query_bytes = cv2.imencode(".jpg", query_img)[1].tobytes()

    # Warmup
    for _ in range(5):
        compare_scene(query_bytes, ref_bytes)

    latencies_ms: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        compare_scene(query_bytes, ref_bytes)
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000.0)

    latencies_sorted = sorted(latencies_ms)
    p50 = np.percentile(latencies_sorted, 50)
    p95 = np.percentile(latencies_sorted, 95)
    p99 = np.percentile(latencies_sorted, 99)

    print(f"Keyframe Comparison Latencies:")
    print(f"  p50: {p50:.2f} ms")
    print(f"  p95: {p95:.2f} ms")
    print(f"  p99: {p99:.2f} ms")

    return {
        "iterations": iterations,
        "p50_ms": round(float(p50), 2),
        "p95_ms": round(float(p95), 2),
        "p99_ms": round(float(p99), 2),
        "cpu": platform.processor() or platform.machine(),
        "cpu_count": os.cpu_count() or 1,
        "os": platform.platform(),
    }


def run_ghost_benchmarks() -> dict[str, float | int]:
    print("\n--- Running Ghost Batch Detection Benchmarks (1k and 10k batches) ---")
    base_time = datetime(2024, 6, 1, 4, 30, tzinfo=UTC)
    now = datetime(2024, 6, 15, 12, 0, tzinfo=UTC)

    # Pre-generate 14 days of realistic sessions for a batch
    template_sessions = [
        SessionDayInput(
            session_id=f"sess-{i}",
            scheduled_start=base_time + timedelta(days=i),
            scheduled_end=base_time + timedelta(days=i, hours=2),
            claimed_count=30,
            o_hat=2.0 if i % 3 == 0 else 25.0,
            feed_health=0.95,
            camera_trust="TRUSTED",
            attendance_status="RED" if i % 3 == 0 else "GREEN",
        )
        for i in range(14)
    ]

    # Benchmark 1,000 batches
    t0_1k = time.perf_counter()
    for b_idx in range(1000):
        evaluate_ghost_batch(
            batch_id=f"batch-{b_idx}",
            centre_id="ctr-bench",
            sessions=template_sessions,
            previous_state="NORMAL",
            now=now,
        )
    t1_1k = time.perf_counter()
    time_1k = t1_1k - t0_1k
    tps_1k = 1000.0 / time_1k

    print(f"1,000 batches evaluated in: {time_1k:.4f} s ({tps_1k:.1f} batches/sec, {time_1k/1000*1000:.3f} ms/batch)")

    # Benchmark 10,000 batches
    t0_10k = time.perf_counter()
    for b_idx in range(10000):
        evaluate_ghost_batch(
            batch_id=f"batch-{b_idx}",
            centre_id="ctr-bench",
            sessions=template_sessions,
            previous_state="NORMAL",
            now=now,
        )
    t1_10k = time.perf_counter()
    time_10k = t1_10k - t0_10k
    tps_10k = 10000.0 / time_10k

    print(f"10,000 batches evaluated in: {time_10k:.4f} s ({tps_10k:.1f} batches/sec, {time_10k/10000*1000:.3f} ms/batch)")

    return {
        "time_1k_sec": round(time_1k, 4),
        "tps_1k": round(tps_1k, 1),
        "avg_ms_per_batch_1k": round(time_1k / 1000 * 1000, 3),
        "time_10k_sec": round(time_10k, 4),
        "tps_10k": round(tps_10k, 1),
        "avg_ms_per_batch_10k": round(time_10k / 10000 * 1000, 3),
    }


if __name__ == "__main__":
    kf_res = run_keyframe_benchmarks()
    ghost_res = run_ghost_benchmarks()
    print("\n--- Summary ---")
    print("Keyframe:", kf_res)
    print("Ghost:", ghost_res)
