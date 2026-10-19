"""scripts/eval_person_counting.py — PRAMAAN Person Counting Evaluation Harness.

Uses the SAME detection function as the live edge agent (edge.detector.PersonDetector)
so that improvements measured here are real improvements of the agent.

Modes
-----
capture   Record a webcam clip and label it with the true person count.
eval      Replay saved clips through the detector and compute accuracy metrics.
list      List all clips and their labels in the data directory.

Usage (from PRAMAAN root, using the backend venv):

    # Record a 10-second clip with 2 people in frame
    python scripts/eval_person_counting.py capture --seconds 10 --label 2

    # Evaluate all saved clips with default detector settings
    python scripts/eval_person_counting.py eval

    # Evaluate with alternative settings to compare
    python scripts/eval_person_counting.py eval --conf 0.25 --iou 0.45

    # List all clips
    python scripts/eval_person_counting.py list

Data storage
------------
Clips and labels are saved to:
    tests/data/counting_eval/
    
This directory is git-ignored (see .gitignore).  Clips are local development data
only and must NOT be committed or transmitted.

IMPORTANT
---------
Only record clips with the consent of every person in frame.
These clips are development evaluation data only.
Delete them when no longer needed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

# ── Path setup ────────────────────────────────────────────────────────────────
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

DATA_DIR = Path(WORKSPACE_ROOT) / "tests" / "data" / "counting_eval"

import cv2
import numpy as np
from edge.detector import PersonDetector, aggregate_counts


# ── Data-directory helpers ────────────────────────────────────────────────────

def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    gitignore = DATA_DIR / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(
            "# All clips, frames and labels in this directory are local development data.\n"
            "# They must NOT be committed, shared, or transmitted.\n"
            "*\n!.gitignore\n!README.md\n",
            encoding="utf-8",
        )
    readme = DATA_DIR / "README.md"
    if not readme.exists():
        readme.write_text(
            "# PRAMAAN Person Counting Evaluation Data\n\n"
            "This directory contains local development clips and labels for the\n"
            "PRAMAAN person counting evaluation harness.\n\n"
            "**This directory is git-ignored.  Files here are local only.**\n\n"
            "Only record clips with the consent of every person in frame.\n"
            "Delete these files when they are no longer needed.\n",
            encoding="utf-8",
        )


def load_manifest() -> list[dict[str, Any]]:
    """Load the clip manifest (list of {clip_path, true_count, scenario, recorded_at})."""
    manifest_path = DATA_DIR / "manifest.json"
    if not manifest_path.exists():
        return []
    with open(manifest_path, encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


def save_manifest(entries: list[dict[str, Any]]) -> None:
    manifest_path = DATA_DIR / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


# ── Capture mode ──────────────────────────────────────────────────────────────

def cmd_capture(args: argparse.Namespace) -> None:
    """Record a webcam clip and prompt for (or accept via --label) the true count."""
    ensure_data_dir()

    true_count: int | None = args.label
    if true_count is None:
        raw = input("How many people are in frame RIGHT NOW? Enter a number: ").strip()
        try:
            true_count = int(raw)
        except ValueError:
            print(f"[ERROR] Invalid number: {raw!r}")
            sys.exit(1)

    scenario = args.scenario or f"{true_count}person"
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    clip_name = f"{timestamp}_{scenario}.avi"
    clip_path = DATA_DIR / clip_name

    # Open camera
    print(f"\n[CAPTURE] Opening camera index {args.camera}...")
    backends = [("DirectShow", cv2.CAP_DSHOW), ("Default", cv2.CAP_ANY)]
    cap = None
    for bname, bid in backends:
        try:
            c = cv2.VideoCapture(args.camera, bid) if bid != cv2.CAP_ANY else cv2.VideoCapture(args.camera)
            if c.isOpened():
                ret, f = c.read()
                if ret and f is not None:
                    cap = c
                    print(f"[CAPTURE] Camera opened ({bname}).")
                    break
                c.release()
        except Exception:
            continue

    if cap is None:
        print("[ERROR] Could not open camera.")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    writer = cv2.VideoWriter(str(clip_path), fourcc, 15.0, (actual_w, actual_h))

    print(f"[CAPTURE] Recording {args.seconds}s clip to {clip_path}")
    print(f"          True person count: {true_count}")
    print(f"          Scenario label:    {scenario!r}")
    print(f"          Resolution:        {actual_w}×{actual_h}")
    print(f"          Press 'q' or ESC to cancel.\n")

    start = time.time()
    frames_written = 0
    cv2.namedWindow("PRAMAAN — Clip Recording (local only)", cv2.WINDOW_AUTOSIZE)

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            time.sleep(0.01)
            continue

        elapsed = time.time() - start
        if elapsed >= args.seconds:
            break

        writer.write(frame)
        frames_written += 1

        disp = frame.copy()
        remaining = max(0.0, args.seconds - elapsed)
        cv2.rectangle(disp, (8, 8), (500, 90), (20, 20, 20), -1)
        cv2.putText(disp, f"RECORDING — {remaining:.1f}s remaining", (16, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 220), 2, cv2.LINE_AA)
        cv2.putText(disp, f"True count: {true_count}  |  Scenario: {scenario}",
                    (16, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)
        cv2.imshow("PRAMAAN — Clip Recording (local only)", disp)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            print("\n[CAPTURE] Cancelled by user.")
            cap.release()
            writer.release()
            cv2.destroyAllWindows()
            if clip_path.exists():
                clip_path.unlink()
            return

    cap.release()
    writer.release()
    cv2.destroyAllWindows()

    duration_actual = time.time() - start
    print(f"\n[CAPTURE] Saved {frames_written} frames ({duration_actual:.1f}s) → {clip_path}")

    # Update manifest
    entries = load_manifest()
    entries.append({
        "clip_path": clip_name,
        "true_count": true_count,
        "scenario": scenario,
        "recorded_at": datetime.now(UTC).isoformat(),
        "frames": frames_written,
        "resolution": f"{actual_w}x{actual_h}",
    })
    save_manifest(entries)
    print(f"[CAPTURE] Manifest updated. Total clips: {len(entries)}")
    print(f"\n  Next step: python scripts/eval_person_counting.py eval\n")


# ── Eval mode ─────────────────────────────────────────────────────────────────

def cmd_eval(args: argparse.Namespace) -> None:
    """Replay saved clips through the detector and compute accuracy metrics."""
    entries = load_manifest()
    if not entries:
        print("[EVAL] No clips found in manifest. Run 'capture' mode first.")
        print(f"       Data dir: {DATA_DIR}")
        return

    print(f"\n[EVAL] Loading PersonDetector (conf={args.conf} iou={args.iou} "
          f"imgsz={args.imgsz} max_det={args.max_det} device={args.device})...")
    detector = PersonDetector(
        model_path=args.model_path,
        conf=args.conf,
        iou=args.iou,
        imgsz=args.imgsz,
        max_det=args.max_det,
        device=args.device,
    )
    desc = detector.describe()
    print(f"[EVAL] Model: {desc['model_path']} (sha256: {desc['weights_sha256_prefix']}...)")

    # Per-clip results
    all_true: list[int] = []
    all_pred: list[int] = []
    all_inf_ms: list[float] = []
    all_confs: list[float] = []
    clip_results: list[dict[str, Any]] = []

    for entry in entries:
        clip_name: str = entry["clip_path"]
        true_count: int = entry["true_count"]
        scenario: str = entry.get("scenario", "unknown")

        clip_path = DATA_DIR / clip_name
        if not clip_path.exists():
            print(f"[EVAL] SKIP {clip_name} (file not found)")
            continue

        cap = cv2.VideoCapture(str(clip_path))
        if not cap.isOpened():
            print(f"[EVAL] SKIP {clip_name} (cannot open video)")
            continue

        frame_counts: list[int] = []
        frame_inf_ms: list[float] = []
        frame_confs: list[float] = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            frame_idx += 1
            result = detector.detect(frame)
            frame_counts.append(result.person_count)
            frame_inf_ms.append(result.inference_ms)
            frame_confs.extend(result.confidences)

        cap.release()

        if not frame_counts:
            print(f"[EVAL] SKIP {clip_name} (no frames decoded)")
            continue

        # Per-clip stats
        arr = np.array(frame_counts, dtype=float)
        minute_stats = aggregate_counts(frame_counts)
        pred_median = float(np.median(arr))
        pred_mean = float(arr.mean())
        exact_matches = int((arr == true_count).sum())
        exact_match_rate = exact_matches / len(frame_counts)

        all_true.extend([true_count] * len(frame_counts))
        all_pred.extend(frame_counts)
        all_inf_ms.extend(frame_inf_ms)
        all_confs.extend(frame_confs)

        clip_result = {
            "clip": clip_name,
            "scenario": scenario,
            "true_count": true_count,
            "frames": len(frame_counts),
            "pred_mean": round(pred_mean, 3),
            "pred_median": round(pred_median, 3),
            "pred_min": int(arr.min()),
            "pred_max": int(arr.max()),
            "exact_match_rate": round(exact_match_rate, 3),
            "mae_this_clip": round(float(np.abs(arr - true_count).mean()), 3),
            "bias_this_clip": round(float((arr - true_count).mean()), 3),
            "minute_p90": round(minute_stats["persons_p90"], 3),
            "minute_max": round(minute_stats["persons_max"], 3),
            "inf_ms_mean": round(float(np.mean(frame_inf_ms)), 1),
            "inf_ms_p95": round(float(np.percentile(frame_inf_ms, 95)), 1),
        }
        clip_results.append(clip_result)

        print(f"\n  Clip: {clip_name}")
        print(f"    True count: {true_count}  |  Frames: {len(frame_counts)}")
        print(f"    Pred mean: {pred_mean:.2f}  |  Pred median: {pred_median:.2f}  "
              f"|  P90: {minute_stats['persons_p90']:.2f}  |  Max: {minute_stats['persons_max']:.0f}")
        print(f"    MAE:  {clip_result['mae_this_clip']:.3f}  "
              f"|  Exact-match: {exact_match_rate:.1%}  "
              f"|  Bias: {clip_result['bias_this_clip']:+.3f}")
        print(f"    Inf ms: mean={clip_result['inf_ms_mean']}  p95={clip_result['inf_ms_p95']}")

    if not all_true:
        print("\n[EVAL] No clips were processed.")
        return

    # ── Global statistics ──────────────────────────────────────────────────────
    true_arr = np.array(all_true, dtype=float)
    pred_arr = np.array(all_pred, dtype=float)
    err_arr = np.abs(pred_arr - true_arr)
    bias_arr = pred_arr - true_arr
    inf_arr = np.array(all_inf_ms)
    conf_arr = np.array(all_confs) if all_confs else np.array([0.0])

    mae = float(err_arr.mean())
    exact_rate = float((pred_arr == true_arr).mean())
    bias = float(bias_arr.mean())
    under_rate = float((bias_arr < 0).mean())
    over_rate = float((bias_arr > 0).mean())

    print("\n" + "=" * 72)
    print("EVALUATION SUMMARY")
    print("=" * 72)
    print(f"  Detector settings: conf={args.conf} iou={args.iou} "
          f"imgsz={args.imgsz} max_det={args.max_det} device={args.device}")
    print(f"  Model: {desc['model_path']}")
    print(f"  Total frames evaluated: {len(all_true)}")
    print(f"  Clips evaluated: {len(clip_results)}")
    print()
    print(f"  MAE (mean absolute error)  : {mae:.4f}  "
          f"(lower is better; 0.0 = perfect)")
    print(f"  Exact-match rate           : {exact_rate:.1%}  "
          f"(% frames with predicted count = true count)")
    print(f"  Bias (mean pred - true)    : {bias:+.4f}  "
          f"(negative = under-count, positive = over-count)")
    print(f"  Under-count rate           : {under_rate:.1%}")
    print(f"  Over-count rate            : {over_rate:.1%}")
    print()
    print("  Per-true-count breakdown:")
    for tc in sorted(set(all_true)):
        mask = true_arr == tc
        if not mask.any():
            continue
        tc_pred = pred_arr[mask]
        tc_mae = float(np.abs(tc_pred - tc).mean())
        tc_exact = float((tc_pred == tc).mean())
        tc_bias = float((tc_pred - tc).mean())
        print(f"    true={tc:2d}: n={int(mask.sum()):5d}  "
              f"MAE={tc_mae:.3f}  exact={tc_exact:.1%}  bias={tc_bias:+.3f}")
    print()
    print("  Inference time (ms):")
    print(f"    mean={inf_arr.mean():.1f}  P50={np.percentile(inf_arr,50):.1f}  "
          f"P95={np.percentile(inf_arr,95):.1f}  "
          f"effective_fps≈{1000/inf_arr.mean():.1f}")
    if len(conf_arr) > 0 and conf_arr[0] > 0:
        print()
        print("  Detection confidence:")
        print(f"    min={conf_arr.min():.3f}  mean={conf_arr.mean():.3f}  "
              f"max={conf_arr.max():.3f}")
    print()
    print("  Per-clip results:")
    header = f"  {'Clip':40s} {'True':>4} {'PredMed':>7} {'MAE':>6} {'Exact%':>7} {'Bias':>6}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for cr in clip_results:
        print(f"  {cr['clip']:40s} {cr['true_count']:>4} {cr['pred_median']:>7.2f} "
              f"{cr['mae_this_clip']:>6.3f} {cr['exact_match_rate']:>6.1%} "
              f"{cr['bias_this_clip']:>+6.3f}")
    print("=" * 72)

    # Save results to a JSON file for tracking
    results_path = DATA_DIR / f"eval_results_{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}.json"
    summary = {
        "timestamp": datetime.now(UTC).isoformat(),
        "detector": desc,
        "settings": {
            "conf": args.conf, "iou": args.iou, "imgsz": args.imgsz,
            "max_det": args.max_det, "device": args.device,
        },
        "global": {
            "total_frames": len(all_true),
            "clips": len(clip_results),
            "mae": round(mae, 4),
            "exact_match_rate": round(exact_rate, 4),
            "bias": round(bias, 4),
            "under_count_rate": round(under_rate, 4),
            "over_count_rate": round(over_rate, 4),
            "inf_ms_mean": round(float(inf_arr.mean()), 1),
            "inf_ms_p50": round(float(np.percentile(inf_arr, 50)), 1),
            "inf_ms_p95": round(float(np.percentile(inf_arr, 95)), 1),
            "effective_fps": round(1000 / inf_arr.mean(), 2),
        },
        "clips": clip_results,
    }
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\n  Results saved to: {results_path}")
    print(f"  (This file is git-ignored — local only.)\n")


# ── List mode ─────────────────────────────────────────────────────────────────

def cmd_list(_args: argparse.Namespace) -> None:
    """List all clips and labels in the data directory."""
    entries = load_manifest()
    if not entries:
        print(f"[LIST] No clips found in {DATA_DIR}")
        print("       Run: python scripts/eval_person_counting.py capture --label N")
        return

    print(f"\n[LIST] {len(entries)} clip(s) in {DATA_DIR}\n")
    print(f"  {'Clip':45s} {'True':>4} {'Scenario':15s} {'Frames':>6} {'Recorded':20s}")
    print("  " + "-" * 100)
    for e in entries:
        clip = e["clip_path"]
        exists = "✓" if (DATA_DIR / clip).exists() else "✗ MISSING"
        print(f"  {clip:45s} {e['true_count']:>4} {e.get('scenario','?'):15s} "
              f"{e.get('frames',0):>6} {e.get('recorded_at','?')[:19]:20s} {exists}")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="PRAMAAN Person Counting Evaluation Harness",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # capture sub-command
    cap_p = sub.add_parser("capture", help="Record a labelled webcam clip")
    cap_p.add_argument("--seconds", type=int, default=10,
                       help="Duration of clip to record")
    cap_p.add_argument("--label", type=int, default=None,
                       help="True person count (prompted interactively if not set)")
    cap_p.add_argument("--scenario", type=str, default=None,
                       help="Scenario label (e.g. '2person_seated', 'empty', 'bright')")
    cap_p.add_argument("--camera", type=int, default=0, help="Camera device index")

    # eval sub-command
    eval_p = sub.add_parser("eval", help="Evaluate clips through the detector")
    eval_p.add_argument("--conf", type=float, default=PersonDetector.DEFAULT_CONF)
    eval_p.add_argument("--iou", type=float, default=PersonDetector.DEFAULT_IOU)
    eval_p.add_argument("--imgsz", type=int, default=PersonDetector.DEFAULT_IMGSZ)
    eval_p.add_argument("--max-det", type=int, default=PersonDetector.DEFAULT_MAX_DET)
    eval_p.add_argument("--model-path", type=str, default="")
    eval_p.add_argument("--device", type=str, default=PersonDetector.DEFAULT_DEVICE)

    # list sub-command
    sub.add_parser("list", help="List all clips and labels")

    args = parser.parse_args()

    if args.cmd == "capture":
        cmd_capture(args)
    elif args.cmd == "eval":
        cmd_eval(args)
    elif args.cmd == "list":
        cmd_list(args)


if __name__ == "__main__":
    main()
