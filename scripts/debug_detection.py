"""scripts/debug_detection.py — PRAMAAN Multi-Person Detection Diagnostic Tool.

Phase 1 diagnostic: opens webcam, runs YOLOv8 person detection with configurable
parameters, and prints per-frame statistics to stdout.  Draws a local overlay window.
No frames are saved.  Exits on 'q' or ESC in the window, or Ctrl+C in the terminal.

Usage:
    python scripts/debug_detection.py [options]

Options:
    --conf      YOLO confidence threshold            (default: 0.35)
    --iou       NMS IoU threshold                    (default: 0.70 = Ultralytics default)
    --imgsz     Model inference image size           (default: 640)
    --max-det   Maximum detections per frame         (default: 300)
    --model     Path to .pt weights file             (default: auto-detect yolov8n.pt)
    --camera    Webcam device index                  (default: 0)
    --device    Inference device: cpu / 0 / cuda     (default: cpu)
    --fps-limit Max frames to attempt per second     (default: 0 = unlimited)
    --frames    Run for this many frames then exit   (default: 0 = unlimited)

Example commands (run from PRAMAAN root):
    # Baseline — reproduce agent settings
    python scripts/debug_detection.py --conf 0.35 --iou 0.70

    # Test lower IoU to reduce NMS merging of overlapping people
    python scripts/debug_detection.py --conf 0.25 --iou 0.45

    # Higher resolution inference
    python scripts/debug_detection.py --imgsz 1280

    # Run for 120 frames then exit (useful for batch comparison)
    python scripts/debug_detection.py --frames 120
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from collections import deque
from typing import Any

# ── Path setup (mirrors agent) ────────────────────────────────────────────────
def _find_workspace_root() -> str:
    cur = os.path.abspath(os.path.dirname(__file__))
    while cur and os.path.dirname(cur) != cur:
        if os.path.exists(os.path.join(cur, "backend")) and os.path.exists(
            os.path.join(cur, "frontend")
        ):
            return cur
        cur = os.path.dirname(cur)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


WORKSPACE_ROOT = _find_workspace_root()
BACKEND_DIR = os.path.join(WORKSPACE_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import cv2
import numpy as np
from ultralytics import YOLO


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_model(arg_model: str) -> str:
    """Return path to YOLO weights, searching common locations."""
    if arg_model and os.path.exists(arg_model):
        return arg_model
    candidates = [
        os.path.join(WORKSPACE_ROOT, "yolov8n.pt"),
        os.path.join(BACKEND_DIR, "yolov8n.pt"),
        "yolov8n.pt",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    # Fall back to Ultralytics auto-download
    return "yolov8n.pt"


def _open_camera(camera_index: int) -> cv2.VideoCapture:
    """Open the first readable camera among common indices and backends."""
    backends = [("DirectShow", cv2.CAP_DSHOW), ("Default", cv2.CAP_ANY)]
    candidates = [camera_index] + [i for i in [0, 1, 2] if i != camera_index]
    for backend_name, backend_id in backends:
        for idx in candidates:
            try:
                cap = (
                    cv2.VideoCapture(idx, backend_id)
                    if backend_id != cv2.CAP_ANY
                    else cv2.VideoCapture(idx)
                )
                if cap.isOpened():
                    ret, test_frame = cap.read()
                    if ret and test_frame is not None:
                        print(f"[CAMERA] Opened index {idx} via {backend_name}.")
                        return cap
                cap.release()
            except Exception:
                continue
    print("[ERROR] Could not open any webcam. Check that a camera is connected and not in use.")
    sys.exit(1)


def _set_and_report_camera(cap: cv2.VideoCapture) -> dict[str, Any]:
    """Request 1280×720 MJPG; read back what the driver actually negotiated."""
    # Prefer MJPEG for higher FPS at higher resolution
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    # FOURCC value → 4-char string
    fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
    fourcc_chars = (
        chr(fourcc_int & 0xFF)
        + chr((fourcc_int >> 8) & 0xFF)
        + chr((fourcc_int >> 16) & 0xFF)
        + chr((fourcc_int >> 24) & 0xFF)
    )

    info: dict[str, Any] = {
        "width": actual_w,
        "height": actual_h,
        "fps": actual_fps,
        "fourcc": fourcc_chars.strip("\x00"),
    }

    print(f"[CAMERA] Negotiated: {actual_w}×{actual_h} @ {actual_fps:.1f} FPS  "
          f"codec={fourcc_chars.strip(chr(0))!r}")
    return info


def _run_detection(
    model: YOLO,
    frame: Any,
    conf: float,
    iou: float,
    imgsz: int,
    max_det: int,
    device: str,
) -> tuple[list[dict[str, Any]], float]:
    """
    Run YOLO person detection on a single frame.

    Returns:
        detections: list of dicts with keys 'conf', 'xyxy'
        inference_ms: wall-clock inference time in milliseconds
    """
    t0 = time.perf_counter()
    results = model(
        frame,
        classes=[0],
        conf=conf,
        iou=iou,
        imgsz=imgsz,
        max_det=max_det,
        device=device,
        verbose=False,
    )
    t1 = time.perf_counter()
    inference_ms = (t1 - t0) * 1000.0

    detections: list[dict[str, Any]] = []
    if results and len(results) > 0:
        boxes = results[0].boxes
        if boxes is not None:
            for box in boxes:
                conf_val = float(box.conf[0])
                xyxy = box.xyxy[0].tolist()
                detections.append({"conf": conf_val, "xyxy": xyxy})

    return detections, inference_ms


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="PRAMAAN Multi-Person Detection Diagnostic",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--conf", type=float, default=0.35, help="YOLO confidence threshold")
    parser.add_argument("--iou", type=float, default=0.70, help="NMS IoU threshold")
    parser.add_argument("--imgsz", type=int, default=640, help="Model inference image size")
    parser.add_argument("--max-det", type=int, default=300, help="Max detections per frame")
    parser.add_argument("--model", type=str, default="", help="Path to YOLO .pt weights")
    parser.add_argument("--camera", type=int, default=0, help="Webcam device index")
    parser.add_argument("--device", type=str, default="cpu", help="Inference device (cpu/0/cuda)")
    parser.add_argument("--fps-limit", type=float, default=0.0,
                        help="Max frames per second to process (0 = unlimited)")
    parser.add_argument("--frames", type=int, default=0,
                        help="Exit after this many frames (0 = unlimited)")
    args = parser.parse_args()

    print("=" * 72)
    print("PRAMAAN — Multi-Person Detection Diagnostic (Phase 1)")
    print("=" * 72)
    print(f"  conf={args.conf}  iou={args.iou}  imgsz={args.imgsz}  "
          f"max_det={args.max_det}  device={args.device}")
    print(f"  fps_limit={args.fps_limit or 'unlimited'}  "
          f"frames_to_run={args.frames or 'unlimited'}")
    print("  Press 'q' or ESC in the window to quit.  Ctrl+C in terminal also works.")
    print("=" * 72)

    # Load model
    model_path = _find_model(args.model)
    print(f"\n[MODEL] Loading {model_path}...")
    model = YOLO(model_path)
    print(f"[MODEL] Loaded. Warming up...")
    # Warm-up run to exclude JIT/load time from timing
    dummy = np.zeros((args.imgsz, args.imgsz, 3), dtype=np.uint8)
    model(dummy, classes=[0], conf=args.conf, iou=args.iou, imgsz=args.imgsz,
          max_det=args.max_det, device=args.device, verbose=False)
    print(f"[MODEL] Warm-up done.\n")

    # Open camera
    cap = _open_camera(args.camera)
    cam_info = _set_and_report_camera(cap)

    cv2.namedWindow("PRAMAAN Debug Detection (local only — not saved)", cv2.WINDOW_AUTOSIZE)

    # Running statistics
    frame_idx = 0
    all_inference_ms: list[float] = []
    all_person_counts: list[int] = []
    all_confs: list[float] = []
    recent_counts: deque[int] = deque(maxlen=30)  # last 30 frames for rolling average

    fps_interval_start = time.time()
    fps_interval_frames = 0
    display_fps = 0.0

    min_frame_interval = 1.0 / args.fps_limit if args.fps_limit > 0 else 0.0

    print(f"\n{'Frame':>6}  {'RawDets':>7}  {'Persons':>7}  {'Confs':>30}  {'InfMs':>8}  {'RollAvg':>8}")
    print("-" * 80)

    try:
        while True:
            loop_start = time.perf_counter()

            ret, frame = cap.read()
            if not ret or frame is None:
                print("[WARN] Failed to read frame. Retrying...")
                time.sleep(0.05)
                continue

            frame_idx += 1
            fps_interval_frames += 1

            # FPS counter (wall-clock, updated every second)
            now = time.time()
            if now - fps_interval_start >= 1.0:
                display_fps = fps_interval_frames / (now - fps_interval_start)
                fps_interval_frames = 0
                fps_interval_start = now

            # Run detection
            detections, inf_ms = _run_detection(
                model, frame,
                conf=args.conf,
                iou=args.iou,
                imgsz=args.imgsz,
                max_det=args.max_det,
                device=args.device,
            )

            person_count = len(detections)
            conf_vals = [d["conf"] for d in detections]

            all_inference_ms.append(inf_ms)
            all_person_counts.append(person_count)
            all_confs.extend(conf_vals)
            recent_counts.append(person_count)
            roll_avg = sum(recent_counts) / len(recent_counts)

            # Per-frame stdout log
            conf_str = ", ".join(f"{c:.3f}" for c in conf_vals) if conf_vals else "—"
            if len(conf_str) > 30:
                conf_str = conf_str[:27] + "..."
            print(f"{frame_idx:>6}  {len(detections):>7}  {person_count:>7}  "
                  f"{conf_str:>30}  {inf_ms:>7.1f}  {roll_avg:>7.2f}")

            # Draw overlay
            disp = frame.copy()

            # Bounding boxes
            for det in detections:
                x1, y1, x2, y2 = map(int, det["xyxy"])
                c = det["conf"]
                cv2.rectangle(disp, (x1, y1), (x2, y2), (0, 255, 80), 2)
                label = f"person {c:.2f}"
                cv2.putText(disp, label, (x1, max(18, y1 - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 80), 2, cv2.LINE_AA)

            # HUD panel
            h, w = disp.shape[:2]
            cv2.rectangle(disp, (8, 8), (w - 8, 170), (20, 20, 20), -1)
            cv2.rectangle(disp, (8, 8), (w - 8, 170), (0, 200, 255), 1)

            hud_lines = [
                f"PRAMAAN Debug Diagnostic — local window only",
                f"Camera: {cam_info['width']}x{cam_info['height']} {cam_info['fourcc']} @ {cam_info['fps']:.0f}fps  |  Display FPS: {display_fps:.1f}",
                f"conf={args.conf}  iou={args.iou}  imgsz={args.imgsz}  max_det={args.max_det}  device={args.device}",
                f"Frame #{frame_idx}  |  DETECTED: {person_count} person(s)  |  Inf: {inf_ms:.1f}ms",
                f"30-frame rolling avg: {roll_avg:.2f}  |  Session: min={min(all_person_counts)} max={max(all_person_counts)} mean={sum(all_person_counts)/len(all_person_counts):.2f}",
            ]
            for i, line in enumerate(hud_lines):
                color = (0, 200, 255) if i == 0 else (0, 255, 80) if i == 3 else (200, 200, 200)
                cv2.putText(disp, line, (16, 32 + i * 26),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 1, cv2.LINE_AA)

            cv2.imshow("PRAMAAN Debug Detection (local only — not saved)", disp)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):  # q or ESC
                print("\n[DIAG] Stopped by user (window key).")
                break

            if args.frames > 0 and frame_idx >= args.frames:
                print(f"\n[DIAG] Reached requested frame limit ({args.frames}).")
                break

            # FPS limiter
            if min_frame_interval > 0:
                elapsed = time.perf_counter() - loop_start
                sleep_for = min_frame_interval - elapsed
                if sleep_for > 0:
                    time.sleep(sleep_for)

    except KeyboardInterrupt:
        print("\n[DIAG] Stopped by Ctrl+C.")
    finally:
        cap.release()
        cv2.destroyAllWindows()

    # ── Summary statistics ────────────────────────────────────────────────────
    if not all_person_counts:
        print("\n[DIAG] No frames processed.")
        return

    n = len(all_person_counts)
    counts_arr = np.array(all_person_counts, dtype=float)
    times_arr = np.array(all_inference_ms)

    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print(f"  Frames processed     : {n}")
    print(f"  Camera resolution    : {cam_info['width']}×{cam_info['height']} "
          f"{cam_info['fourcc']} @ {cam_info['fps']:.1f} FPS")
    print(f"  Model                : {model_path}")
    print(f"  Settings             : conf={args.conf}  iou={args.iou}  "
          f"imgsz={args.imgsz}  max_det={args.max_det}  device={args.device}")
    print()
    print("  Person count statistics:")
    print(f"    min      = {int(counts_arr.min())}")
    print(f"    max      = {int(counts_arr.max())}")
    print(f"    mean     = {counts_arr.mean():.3f}")
    print(f"    median   = {np.median(counts_arr):.3f}")
    print(f"    P90      = {np.percentile(counts_arr, 90):.3f}")
    print(f"    P95      = {np.percentile(counts_arr, 95):.3f}")
    print()
    print("  Frames with count 0  :", int((counts_arr == 0).sum()),
          f"({100*(counts_arr == 0).mean():.1f}%)")
    for k in range(1, int(counts_arr.max()) + 1):
        print(f"  Frames with count {k}  :", int((counts_arr == k).sum()),
              f"({100*(counts_arr == k).mean():.1f}%)")
    print()
    print("  Inference time (ms):")
    print(f"    mean = {times_arr.mean():.1f}")
    print(f"    P50  = {np.percentile(times_arr, 50):.1f}")
    print(f"    P95  = {np.percentile(times_arr, 95):.1f}")
    print(f"    effective FPS ≈ {1000/times_arr.mean():.1f} (inference only)")
    if all_confs:
        confs_arr = np.array(all_confs)
        print()
        print("  Detection confidence distribution:")
        print(f"    min   = {confs_arr.min():.3f}")
        print(f"    mean  = {confs_arr.mean():.3f}")
        print(f"    max   = {confs_arr.max():.3f}")
        print(f"    <0.40 = {100*(confs_arr < 0.40).mean():.1f}%  "
              f"(would be dropped if conf raised to 0.40)")
        print(f"    <0.50 = {100*(confs_arr < 0.50).mean():.1f}%  "
              f"(would be dropped if conf raised to 0.50)")
    print("=" * 72)
    print("\nDIAGNOSTIC COMPLETE")
    print("  — No frames were saved.  The overlay window was local only.")
    print("  — Copy the SUMMARY block above into the Phase 1 report.")
    print()


if __name__ == "__main__":
    main()
