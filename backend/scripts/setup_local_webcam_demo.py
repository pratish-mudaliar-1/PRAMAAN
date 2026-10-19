"""scripts/setup_local_webcam_demo.py — Setup script for Authentic Laptop Webcam Edge Pipeline.

Idempotently configures:
1. Real local Ed25519 device keypair stored in .webcam_state/device_key.json (gitignored).
2. Dedicated Development Centre ("Laptop Development Centre (Local Webcam)").
3. Dedicated Development Zone ("Z-DEV-WEBCAM-01").
4. Dedicated Development Device ("DEV-WEBCAM-001") registered with the backend DB.
5. Dedicated Development Session ("LOCAL-WEBCAM-DEMO") with an explicit Development Attendance Claim (e.g., claimed_count = 3).
6. Agent configuration file in .webcam_state/agent_config.json.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta

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

from app.core.config import get_settings
from app.core.security.device_key import DeviceSigningKey, encode_public_key
from app.db.base import create_engine, create_session_factory
from app.db.models.centre import Centre, Zone, Camera
from app.db.models.camera_integrity import CameraIntegrityState
from app.db.models.device import Device, DeviceStatusEnum
from app.db.models.session_ import Batch, Session
from app.db.models.threshold import ThresholdProfile
from sqlalchemy import select

STATE_DIR = os.path.join(WORKSPACE_ROOT, ".webcam_state")
KEY_FILE = os.path.join(STATE_DIR, "device_key.json")
CONFIG_FILE = os.path.join(STATE_DIR, "agent_config.json")



def ensure_keypair() -> tuple[DeviceSigningKey, str]:
    """Load existing Ed25519 signing key or generate a new one and store locally."""
    os.makedirs(STATE_DIR, exist_ok=True)
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        seed = bytes.fromhex(data["seed_hex"])
        key = DeviceSigningKey.from_seed(seed)
        return key, "loaded_existing"

    key = DeviceSigningKey()
    seed_hex = key._sk.encode().hex()
    with open(KEY_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "serial_number": "DEV-WEBCAM-001",
                "seed_hex": seed_hex,
                "public_key_b64url": key.public_key_b64url,
                "created_at": datetime.now(UTC).isoformat(),
                "notice": "DO NOT COMMIT THIS FILE — Contains local Ed25519 private key.",
            },
            f,
            indent=2,
        )
    return key, "generated_new"


async def setup() -> None:
    print("=" * 80)
    print("PRAMAAN — Local Laptop Webcam Demo Setup")
    print("=" * 80)

    # 1. Cryptographic Keypair
    key, key_action = ensure_keypair()
    print(f"\n[CRYPTO] Ed25519 Device Key: {key_action}")
    print(f"         Public Key (b64url): {key.public_key_b64url}")
    print(f"         Private Seed File:   {KEY_FILE} (Strictly Local)")

    # 2. Database Connection
    s = get_settings()
    db_url = os.environ.get("DB_ASYNC_URL_OVERRIDE") or s.db.async_url_override
    if not db_url or "localhost:5432" in s.db.async_url:
        sqlite_path = os.path.abspath(os.path.join(BACKEND_DIR, "pramaan_dev.db")).replace("\\", "/")
        db_url = f"sqlite+aiosqlite:///{sqlite_path}"
    else:
        db_url = s.db.async_url
    print(f"[*] Connecting to database at: {db_url}")
    engine = create_engine(db_url)
    session_factory = create_session_factory(engine)

    from app.db.base import Base
    import app.db.models as _models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as db:
        now = datetime.now(UTC)

        # 3. Development Centre
        centre_code = "TC-DEV-001"
        centre = (
            await db.execute(select(Centre).where(Centre.code == centre_code))
        ).scalar_one_or_none()

        if not centre:
            centre = Centre(
                id=uuid.uuid4(),
                code=centre_code,
                name="Laptop Development Centre (Local Webcam)",
                state_code="DL",
                district="Central Delhi",
                scheme_code="DEV-DEMO",
                is_active=True,
                latitude=28.6139,
                longitude=77.2090,
            )
            db.add(centre)
            await db.flush()
            print(f"[CENTRE] Created development centre: {centre.name} (Code: {centre.code})")
        else:
            print(f"[CENTRE] Using existing development centre: {centre.name} (ID: {centre.id})")

        # 4. Development Zone
        zone_code = "Z-DEV-WEBCAM-01"
        zone = (
            await db.execute(
                select(Zone).where(Zone.centre_id == centre.id, Zone.zone_code == zone_code)
            )
        ).scalar_one_or_none()

        if not zone:
            zone = Zone(
                id=uuid.uuid4(),
                centre_id=centre.id,
                zone_code=zone_code,
                zone_type="CLASSROOM",
                coverage_factor=1.0,
            )
            db.add(zone)
            await db.flush()
            print(f"[ZONE]   Created development zone: {zone.zone_code}")
        else:
            print(f"[ZONE]   Using existing development zone: {zone.zone_code} (ID: {zone.id})")

        # 5. Development Camera
        cam_code = "CAM-DEV-WEBCAM-01"
        cam = (
            await db.execute(
                select(Camera).where(Camera.centre_id == centre.id, Camera.camera_code == cam_code)
            )
        ).scalar_one_or_none()

        if not cam:
            cam = Camera(
                id=uuid.uuid4(),
                centre_id=centre.id,
                camera_code=cam_code,
                location_description="Integrated Laptop Webcam (Development Source)",
                is_active=True,
            )
            db.add(cam)
            await db.flush()

            cis = CameraIntegrityState(
                camera_id=cam.id,
                state="STABLE",
                since=now - timedelta(hours=1),
                last_transition_at=now - timedelta(hours=1),
                confidence=1.0,
            )
            db.add(cis)
            await db.flush()
            print(f"[CAMERA] Created development camera: {cam.camera_code} (Status: STABLE)")
        else:
            print(f"[CAMERA] Using existing development camera: {cam.camera_code}")

        # 6. Development Device (DEV-WEBCAM-001)
        serial = "DEV-WEBCAM-001"
        dev = (
            await db.execute(select(Device).where(Device.serial_number == serial))
        ).scalar_one_or_none()

        if not dev:
            dev = Device(
                id=uuid.uuid4(),
                centre_id=centre.id,
                zone_id=zone.id,
                camera_id=cam.id,
                serial_number=serial,
                public_key=key.public_key_bytes,
                public_key_b64url=key.public_key_b64url,
                enrollment_token_hash="local-dev-token-hash",
                status=DeviceStatusEnum.ACTIVE,
                is_active=True,
                model_version="laptop-webcam-edge-v1",
                firmware_version="dev-agent-1",
                last_seen_at=now,
                last_heartbeat_at=now,
                last_telemetry={"source": "laptop_integrated_webcam", "detector": "yolov8n"},
            )
            db.add(dev)
            await db.flush()
            print(f"[DEVICE] Enrolled development edge device: {dev.serial_number} (ID: {dev.id})")
        else:
            # Update public key in case keypair was regenerated
            dev.public_key = key.public_key_bytes
            dev.public_key_b64url = key.public_key_b64url
            dev.zone_id = zone.id
            dev.status = DeviceStatusEnum.ACTIVE
            dev.is_active = True
            dev.last_seen_at = now
            print(f"[DEVICE] Updated development edge device: {dev.serial_number} (ID: {dev.id})")

        # 7. Development Batch
        batch_code = "BATCH-DEV-WEBCAM"
        batch = (
            await db.execute(
                select(Batch).where(Batch.centre_id == centre.id, Batch.batch_code == batch_code)
            )
        ).scalar_one_or_none()

        if not batch:
            batch = Batch(
                id=uuid.uuid4(),
                centre_id=centre.id,
                batch_code=batch_code,
                scheme_code="DEV-DEMO",
                trade_code="Local Webcam Analytics PoC",
                enrolled_count=5,
                batch_start_date=now.date() - timedelta(days=5),
                batch_end_date=now.date() + timedelta(days=30),
                is_active=True,
            )
            db.add(batch)
            await db.flush()
            print(f"[BATCH]  Created development batch: {batch.batch_code}")
        else:
            print(f"[BATCH]  Using existing development batch: {batch.batch_code}")

        # 8. Development Session (LOCAL-WEBCAM-DEMO)
        # Scheduled window: covers the current time with an explicit attendance claim
        sess_start = (now - timedelta(minutes=2)).replace(second=0, microsecond=0)
        sess_end = (now + timedelta(hours=3)).replace(second=0, microsecond=0)

        # Look for an active session for this batch
        sess = (
            await db.execute(
                select(Session)
                .where(
                    Session.batch_id == batch.id,
                    Session.zone_id == zone.id,
                    Session.scheduled_end >= now,
                )
                .order_by(Session.scheduled_start.desc())
            )
        ).scalars().first()

        claimed_attendance_count = 3  # Development attendance claim
        trainer_count = 0             # 0 so observed people = candidates

        if not sess:
            sess = Session(
                id=uuid.uuid4(),
                batch_id=batch.id,
                zone_id=zone.id,
                scheduled_start=sess_start,
                scheduled_end=sess_end,
                claimed_count=claimed_attendance_count,
                trainer_count=trainer_count,
                attendance_status="PENDING",
                attendance_ratio=None,
                source_ref="LOCAL-WEBCAM-DEMO",
            )
            db.add(sess)
            await db.flush()
            print(f"[SESSION] Created new active session: ID={sess.id}")
        else:
            sess.scheduled_start = sess_start
            sess.scheduled_end = sess_end
            sess.claimed_count = claimed_attendance_count
            sess.trainer_count = trainer_count
            sess.source_ref = "LOCAL-WEBCAM-DEMO"
            print(f"[SESSION] Synchronized active session: ID={sess.id}")


        print(f"          Window:  {sess.scheduled_start.strftime('%Y-%m-%d %H:%M UTC')} -> {sess.scheduled_end.strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"          Claimed: {claimed_attendance_count} candidates (DEVELOPMENT ATTENDANCE CLAIM)")

        await db.commit()

        # 9. Save Agent Config
        config_data = {
            "device_id": str(dev.id),
            "serial_number": dev.serial_number,
            "centre_id": str(centre.id),
            "centre_name": centre.name,
            "zone_id": str(zone.id),
            "zone_code": zone.zone_code,
            "session_id": str(sess.id),
            "claimed_count": claimed_attendance_count,
            "api_url": os.getenv("PRAMAAN_BACKEND_URL", "http://localhost:8001"),
            "model_version": "yolov8n-laptop-webcam",
            "camera_index": 0,
            "aggregation_interval_seconds": 60,
        }

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)

        print(f"\n[CONFIG] Agent runtime configuration written to: {CONFIG_FILE}")
        print("=" * 80)
        print("SETUP COMPLETED SUCCESSFULLY!")
        print(f"Ready to run webcam edge agent: python scripts/webcam_edge_agent.py")
        print("=" * 80)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(setup())
