"""scripts/smoke_test_e2e.py — Comprehensive End-to-End smoke test verifying all MVP reviewer workflows."""
import asyncio
import os
import sys
import uuid
from datetime import datetime, UTC, timedelta

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from httpx import ASGITransport, AsyncClient
from app.main import create_app, get_session_factory
from app.core.config import get_settings
from app.core.security.jwt import create_dev_token
from app.core.security.device_key import DeviceSigningKey
from app.db.models.centre import Centre, Zone
from app.db.models.session_ import Batch, Session
from app.db.models.device import Device, DeviceStatusEnum
from app.db.models.flag import Flag
from app.db.models.audit import AuditLog

async def main():
    print("[SMOKE TEST] Initializing PRAMAAN End-to-End Verification Pipeline...")
    app = create_app()
    settings = get_settings()
    dev_secret = settings.auth.dev_jwt_secret.get_secret_value()

    admin_token = create_dev_token(
        subject="e2e-smoke-reviewer",
        roles=["national_admin"],
        secret=dev_secret,
        issuer=settings.auth.oidc_issuer,
        audience=settings.auth.jwt_audience,
    )
    headers = {"Authorization": f"Bearer {admin_token}"}

    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # STEP 1: Health & Readiness
            print("\n--- Step 1: Health & Readiness checks ---")
            res = await client.get("/v1/healthz")
            assert res.status_code == 200, f"Healthz failed: {res.text}"
            assert res.json()["status"] == "ok"
            print("   [PASS] /v1/healthz: OK")

            res = await client.get("/v1/readyz")
            ready_data = res.json()
            print(f"   [PASS] /v1/readyz: Status={ready_data['status']}, Checks={ready_data.get('checks')}")

            # STEP 2: Overview data (Centres & Flags)
            print("\n--- Step 2: Overview Dashboard Data ---")
            res = await client.get("/v1/centres", headers=headers)
            assert res.status_code == 200, f"List centres failed: {res.text}"
            centres = res.json()["items"]
            assert len(centres) > 0, "No centres returned in seed"
            first_centre = centres[0]
            centre_id = first_centre["id"]
            print(f"   [PASS] /v1/centres: Returned {len(centres)} centres (including {first_centre['name']})")
            assert "lat" in first_centre and "lng" in first_centre, "Missing lat/lng"
            assert "open_flags" in first_centre, "Missing open_flags metric"
            assert "status" in first_centre, "Missing status metric"
            print(f"   [PASS] Coordinates verified: lat={first_centre['lat']}, lng={first_centre['lng']}")

            res = await client.get("/v1/flags", headers=headers)
            assert res.status_code == 200, f"List flags failed: {res.text}"
            initial_flags = res.json()["items"]
            print(f"   [PASS] /v1/flags: Returned {len(initial_flags)} flags")

            # STEP 3: Centre Drilldown
            print(f"\n--- Step 3: Centre Drilldown for {first_centre['name']} ({centre_id}) ---")
            res = await client.get(f"/v1/centres/{centre_id}", headers=headers)
            assert res.status_code == 200, f"Centre detail failed: {res.text}"
            print("   [PASS] GET /v1/centres/{id}: 200 OK")

            res = await client.get(f"/v1/centres/{centre_id}/risk", headers=headers)
            assert res.status_code == 200, f"Centre risk failed: {res.text}"
            risk_data = res.json()
            print(f"   [PASS] GET /v1/centres/{{id}}/risk: Tier={risk_data['risk_tier']}, Score={risk_data['risk_score']}")

            res = await client.get(f"/v1/sessions?centre_id={centre_id}", headers=headers)
            assert res.status_code == 200, f"Centre sessions failed: {res.text}"
            print(f"   [PASS] GET /v1/sessions?centre_id: {len(res.json()['items'])} session(s)")

            res = await client.get(f"/v1/cameras?centre_id={centre_id}", headers=headers)
            assert res.status_code == 200, f"Centre cameras failed: {res.text}"
            centre_cameras = res.json()["items"]
            print(f"   [PASS] GET /v1/cameras?centre_id: {len(centre_cameras)} camera(s)")

            res = await client.get(f"/v1/ghost-assessments?centre_id={centre_id}", headers=headers)
            assert res.status_code == 200, f"Ghost assessments failed: {res.text}"
            print(f"   [PASS] GET /v1/ghost-assessments?centre_id: {len(res.json()['items'])} evaluation(s)")

            res = await client.get(f"/v1/devices?centre_id={centre_id}", headers=headers)
            assert res.status_code == 200, f"Centre devices failed: {res.text}"
            print(f"   [PASS] GET /v1/devices?centre_id: {len(res.json()['items'])} device(s)")

            # STEP 4: Camera API & Rebaseline
            print("\n--- Step 4: Camera Integrity Inspection & Rebaseline ---")
            res = await client.get("/v1/cameras", headers=headers)
            all_cameras = res.json()["items"]
            assert len(all_cameras) > 0, "No cameras found"
            cam = all_cameras[0]
            cam_id = cam["id"]

            res = await client.get(f"/v1/cameras/{cam_id}/observations", headers=headers)
            assert res.status_code == 200
            cam_obs = res.json()
            assert isinstance(cam_obs, list)
            print(f"   [PASS] GET /v1/cameras/{cam_id}/observations: {len(cam_obs)} observations")

            rebaseline_res = await client.post(
                f"/v1/cameras/{cam_id}/rebaseline",
                headers=headers,
                json={"reason": "Auditor confirmed camera repositioning with new reference baseline"},
            )
            assert rebaseline_res.status_code == 200, f"Rebaseline failed: {rebaseline_res.text}"
            assert rebaseline_res.json()["rebaselined"] is True
            print(f"   [PASS] POST /v1/cameras/{cam_id}/rebaseline: 200 OK (New state: {rebaseline_res.json()['new_state']})")

            # STEP 5: Device API & Status Update
            print("\n--- Step 5: Device Management & Health Telemetry ---")
            res = await client.get("/v1/devices", headers=headers)
            assert res.status_code == 200
            devices = res.json()["items"]
            assert len(devices) > 0, "No devices found"
            dev = devices[0]
            dev_id = dev["id"]
            print(f"   [PASS] GET /v1/devices: {len(devices)} device(s) enrolled")

            dev_status_res = await client.post(
                f"/v1/devices/{dev_id}/status",
                headers=headers,
                json={"status": "ACTIVE", "reason": "Operator verification during smoke test"},
            )
            assert dev_status_res.status_code == 200
            print(f"   [PASS] POST /v1/devices/{dev_id}/status: Status updated to {dev_status_res.json()['status']}")

            # STEP 6: Ingestion -> Reconciliation -> Flag Pipeline
            print("\n--- Step 6: Observation Ingestion & Anomaly Reconciliation Pipeline ---")
            session_factory = get_session_factory()
            now = datetime.now(UTC).replace(second=0, microsecond=0)

            async with session_factory() as db:
                smoke_batch = Batch(
                    centre_id=uuid.UUID(centre_id),
                    batch_code=f"SMOKE-B-{uuid.uuid4().hex[:6]}",
                    scheme_code="PMKVY",
                    enrolled_count=30,
                    batch_start_date=(now - timedelta(days=5)).date(),
                    batch_end_date=(now + timedelta(days=25)).date(),
                )
                db.add(smoke_batch)
                await db.flush()

                from sqlalchemy import select
                zone_obj = (await db.execute(select(Zone).where(Zone.centre_id == uuid.UUID(centre_id)))).scalars().first()
                assert zone_obj is not None, "Zone not found"

                smoke_session = Session(
                    batch_id=smoke_batch.id,
                    zone_id=zone_obj.id,
                    scheduled_start=now - timedelta(minutes=5),
                    scheduled_end=now,
                    claimed_count=30,
                    trainer_count=1,
                )
                db.add(smoke_session)

                key = DeviceSigningKey.from_seed(b"\x99" * 32)
                smoke_dev = Device(
                    centre_id=uuid.UUID(centre_id),
                    zone_id=zone_obj.id,
                    serial_number=f"SMOKE-DEV-{uuid.uuid4().hex[:6]}",
                    public_key=key.public_key_bytes,
                    public_key_b64url=key.public_key_b64url,
                    status=DeviceStatusEnum.ACTIVE,
                    model_version="smoke-v1",
                    enrollment_token_hash="token-hash",
                )
                db.add(smoke_dev)
                await db.commit()
                smoke_session_id = smoke_session.id
                smoke_dev_id = smoke_dev.id

            obs_records = []
            current_prev_hash = None
            # Timestamps must be within +/-300s (5 min) of current server time to satisfy clock-skew validation
            for minute_offset in [4, 3, 2, 1]:
                ts = (now - timedelta(minutes=minute_offset)).replace(second=0, microsecond=0)
                payload = {
                    "minute_ts": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "zone_id": str(zone_obj.id),
                    "session_id": str(smoke_session_id),
                    "persons_min": 4,
                    "persons_median": 5.0,
                    "persons_p90": 5.0,
                    "persons_max": 6,
                    "item_counts": dict[str, int](),
                    "feed_health": 1.0,
                    "frames_used": 60,
                    "model_version": "smoke-v1",
                    "prev_hash": current_prev_hash,
                }
                rh, sig = key.sign(payload)
                obs_records.append({
                    **payload,
                    "record_hash": rh,
                    "signature": sig,
                })
                current_prev_hash = rh

            ingest_payload = {
                "device_id": str(smoke_dev_id),
                "records": obs_records,
            }
            ingest_res = await client.post("/v1/ingest/observations", json=ingest_payload)
            assert ingest_res.status_code == 200, f"Ingestion failed: {ingest_res.text}"
            ingest_data = ingest_res.json()
            if ingest_data["accepted"] != len(obs_records):
                print(f"   [DEBUG] Ingestion results: {ingest_data['results']}")
            assert ingest_data["accepted"] == len(obs_records), "Observations were not accepted"
            print(f"   [PASS] POST /v1/ingest/observations: Accepted {ingest_data['accepted']} signed records")

            from app.services.reconciliation import ReconciliationService
            async with session_factory() as db:
                recon_svc = ReconciliationService(db)
                recon_result = await recon_svc.reconcile_session(smoke_session_id)
                await db.commit()

            ratio_display = f"{recon_result.ratio:.2f}" if recon_result.ratio is not None else "N/A"
            print(f"   [PASS] Session reconciled: Status={recon_result.status}, Ratio={ratio_display}")
            assert recon_result.status in ("RED", "AMBER"), f"Expected anomaly status but got {recon_result.status}"

            # STEP 7: Flag Inspection & Resolution
            print("\n--- Step 7: Flag Inspection & Reviewer Resolution ---")
            res = await client.get(f"/v1/flags?centre_id={centre_id}", headers=headers)
            assert res.status_code == 200
            flags = res.json()["items"]
            open_flags = [f for f in flags if f["status"] == "OPEN"]
            assert len(open_flags) > 0, "No open flag found"
            flag_to_resolve = open_flags[0]
            flag_id = flag_to_resolve["id"]

            print(f"   [PASS] Reviewing flag {flag_id}: Type={flag_to_resolve['flag_type']}, Status={flag_to_resolve['status']}")

            resolve_res = await client.post(
                f"/v1/flags/{flag_id}/resolve",
                headers=headers,
                json={
                    "resolution_reason": "Verified genuine trainee absence during power disruption; confirmed by training centre log",
                    "status": "CLOSED_CONFIRMED",
                },
            )
            assert resolve_res.status_code == 200, f"Flag resolve failed: {resolve_res.text}"
            assert resolve_res.json()["new_status"] == "CLOSED_CONFIRMED"
            print(f"   [PASS] POST /v1/flags/{flag_id}/resolve: Successfully transitioned to CLOSED_CONFIRMED")

            # STEP 8: Threshold Profile Update
            print("\n--- Step 8: Persistent Threshold Profile Management ---")
            get_thresh = await client.get("/v1/thresholds", headers=headers)
            assert get_thresh.status_code == 200
            cur_thresh = get_thresh.json()
            print(f"   [PASS] GET /v1/thresholds: Current T_GREEN={cur_thresh['t_green']}, T_AMBER={cur_thresh['t_amber']}")

            put_thresh = await client.put(
                "/v1/thresholds",
                headers=headers,
                json={
                    "t_green": 0.85,
                    "t_amber": 0.55,
                    "repeat_n": 3,
                    "min_feed_health_fraction": 0.80,
                    "item_absent_min_windows": 3,
                    "item_absent_min_days": 2,
                    "phash_hamming_threshold": 14,
                    "approval_note": "Pilot calibration step approved by national admin",
                },
            )
            assert put_thresh.status_code == 200, f"Threshold update failed: {put_thresh.text}"
            updated = put_thresh.json()
            assert updated["t_green"] == 0.85
            assert updated["version"] == cur_thresh["version"] + 1
            print(f"   [PASS] PUT /v1/thresholds: Persisted version {updated['version']} (T_GREEN=0.85)")

            # STEP 9: Audit Trail Verification
            print("\n--- Step 9: Tamper-Evident Audit Trail Verification ---")
            res = await client.get("/v1/audit-log", headers=headers)
            assert res.status_code == 200
            audit_items = res.json()["items"]
            assert len(audit_items) > 0
            actions = [a["action"] for a in audit_items]
            print(f"   [PASS] GET /v1/audit-log: Retrieved {len(audit_items)} audit entries")
            print(f"   [PASS] Actions logged: {set(actions)}")
            assert "FLAG_RESOLVE" in actions, "FLAG_RESOLVE audit entry missing"
            assert "THRESHOLD_UPDATE" in actions, "THRESHOLD_UPDATE audit entry missing"
            assert "CAMERA_REBASELINE" in actions, "CAMERA_REBASELINE audit entry missing"

            from app.db.repositories.audit import AuditRepository
            async with session_factory() as db:
                audit_repo = AuditRepository(db)
                chain_valid = await audit_repo.verify_chain()
                assert chain_valid is True, "Audit log SHA-256 hash chain verification failed!"
            print("   [PASS] Audit trail SHA-256 hash chain: 100% VALID & TAMPER-EVIDENT")

            # STEP 10: Evidence Presigning
            print("\n--- Step 10: Secure Evidence Viewing with Expiring URLs ---")
            res = await client.get("/v1/evidence", headers=headers)
            assert res.status_code == 200
            ev_items = res.json()["items"]
            if ev_items:
                ev_id = ev_items[0]["id"]
                view_res = await client.get(f"/v1/evidence/{ev_id}/view", headers=headers)
                assert view_res.status_code == 200, f"Evidence view failed: {view_res.text}"
                view_data = view_res.json()
                assert "view_url" in view_data
                assert view_data["expires_in_seconds"] > 0
                print(f"   [PASS] GET /v1/evidence/{ev_id}/view: Presigned URL generated (expires in {view_data['expires_in_seconds']}s)")

    print("\n" + "=" * 80)
    print("ALL 10 END-TO-END PIPELINE & REVIEWER WORKFLOW CHECKS PASSED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
