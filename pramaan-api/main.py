"""
PRAMAAN FastAPI backend — Phase 1 skeleton
Phase 2 will add real DB, engines, and full routers.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import datetime

app = FastAPI(
    title="PRAMAAN API",
    description=(
        "AI-Based Real-Time Monitoring of Training Centres — SIH 2026 PS 26245. "
        "⚠️ SIMULATED DATA — not real monitoring output."
    ),
    version="0.1.0-phase1",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
async def health():
    """System health check."""
    return {
        "status": "ok",
        "simulated": True,
        "phase": "1 — skeleton",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "note": "SIMULATED DATA — Phase 2 adds real DB and engines.",
    }


@app.get("/centres", tags=["centres"])
async def list_centres():
    """List all centres (Phase 1: mock data)."""
    return JSONResponse(
        content={"data": [], "simulated": True, "phase": "1"},
        headers={"X-Pramaan-Simulated": "true"},
    )


@app.get("/centres/{centre_id}", tags=["centres"])
async def get_centre(centre_id: str):
    return JSONResponse(
        content={"id": centre_id, "simulated": True, "phase": "1"},
        headers={"X-Pramaan-Simulated": "true"},
    )


@app.get("/cameras", tags=["cameras"])
async def list_cameras():
    return JSONResponse(content={"data": [], "simulated": True})


@app.get("/cameras/{camera_id}/integrity", tags=["cameras"])
async def camera_integrity(camera_id: str):
    return JSONResponse(content={"camera_id": camera_id, "simulated": True})


@app.get("/cameras/{camera_id}/view-events", tags=["cameras"])
async def camera_view_events(camera_id: str):
    return JSONResponse(content={"data": [], "simulated": True})


@app.get("/ghost-batches", tags=["ghost"])
async def list_ghost_batches():
    return JSONResponse(content={"data": [], "simulated": True})


@app.get("/ghost-batches/{batch_id}", tags=["ghost"])
async def get_ghost_batch(batch_id: str):
    return JSONResponse(content={"batch_id": batch_id, "simulated": True})


@app.get("/flags", tags=["flags"])
async def list_flags():
    return JSONResponse(content={"data": [], "simulated": True})


@app.post("/flags/{flag_id}/actions", tags=["flags"])
async def flag_action(flag_id: str, action: dict):
    return JSONResponse(content={"flag_id": flag_id, "action": action, "simulated": True})


@app.get("/edge/status", tags=["edge"])
async def edge_status():
    return JSONResponse(content={"devices": [], "simulated": True})


@app.post("/demo/{trigger}", tags=["demo"])
async def demo_trigger(trigger: str):
    """Demo mode triggers — Phase 6 implements real behaviour."""
    allowed = ["disconnect", "reconnect", "cover-camera", "replay-photo", "swap-camera", "seed-ghost"]
    if trigger not in allowed:
        return JSONResponse(status_code=400, content={"error": f"Unknown trigger. Allowed: {allowed}"})
    return JSONResponse(content={"trigger": trigger, "status": "queued (stub — Phase 6)", "simulated": True})


@app.get("/config/thresholds", tags=["config"])
async def get_thresholds():
    """Return current threshold configuration."""
    return JSONResponse(content={"data": [], "simulated": True, "note": "Phase 2 reads from DB."})


@app.put("/config/thresholds/{key}", tags=["config"])
async def update_threshold(key: str, body: dict):
    return JSONResponse(content={"key": key, "new_value": body.get("value"), "simulated": True})


@app.get("/audit-log", tags=["audit"])
async def audit_log():
    return JSONResponse(content={"data": [], "simulated": True})


@app.post("/ingest/records", tags=["ingest"])
async def ingest_records(payload: dict):
    """Receive batched, signed observation records from edge devices."""
    return JSONResponse(
        content={
            "accepted": len(payload.get("records", [])),
            "rejected": 0,
            "simulated": True,
            "note": "Phase 2 validates hash-chain and writes to DB.",
        }
    )
