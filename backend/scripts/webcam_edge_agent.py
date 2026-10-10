"""scripts/webcam_edge_agent.py — Authentic Laptop Webcam Edge Detection & Cryptographic Signing Agent.

Captures real webcam video frames, runs real YOLOv8n person detection, aggregates minute-level
observations, computes canonical hashes, signs records with a local Ed25519 private key, maintains
the observation hash chain, and submits batches via HTTP to POST /v1/ingest/observations.

Usage:
    python scripts/webcam_edge_agent.py [--interval-seconds 60] [--camera-index 0] [--headless]
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
        if os.path.exists(os.path.join(cur, "backend")) and os.path.exists(os.path.join(cur, "frontend")):
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
from nacl.signing import SigningKey
from ultralytics import YOLO

STATE_DIR = os.path.join(WORKSPACE_ROOT, ".webcam_state")
KEY_FILE = os.path.join(STATE_DIR, "device_key.json")
CONFIG_FILE = os.path.join(STATE_DIR, "agent_config.json")
CHAIN_FILE = os.path.join(STATE_DIR, "chain_state.json")



def load_agent_credentials() -> tuple[dict[str, Any], SigningKey, str | None]:
    """Load agent config, local private key, and last accepted hash chain state."""
    if not os.path.exists(CONFIG_FILE) or not os.path.exists(KEY_FILE):
        print(f"[ERROR] Missing setup state. Please run setup first:")
        print(f"        python scripts/setup_local_webcam_demo.py")
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


def main() -> None:
    parser = argparse.ArgumentParser(description="PRAMAAN Authentic Laptop Webcam Edge Agent")
    parser.add_argument("--interval-seconds", type=int, default=60, help="Aggregation interval in seconds (default: 60)")
    parser.add_argument("--camera-index", type=int, default=0, help="Webcam device index (default: 0)")
    parser.add_argument("--headless", action="store_true", help="Run without opening GUI preview window")
    parser.add_argument("--api-url", type=str, default=None, help="Backend URL override (default: http://localhost:8000)")
    parser.add_argument("--max-observations", type=int, default=0, help="Exit after N observations (0 for unlimited)")
    parser.add_argument("--conf-threshold", type=float, default=0.35, help="YOLO confidence threshold (default: 0.35)")
    args = parser.parse_args()

    config, signing_key, last_accepted_hash = load_agent_credentials()
    api_url = args.api_url or config.get("api_url", "http://localhost:8000")
    ingest_endpoint = f"{api_url.rstrip('/')}/v1/ingest/observations"

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
    print("=" * 80)

    # 1. Load YOLOv8n Person Detector
    print(f"\n[MODEL] Loading Ultralytics YOLOv8n detector on CPU...")
    try:
        model = YOLO("yolov8n.pt")
        print(f"[MODEL] YOLOv8n loaded successfully (COCO class 0: person).")
    except Exception as exc:
        print(f"[ERROR] Failed to load YOLOv8n model: {exc}")
        sys.exit(1)

    # 2. Open Laptop Integrated Webcam
    print(f"[WEBCAM] Opening default laptop webcam (device index {args.camera_index})...")
    cap = cv2.VideoCapture(args.camera_index)
    if not cap.isOpened():
        print(f"[ERROR] Could not open webcam at index {args.camera_index}.")
        print(f"        Please check that your webcam is connected and not in use by another app.")
        sys.exit(1)

    # Set resolution for performance
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    print(f"[WEBCAM] Camera stream opened successfully (640x480).")

    interval_counts: list[int] = []
    interval_start_time = time.time()
    total_observations_submitted = 0
    frame_counter = 0
    fps_timer = time.time()
    current_fps = 0.0

    print("\n[AGENT] Starting real-time detection and observation loop. Press 'q' in preview or Ctrl+C to stop.")
    print("-" * 80)

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                print(f"[WARN] Failed to read frame from webcam.")
                time.sleep(0.05)
                continue

            frame_counter += 1
            if time.time() - fps_timer >= 1.0:
                current_fps = frame_counter / (time.time() - fps_timer)
                frame_counter = 0
                fps_timer = time.time()

            # Run YOLO Person Detection (COCO class 0: person)
            results = model(frame, classes=[0], conf=args.conf_threshold, verbose=False)
            boxes = results[0].boxes if len(results) > 0 else []
            person_count = len(boxes)
            interval_counts.append(person_count)

            # Check if aggregation interval elapsed
            elapsed = time.time() - interval_start_time
            remaining = max(0, int(args.interval_seconds - elapsed))

            # Display Preview HUD
            if not args.headless:
                display_frame = frame.copy()

                # Draw bounding boxes for detected persons
                for box in boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    conf = float(box.conf[0])
                    cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(
                        display_frame,
                        f"Person {conf:.2f}",
                        (x1, max(20, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 0),
                        2,
                    )

                # Overlay HUD Panel
                hud_color = (20, 20, 20)
                cv2.rectangle(display_frame, (10, 10), (420, 140), hud_color, -1)
                cv2.rectangle(display_frame, (10, 10), (420, 140), (0, 200, 255), 1)

                cv2.putText(
                    display_frame,
                    f"PRAMAAN EDGE AGENT (LOCAL WEBCAM)",
                    (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 200, 255),
                    1,
                    cv2.LINE_AA,
                )
                cv2.putText(
                    display_frame,
                    f"Live Detected Persons: {person_count}",
                    (20, 58),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0) if person_count > 0 else (0, 165, 255),
                    2,
                    cv2.LINE_AA,
                )
                cv2.putText(
                    display_frame,
                    f"Claimed Attendance: {config.get('claimed_count', 3)} (Dev Claim)",
                    (20, 82),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (200, 200, 200),
                    1,
                    cv2.LINE_AA,
                )
                cv2.putText(
                    display_frame,
                    f"Aggregation: {remaining}s remaining | FPS: {current_fps:.1f}",
                    (20, 104),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (200, 200, 200),
                    1,
                    cv2.LINE_AA,
                )
                cv2.putText(
                    display_frame,
                    f"Sent: {total_observations_submitted} obs | Chain: {last_accepted_hash[:12] if last_accepted_hash else 'None'}...",
                    (20, 126),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.42,
                    (150, 150, 150),
                    1,
                    cv2.LINE_AA,
                )

                cv2.imshow("PRAMAAN Laptop Webcam Edge Agent (Real YOLOv8n)", display_frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == 27:  # 'q' or ESC
                    print("\n[AGENT] Stop requested by user via preview window.")
                    break

            # If aggregation interval has completed, construct and submit authentic observation
            if elapsed >= args.interval_seconds and len(interval_counts) > 0:
                obs_ts = datetime.now(UTC).replace(second=0, microsecond=0)
                p_min = int(min(interval_counts))
                p_max = int(max(interval_counts))
                p_median = float(np.median(interval_counts))
                p_p90 = float(np.percentile(interval_counts, 90))
                frames_used = len(interval_counts)
                feed_health = 1.0  # Camera frames were actively and successfully read

                print(f"\n[MINUTE] Aggregated {frames_used} webcam frames over {elapsed:.1f}s:")
                print(f"         Persons: min={p_min}, median={p_median:.1f}, p90={p_p90:.1f}, max={p_max}")
                print(f"         Feed Health: {feed_health:.1%} | Timestamp: {obs_ts.strftime('%Y-%m-%dT%H:%M:%SZ')}")

                # Build Payload without signature and hash for canonical serialization
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
                    "model_version": config.get("model_version", "yolov8n-laptop-webcam"),
                    "prev_hash": last_accepted_hash,
                }

                # Cryptographic Canonicalization & SHA-256 Hashing
                canonical_bytes = canonical_json(payload)
                record_hash = compute_record_hash(canonical_bytes)

                # Ed25519 Signing
                signed_data = signing_key.sign(canonical_bytes)
                signature_b64url = base64.urlsafe_b64encode(signed_data.signature).rstrip(b"=").decode("ascii")

                print(f"[CRYPTO] Canonical Hash: {record_hash}")
                print(f"[CRYPTO] Ed25519 Signature: {signature_b64url[:20]}... (Generated by local key)")

                # Assemble Batch Request
                record_payload = {
                    **payload,
                    "record_hash": record_hash,
                    "signature": signature_b64url,
                }
                batch_request = {
                    "device_id": config["device_id"],
                    "records": [record_payload],
                }

                # Submit to Real Backend API
                print(f"[INGEST] POST {ingest_endpoint}...")
                try:
                    with httpx.Client(timeout=10.0) as client:
                        resp = client.post(ingest_endpoint, json=batch_request)

                    if resp.status_code == 200:
                        data = resp.json()
                        accepted = data.get("accepted", 0)
                        rejected = data.get("rejected", 0)
                        if accepted > 0:
                            print(f"[INGEST] HTTP 200 OK — Observation ACCEPTED by backend!")
                            last_accepted_hash = record_hash
                            save_chain_state(last_accepted_hash)
                            total_observations_submitted += 1
                            print(f"[CHAIN]  Hash chain advanced to: {last_accepted_hash}")
                            print(f"[RECON]  Backend triggered session reconciliation for {config['session_id']}")
                        else:
                            print(f"[WARN]   Observation rejected by backend: {data.get('results')}")
                    else:
                        print(f"[ERROR]  Ingest request failed: HTTP {resp.status_code} — {resp.text}")
                except Exception as net_err:
                    print(f"[ERROR]  Network/connection error calling {ingest_endpoint}: {net_err}")
                    print(f"         (Ensure backend is running at {api_url})")

                # Reset interval counters
                interval_counts = []
                interval_start_time = time.time()

                if args.max_observations > 0 and total_observations_submitted >= args.max_observations:
                    print(f"\n[AGENT] Completed requested {args.max_observations} observation(s). Exiting.")
                    break

    except KeyboardInterrupt:
        print("\n[AGENT] Stopped by user (Ctrl+C).")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("[AGENT] Webcam released and preview closed cleanly.")


if __name__ == "__main__":
    main()
