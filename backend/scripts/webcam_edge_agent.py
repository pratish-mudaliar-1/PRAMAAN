"""backend/scripts/webcam_edge_agent.py — Authentic Laptop Webcam Edge Detection & Cryptographic Signing Agent.

Captures real webcam video frames, runs real YOLOv8n person detection via the
shared edge.detector.PersonDetector module, aggregates minute-level observations,
computes canonical hashes, signs records with a local Ed25519 private key, maintains
the observation hash chain, and submits batches via HTTP to POST /v1/ingest/observations.

Usage:
    python scripts/webcam_edge_agent.py [options]

Key options:
    --interval-seconds  Aggregation interval in seconds (default: 60)
    --camera-index      Webcam device index (default: 0)
    --headless          Run without opening GUI preview window
    --debug-overlay     Open local debug window with boxes drawn (off by default)
    --api-url           Backend URL override
    --max-observations  Exit after N observations (0 = unlimited)
    --conf              YOLO confidence threshold (default: 0.25)
    --iou               NMS IoU threshold (default: 0.45)
    --imgsz             Model inference image size (default: 640)
    --max-det           Max detections per frame (default: 100)
    --model-path        Path to YOLO .pt weights (default: auto-detect yolov8n.pt)
    --cap-width         Requested capture width in pixels (default: 1280)
    --cap-height        Requested capture height in pixels (default: 720)
    --frame-skip        Process every Nth frame (default: 1 = every frame)
    --device            Inference device: cpu / 0 / cuda (default: cpu)
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from datetime import UTC, datetime
from typing import Any

def find_workspace_root() -> str:
    cur = os.path.abspath(os.path.dirname(__file__))
    while cur and os.path.dirname(cur) != cur:
        if os.path.exists(os.path.join(cur, "backend")) and os.path.exists(
            os.path.join(cur, "frontend")
        ):
            return cur
        cur = os.path.dirname(cur)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


WORKSPACE_ROOT = find_workspace_root()
BACKEND_DIR = os.path.join(WORKSPACE_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import cv2
import httpx
import numpy as np
from app.core.security.device_key import canonical_json, compute_record_hash
from edge.detector import PersonDetector, aggregate_counts
from nacl.signing import SigningKey

STATE_DIR = os.path.join(WORKSPACE_ROOT, ".webcam_state")
KEY_FILE = os.path.join(STATE_DIR, "device_key.json")
CONFIG_FILE = os.path.join(STATE_DIR, "agent_config.json")
CHAIN_FILE = os.path.join(STATE_DIR, "chain_state.json")


# ---------------------------------------------------------------------------
# Credential helpers (unchanged from original)
# ---------------------------------------------------------------------------

def load_agent_credentials() -> tuple[dict[str, Any], SigningKey, str | None]:
    """Load agent config, local private key, and last accepted hash chain state."""
    if not os.path.exists(CONFIG_FILE) or not os.path.exists(KEY_FILE):
        print("[ERROR] Missing setup state. Please run setup first:")
        print("        python scripts/setup_local_webcam_demo.py")
        sys.exit(1)

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

    with open(KEY_FILE, "r", encoding="utf-8") as f:
        key_data = json.load(f)

    seed = bytes.fromhex(key_data["seed_hex"])
    signing_key = SigningKey(seed)

    last_accepted_hash = None
    if os.path.exists(CHAIN_FILE):
        try:
            with open(CHAIN_FILE, "r", encoding="utf-8") as f:
                chain_data = json.load(f)
                last_accepted_hash = chain_data.get("last_accepted_hash")
        except Exception:
            last_accepted_hash = None

    return config, signing_key, last_accepted_hash


def save_chain_state(last_hash: str) -> None:
    """Persist the last successfully accepted record hash."""
    with open(CHAIN_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "last_accepted_hash": last_hash,
                "updated_at": datetime.now(UTC).isoformat(),
            },
            f,
            indent=2,
        )


# ---------------------------------------------------------------------------
# Camera helpers
# ---------------------------------------------------------------------------

def open_camera(camera_index: int) -> cv2.VideoCapture:
    """Open the first readable camera, trying DirectShow then default backend."""
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
                        print(f"[WEBCAM] Opened index {idx} ({backend_name}).")
                        return cap
                cap.release()
            except Exception:
                continue

    print("[ERROR] Could not open webcam. Check that it is connected and not in use.")
    sys.exit(1)


def configure_camera(
    cap: cv2.VideoCapture,
    width: int,
    height: int,
) -> dict[str, Any]:
    """Request resolution and MJPG; read back what the driver actually negotiated."""
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, 30)

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
    fourcc_chars = "".join(
        chr((fourcc_int >> (8 * i)) & 0xFF) for i in range(4)
    ).strip("\x00")

    return {
        "width": actual_w,
        "height": actual_h,
        "fps": actual_fps,
        "fourcc": fourcc_chars,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="PRAMAAN Authentic Laptop Webcam Edge Agent",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--interval-seconds", type=int, default=60,
                        help="Aggregation interval in seconds")
    parser.add_argument("--camera-index", type=int, default=0,
                        help="Webcam device index")
    parser.add_argument("--headless", action="store_true",
                        help="Run without opening any GUI window (overrides --debug-overlay)")
    parser.add_argument("--debug-overlay", action="store_true",
                        help="Open local window with bounding boxes and live count drawn "
                             "(off by default; local only, no frames saved)")
    parser.add_argument("--api-url", type=str, default=None,
                        help="Backend URL override (default: http://localhost:8000)")
    parser.add_argument("--max-observations", type=int, default=0,
                        help="Exit after N observations (0 for unlimited)")
    # Detector configuration (Phase 3 improvements)
    parser.add_argument("--conf", type=float, default=PersonDetector.DEFAULT_CONF,
                        help="YOLO confidence threshold")
    parser.add_argument("--iou", type=float, default=PersonDetector.DEFAULT_IOU,
                        help="NMS IoU threshold (lower = less merging of nearby boxes)")
    parser.add_argument("--imgsz", type=int, default=PersonDetector.DEFAULT_IMGSZ,
                        help="Model inference image size in pixels")
    parser.add_argument("--max-det", type=int, default=PersonDetector.DEFAULT_MAX_DET,
                        help="Maximum detections per frame")
    parser.add_argument("--model-path", type=str, default="",
                        help="Path to YOLO .pt weights (auto-detected if not set)")
    parser.add_argument("--device", type=str, default=PersonDetector.DEFAULT_DEVICE,
                        help="Inference device: cpu / 0 / cuda")
    # Camera configuration
    parser.add_argument("--cap-width", type=int, default=1280,
                        help="Requested capture width (driver may negotiate lower)")
    parser.add_argument("--cap-height", type=int, default=720,
                        help="Requested capture height (driver may negotiate lower)")
    parser.add_argument("--frame-skip", type=int, default=1,
                        help="Process every Nth frame (1 = every frame)")
    args = parser.parse_args()

    config, signing_key, last_accepted_hash = load_agent_credentials()
    api_url = args.api_url or config.get("api_url", "http://localhost:8000")
    ingest_endpoint = f"{api_url.rstrip('/')}/v1/ingest/observations"

    show_overlay = args.debug_overlay and not args.headless

    print("=" * 80)
    print("PRAMAAN — Authentic Laptop Webcam Edge Agent")
    print("=" * 80)
    print(f"[DEVICE]  Serial:  {config['serial_number']} (ID: {config['device_id']})")
    print(f"[CENTRE]  Name:    {config.get('centre_name', 'Laptop Development Centre')}")
    print(f"[ZONE]    Code:    {config['zone_code']} (ID: {config['zone_id']})")
    print(f"[SESSION] ID:      {config['session_id']}")
    print(f"[CLAIM]   Claimed: {config.get('claimed_count', 3)} candidates (DEVELOPMENT ATTENDANCE CLAIM)")
    print(f"[CRYPTO]  Public:  {signing_key.verify_key.encode().hex()[:16]}... (Private Key: Protected Local File)")
    print(f"[CHAIN]   Initial prev_hash: {last_accepted_hash or 'None (genesis record)'}")
    print(f"[INTERVAL] {args.interval_seconds} seconds per observation")
    print(f"[TARGET]  {ingest_endpoint}")
    print(f"[OVERLAY] debug-overlay={'ON (local window)' if show_overlay else 'OFF'}")
    print("=" * 80)

    # 1. Load detector (shared module — same code as eval harness)
    print(f"\n[MODEL] Loading PersonDetector "
          f"(conf={args.conf} iou={args.iou} imgsz={args.imgsz} "
          f"max_det={args.max_det} device={args.device})...")
    detector = PersonDetector(
        model_path=args.model_path,
        conf=args.conf,
        iou=args.iou,
        imgsz=args.imgsz,
        max_det=args.max_det,
        device=args.device,
    )
    desc = detector.describe()
    print(f"[MODEL] Loaded: {desc['model_path']}")
    print(f"[MODEL] Weights SHA-256 prefix: {desc['weights_sha256_prefix']}")
    print(f"[MODEL] Settings: conf={desc['conf']} iou={desc['iou']} "
          f"imgsz={desc['imgsz']} max_det={desc['max_det']}")

    # 2. Open webcam
    print(f"\n[WEBCAM] Probing laptop webcam (preferred index {args.camera_index})...")
    cap = open_camera(args.camera_index)
    cam_info = configure_camera(cap, args.cap_width, args.cap_height)
    print(f"[WEBCAM] Negotiated: {cam_info['width']}×{cam_info['height']} "
          f"{cam_info['fourcc']} @ {cam_info['fps']:.0f}fps")

    if show_overlay:
        cv2.namedWindow("PRAMAAN Edge Agent — Debug Overlay (local only)", cv2.WINDOW_AUTOSIZE)

    interval_counts: list[int] = []
    interval_start_time = time.time()
    total_observations_submitted = 0
    raw_frame_counter = 0
    fps_timer = time.time()
    fps_frame_count = 0
    current_fps = 0.0

    print("\n[AGENT] Starting detection loop. Press 'q'/ESC in overlay, or Ctrl+C to stop.")
    print("-" * 80)

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                print("[WARN] Failed to read frame from webcam.")
                time.sleep(0.05)
                continue

            raw_frame_counter += 1
            fps_frame_count += 1

            # FPS counter
            now = time.time()
            if now - fps_timer >= 1.0:
                current_fps = fps_frame_count / (now - fps_timer)
                fps_frame_count = 0
                fps_timer = now

            # Frame-skip: only run inference on every Nth frame
            if raw_frame_counter % args.frame_skip != 0:
                # Still update overlay if needed
                if show_overlay:
                    cv2.imshow("PRAMAAN Edge Agent — Debug Overlay (local only)", frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (ord("q"), 27):
                        print("\n[AGENT] Stop requested by user.")
                        break
                continue

            # Run detection via shared module
            result = detector.detect(frame)
            person_count = result.person_count
            interval_counts.append(person_count)

            # Timer
            elapsed = time.time() - interval_start_time
            remaining = max(0, int(args.interval_seconds - elapsed))

            # Debug overlay (--debug-overlay flag; off by default)
            if show_overlay:
                disp = frame.copy()

                for det in result.detections:
                    x1, y1, x2, y2 = map(int, det.xyxy)
                    conf_val = det.confidence
                    cv2.rectangle(disp, (x1, y1), (x2, y2), (0, 255, 80), 2)
                    cv2.putText(
                        disp,
                        f"Person {conf_val:.2f}",
                        (x1, max(20, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 80), 2,
                    )

                h_img, w_img = disp.shape[:2]
                cv2.rectangle(disp, (8, 8), (w_img - 8, 175), (20, 20, 20), -1)
                cv2.rectangle(disp, (8, 8), (w_img - 8, 175), (0, 200, 255), 1)

                hud = [
                    ("PRAMAAN EDGE AGENT — Debug Overlay (local only)", (0, 200, 255)),
                    (f"Detected: {person_count} person(s)  |  Inf: {result.inference_ms:.0f}ms  |  FPS: {current_fps:.1f}", (0, 255, 80)),
                    (f"conf={args.conf}  iou={args.iou}  imgsz={args.imgsz}  skip={args.frame_skip}", (200, 200, 200)),
                    (f"Aggregation: {remaining}s remaining  |  Frames this interval: {len(interval_counts)}", (200, 200, 200)),
                    (f"Sent: {total_observations_submitted} obs  |  Chain: {last_accepted_hash[:12] if last_accepted_hash else 'None'}...", (150, 150, 150)),
                ]
                for i, (text, color) in enumerate(hud):
                    cv2.putText(disp, text, (16, 32 + i * 28),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 1, cv2.LINE_AA)

                cv2.imshow("PRAMAAN Edge Agent — Debug Overlay (local only)", disp)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    print("\n[AGENT] Stop requested by user.")
                    break

            # Aggregation interval complete
            if elapsed >= args.interval_seconds and len(interval_counts) > 0:
                obs_ts = datetime.now(UTC).replace(second=0, microsecond=0)

                stats = aggregate_counts(interval_counts)
                p_min = int(stats["persons_min"])
                p_max = int(stats["persons_max"])
                p_median = stats["persons_median"]
                p_p90 = stats["persons_p90"]
                frames_used = len(interval_counts)
                feed_health = 1.0

                print(f"\n[MINUTE] Aggregated {frames_used} frames over {elapsed:.1f}s:")
                print(f"         Persons: min={p_min}, median={p_median:.1f}, "
                      f"p90={p_p90:.1f}, max={p_max}")
                print(f"         Feed Health: {feed_health:.1%} | "
                      f"Timestamp: {obs_ts.strftime('%Y-%m-%dT%H:%M:%SZ')}")

                # Build payload (schema unchanged — signing contract preserved)
                payload = {
                    "minute_ts": obs_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "zone_id": config["zone_id"],
                    "session_id": config["session_id"],
                    "persons_min": p_min,
                    "persons_median": p_median,
                    "persons_p90": p_p90,
                    "persons_max": p_max,
                    "item_counts": {},
                    "feed_health": feed_health,
                    "frames_used": frames_used,
                    # model_version field carries detector identity — no schema change needed
                    "model_version": config.get("model_version", "yolov8n-laptop-webcam"),
                    "prev_hash": last_accepted_hash,
                }

                canonical_bytes = canonical_json(payload)
                record_hash = compute_record_hash(canonical_bytes)
                signed_data = signing_key.sign(canonical_bytes)
                signature_b64url = (
                    base64.urlsafe_b64encode(signed_data.signature)
                    .rstrip(b"=")
                    .decode("ascii")
                )

                print(f"[CRYPTO] Hash: {record_hash}")
                print(f"[CRYPTO] Sig:  {signature_b64url[:20]}...")

                record_payload = {
                    **payload,
                    "record_hash": record_hash,
                    "signature": signature_b64url,
                }
                batch_request = {
                    "device_id": config["device_id"],
                    "records": [record_payload],
                }

                print(f"[INGEST] POST {ingest_endpoint}...")
                try:
                    with httpx.Client(timeout=10.0) as client:
                        resp = client.post(ingest_endpoint, json=batch_request)

                    if resp.status_code == 200:
                        data = resp.json()
                        accepted = data.get("accepted", 0)
                        if accepted > 0:
                            print(f"[INGEST] HTTP 200 OK — Observation ACCEPTED!")
                            last_accepted_hash = record_hash
                            save_chain_state(last_accepted_hash)
                            total_observations_submitted += 1
                            print(f"[CHAIN]  Hash chain advanced to: {last_accepted_hash}")
                        else:
                            print(f"[WARN]   Observation rejected: {data.get('results')}")
                    else:
                        print(f"[ERROR]  HTTP {resp.status_code} — {resp.text}")
                except Exception as net_err:
                    print(f"[ERROR]  Network error: {net_err}")

                interval_counts = []
                interval_start_time = time.time()

                if args.max_observations > 0 and total_observations_submitted >= args.max_observations:
                    print(f"\n[AGENT] Completed {args.max_observations} observation(s). Exiting.")
                    break

    except KeyboardInterrupt:
        print("\n[AGENT] Stopped by user (Ctrl+C).")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("[AGENT] Webcam released and windows closed.")


if __name__ == "__main__":
    main()
